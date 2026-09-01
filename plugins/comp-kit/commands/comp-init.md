---
description: 初始化一个数据竞赛参赛仓库：标准目录布局、CLAUDE.md+AGENTS.md 双入口、docs 知识库模板、官网材料存档、数据审计与上下界基线清单
argument-hint: [比赛名称/平台，可选]
---

# Claude Command: comp-init

调用 comp-kit 插件的 `comp-init` skill，按其流程初始化当前目录（或用户指定目录）为竞赛参赛仓库。

执行要求：

1. 先读取并遵循 `comp-init` skill（含 `references/CLAUDE.md.template` 与 `references/docs-templates.md`）。
2. 若用户在参数中给出比赛名称/平台/官网链接（`$ARGUMENTS`），以此为起点收集基本信息；否则先向用户确认 skill 第一步列出的基本信息。
3. 按 skill 的"完成标准"逐项落地并汇报勾选情况；无法完成的项（如需要用户提供数据）明确列出。
