# Math Modeling Skill

为数学建模竞赛（CUMCM、MCM/ICM 等）提供**建模分析 → 代码实现 → 论文撰写**三角色
协作工作流程。入口与完整使用说明见 [SKILL.md](SKILL.md)。

**使用前请先阅读 [使用指南.md](使用指南.md)**，明确交付物的使用边界——
本 Skill 生成的论文仅供参考，不作为可直接提交的作品。

## 目录结构

- `SKILL.md` — 技能入口：三角色工作流程与资源索引。
- `使用指南.md` — 定位、交付物使用边界、提交前人工核对事项。
- `assets/` — 7 大类算法资源库（优化 / 预测 / 评价 / 图论 / 统计 / 综合 / 机器学习）。
- `references/roles/` — 建模手 / 编程手 / 论文手三角色工作细则（各含 SKILL.md 与子文档）。
- `references/Subagent调度.md` — 质检门禁（M1 / P1 / P2 / W1 / W2）与可选协作。
- `references/交付与截止时间协议.md` — Checkpoint 与截止时间保护。
- `tools/` — 六个子 skill：`docx` / `latex` / `figure` / `xlsx` / `pdf` / `paper_search`。
  **中文导读见 [`tools/README.md`](tools/README.md)**。
- `VERSION` / `CHANGELOG.md` — 当前收录的上游版本与变更记录。

## 与上游的差异

本插件收录版只打包**技能本体**，相对上游未包含以下非本体内容：

- `imgs/` — 三角色流程图 PNG（约 4.3MB，仅上游 README 引用）
- `dsh-plugin/` — 数学建模 Workbench 进度看板 UI 插件（独立插件形态）
- `tests/` / `scripts/` — 上游自用的回归测试与同步脚本
- `tools/update_star_history.py` — 上游仓库自用的 Star 历史图脚本

上游本身也不再打包优秀获奖论文 PDF。撰写论文时请自备优秀论文放入项目目录，
`SKILL.md` 中已给出使用方式。

## 来源与许可

- 上游作者：[XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)，MIT License。
- 当前收录版本见 [`VERSION`](VERSION)，历次变更见 [`CHANGELOG.md`](CHANGELOG.md)。
- `tools/docx`、`tools/pdf`、`tools/xlsx` 含 Anthropic 官方 skill 代码，
  许可见各目录 `LICENSE.txt`。

## 同步上游

本目录内容保持上游原样，未做翻译或改写，以便后续同步。
需要补充中文说明时写入 `tools/README.md` 或本文件，不要改动上游文件正文。
