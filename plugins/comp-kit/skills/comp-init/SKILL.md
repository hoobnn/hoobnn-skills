---
name: comp-init
description: >-
  初始化一个数据竞赛 / 算法竞赛参赛仓库：落地标准目录布局（src / data / models / submissions /
  docs / metadata / archive）、同步的 CLAUDE.md + AGENTS.md 双入口、docs 知识库模板（requirements /
  competition-rules / faq / data-files / source-material / experiment-log / working-notes /
  freeze-checklist）、.gitignore 与 uv 环境，并给出开赛期动作清单（官网材料存档、赛程从规则正文
  读取、数据审计与分组结构、验证协议先定、常数策略下界 + oracle 上界 + 单步分辨率、校验器与门禁
  脚手架、管道验证提交）。当用户说「新开一个比赛项目」「初始化竞赛仓库」「参加 Kaggle / 天池 /
  DataFountain / AI4S / 讯飞等比赛帮我搭好项目」「把比赛官网材料整理进仓库」时使用。
  只负责开赛期落地，不负责日常实验记录（comp-experiment）与提交管理（comp-submit）；
  同时参加多题时另见 comp-campaign。
---

# comp-init：竞赛仓库初始化

把一场数据竞赛的参赛仓库一次性搭到「可迭代」状态。布局与流程经两轮实战验证
（时间序列决策赛：4106 → 6847 晋级决赛；七题并行 CV / 语音赛：多题进入前五）。

核心理念：**开赛期的产出不是模型，是「吃透规则的知识库 + 定好的验证协议 + 校准过的上下界与
单步分辨率 + 验证过的提交管道」**。这四样没有之前，任何建模迭代都是在浪费提交次数。

## 第一步：确认基本信息

从官网材料中提取（存档见第四步），逐项写进 `docs/requirements.md` 与 `docs/competition-rules.md`：

1. 比赛名称、平台、赛道、slug / 赛题 ID（B 榜可能是独立 ID）。
2. **评分公式**逐字抄，标明「最终排名只看什么」；A 榜成绩是否计入最终成绩。
3. 提交格式（文件名、列名、id 映射、编码、分隔符、ZIP 结构）与**每日 / 累计提交次数**。
4. **赛程只信规则正文的【赛程周期】**：A 榜截止、B 榜发布与截止、冻结登记死线
   （通常是 B 榜发布前，比提交死线早一天）、复赛 / 决赛节点。
   API 字段与页面「报名截止」常是整体结束日，不能当截止用。
5. 硬约束：外部数据 / 预训练权重口径（同平台不同题可能相反，勿互抄）、
   冻结条款边界（「发布后不得改」vs「上传后不得改」）、最终取「最后一次」还是「历史最优」、
   代码审核与复现环境（Python 版本、batch size、离线、Δ 容忍）、组队与账号规则。
6. 语言与环境（默认 Python + uv）；训练机器（本机 / 远程 GPU）与其约束。

## 第二步：落地目录布局

```
<competition-repo>/
├── CLAUDE.md            # Claude Code 入口（见 references/CLAUDE.md.template）
├── AGENTS.md            # Codex 入口，与 CLAUDE.md 内容保持同步
├── README.md
├── pyproject.toml       # uv 管理
├── .gitignore
├── docs/                # 知识库（见 references/docs-templates.md）
│   ├── requirements.md      # 数据、约束、评分、提交格式的权威整理
│   ├── competition-rules.md # 赛程（正文口径）、A/B 榜、冻结、复现环境、额度
│   ├── faq.md               # 官网 FAQ / 答疑群重点 + 待向赛方确认项
│   ├── data-files.md        # 数据文件清单
│   ├── source-material.md   # 官网原文备份索引
│   ├── experiment-log.md    # 实验记录（comp-experiment 维护）
│   ├── working-notes.md     # 当前思路 + 已关闭方向（勿复活）
│   └── freeze-checklist.md  # B 榜冻结检查单（有 B 榜 / 冻结条款时）
├── metadata/            # 官网原始 JSON / HTML / 公告截图 / 榜单快照
├── src/                 # 训练、预测、check_submission.py、gate_candidate.py、verify_* 脚本
├── data/raw/ data/processed/   # 不入 git
├── models/              # 不入 git
├── submissions/         # 不入 git，子目录按方案命名，含 manifest（SHA-256 / 字节数）
├── notebooks/
└── archive/             # 阶段冲刺归档
```

`.gitignore` 至少包含 `data/`、`models/`、`submissions/`、`.venv/`、`__pycache__/`。
原则：代码与文档入 git，产物与数据不入 git，产物用 SHA-256 + 字节数在文档里留痕。

## 第三步：写 CLAUDE.md + AGENTS.md 双入口

按 `references/CLAUDE.md.template` 生成 `CLAUDE.md`，再生成内容一致的 `AGENTS.md`
（仅开头「提供给 Claude Code / Codex」措辞不同）。两份**必须同步**，但同步脚本要保留
这一处故意的差异。

