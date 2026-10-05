# hoobnn-skills：Claude Code、Codex 通用的 Agent Skills

**简体中文** · [English](README.en.md)

我自己在 Claude Code、Codex、opencode 里常用的一组 Agent Skills，按 [Agent Skills](https://agentskills.io) 规范写，用 `npx skills add` 安装，也能装进 Antigravity 和 Grok。

目前有四组：

- Git 工作流：生成 Conventional Commits 提交信息、管理 git worktree、回滚、清理分支，以及给项目配好 gitmoji + commitlint + husky。
- 数据竞赛（Kaggle、天池、DataFountain 等）：开赛时的仓库初始化、实验记录、提交额度管理、复盘答辩、多题并行时的总控。
- 数学建模竞赛（国赛 CUMCM、美赛 MCM / ICM）：建模、写代码求解、写论文三个阶段，带算法资料和 Word / LaTeX 论文模板。
- 调用其他 agent：在当前 agent 里让 grok、agy、codex、opencode、pi、hermes、claude 等 CLI 干活或给第二意见。

## 安装

```bash
# 把全部 skill 装到 Claude Code（全局）
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y

# 只装一个 skill 到 Codex
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y

# 更新已安装的 skill
npx skills update -g -y
```

装好后开一个新会话。平时直接用自然语言说要做什么，agent 会自己挑对应的 skill；想手动调用就用斜杠命令，比如 `/git-commit`、`/git-worktree add feature-ui`。

## Skill 列表

### Git 工作流（git-kit）

| Skill | 用途 | 示例 |
|---|---|---|
| `git-commit` | 看改动生成 Conventional Commits 提交信息，跟随项目的 commitlint 配置（没有配置时默认带 emoji），改动太杂时会建议拆开提交 | `/git-commit --all` |
| `git-worktree` | 在仓库同级的 `<仓库名>.worktrees/` 下创建、列出、删除 worktree，可以把未提交的改动一起带过去 | `/git-worktree add feature-ui` |
| `git-rollback` | 把分支回滚到某个历史版本：先查未提交改动、自动建备份分支、预览，再 reset 或 revert（含 merge 提交也能回滚） | `/git-rollback --branch dev` |
| `git-clean-branches` | 清理已合并（含 squash / rebase 合并）或很久没动的分支，跳过被 worktree 占用的分支，不删 `upstream` 上的分支 | `/git-clean-branches --dry-run` |
| `gitmoji-commitlint-setup` | 给项目装 commitlint 和 husky 的 commit-msg 钩子，gitmoji 风格和纯 Conventional Commits 二选一 | 「给这个项目配上 gitmoji 提交规范」 |

### 数据竞赛（comp-kit）

这几个 skill 是从我打过的两轮比赛里总结出来的：一次时间序列决策赛，一次七道题并行的 CV / 语音赛。

| Skill | 用途 |
|---|---|
| `comp-init` | 初始化竞赛仓库：目录结构、CLAUDE.md 和 AGENTS.md、官网材料存档、数据审计、验证方案、分数上下界和单次提交能分辨的最小差异 |
| `comp-experiment` | 实验怎么做才可信：一次只改一个变量、按数据来源分组切折、同口径对照、证据分级；也用来判断离线涨了线上会不会涨 |
| `comp-submit` | 提交管理：提交前用脚本校验、准入门槛、每次提交留证据和回执、每日额度预算、探针提交、B 榜冻结 |
| `comp-retrospective` | 阶段复盘和答辩：作战手册、被证伪的想法清单、离线和线上分数的对照表、答辩 PPT 和问答准备 |
| `comp-campaign` | 同时做好几道题时的总控：看板、额度和提交权限、共享机器怎么分、子代理怎么用、夜间值守和唤醒 |

### 数学建模（math-modeling）

| Skill | 用途 |
|---|---|
| `math-modeling` | 国赛 / 美赛的三角色流程（建模手、编程手、论文手），带 7 大类算法资料、Subagent 质检，以及 docx、latex、figure、xlsx、pdf、论文检索六个子工具 |

### 调用其他 agent（agent-relay）

| Skill | 作用 | 示例 |
|---|---|---|
| `agent-relay` | 在当前 agent 里调用 grok、agy、codex、opencode、pi、hermes、claude 等 CLI 派活或给第二意见。统一处理各家的 headless 参数、只读 / 可写权限、续会话和输出解析，返回一个 JSON（回答、会话 ID、用量、花费）。默认只读，agy 和 hermes 的只读只能靠 prompt 约束 | 「问问 grok 这段代码有什么并发问题」 |

## 支持的 Agent

| Agent | 安装参数 `-a` | 手动调用 |
|---|---|---|
| Claude Code | `claude-code` | `/git-commit` |
| Codex | `codex` | `$git-commit` |
| opencode | `opencode` | `/git-commit` |
| Grok Build | `grok` | `/git-commit` |
| Antigravity CLI（agy） | `antigravity-cli` | `/git-commit` |

`-a '*'` 会装到 `npx skills` 支持的所有 agent。全局安装时文件放在 `~/.agents/skills`，Claude Code 和 Grok 通过软链读同一份。

agy 全局安装时不读 `~/.agents/skills`，要在 `~/.gemini/config/skills.json` 里登记一次（写绝对路径，`~` 不会展开）：

```json
{ "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
```

## 用插件市场安装

想让 skill 跟着插件自动更新，可以走插件市场。同一个 agent 不要两种方式都装，否则同名 skill 会出现两次。

<details>
<summary>Claude Code / Codex / Grok 的安装命令</summary>

Claude Code（装好后入口是 `/git-kit:git-commit`）：

```
/plugin marketplace add hoobnn/hoobnn-skills
/plugin install git-kit@hoobnn-skills
```

Codex：

```
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

Grok：

```
grok plugin marketplace add hoobnn/hoobnn-skills
grok plugin install git-kit@hoobnn-skills
```

可选的插件有 `git-kit`、`comp-kit`、`math-modeling`、`agent-relay`。

</details>

## 写 skill 时要注意

- skill 放在 `plugins/<plugin>/skills/<name>/SKILL.md`。frontmatter 里的 `name` 用小写加连字符，和目录名一致；值以 `[` 或 `<` 开头时要加引号，不然 `npx skills` 会跳过这个 skill。
- skill 目录里不要再放第二个 `SKILL.md`，子文档换个名字（比如 `GUIDE.md`），否则 Codex 和 opencode 会把它当成另一个 skill 注册。
- 需要斜杠命令的功能也写成 skill，不写 `commands/`。

## 许可

[MIT License](LICENSE)，以下内容除外：

- `plugins/math-modeling/skills/math-modeling/tools/docx`、`tools/pdf`、`tools/xlsx` 里有 Anthropic 官方 skill 的代码，许可见各目录下的 `LICENSE.txt`。
- math-modeling 改自 [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)（MIT License）。
