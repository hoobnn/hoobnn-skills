---
name: comp-init
description: >-
  初始化一个数据竞赛 / 算法竞赛参赛仓库：标准目录布局、CLAUDE.md + AGENTS.md 双入口、docs 知识库模板、
  校验器与门禁脚手架，并完成开赛期动作（官网材料存档、赛程从规则正文读取、数据审计与验证协议、
  上下界与单步分辨率、管道验证提交）。当用户说「新开一个比赛项目」「初始化竞赛仓库」「参加 Kaggle /
  天池 / DataFountain / AI4S / 讯飞等比赛帮我搭好项目」「把比赛官网材料整理进仓库」时使用。
  只负责开赛期落地；日常实验见 comp-experiment，提交见 comp-submit，多题并行见 comp-campaign。
---

# comp-init：竞赛仓库初始化

开赛期的产出不是模型，是四样东西：**吃透规则的知识库、定好的验证协议、校准过的上下界与单步分辨率、
验证过的提交管道**。这四样没有之前，任何建模迭代都是在浪费提交次数。

## 1. 从规则里抠出会咬人的信息

存档官网原文（题目、数据说明、评分、FAQ、规则页）到 `metadata/`，在 `docs/source-material.md` 建索引
（URL、抓取日期、本地路径）。页面会改版、赛中有补充公告，每次变更追加存档并标日期。若平台有免登录的
赛题信息接口，记下 curl 命令，之后核实截止不用开浏览器。

提炼到 `docs/requirements.md` 与 `docs/competition-rules.md` 时，这几项最容易写错：

- **评分公式逐字抄**，标明最终排名只看什么、A 榜成绩是否计入最终成绩（只有 B 榜算时，A 榜末日冲榜没有
  名次价值，真正的交付点是冻结包）。
- **赛程只信规则正文的【赛程周期】**。API 字段与页面「报名截止」常是整体结束日；冻结登记死线通常在
  B 榜发布前，比提交死线早一天。
- 硬约束：外部数据 / 预训练权重口径（同平台不同题可能相反，勿互抄）、冻结条款边界（「发布后不得改」
  vs「上传后不得改」）、最终取「最后一次」还是「历史最优」、代码审核与复现环境、组队与账号规则。
- 提交格式细节与每日 / 累计次数。下载链接与样例文件要核对：实战遇到「提交样例」链接指向训练集、
  zip 内中文文件名 GBK 编码。

## 2. 布局与入口文件

```
├── CLAUDE.md / AGENTS.md   # 双入口，内容同步（模板：references/CLAUDE.md.template）
├── docs/                   # requirements / competition-rules / faq / data-files / source-material /
│                           # experiment-log / working-notes / freeze-checklist（模板：references/docs-templates.md）
├── metadata/               # 官网原文、公告截图、榜单快照
├── src/                    # 训练、预测、check_submission.py、gate_candidate.py、verify_* 脚本
├── data/  models/  submissions/<方案名>/   # 不入 git；产物用 SHA-256 + 字节数在文档留痕
├── notebooks/  archive/
└── pyproject.toml          # uv
```

入口文件是每个代理开工必读的第一份文件，**约束性规则写在这里**（约束 → 入口文件；实验事实 →
experiment-log；当前状态 → working-notes）。价值密度最高的两节是「关键约束（容易踩坑）」与
「提交准入门禁」。入口文件纪律：改动纯增量并 `git diff` 逐行确认；不引用会漂移的章节号，用脚本路径 +
判据数值；补完后验证引用的脚本与文档真实存在，坏指针比没指针更糟。AGENTS.md 与 CLAUDE.md 只在开头
一句「提供给 Claude Code / Codex」上不同，同步时保留这一处差异。

## 3. 数据审计与验证协议

逐项过 `references/data-audit-checklist.md`，结论写进入口文件数据概况表与 experiment-log「数据审计实测」
节，标明哪些先验被推翻。审计的重点不是描述统计，是三件决定后续所有离线数字可信度的事：

1. **分组结构**：真实独立样本数（来源视频、底图与增强副本、说话人、生成批次）。
2. **验证协议**：按组划分，用「故意瞎掉的代理探针」量化随机划分的高估幅度（comp-experiment
   `assets/leak_probe.py`），分组与分层冲突时先裁决。**验证协议定下来之前不训 baseline。**
3. **训练 / 测试信息不对称**：测试期拿不到的列、公开集与隐藏集是否同一生成批次、测试集私有的评测元数据。

## 4. 锚定四个数，再交第一发

1. **下界**：跑一族常数 / 兜底策略（全 A 类、全 B 类、官方 demo），取最高者作兜底。兜底路径的得分就是
   下限，方案再准也要单独测它。
2. **上界**：oracle（用真值反推理论最优），之后用捕获率衡量。
3. **单步分辨率**：翻动 1 个预测单元线上指标变多少（comp-experiment `assets/step_resolution.py`），
   写进入口文件与 `gate_candidate.py` 常数，之后所有线上判读对照它。
4. **可运行 baseline**：官方 baseline 修通或最小可行方案，端到端出合法提交文件。

同时把 comp-submit `assets/` 的 `check_submission.py`、`gate_candidate.py`、`receipts.py` 与 comp-experiment
`assets/` 的四个计算脚本拷进 `src/`（门禁此时可只启用格式门），baseline 产物全 PASS。然后**尽早用一次提交验证管道**：确认格式通过、分数落在预期区间、
线上-线下差值已知。不要等「做到满分再交」，本地满分本身是危险信号。首条记录写入 experiment-log。

## 5. 有 B 榜 / 远程训练时

- 有冻结条款就现在建 `docs/freeze-checklist.md`，写上冻结死线与自设「方案锁定截止」。
- 训练在远程机器上跑时，第一天验证 `save-every ≤ 2` + resume 可用（守夜模式见 comp-campaign）。

## 完成标准

- [ ] 布局、.gitignore、git 初始化；CLAUDE.md 与 AGENTS.md 同步，含评分公式、关键约束、准入门禁、执行环境约束。
- [ ] 官网材料存档；requirements / competition-rules（正文口径赛程、冻结、复现环境）/ faq 成稿。
- [ ] 数据审计完成，分组结构与验证协议写入入口文件与日志。
- [ ] 下界、oracle、baseline、单步分辨率四个数有数；两个脚本落地且 baseline 产物全 PASS。
- [ ] 至少一次线上提交成功（三层证据齐，见 comp-submit），experiment-log 有首条记录。
- [ ] 有冻结条款的赛题：freeze-checklist.md 已建并写明死线。
