---
description: 从 docs/experiment-log.md 与回执提炼阶段复盘/作战手册：一句话结论、最有效方法、已验证规律（标注适用边界）、证伪清单（区分证伪/不可分辨/外部约束关闭，写明前提）、离线↔线上标定库、可复用资产、下一阶段计划
argument-hint: [阶段名，如 初赛|复赛，可选]
---

# /comp-retro

按 comp-retrospective skill 及其 `references/retrospective-template.md`，为当前仓库生成 `docs/<阶段>复盘.md`。

1. 原料以 `docs/experiment-log.md` 为准，辅以 `campaign/*-receipts.md`（若有）、`docs/working-notes.md`
   「已关闭方向」与 `src/` 现状；逐条实验归类为有效方法 / 已验证规律 / 证伪清单。
2. 证伪清单三分：证伪 / 不可分辨（小于单步分辨率）/ 外部约束关闭；回头检查旧「证伪」里有多少其实属于
   后两类，逐条写依赖的前提。
3. 每条已验证规律标注适用边界与下一阶段是否需重验；用标定库（离线 Δ vs 线上 Δ）给出本题的兑现率结论。
4. 多赛题工作区：跨题规律沉淀到 `METHODOLOGY.md`，标注来源赛题并注明「转到其他题时是待验证假设」。
5. 生成后提示归档动作（冲刺产物移入 `archive/<阶段>冲刺/`），经用户确认再执行移动。
