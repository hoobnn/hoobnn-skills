#!/usr/bin/env python3
"""单步分辨率标定（comp-kit / comp-experiment）。

回答「翻动 1 个预测单元，线上指标变多少」。小于它的线上差异是噪声不是证据。
拷贝为竞赛仓库的 `src/step_resolution.py`，结果写进入口文件「基线参考指标」节，
并作为 gate_candidate.py 的 STEP_RESOLUTION 常数。

两种模式：

  analytic   按指标公式反解，只需样本数或 TP/FP/FN，几秒出数。
  empirical  拿一份 dev 预测，随机翻动 1 个单元后重算完整指标，取 |Δ| 分布。
             对 mAP、线级 F1 这类没有闭式解的指标用这个；通过 --metric / --perturb
             挂自定义函数，默认扰动是「单行标签换成另一个取值」。

用法：

  uv run python src/step_resolution.py analytic accuracy --n 141
  uv run python src/step_resolution.py analytic f1 --tp 2400 --fp 300 --fn 600
  uv run python src/step_resolution.py analytic macro-f1 --support normal:800,small:95,cracked:40
  uv run python src/step_resolution.py empirical --pred dev_pred.csv --true-col y --pred-col p \
      --metric macro_f1 --trials 300
  uv run python src/step_resolution.py empirical --pred dev_pred.csv --metric mymetrics:score \
      --perturb mymetrics:flip_one_instance --trials 200

输出的 step 与三档判据（< 1 步不可分辨 / 1~3 步弱信号 / > 3 步真实差异）即为线上判读依据。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# 内置指标：签名 (y_true, y_pred) -> float。自定义用 --metric module:function。
# ----------------------------------------------------------------------


def _accuracy(y, p):
    return float((y == p).mean())


def _f1_binary(y, p, pos=1):
    tp = int(((y == pos) & (p == pos)).sum())
    fp = int(((y != pos) & (p == pos)).sum())
    fn = int(((y == pos) & (p != pos)).sum())
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def _macro_f1(y, p):
    import numpy as np

    labels = np.unique(np.concatenate([y, p]))
    return float(np.mean([_f1_binary(y, p, c) for c in labels]))


BUILTIN = {"accuracy": _accuracy, "f1": _f1_binary, "macro_f1": _macro_f1}


def load_callable(spec: str):
    if spec in BUILTIN:
        return BUILTIN[spec]
    mod, _, fn = spec.partition(":")
    sys.path.insert(0, str(Path.cwd()))
    return getattr(importlib.import_module(mod), fn)


def bands(step: float) -> dict:
    return {
        "step": step,
        "noise": f"|Δ| < {step:.6g}（不可分辨，不写证伪）",
        "weak": f"{step:.6g} ≤ |Δ| < {3 * step:.6g}（弱信号）",
        "real": f"|Δ| ≥ {3 * step:.6g}（真实差异）",
        "gate_min_gain": 3 * step,
    }


# ----------------------------------------------------------------------
# analytic
# ----------------------------------------------------------------------


def analytic(args) -> dict:
    if args.metric == "accuracy":
        step = 1.0 / args.n
        return {"mode": "analytic/accuracy", "n": args.n, **bands(step)}

    if args.metric == "f1":
        tp, fp, fn = args.tp, args.fp, args.fn
        base = 2 * tp / (2 * tp + fp + fn)
        moves = {
            "FN→TP": 2 * (tp + 1) / (2 * (tp + 1) + fp + fn - 1) - base,
            "TP→FN": 2 * (tp - 1) / (2 * (tp - 1) + fp + fn + 1) - base,
            "+FP": 2 * tp / (2 * tp + fp + 1 + fn) - base,
            "−FP": 2 * tp / (2 * tp + fp - 1 + fn) - base,
        }
        step = max(abs(v) for v in moves.values())
        return {"mode": "analytic/f1", "base_f1": base, "moves": moves,
                "note": "端点（TP/FP/FN 读数）不同时 step 会漂 ±7% 左右，取最大者", **bands(step)}

    if args.metric == "macro-f1":
        support = {k: int(v) for k, v in (kv.split(":") for kv in args.support.split(","))}
        f = args.assumed_f1
        per_class = {}
        for c, n in support.items():
            e = n * (1 - f)                       # 假设 fp = fn = e，使该类 F1 = f
            tp = n - e
            f1_after = 2 * (tp + 1) / (2 * (tp + 1) + (e - 1) + e)
            per_class[c] = {"support": n, "flip_one": (f1_after - f) / len(support)}
        step_max = max(v["flip_one"] for v in per_class.values())
        step_min = min(v["flip_one"] for v in per_class.values())
        return {"mode": "analytic/macro-f1", "assumed_per_class_f1": f, "per_class": per_class,
                "note": "估计值：稀有类最贵，门禁按最贵的类设；要精确值用 empirical 模式",
                "step_range": [step_min, step_max], **bands(step_max)}

    raise SystemExit(f"analytic 不支持 {args.metric}")


# ----------------------------------------------------------------------
# empirical
# ----------------------------------------------------------------------


def default_perturb(df, rng, true_col, pred_col):
    """翻动一行：预测对的改成随机错标签，预测错的改成正确标签。"""
    out = df.copy()
    i = rng.integers(len(out))
    labels = out[true_col].unique()
    y, p = out.iloc[i][true_col], out.iloc[i][pred_col]
    if p == y and len(labels) > 1:
        out.iat[i, out.columns.get_loc(pred_col)] = rng.choice(labels[labels != y])
    else:
        out.iat[i, out.columns.get_loc(pred_col)] = y
    return out


def empirical(args) -> dict:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(args.pred)
    metric = load_callable(args.metric)
    perturb = load_callable(args.perturb) if args.perturb else None
    rng = np.random.default_rng(args.seed)

    def score(d):
        return metric(d[args.true_col].to_numpy(), d[args.pred_col].to_numpy())

    base = score(df)
    deltas = []
    for _ in range(args.trials):
        d = perturb(df, rng) if perturb else default_perturb(df, rng, args.true_col, args.pred_col)
        deltas.append(abs(score(d) - base))
    deltas = np.array(deltas)
    step = float(np.median(deltas))
    return {
        "mode": "empirical", "n_rows": len(df), "base_metric": base, "trials": args.trials,
        "abs_delta": {"median": step, "p95": float(np.percentile(deltas, 95)),
                      "max": float(deltas.max())},
        "note": "step 取中位数；稀有类实例翻动落在 p95 附近，涉及稀有类时按 p95 设门",
        **bands(step),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="单步分辨率标定（comp-kit）")
    sub = ap.add_subparsers(dest="mode", required=True)

    a = sub.add_parser("analytic")
    a.add_argument("metric", choices=["accuracy", "f1", "macro-f1"])
    a.add_argument("--n", type=int, help="accuracy：样本数")
    a.add_argument("--tp", type=int); a.add_argument("--fp", type=int); a.add_argument("--fn", type=int)
    a.add_argument("--support", help="macro-f1：各类样本数，如 A:800,B:95")
    a.add_argument("--assumed-f1", type=float, default=0.8, help="macro-f1：假设的各类 F1 水平")

    e = sub.add_parser("empirical")
    e.add_argument("--pred", type=Path, required=True, help="dev 预测 CSV")
    e.add_argument("--true-col", default="y_true"); e.add_argument("--pred-col", default="y_pred")
    e.add_argument("--metric", required=True, help="accuracy | f1 | macro_f1 | module:function")
    e.add_argument("--perturb", default=None, help="module:function(df, rng) -> df，自定义扰动")
    e.add_argument("--trials", type=int, default=200); e.add_argument("--seed", type=int, default=0)

    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    res = analytic(args) if args.mode == "analytic" else empirical(args)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if args.out:
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
