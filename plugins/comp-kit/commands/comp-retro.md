---
description: 从 docs/experiment-log.md 提炼阶段复盘/作战手册：一句话结论、最有效方法、已验证规律（标注适用边界）、证伪清单、可复用资产、下一阶段计划
argument-hint: [阶段名，如 初赛|复赛，可选]
---

# Claude Command: comp-retro

调用 comp-kit 插件的 `comp-retrospective` skill，为当前仓库生成 `docs/<阶段>复盘.md`。

执行要求：

1. 先读取 `comp-retrospective` skill 及其 `references/retrospective-template.md`。
2. 原料以 `docs/experiment-log.md` 为准，辅以 `docs/working-notes.md` 与 `src/` 现状；逐条实验归类为"有效方法 / 已验证规律 / 证伪清单"。
3. 每条"已验证规律"必须标注适用边界与下一阶段是否需要重验；证伪条目附证据分数。
4. 生成后向用户提示归档动作（冲刺产物移入 `archive/<阶段>冲刺/`），经确认再执行移动。
