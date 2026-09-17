#!/usr/bin/env python3
"""提交回执台账与离线↔线上标定库（comp-kit / comp-submit）。

回执落成 JSONL（默认 `docs/receipts.jsonl`），一行一发；出分后回填；随时渲染标定表。
字段与 references/receipt-schema.md 一致，另加 `offline` 块记录投递前的离线证据，
标定库就靠它和 `score` 对照。拷贝为竞赛仓库的 `src/receipts.py`。

用法：

  # 投递后立刻登记（receipt.json 按 receipt-schema 填；缺硬证据会标「不可验」但仍登记）
  uv run python src/receipts.py add receipt.json
  # 出分后回填：用 SHA 前缀或 submitted_at 定位
  uv run python src/receipts.py score 9f3a --score 0.89712 --verdict "不可分辨（0.6 步）"
  # 标定库：渲染 markdown 表 + 兑现率统计（--step 单步分辨率，用于把线上 Δ 换成步数）
  uv run python src/receipts.py calibrate --step 0.00709
  uv run python src/receipts.py list

标定库的读法（comp-experiment「离线↔线上标定」）：
  - 「dev 域匹配 + CI 不跨零」的候选兑现率是可外推性的依据，只能单向用；
  - 离线负向在线上通常方向一致、幅度被低估，需要标定的是正向兑现率；
  - 兑现率持续低于一半时停止刷离线指标，切到无标签代理指标。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path("docs/receipts.jsonl")

REQUIRED = ["competition", "board", "submitted_at", "artifact.path", "artifact.sha256",
            "artifact.bytes", "quota.before", "quota.after"]
HARD_EVIDENCE = ["remote_readback.sha256_match", "quota.before", "quota.after"]


def get(d: dict, dotted: str):
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def load(db: Path) -> list[dict]:
    if not db.exists():
        return []
    return [json.loads(line) for line in db.read_text().splitlines() if line.strip()]


def save(db: Path, rows: list[dict]) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def validate(r: dict) -> list[str]:
    problems = [f"缺字段 {k}" for k in REQUIRED if get(r, k) is None]
    qb, qa = get(r, "quota.before"), get(r, "quota.after")
    if qb is not None and qa is not None and qa != qb - 1:
        problems.append(f"额度未减 1（{qb}→{qa}）：受理层证据不成立")
    if get(r, "remote_readback.sha256_match") is not True:
        problems.append("回读指纹未确认：传输层证据不成立")
    if get(r, "preregistered_reading.expect") is None:
        problems.append("缺预登记判读：出分后只能临场解释")
    return problems


def cmd_add(args) -> int:
    r = json.loads(Path(args.receipt).read_text())
    problems = validate(r)
    r.setdefault("recorded_at", datetime.now().astimezone().isoformat(timespec="seconds"))
    r["verifiable"] = not any("证据不成立" in p for p in problems)
    rows = load(args.db)
    sha = get(r, "artifact.sha256")
    if sha and any(get(x, "artifact.sha256") == sha and x.get("board") == r.get("board") for x in rows):
        print(f"⚠ 同一 SHA 已在 {r.get('board')} 榜登记过（同包复投或重复登记），仍追加")
    rows.append(r)
    save(args.db, rows)
    print(f"已登记 → {args.db}（第 {len(rows)} 条）" + ("" if r["verifiable"] else "  [不可验]"))
    for p in problems:
        print("  ⚠ " + p)
    return 0


def find(rows: list[dict], key: str) -> list[int]:
    return [i for i, r in enumerate(rows)
            if (get(r, "artifact.sha256") or "").startswith(key) or r.get("submitted_at") == key]


def cmd_score(args) -> int:
    rows = load(args.db)
    hits = find(rows, args.key)
    if len(hits) != 1:
        print(f"定位到 {len(hits)} 条，需要唯一匹配（SHA 前缀或 submitted_at）")
        return 1
    r = rows[hits[0]]
    r["score"] = args.score
    r["scored_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if args.verdict:
        r["verdict"] = args.verdict
    anchor = get(r, "preregistered_reading.anchor")
    if anchor is not None:
        r["online_delta"] = args.score - anchor
    save(args.db, rows)
    print(f"已回填 score={args.score}" + (f"，线上 Δ={r['online_delta']:+.6f}" if anchor is not None else ""))
    return 0


def cmd_list(args) -> int:
    for i, r in enumerate(load(args.db), 1):
        sha = (get(r, "artifact.sha256") or "")[:8]
        print(f"{i:>3} {r.get('submitted_at','?')} {r.get('board','?')} {sha} "
              f"score={r.get('score')} {'' if r.get('verifiable', True) else '[不可验]'} "
              f"{(r.get('remark') or '')[:50]}")
    return 0


def cmd_calibrate(args) -> int:
    rows = [r for r in load(args.db) if r.get("score") is not None]
    step = args.step
    lines = ["| 日期 | 榜 | 候选 | 离线 Δ | 暴露度 | CI 不跨零 | 域匹配 | 线上 Δ | 步数 | 判读 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    stats = {"n": 0, "pos_offline": 0, "pos_realized": 0, "neg_offline": 0, "neg_consistent": 0,
             "strong": 0, "strong_realized": 0}
    for r in rows:
        off = r.get("offline") or {}
        anchor = get(r, "preregistered_reading.anchor")
        od = off.get("delta")
        online = r.get("online_delta", (r["score"] - anchor) if anchor is not None else None)
        steps = online / step if (online is not None and step) else None
        ci_ok = off.get("ci_low") is not None and off["ci_low"] > 0
        dom = off.get("domain_match")
        if online is not None and od is not None:
            stats["n"] += 1
            if od > 0:
                stats["pos_offline"] += 1
                stats["pos_realized"] += online > 0
                if ci_ok and dom:
                    stats["strong"] += 1
                    stats["strong_realized"] += online > 0
            elif od < 0:
                stats["neg_offline"] += 1
                stats["neg_consistent"] += online < 0
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            (r.get("submitted_at") or "")[:10], r.get("board", ""),
            (get(r, "artifact.path") or "").split("/")[-2:][0] if get(r, "artifact.path") else "",
            f"{od:+.5f}" if od is not None else "—", off.get("exposure", "—"),
            "是" if ci_ok else ("否" if off.get("ci_low") is not None else "—"),
            {True: "是", False: "否"}.get(dom, "—"),
            f"{online:+.5f}" if online is not None else "—",
            f"{steps:+.1f}" if steps is not None else "—", r.get("verdict") or ""))
    md = "\n".join(lines)
    summary = []
    if stats["pos_offline"]:
        summary.append(f"离线正向 {stats['pos_offline']} 发，线上兑现 {stats['pos_realized']}"
                       f"（{stats['pos_realized']/stats['pos_offline']:.0%}）")
    if stats["strong"]:
        summary.append(f"其中「CI 不跨零 + 域匹配」{stats['strong']} 发，兑现 {stats['strong_realized']}"
                       f"（{stats['strong_realized']/stats['strong']:.0%}）")
    if stats["neg_offline"]:
        summary.append(f"离线负向 {stats['neg_offline']} 发，线上同向 {stats['neg_consistent']}"
                       f"（{stats['neg_consistent']/stats['neg_offline']:.0%}）")
    out = md + "\n\n" + ("；".join(summary) + "。" if summary else "尚无可对照的数据点。")
    print(out)
    if args.out:
        Path(args.out).write_text(out + "\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="提交回执台账与标定库（comp-kit）")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("receipt")
    s = sub.add_parser("score"); s.add_argument("key", help="SHA 前缀或 submitted_at")
    s.add_argument("--score", type=float, required=True); s.add_argument("--verdict", default=None)
    sub.add_parser("list")
    c = sub.add_parser("calibrate"); c.add_argument("--step", type=float, default=None)
    c.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    return {"add": cmd_add, "score": cmd_score, "list": cmd_list, "calibrate": cmd_calibrate}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