入口文件是每个代理开工必读的第一份文件，**约束性规则必须写在这里**（约束 → 入口文件；
实验事实 → experiment-log；当前状态 → STATUS / working-notes）。关键章节：

- 项目背景 + 评分公式 + 「最终只看什么」。
- 仓库当前状态；数据概况表；**基线参考指标（下界 / oracle / baseline / 单步分辨率）**。
- **关键约束（容易踩坑）**——价值密度最高的一节。
- 提交格式 + **提交准入门禁**（格式通过 ≠ 可以投）。
- 执行环境硬约束（哪台机器算、并发上限、resume 要求）。
- B 榜冻结指针；主要文档索引；开发环境；代码规范。

入口文件纪律：改动**纯增量**并 `git diff` 逐行确认；**不引用会漂移的章节号**
（用脚本路径 + 判据数值，或「编号 + 章节标题」双保险）——坏指针比没指针更糟；
补完后验证引用的脚本与文档真实存在。

## 第四步：存档官网材料

趁页面还在，把题目描述、数据说明、评分说明、FAQ、规则页原文存 `metadata/`，
在 `docs/source-material.md` 建索引（URL、抓取日期、本地路径），提炼成
`docs/requirements.md` 与 `docs/faq.md`。官网会改版、赛中会发补充公告，每次变更追加存档并标日期。

若平台有免登录的赛题信息接口（page-data / time 类），记下 curl 命令——之后核实截止不用开浏览器。
下载链接与样例文件也要核对：实战遇到「提交样例」链接指向训练集、zip 内中文文件名 GBK 编码。

## 第五步：数据审计与验证协议

写 `src/explore_data.py`（或等价），逐项过 `references/data-audit-checklist.md`，
产出写进 CLAUDE.md 数据概况表与 experiment-log「数据审计实测」节（记录哪些先验被推翻）。

审计的重点不是描述统计，是三件决定后续所有离线数字可信度的事：

1. **分组结构**：真实独立样本数（来源视频 / 底图与增强副本 / 说话人 / 生成批次）。
2. **验证协议**：按组划分；用「故意瞎掉的代理探针」量化随机划分的高估幅度；
   分组与分层冲突时先裁决。**验证协议定下来之前不训 baseline。**
3. **训练 / 测试信息不对称**：测试期拿不到的列、公开集与隐藏集是否同一生成批次、
   测试集私有的评测元数据（忽略区等）。

## 第六步：上下界、单步分辨率 + 管道验证

迭代开始前锚定四个数：

1. **下界**：不止全零——跑一族**常数 / 兜底策略**（全 A 类 / 全 B 类 / 官方 demo），
   取最高者作兜底。兜底路径的得分就是你的下限，方案再准也要单独测它。
2. **上界**：oracle（用真值反推理论最优），之后用捕获率衡量。
3. **单步分辨率**：翻动 1 个预测单元线上指标变多少（方法见 comp-experiment
   `references/resolution-and-exposure.md`），写进入口文件；之后所有线上判读对照它。
4. **可运行 baseline**：官方 baseline 修通或最小可行方案，端到端出合法提交文件。

同时落地两个脚本：`src/check_submission.py`（拷自 comp-submit `assets/check_submission.py`，
填好 `MANIFEST` 与 `@rule`，baseline 产物全 PASS）和 `src/gate_candidate.py`
（拷自 `assets/gate_candidate.py`，填锚点常数，此时可先只启用格式门）。

然后**尽早用一次提交验证管道**：baseline 投上去，确认格式通过、分数落在预期区间、
线上-线下差值已知。不要等「做到满分再交」——本地满分本身是危险信号。
首条记录写入 `docs/experiment-log.md`。

## 第七步：冻结与远程训练的骨架（有 B 榜 / 远程 GPU 时）

- 有冻结条款就现在建 `docs/freeze-checklist.md`（模板见 docs-templates），
  写上冻结死线与自设「方案锁定截止」，之后每个新成员进来都登记。
- 训练在远程机器（WSL / 云 GPU）上跑时，第一天就验证 `save-every ≤ 2` + resume 可用；
  守夜脚本模式见 comp-campaign `references/watchdog-patterns.md`。

## 完成标准

- [ ] 目录布局与 .gitignore 落地，git 初始化。
- [ ] CLAUDE.md 与 AGENTS.md 内容一致，含评分公式、关键约束、准入门禁、执行环境约束。
- [ ] 官网材料存档；requirements / competition-rules（正文口径赛程、冻结、复现环境）/ faq 成稿。
- [ ] 数据审计完成，分组结构与验证协议写入入口文件与日志。
- [ ] 下界（常数策略族）、oracle 上界、baseline、单步分辨率四个数有数。
- [ ] `check_submission.py` 与 `gate_candidate.py` 落地，baseline 产物全 PASS。
- [ ] 至少一次线上提交成功（三层证据齐），experiment-log 有首条记录。
- [ ] 有冻结条款的赛题：freeze-checklist.md 已建并写明死线。
