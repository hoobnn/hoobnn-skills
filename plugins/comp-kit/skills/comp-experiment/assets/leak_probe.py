#!/usr/bin/env python3
"""分组泄漏代理探针（comp-kit / comp-experiment）。

用一个「只看得到泄漏信号、看不到任务信号」的弱特征（如中间帧 32×32 灰度缩略图、
文件元数据、EXIF 时间），跑 1-NN 分类，分别在随机分层划分与按来源组划分下评估。
两者的差值就是随机划分对离线指标的高估幅度；几分钟出数，比争论方法论有说服力。
拷贝为竞赛仓库的 `src/leak_probe.py`，结论写进入口文件的验证协议一节。

用法：

  # meta.csv 含 label 与 group 列，feats.npy 每行一个样本的弱特征
  uv run python src/leak_probe.py --features feats.npy --meta meta.csv --label-col label --group-col source_video
  # 或全部在一个 CSV 里：除 label / group 外的列都当特征
  uv run python src/leak_probe.py --csv probe.csv --label-col label --group-col source_video --folds 5

判读：随机划分下探针远高于按组划分、且按组划分接近多数类基线 ⇒ 随机划分在测泄漏而不是任务；
所有实验共用按组的折。探针本身不该学会任务，否则说明「弱特征」其实包含任务信号，换更瞎的特征。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def stratified_folds(labels, k, rng):
    import numpy as np
    fold = np.empty(len(labels), dtype=int)
    for c in np.unique(labels):
        idx = np.flatnonzero(labels == c)
        rng.shuffle(idx)
        fold[idx] = np.arange(len(idx)) % k
    return fold


def group_folds(groups, k, rng):
    """把组按大小降序贪心分给当前最小的折，兼顾折大小平衡。"""
    import numpy as np
    uniq, inv, counts = np.unique(groups, return_inverse=True, return_counts=True)
    order = np.argsort(-counts, kind="stable")
    order = order[rng.permutation(len(order))] if len(order) < 2 * k else order
    fold_of_group = np.empty(len(uniq), dtype=int)
    load = np.zeros(k, dtype=int)
    for g in order:
        f = int(np.argmin(load))
        fold_of_group[g] = f
        load[f] += counts[g]
    return fold_of_group[inv]


def knn1_predict(x_train, y_train, x_test, chunk=2048):
    import numpy as np
    pred = np.empty(len(x_test), dtype=y_train.dtype)
    sq_train = (x_train ** 2).sum(1)
    for s in range(0, len(x_test), chunk):
        xt = x_test[s:s + chunk]
        d = (xt ** 2).sum(1)[:, None] - 2 * xt @ x_train.T + sq_train[None, :]
        pred[s:s + chunk] = y_train[np.argmin(d, axis=1)]
    return pred


def macro_f1(y, p):
    import numpy as np
    out = []
    for c in np.unique(np.concatenate([y, p])):
        tp = ((y == c) & (p == c)).sum(); fp = ((y != c) & (p == c)).sum(); fn = ((y == c) & (p != c)).sum()
        out.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return float(np.mean(out))


def evaluate(x, y, fold, k):
    import numpy as np
    preds = np.empty_like(y)
    for f in range(k):
        te = fold == f; tr = ~te
        if te.sum() == 0:
            continue
        preds[te] = knn1_predict(x[tr], y[tr], x[te])
    return {"accuracy": float((preds == y).mean()), "macro_f1": macro_f1(y, preds)}


def main() -> int:
    import numpy as np
    import pandas as pd

    ap = argparse.ArgumentParser(description="分组泄漏代理探针（comp-kit）")
    ap.add_argument("--csv", type=Path, help="含 label / group 与特征列的 CSV")
    ap.add_argument("--features", type=Path, help=".npy 特征矩阵，与 --meta 行对齐")
    ap.add_argument("--meta", type=Path, help="含 label / group 列的 CSV")
    ap.add_argument("--label-col", default="label")
    ap.add_argument("--group-col", default="group")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
        feat_cols = [c for c in df.columns if c not in (args.label_col, args.group_col)]
        x = df[feat_cols].to_numpy(dtype=float)
    elif args.features and args.meta:
        df = pd.read_csv(args.meta)
        x = np.load(args.features).reshape(len(df), -1).astype(float)
    else:
        ap.error("给 --csv，或 --features + --meta")

    y = df[args.label_col].to_numpy()
    groups = df[args.group_col].to_numpy()
    x = (x - x.mean(0)) / (x.std(0) + 1e-9)
    rng = np.random.default_rng(args.seed)

    random_split = evaluate(x, y, stratified_folds(y, args.folds, rng), args.folds)
    group_split = evaluate(x, y, group_folds(groups, args.folds, rng), args.folds)
    _, counts = np.unique(y, return_counts=True)
    majority = float(counts.max() / counts.sum())

    res = {
        "n_samples": int(len(y)), "n_groups": int(len(np.unique(groups))), "n_classes": int(len(counts)),
        "majority_baseline_accuracy": majority,
        "random_stratified": random_split, "group_kfold": group_split,
        "overestimate": {m: random_split[m] - group_split[m] for m in random_split},
    }
    gap = res["overestimate"]["accuracy"]
    near_chance = group_split["accuracy"] <= majority + 0.05
    if gap > 0.05 and near_chance:
        res["verdict"] = "随机划分在测泄漏：探针按组划分≈多数类基线，随机划分显著更高。所有实验按组切折"
    elif gap > 0.05:
        res["verdict"] = "随机划分高估明显，但探针按组仍高于基线：弱特征可能含任务信号，换更瞎的特征复核"
    else:
        res["verdict"] = "两种划分差异小：分组泄漏不明显（仍建议按组切折，代价为零）"

    print(f"样本 {res['n_samples']}，来源组 {res['n_groups']}，多数类基线 acc={majority:.4f}")
    print(f"随机分层  acc={random_split['accuracy']:.4f}  macro_f1={random_split['macro_f1']:.4f}")
    print(f"按组划分  acc={group_split['accuracy']:.4f}  macro_f1={group_split['macro_f1']:.4f}")
    print(f"高估幅度  acc={gap:+.4f}  macro_f1={res['overestimate']['macro_f1']:+.4f}")
    print("判读：" + res["verdict"])
    if args.out:
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
