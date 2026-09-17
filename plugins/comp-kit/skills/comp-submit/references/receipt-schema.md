# 提交回执（receipt）字段

每次线上投递写一条回执，按日聚合在 `campaign/<日期>-receipts.md`（多赛题）或
`docs/experiment-log.md` 提交行（单赛题）。回执是 experiment-log 的提交行、
comp-retrospective 标定库、以及「这发到底投没投成功」争议的唯一依据。

```json
{
  "competition": "<赛题 slug>",
  "board": "A | B | final",
  "account": "<脱敏账号>",
  "submitted_at": "2026-09-16T23:21:08+08:00",
  "artifact": {
    "path": "submissions/<方案名>/<文件>",
    "sha256": "<64 hex>",
    "bytes": 9345164,
    "md5": "<32 hex>"
  },
  "remote_readback": { "sha256_match": true, "checked_at": "..." },
  "quota": { "before": 3, "after": 2, "cumulative_left": null },
  "platform_record": { "visible": true, "note": "B 榜记录不在 A 榜表里，以额度为准" },
  "remark": "<备注栏原文：方法 + 关键指标 + SHA 前缀>",
  "preregistered_reading": {
    "anchor": 0.89330,
    "expect": ">= 0.897 真增益 / 0.886~0.897 不可分辨 / < 0.886 方向关闭",
    "not_to_do": "不可分辨时不变体化"
  },
  "score": null,
  "scored_at": null,
  "verdict": null
}
```

要点：

- `quota.before/after` 与 `remote_readback` 是判「投成功」的硬证据，缺一条都写「不可验」。
- `preregistered_reading` 在投递**前**写好，出分后只填 `score` / `verdict`。
- 平台不给稳定 submitId 时（表格行号是易变的），用提交时间 + SHA 前缀定位，不伪造 ID。
- 浏览器投递若终点击被权限拦截，回执写明「未投」，不写「已投」。
