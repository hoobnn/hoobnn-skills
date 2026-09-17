#!/usr/bin/env python3
"""暴露度与流向分解（comp-kit / comp-experiment）。

回答两个问题：候选相对**线上锚点包**改动了多少个预测单元（能不能被线上测出），
以及这些改动往哪个方向流、每个流向按单步分辨率值多少（该不该投、该改设计还是调参）。
拷贝为竞赛仓库的 `src/exposure.py`；输出 JSON 的 changed / total / flows 三个字段
与 gate_candidate.measure_exposure 的约定一致，可直接接入门禁。

用法：

  uv run python src/exposure.py --cand submissions/x/output.csv --anchor submissions/anchor/output.csv \
      --id-col id --pred-col label
  # 带 dev 真值时做流向定价（cand / anchor 与 truth 按 id 对齐）
  uv run python src/exposure.py --cand dev_cand.csv --anchor dev_anchor.csv --truth dev_truth.csv \
      --id-col id --pred-col label --true-col y --step 0.00709 --out exposure.json
  # 数值预测：|差| > tol 算改动
  uv run python src/exposure.py --cand a.csv --anchor b.csv --id-col id --pred-col score --tol 1e-6

判读：等效翻转实例数 ≤ 4 的流向标「噪声带内」；暴露度是必要条件不是充分条件——够暴露的候选
仍可能线上为负，但不够暴露的候选投出去一定测不出。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

NOISE_BAND = 4


def main() -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(description="暴露度与流向分解（comp-kit）")
    ap.add_argument("--cand", type=Path, required=True)
    ap.add_argument("--anchor", type=Path, required=True, help="线上锚点包（不是离线基线）")
    ap.add_argument("--truth", type=Path, default=None, help="dev 真值，有则做流向定价")
    ap.add_argument("--id-col", default="id")
    ap.add_argument("--pred-col", default="label")
    ap.add_argument("--true-col", default="y_true")
    ap.add_argument("--tol", type=float, default=None, help="数值预测的改动阈值")
    ap.add_argument("--step", type=float, default=None, help="单步分辨率，用于给流向定价")
    ap.add_argument("--min-exposure", type=int, default=None, help="暴露度门槛（可选，只用于判读）")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cand = pd.read_csv(args.cand)[[args.id_col, args.pred_col]].rename(columns={args.pred_col: "cand"})
    anchor = pd.read_csv(args.anchor)[[args.id_col, args.pred_col]].rename(columns={args.pred_col: "anchor"})
    df = anchor.merge(cand, on=args.id_col, how="outer", indicator=True)
    missing = df[df["_merge"] != "both"]
    df = df[df["_merge"] == "both"].drop(columns="_merge")

    if args.tol is not None:
        changed_mask = (df["cand"] - df["anchor"]).abs() > args.tol
        df["flow"] = ["up" if c > a else "down" for c, a in zip(df["cand"], df["anchor"])]
    else:
        changed_mask = df["cand"] != df["anchor"]
        df["flow"] = df["anchor"].astype(str) + "->" + df["cand"].astype(str)

    changed = df[changed_mask]
    flows = Counter(changed["flow"])
    res = {
        "changed": int(changed_mask.sum()),
        "total": int(len(df)),
        "ids_missing_one_side": int(len(missing)),
        "flows": dict(flows.most_common()),
    }
    if args.min_exposure is not None:
        res["exposure_pass"] = res["changed"] >= args.min_exposure

    if args.truth is not None:
        truth = pd.read_csv(args.truth)[[args.id_col, args.true_col]]
        ch = changed.merge(truth, on=args.id_col, how="inner")
        ch["gain"] = (ch["cand"] == ch[args.true_col]).astype(int) - (ch["anchor"] == ch[args.true_col]).astype(int)
        per_flow = []
        for flow, g in ch.groupby("flow"):
            net = int(g["gain"].sum())
            row = {"flow": flow, "n": int(len(g)), "became_correct": int((g["gain"] == 1).sum()),
                   "became_wrong": int((g["gain"] == -1).sum()), "net_equiv_instances": net,
                   "noise_band": abs(net) <= NOISE_BAND}
            if args.step:
                row["priced_delta"] = net * args.step
            per_flow.append(row)
        per_flow.sort(key=lambda r: r["net_equiv_instances"])
        net_total = int(ch["gain"].sum())
        res["per_flow"] = per_flow
        res["net_equiv_instances"] = net_total
        res["noise_band"] = abs(net_total) <= NOISE_BAND
        if args.step:
            res["priced_delta_total"] = net_total * args.step
            res["priced_delta_in_steps"] = float(net_total)

    print(f"暴露度 {res['changed']}/{res['total']}"
          + (f"（缺失一侧 {res['ids_missing_one_side']}）" if res["ids_missing_one_side"] else ""))
    for flow, n in list(flows.most_common())[:10]:
        print(f"  {flow}: {n}")
    if "per_flow" in res:
        print("流向定价（按净等效实例升序）：")
        for r in res["per_flow"]:
            tag = "  [噪声带内]" if r["noise_band"] else ""
            price = f"  ≈ {r['priced_delta']:+.5f}" if "priced_delta" in r else ""
            print(f"  {r['flow']}: n={r['n']} 对{r['became_correct']} 错{r['became_wrong']} "
                  f"净{r['net_equiv_instances']:+d}{price}{tag}")
        print(f"净等效实例 {res['net_equiv_instances']:+d}"
              + (f"，定价 {res['priced_delta_total']:+.5f}" if "priced_delta_total" in res else ""))
    if args.out:
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
