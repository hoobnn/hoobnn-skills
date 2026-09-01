# Math Modeling Skill

为数学建模竞赛（CUMCM、MCM/ICM 等）提供**建模分析 → 代码实现 → 论文撰写**三阶段
协作工作流程。入口与完整使用说明见 [SKILL.md](SKILL.md)。

## 目录结构

- `SKILL.md` — 技能入口：三阶段工作流程与资源索引。
- `assets/` — 7 大类算法资源库（优化 / 预测 / 评价 / 图论 / 统计 / 综合 / 机器学习）。
- `references/roles/` — 建模手 / 编程手 / 论文手三角色工作细则。
- `references/论文模板.docx` — 标准数学建模论文模板。
- `tools/` — 集成的文档处理子 skill：`docx` / `pdf` / `xlsx` / `paper_search`
  （前三者来自 Anthropic 官方 skills，保留各自 LICENSE）。

## 与上游的差异

本插件收录版相对上游做了一处瘦身：**不打包** `references/Outstanding Thesis/`
优秀获奖论文 PDF（约 53MB）。撰写论文时请自备优秀论文放入项目目录，
SKILL.md 中已给出使用方式。

## 来源与许可

- 上游作者：SJbeITenginner（[CSDN](https://blog.csdn.net/SJbeITenginner)），MIT License。
- `tools/docx`、`tools/pdf`、`tools/xlsx` 为 Anthropic 官方 skills，许可见各目录 `LICENSE.txt`。
