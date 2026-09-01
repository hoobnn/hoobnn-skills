---
description: 按 comp-kit 实验纪律向 docs/experiment-log.md 追加一条实验/提交记录（方法、配置、离线指标、产物 MD5、submitId、线上得分、剩余次数、结论）
argument-hint: [本次实验/提交的要点，可选]
---

# Claude Command: comp-log

调用 comp-kit 插件的 `comp-experiment` skill，向当前仓库 `docs/experiment-log.md` 顶部追加一条记录。

执行要求：

1. 先读取 `comp-experiment` skill 的记录格式（`references/experiment-log-template.md`）。
2. 从 `$ARGUMENTS`、当前会话上下文与仓库状态（新增脚本、`submissions/` 产物）收集字段；产物存在时实际计算 MD5，不要留占位符。
3. 缺失的关键字段（submitId、线上得分、剩余次数）向用户逐项询问；未上线的纯离线实验按模板省略提交行。
4. 记录必须落到"结论"：这次实验回答了什么问题、下一步做什么或放弃什么。
