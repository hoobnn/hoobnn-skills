---
name: comp-init
description: >-
  初始化一个数据竞赛 / 算法竞赛参赛仓库：落地标准目录布局（src / data / models /
  submissions / docs / metadata / archive）、同步的 CLAUDE.md + AGENTS.md 双入口、docs
  知识库模板（requirements / competition-rules / faq / data-files / source-material /
  experiment-log / working-notes）、.gitignore 与 uv 环境，并给出开赛期动作清单（官网材料存档、
  数据审计、上下界基线、管道验证提交）。当用户说「新开一个比赛项目」「初始化竞赛仓库」「参加
  Kaggle / 天池 / DataFountain / AI4S / 讯飞等比赛帮我搭好项目」「把比赛官网材料整理进仓库」时使用。
  只负责开赛期落地，不负责日常实验记录（见 comp-experiment）与提交管理（见 comp-submit）。
---

# comp-init：竞赛仓库初始化

把一场数据竞赛的参赛仓库一次性搭到「可迭代」状态。这套布局与流程来自完整实战验证
（第四届世界科学智能大赛电力市场交易赛道，初赛线上 4106 → 6847，晋级决赛）。

核心理念：**开赛期的产出不是模型，是"吃透规则的知识库 + 校准过的上下界 + 验证过的提交管道"**。
这三样没有之前，任何建模迭代都是在浪费提交次数。

## 第一步：确认基本信息

向用户确认（或从官网材料中提取）：

1. 比赛名称、平台（Kaggle / 天池 / DataFountain / AI4S / …）、赛道。
2. **评分公式**——逐字抄下来，标明"最终排名只看什么"。
3. 提交格式（文件名、列名、行数、编码）与**每日提交次数限制**。
4. 硬约束：外部数据是否允许、是否代码审核、组队规则、赛程节点。
5. 使用的语言与环境（默认 Python + uv）。

## 第二步：落地目录布局

```
<competition-repo>/
├── CLAUDE.md            # Claude Code 入口（见 references/CLAUDE.md.template）
├── AGENTS.md            # Codex 入口，与 CLAUDE.md 内容保持同步
├── README.md
├── pyproject.toml       # uv 管理；uv add / uv sync / uv run
├── .gitignore
├── docs/                # 知识库（见 references/docs-templates.md）
│   ├── requirements.md      # 数据、约束、评分、提交格式的权威整理
│   ├── competition-rules.md # 赛程、组队、晋级、提交次数
│   ├── faq.md               # 官网 FAQ / 答疑群重点
│   ├── data-files.md        # 数据文件清单
│   ├── source-material.md   # 官网原文备份索引
│   ├── experiment-log.md    # 实验记录（comp-experiment 维护）
│   └── working-notes.md     # 当前解题思路
├── metadata/            # 官网原始 JSON / HTML / 公告截图备份
├── src/                 # 训练、预测、策略生成、verify_* 验证脚本
├── data/
│   ├── raw/             # 原始数据（不入 git）
│   └── processed/
├── models/              # 模型产物（不入 git）
├── submissions/         # 提交产物（不入 git），子目录按方案命名
├── notebooks/
└── archive/             # 阶段冲刺归档（初赛冲刺/、复赛冲刺/…）
```

`.gitignore` 至少包含：`data/`、`models/`、`submissions/`、`.venv/`、`__pycache__/`、
大文件产物。原则：**代码与文档入 git，产物与数据不入 git，产物用 MD5 在文档里留痕**。

## 第三步：写 CLAUDE.md + AGENTS.md 双入口

按 `references/CLAUDE.md.template` 生成 `CLAUDE.md`，然后生成内容一致的 `AGENTS.md`
（仅开头一行"提供给 Claude Code / Codex"的措辞不同）。两份文件**必须保持同步**，
在文件顶部互相注明"修改本文件时同步另一份"。

模板的关键章节（缺一不可）：

- **项目背景**：题目机制一句话讲清，评分公式原文，"最终只看什么"加粗。
- **仓库当前状态**：哪些能跑、哪些是 stub。
- **数据概况**：表格列出每个数据集的行数、时间范围、缺失情况。
- **关键约束（容易踩坑）**：把最容易写错的规则列成清单——这是双入口文件里价值密度最高的一节。
- **提交格式**：精确到列名顺序、时间格式、行数公式。
- **主要文档索引**：按优先级列 docs/ 各文件。
- **开发环境**与**代码规范**。

## 第四步：存档官网材料

趁比赛页面还在，把官网原文抓下来：

1. 题目描述、数据说明、评分说明、FAQ、规则页 → 原文存 `metadata/`（JSON/HTML/markdown 均可）。
2. 在 `docs/source-material.md` 建立索引：每份材料的来源 URL、抓取日期、本地路径。
3. 提炼成 `docs/requirements.md`（权威整理，之后所有争议以它为准）与 `docs/faq.md`。

官网会改版、FAQ 会更新、赛中会发补充公告——每次变更都追加存档并在整理稿中标注日期。

## 第五步：数据审计

写 `src/explore_data.py`（或等价 notebook），产出写进 CLAUDE.md 的数据概况表：

- 每个数据集的行数、时间/样本范围、列清单。
- **缺失值分布**（哪些列、集中在哪些时段/样本）。
- **异常但合法的数据**（如负电价、离群值）——先确认官方口径再决定是否处理，
  实战教训：负电价占 9.56% 且是正常数据，当异常剔除会直接砍掉信号。
- **训练/测试可用列差异**：测试期拿不到的列（如历史真实标签）逐一列出，
  写进"关键约束"——这是后续特征泄漏检查的依据。

## 第六步：上下界基线 + 管道验证

迭代开始前必须锚定三个点：

1. **下界**：全零/常数/官方 demo 策略的得分（通常为 0 或已知值）。
2. **上界**：oracle——用真实标签反推理论最优（如用真实价格枚举最优窗口），
   得到"满分是多少"。所有后续实验用"捕获率 =实际/oracle"衡量，而不是只看绝对值。
3. **可运行 baseline**：官方 baseline 修通（官方代码常有硬编码路径、缺失函数），
   或自己写最小可行方案，端到端跑出一份合法提交文件。

同时落地提交校验器：把 comp-submit skill 的 `assets/check_submission.py` 脚手架
拷贝为 `src/check_submission.py`，按官方 demo 填好 `MANIFEST`（单文件 / 目录 / ZIP
形态与条目 Spec）与合法性 `@rule`，用 baseline 产物跑通全部 PASS。

然后**用一次提交验证管道**：把 baseline 提交上去，确认格式通过、分数落在预期区间。
这次提交买到的是"管道可信"，之后每一次提交才有意义。首条记录写入
`docs/experiment-log.md`（格式见 comp-experiment skill）。

## 完成标准

- [ ] 目录布局与 .gitignore 落地，git 初始化（或确认已有）。
- [ ] CLAUDE.md 与 AGENTS.md 内容一致，含评分公式与关键约束清单。
- [ ] 官网材料已存档，requirements.md / faq.md 成稿。
- [ ] 数据审计完成，概况表写入双入口文件。
- [ ] 下界、上界、baseline 三个锚点有数。
- [ ] `src/check_submission.py` 落地（SPEC + 合法性规则），baseline 产物全部 PASS。
- [ ] 至少一次线上提交成功，experiment-log.md 有首条记录。
