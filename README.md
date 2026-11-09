<div align="center">

# hoobnn-skills

Claude Code、Codex 通用的 Agent Skills，涵盖 Git 工作流、数据竞赛与数学建模。

[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

**简体中文** · [English](README.en.md)

</div>

**hoobnn-skills** 是一组免费开源（MIT）的 Agent Skills，也是 Claude Code 插件市场：适用于 Claude Code、Codex、opencode、Grok Build 和 Antigravity CLI，包含 Git 提交与 worktree 工作流、数据竞赛（Kaggle / 天池）流程和数学建模（国赛 / 美赛）流程。遵循 [Agent Skills](https://agentskills.io) 规范，通过 `npx skills add` 安装，同时支持 Antigravity 和 Grok。

目前包含四组：

- Git 工作流：生成 Conventional Commits 提交信息、管理 git worktree、回滚、清理分支，以及给项目配好 gitmoji + commitlint + husky。
- 数据竞赛（Kaggle、天池、DataFountain 等）：开赛时的仓库初始化、实验记录、提交额度管理、复盘答辩、多题并行时的总控。
- 数学建模竞赛（国赛 CUMCM、美赛 MCM / ICM）：建模、写代码求解、写论文三个阶段，带算法资料、LaTeX 论文模板和 Word 论文排版工具。
- 调用其他 agent：通过 ACP 在当前 agent 中调用 grok、agy、codex、opencode、pi、mcode（MiniMax Code）、hermes、dsh（DeepSeek Harness）、claude，委派任务或获取第二意见。

## 安装

### 用 npx skills 安装

```bash
# 把全部 skill 装到 Claude Code（全局）
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y

# 只装一个 skill 到 Codex
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y
```

安装后需新开会话。用自然语言描述需求时，agent 会自动选择对应的 skill；也可以通过斜杠命令手动调用，例如 `/git-commit`、`/git-worktree add feature-ui`。

### 用插件市场安装

如需让 skill 随插件自动更新，可以通过插件市场安装。同一个 agent 不要同时使用两种安装方式，否则同名 skill 会重复出现。

Claude Code（装好后入口是 `/git-kit:git-commit`）：

```text
/plugin marketplace add hoobnn/hoobnn-skills
/plugin install git-kit@hoobnn-skills
```

Codex：

```bash
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

Grok：

```bash
grok plugin marketplace add hoobnn/hoobnn-skills
grok plugin install git-kit@hoobnn-skills
```

可选的插件有 `git-kit`、`comp-kit`、`math-modeling`。

### 更新

```bash
npx skills update -g -y
```

用插件市场安装的 skill 随插件更新。

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

这组 skill 总结自两次参赛经验：一次时间序列决策赛，一次七道题并行的 CV / 语音赛。

| Skill | 用途 |
|---|---|
| `comp-init` | 初始化竞赛仓库：目录结构、AGENTS.md 入口文件、官网材料存档、数据审计、验证方案、分数上下界和单次提交能分辨的最小差异 |
| `comp-experiment` | 保证实验结论可信：一次只改一个变量、按数据来源分组切折、同口径对照、证据分级；也用于判断离线提升能否在线上兑现 |
| `comp-submit` | 提交管理：提交前用脚本校验、准入门槛、每次提交留证据和回执、每日额度预算、探针提交、B 榜冻结 |
| `comp-retrospective` | 阶段复盘和答辩：作战手册、被证伪的想法清单、离线和线上分数的对照表、答辩 PPT 和问答准备 |
| `comp-campaign` | 多道题并行时的统筹：看板、额度与提交权限、共享机器分配、子代理使用规范、夜间值守与唤醒 |

### 数学建模（math-modeling）

| Skill | 用途 |
|---|---|
| `math-modeling` | 国赛 / 美赛的三角色流程（建模手、编程手、论文手），带 7 大类算法资料、Subagent 质检，以及 docx、latex、figure、xlsx、pdf、论文检索六个子工具 |

## 支持的 Agent

| Agent | 安装参数 `-a` | 手动调用 |
|---|---|---|
| Claude Code | `claude-code` | `/git-commit` |
| Codex | `codex` | `$git-commit` |
| opencode | `opencode` | `/git-commit` |
| Grok Build | `grok` | `/git-commit` |
| Antigravity CLI（agy） | `antigravity-cli` | `/git-commit` |

`-a '*'` 会装到 `npx skills` 支持的所有 agent。全局安装时文件放在 `~/.agents/skills`，Claude Code 和 Grok 通过软链读同一份。pi 和 MiniMax Code（mcode）会直接扫描 `~/.agents/skills`，不需要单独的 `-a`。

agy 全局安装时不读 `~/.agents/skills`，要在 `~/.gemini/config/skills.json` 里登记一次（写绝对路径，`~` 不会展开）：

```json
{ "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
```

## 常见问题

**支持哪些 agent？** Claude Code、Codex、opencode、Grok Build 和 Antigravity CLI（agy）；pi 和 MiniMax Code 直接扫描 `~/.agents/skills`。见上面的「支持的 Agent」。

**怎么安装、更新和卸载？** 推荐 `npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y` 安装，`npx skills update -g -y` 更新，卸载用 `npx skills remove -g`（也可以直接删 `~/.agents/skills` 下对应目录）。同一个 agent 不要同时用 `npx skills` 和插件市场两种方式装，否则同名 skill 会重复。

**只想要其中一个 skill 行吗？** 行，`--skill git-worktree` 这样按名字装；插件市场则是 `git-kit`、`comp-kit`、`math-modeling` 三个插件按组装。

**装好后怎么用？** 新开会话，直接用自然语言描述需求，agent 会选对应的 skill；也可以手动调用，Claude Code / opencode / Grok / agy 用 `/git-commit`，Codex 用 `$git-commit`。

**会联网或上传我的代码吗？** skill 本身是给 agent 读的说明文件和少量辅助脚本，不会收集或上传数据。会联网的只有明确调用外部服务的部分：`math-modeling` 的论文检索工具会访问 OpenAlex 和 AnySearch。

**skill 没有触发或装不上怎么办？** 先确认安装后新开了会话；`SKILL.md` 的 frontmatter 里 `name` 要和目录名一致，值以 `[` 或 `<` 开头时要加引号，否则 `npx skills` 会跳过；同一个 agent 重复装了两种方式也会冲突。

**和别的 skill 集合有什么不同？** 这里只收作者自己在 Git 工作流、数据竞赛和数学建模中反复使用的流程，保持精简；想找更大的通用 skill 合集，可以去 [Agent Skills](https://agentskills.io) 生态里挑。

## 编写 skill 的约定

- skill 放在 `plugins/<plugin>/skills/<name>/SKILL.md`。frontmatter 里的 `name` 用小写加连字符，和目录名一致；值以 `[` 或 `<` 开头时要加引号，不然 `npx skills` 会跳过这个 skill。
- skill 目录里不要再放第二个 `SKILL.md`，子文档换个名字（比如 `GUIDE.md`），否则 Codex 和 opencode 会把它当成另一个 skill 注册。
- 需要斜杠命令的功能也写成 skill，不写 `commands/`。

## 许可证

[MIT](LICENSE) © 2026 hoobnn。可自由使用、修改和分发，需保留版权声明。以下内容除外：

- `plugins/math-modeling/skills/math-modeling/tools/docx`、`tools/pdf`、`tools/xlsx` 里有 Anthropic 官方 skill 的代码，许可见各目录下的 `LICENSE.txt`。
- math-modeling 改自 [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)（MIT License）。
