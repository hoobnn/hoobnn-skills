#!/usr/bin/env python3
"""候选准入门禁脚手架（comp-kit / comp-submit）。

拷贝为竞赛仓库的 `src/gate_candidate.py`。`check_submission.py` 只验格式；本脚本回答
「这个候选值不值得消耗一次提交额度」。设计原则见 comp-experiment/references/gate-design.md：

    - 阈值与锚点常数写死在脚本里，事前定、事后不改；
    - 判据无缝覆盖，每条门带 why 字段；
    - exit code 0 才放行；输出 verdict JSON 供回执与 experiment-log 引用；
    - 用已知线上崩盘的候选做回归验证（--regression），能拦下它才算门禁成立。

按比赛定制三处：ANCHOR 常数、四个 measure_* 函数、（可选）REGRESSION 用例。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ======================================================================
# 1. 锚点与阈值 —— 唯一线上验证过的包及其同口径离线读数。改这里 = 改判据，须记日志。
# ======================================================================

ANCHOR = {
    "package": "submissions/<锚点方案>/<文件>",   # 线上锚点包（暴露度相对它算）
    "online_score": 0.0,                           # 线上得分（完整精度）
    "dev_metric": 0.0,                             # 同口径 dev 主指标
    "bottleneck_metric": 0.0,                      # 瓶颈维度读数（如 classification_loss），越小越好
    "cost_metric": 0.0,                            # 否决门看的代价侧指标（如稀有类 F1），越大越好
}

STEP_RESOLUTION = 0.0        # 单步分辨率：翻 1 个预测单元线上变多少（step_resolution.py 标定）
MIN_GAIN = 3 * STEP_RESOLUTION          # 主门：同口径 dev 增益 ≥ 3 步
MIN_EXPOSURE = 20                       # 暴露度门：相对锚点改动单元数 ≥ 此值
COST_UNIT_SENSITIVITY = 0.0             # 代价侧单例敏感度；否决门允许恶化 ≤ 1 个等效实例
BOTTLENECK_TOLERANCE = 0.0              # 瓶颈维度允许的恶化量（通常 0）

# ======================================================================
# 2. 度量函数 —— 按比赛实现。全部同口径：冻结权重 / 同设备 / 同 dev 集 / 同后处理。
# ======================================================================


def measure_dev(cand_dev_path: Path) -> dict:
    """返回 {"dev_metric": float, "bottleneck_metric": float, "cost_metric": float,
    "ci_low": float | None}。ci_low 为按来源组配对 bootstrap 的 2.5 百分位（相对锚点），
    可直接调 comp-experiment 的 paired_bootstrap.py（--out 的 JSON 里就是 ci_low）。"""
    raise NotImplementedError("按比赛实现：读候选 dev 预测，用官方评测口径算三个读数")


def measure_exposure(cand_pkg: Path, anchor_pkg: Path) -> dict:
    """返回 {"changed": int, "total": int, "flows": {"a->b": n, ...}}。
    changed 是相对线上锚点改动的预测单元数；flows 为流向分解（可选）。
    comp-experiment 的 exposure.py --out 输出的 JSON 与此约定一致，可直接读入。"""
    raise NotImplementedError("按比赛实现：逐单元对比候选包与锚点包")


def measure_format(cand_pkg: Path) -> bool:
    """调用 check_submission.py，返回是否全部 PASS。"""
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "check_submission.py"), str(cand_pkg)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return proc.returncode == 0


# ======================================================================
# 3. 门 —— 一般无需修改。每条门返回 (passed, detail)。
# ======================================================================


def gate_direction(dev: dict) -> tuple[bool, dict]:
    delta = dev["bottleneck_metric"] - ANCHOR["bottleneck_metric"]
    return delta <= BOTTLENECK_TOLERANCE, {
        "delta_bottleneck": delta,
        "rule": "瓶颈维度不得恶化",
        "why": "「总分涨、瓶颈维恶化」是已知失败签名；总分不作准入依据",
    }


def gate_main(dev: dict) -> tuple[bool, dict]:
    delta = dev["dev_metric"] - ANCHOR["dev_metric"]
    ci_low = dev.get("ci_low")
    ok = delta >= MIN_GAIN and (ci_low is None or ci_low > 0)
    return ok, {
        "delta_dev": delta,
        "min_gain": MIN_GAIN,
        "ci_low": ci_low,
        "rule": "同口径增益 ≥ 3 个单步分辨率，且组级配对 CI 下界 > 0",
        "why": "小于单步的差异线上不可分辨；CI 跨零的弱正是历史线上反转的典型信号",
    }


def gate_veto(dev: dict) -> tuple[bool, dict]:
    delta = dev["cost_metric"] - ANCHOR["cost_metric"]
    return delta >= -COST_UNIT_SENSITIVITY, {
        "delta_cost": delta,
        "allowed": -COST_UNIT_SENSITIVITY,
        "rule": "代价侧不得恶化超过 1 个等效实例",
        "why": "只满足主门、代价侧照旧恶化的候选是换包装，不是解决了冲突",
    }


def gate_exposure(exp: dict) -> tuple[bool, dict]:
    return exp["changed"] >= MIN_EXPOSURE, {
        "changed": exp["changed"],
        "total": exp["total"],
        "min": MIN_EXPOSURE,
        "flows": exp.get("flows", {}),
        "rule": "相对线上锚点改动单元数 ≥ 门槛",
        "why": "暴露度是必要条件：测不出的候选投出去是抛硬币；候选保留作后续基座",
    }


def run_gates(dev_path: Path, pkg_path: Path | None, anchor_pkg: Path) -> dict:
    dev = measure_dev(dev_path)
    verdicts = {}
    for name, fn in [("direction", gate_direction), ("main", gate_main), ("veto", gate_veto)]:
        ok, detail = fn(dev)
        verdicts[name] = {"pass": ok, **detail}
    if pkg_path is not None:
        ok, detail = gate_exposure(measure_exposure(pkg_path, anchor_pkg))
        verdicts["exposure"] = {"pass": ok, **detail}
        verdicts["format"] = {"pass": measure_format(pkg_path), "rule": "check_submission.py 全 PASS"}
    admitted = all(v["pass"] for v in verdicts.values())
    return {"admitted": admitted, "anchor": ANCHOR, "gates": verdicts}


# ======================================================================
# 4. 回归用例 —— 已知线上结果的历史候选。新门禁必须拦下崩盘的、放行兑现的。
# ======================================================================

REGRESSION = [
    # {"dev": "models/<run>/official_val/result.json", "pkg": "submissions/<x>/<file>",
    #  "online_delta": -0.029, "expect_admitted": False, "note": "总 mAP 涨但分类损失恶化"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description="候选准入门禁（comp-kit）")
    ap.add_argument("--dev-pred", type=Path, help="候选的同口径 dev 预测 / 指标文件")
    ap.add_argument("--package", type=Path, default=None, help="候选的提交包（暴露度 + 格式门）")
    ap.add_argument("--anchor-package", type=Path, default=Path(ANCHOR["package"]))
    ap.add_argument("--out", type=Path, default=None, help="verdict JSON 输出路径")
    ap.add_argument("--regression", action="store_true", help="跑 REGRESSION 用例验证门禁本身")
    args = ap.parse_args()

    if args.regression:
        bad = 0
        for case in REGRESSION:
            v = run_gates(Path(case["dev"]), Path(case["pkg"]) if case.get("pkg") else None,
                          args.anchor_package)
            ok = v["admitted"] == case["expect_admitted"]
            bad += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {case['note']} → admitted={v['admitted']} "
                  f"(online Δ {case['online_delta']:+})")
        print(f"\n回归 {len(REGRESSION) - bad}/{len(REGRESSION)} 通过")
        return 1 if bad else 0

    if args.dev_pred is None:
        ap.error("--dev-pred 必填（或用 --regression）")
    verdict = run_gates(args.dev_pred, args.package, args.anchor_package)
    for name, v in verdict["gates"].items():
        print(f"[{'PASS' if v['pass'] else 'FAIL'}] {name}: {v.get('rule', '')}")
    print("\nADMITTED" if verdict["admitted"] else "\nREJECTED：不进提交队列")
    if args.out:
        args.out.write_text(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["admitted"] else 1


if __name__ == "__main__":
    sys.exit(main())
