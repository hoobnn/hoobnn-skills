#!/usr/bin/env python3
"""按来源组的配对 bootstrap CI（comp-kit / comp-experiment）。

比较两臂（锚点 vs 候选）在同一 dev 集上的指标差，重采样单位是**来源组**而不是行：
同一视频 / 底图 / 说话人的样本一起进出，每次重算完整官方指标，不把逐组指标平均后当官方量。
拷贝为竞赛仓库的 `src/paired_bootstrap.py`；输出的 ci_low 直接供 gate_candidate.measure_dev 使用。

用法：

  uv run python src/paired_bootstrap.py --file dev_preds.csv --group-col video_id --true-col y \
      --a-col pred_anchor --b-col pred_cand --metric macro_f1 --n-boot 2000 --seed 0 --out ci.json
  # 自定义指标：module:function(y_true, y_pred) -> float，可以是官方评测的包装
  uv run python src/paired_bootstrap.py --file dev_preds.csv --group-col g --true-col y \
      --a-col a --b-col b --metric official_metric:score

判读：CI 不跨零且 dev 域匹配 ⇒ 可外推（只能单向用：没有它不等于该弃）；
组数 < 10 时 CI 只作描述，同时看逐组 Δ 的符号分布；增益只来自单组 / 单折是假信号。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path


def _accuracy(y, p):
    return float((y == p).mean())


def _f1_binary(y, p, pos=1):
    tp = int(((y == pos) & (p == pos)).sum()); fp = int(((y != pos) & (p == pos)).sum())
    fn = int(((y == pos) & (p != pos)).sum())
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0


def _macro_f1(y, p):
    import numpy as np
    labels = np.unique(np.concatenate([y, p]))
    return float(np.mean([_f1_binary(y, p, c) for c in labels]))


def _rmse(y, p):
    import numpy as np
    return float(np.sqrt(np.mean((y - p) ** 2)))


def _mae(y, p):
    import numpy as np
    return float(np.mean(np.abs(y - p)))


BUILTIN = {"accuracy": _accuracy, "f1": _f1_binary, "macro_f1": _macro_f1, "rmse": _rmse, "mae": _mae}
LOWER_IS_BETTER = {"rmse", "mae"}


def load_metric(spec):
    if spec in BUILTIN:
        return BUILTIN[spec]
    mod, _, fn = spec.partition(":")
    sys.path.insert(0, str(Path.cwd()))
    return getattr(importlib.import_module(mod), fn)


def main() -> int:
    import numpy as np
    import pandas as pd

    ap = argparse.ArgumentParser(description="按来源组配对 bootstrap（comp-kit）")
    ap.add_argument("--file", type=Path, required=True)
    ap.add_argument("--group-col", required=True)
    ap.add_argument("--true-col", required=True)
    ap.add_argument("--a-col", required=True, help="锚点臂预测列")
    ap.add_argument("--b-col", required=True, help="候选臂预测列")
    ap.add_argument("--metric", default="accuracy")
    ap.add_argument("--lower-is-better", action="store_true")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    df = pd.read_csv(args.file)
    metric = load_metric(args.metric)
    sign = -1.0 if (args.lower_is_better or args.metric in LOWER_IS_BETTER) else 1.0
    y, a, b = (df[c].to_numpy() for c in (args.true_col, args.a_col, args.b_col))
    groups = df[args.group_col].to_numpy()
    uniq, inv = np.unique(groups, return_inverse=True)
    idx_by_group = [np.flatnonzero(inv == g) for g in range(len(uniq))]

    m_a, m_b = metric(y, a), metric(y, b)
    delta = sign * (m_b - m_a)

    rng = np.random.default_rng(args.seed)
    boot = np.empty(args.n_boot)
    for i in range(args.n_boot):
        pick = rng.integers(len(uniq), size=len(uniq))
        idx = np.concatenate([idx_by_group[g] for g in pick])
        boot[i] = sign * (metric(y[idx], b[idx]) - metric(y[idx], a[idx]))
    lo, hi = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))

    per_group = []
    for g, idx in zip(uniq, idx_by_group):
        d = sign * (metric(y[idx], b[idx]) - metric(y[idx], a[idx]))
        per_group.append({"group": str(g), "n": int(len(idx)), "delta": float(d)})
    per_group.sort(key=lambda r: r["delta"])
    pos = sum(r["delta"] > 0 for r in per_group); neg = sum(r["delta"] < 0 for r in per_group)

    res = {
        "metric": args.metric, "metric_a": m_a, "metric_b": m_b, "delta": delta,
        "ci": [lo, hi], "ci_low": lo, "crosses_zero": lo <= 0 <= hi,
        "n_groups": int(len(uniq)), "n_boot": args.n_boot,
        "groups_positive": pos, "groups_negative": neg, "per_group": per_group,
    }
    if len(uniq) < 10:
        res["warning"] = "组数 < 10，CI 只作描述；判定看逐组 Δ 的符号分布"
    top = max(per_group, key=lambda r: r["delta"])["delta"] if per_group else 0.0
    if delta > 0 and top > 0 and top >= 0.8 * delta * len(uniq):
        res["warning_single_group"] = "增益几乎全部来自单个组，按假信号处理"

    print(f"{args.metric}: A={m_a:.6f} B={m_b:.6f} Δ={delta:+.6f}  95% CI [{lo:+.6f}, {hi:+.6f}]"
          f"  {'跨零' if res['crosses_zero'] else '不跨零'}")
    print(f"组数 {len(uniq)}：Δ>0 的组 {pos}，Δ<0 的组 {neg}")
    for k in ("warning", "warning_single_group"):
        if k in res:
            print("⚠ " + res[k])
    if args.out:
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
