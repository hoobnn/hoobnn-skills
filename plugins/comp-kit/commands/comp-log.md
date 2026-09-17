---
description: 按 comp-kit 实验纪律向 docs/experiment-log.md 追加一条实验/提交记录（预登记判据、唯一变量、证据分级、同口径指标与 CI、暴露度、产物 SHA-256/字节数、额度前后值、线上得分与单步倍数、结论与前提）
argument-hint: [本次实验/提交的要点，可选]
---

# Claude Command: comp-log

调用 comp-kit 插件的 `comp-experiment` skill，向当前仓库 `docs/experiment-log.md` 顶部追加一条记录。

执行要求：

1. 先读取 `comp-experiment` skill 的记录格式（`references/experiment-log-template.md`）。
2. 从 `$ARGUMENTS`、当前会话上下文与仓库状态（新增脚本、`submissions/` 产物、`campaign/` 回执）
   收集字段；产物存在时实际计算 SHA-256、字节数与 MD5，不留占位符；
   「已产出」的断言先 `ls` 核实。
3. 结果标签严格三分：**证伪**（幅度远超单步分辨率）/ **不可分辨**（小于单步）/
   **外部约束关闭**（OOM、权重拉不到、平台失败）；线上 Δ 换算成单步分辨率倍数。
4. 缺失的关键字段（额度前后值、回读指纹是否一致、线上得分）向用户逐项询问；
   未上线的纯离线实验按模板省略提交行；弃投要写弃投原因。
5. 若该实验此前用 `/comp-gate` 预登记过判据，把出分后的判读回填到同一条目，不改判据。
6. 记录必须落到"结论"：回答了什么问题、下一步做什么或放弃什么、结论依赖的前提。
