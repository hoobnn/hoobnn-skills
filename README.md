# hoobnn-skills：Claude Code / Codex / opencode 通用 Agent Skills 合集

> Agent Skills for Claude Code, Codex, opencode, Antigravity and Grok — Git workflow (commit, worktree, rollback, commitlint), data science competition playbook (Kaggle / 天池), and math modeling contest (CUMCM / MCM / ICM).

一组经过实战打磨的 **AI 编程助手 skill**，遵循 [Agent Skills](https://agentskills.io) 规范，一条 `npx skills add` 命令即可装进 Claude Code、Codex、opencode、Antigravity、Grok 等 agent。覆盖三类场景：

- **Git 工作流**：自动生成 Conventional Commits 提交信息、管理 git worktree、安全回滚与清理分支、一键落地 gitmoji + commitlint + husky 提交规范。
- **数据竞赛（Kaggle / 天池 / DataFountain）**：竞赛仓库初始化、可信实验与预登记门禁、提交额度管理、阶段复盘与答辩、多赛题并行总控。
- **数学建模竞赛（国赛 CUMCM / 美赛 MCM / ICM）**：建模分析 → 代码求解 → 论文撰写三阶段工作流，自带算法库与 Word / LaTeX 论文模板。

## 快速开始

```bash
# 安装全部 skill 到 Claude Code（全局）
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y

# 只装一个 skill 到 Codex
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y

# 先看有哪些 skill
npx skills add hoobnn/hoobnn-skills --list
```

装好后新开会话即可使用：直接用自然语言描述需求，agent 会自动选用对应 skill；也可以用斜杠入口手动调用，例如 `/git-commit`、`/git-worktree add feature-ui`。

## Skill 列表

### Git 工作流（git-kit）

| Skill | 用途 | 示例 |
|---|---|---|
| `git-commit` | 分析改动，生成 Conventional Commits 提交信息（跟随项目 commitlint 配置，默认带 emoji），必要时建议拆分提交 | `/git-commit --all` |
| `git-worktree` | 在仓库同级的 `.worktree-<仓库名>/` 下创建、列出、删除 worktree，并迁移未提交改动 | `/git-worktree add feature-ui` |
| `git-rollback` | 交互式回滚分支到历史版本，默认 dry-run，二次确认后执行 reset / revert | `/git-rollback --branch dev` |
| `git-clean-branches` | 安全清理已合并或过期的本地 / 远程分支，支持保护分支 | `/git-clean-branches --dry-run` |
| `gitmoji-commitlint-setup` | 为项目落地 commitlint + husky commit-msg 钩子，支持 gitmoji 或纯 Conventional Commits | 「给这个项目配上 gitmoji 提交规范」 |

### 数据竞赛作战（comp-kit）

方法论提炼自时间序列决策赛与七题并行 CV / 语音赛两轮完整实战。

| Skill | 用途 |
|---|---|
| `comp-init` | 初始化竞赛仓库：目录布局、CLAUDE.md + AGENTS.md、官网材料存档、数据审计、验证协议、上下界与单步分辨率 |
| `comp-experiment` | 实验纪律：单变量、按来源组切折、同口径对照、证据分级，判断离线提升是否真实、线上会不会涨 |
| `comp-submit` | 提交管理：脚本化校验与准入门禁、三层提交证据与回执、每日额度预算、探针提交、B 榜冻结 |
| `comp-retrospective` | 阶段复盘与答辩：作战手册、证伪清单、离线↔线上标定库、答辩 PPT 与 QA |
| `comp-campaign` | 多赛题并行总控：看板、额度与提交权、共享机器资源仲裁、子代理纪律、守夜与唤醒 |
| `comp-gate` / `comp-log` / `comp-retro` | 手动入口：实验预登记、追加实验记录、生成阶段复盘 |

### 数学建模竞赛（math-modeling）

| Skill | 用途 |
|---|---|
| `math-modeling` | 国赛 / 美赛三角色工作流（建模手、编程手、论文手），含 7 大类算法资源库、Subagent 质检门禁，以及 docx / latex / figure / xlsx / pdf / 论文检索六个子工具 |

基于 [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)（MIT License）精简收录。

## 支持的 Agent

| Agent | 安装参数 `-a` | 斜杠入口 | 备注 |
|---|---|---|---|
| Claude Code | `claude-code` | `/git-commit` | |
| Codex | `codex` | `$git-commit` 或直接描述需求 | |
| opencode | `opencode` | `/git-commit` | |
| Grok Build | `grok` | `/git-commit` | |
| Antigravity CLI（agy） | `antigravity-cli` | `/git-commit` | 需额外配置，见下方 FAQ |

`npx skills` 支持的其他 agent 同样可用，`-a '*'` 一次装到全部。

## 常见问题

### 怎么更新？

```bash
npx skills update -g -y
```

### skill 装在哪里？

全局安装时本体放在 `~/.agents/skills`，Codex、opencode 直接读取；Claude Code（`~/.claude/skills`）和 Grok（`~/.grok/skills`）通过软链指向同一份。加 `--copy` 可改为复制。

### Antigravity CLI（agy）读不到 skill？

agy 全局不读 `~/.agents/skills`，需要在 `~/.gemini/config/skills.json` 登记一次（必须写绝对路径，`~` 不会展开）：

```json
{ "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
```

### 斜杠命令需要单独安装吗？

不需要。所有能力都以 skill（`SKILL.md`）提供，支持 skill 的 agent 会自动注册斜杠入口。

### 可以用插件市场安装吗？

可以，适合想跟随插件自动更新的场景。同一个 agent 不要同时用 `npx skills` 和插件两种方式安装，同名 skill 会重复出现。

<details>
<summary>Claude Code / Codex / Grok 插件市场安装命令</summary>

Claude Code（安装后入口为 `/git-kit:git-commit`）：

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

可选插件：`git-kit`、`comp-kit`、`math-modeling`。

</details>

## 开发与贡献

### 仓库结构

```
hoobnn-skills/
├── .claude-plugin/marketplace.json     # Claude Code 插件市场清单
├── .agents/plugins/marketplace.json    # Codex 插件市场清单
└── plugins/<plugin-name>/
    ├── .claude-plugin/plugin.json
    ├── .codex-plugin/plugin.json
    └── skills/<skill-name>/SKILL.md
```

### 新增一个 skill

1. 在 `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` 编写 skill。frontmatter 必须有 `name`（小写加连字符，与目录名一致）和 `description`；值以 `[`、`<` 开头时加引号，否则 `npx skills` 解析失败会跳过该 skill。
2. skill 目录内不要再放其他 `SKILL.md`：Codex、opencode 会递归扫描并把它们误注册为独立 skill，子文档改用其他文件名（如 `GUIDE.md`）。
3. 需要斜杠入口的能力也写成 skill，不写 `commands/`。

### 新增一个插件

1. 在 `plugins/<plugin-name>/.claude-plugin/plugin.json` 定义 Claude Code 插件。
2. 在 `plugins/<plugin-name>/.codex-plugin/plugin.json` 定义 Codex 插件，并声明 `"skills": "./skills/"`。
3. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组追加一项（`source` 必须以 `./` 开头，裸目录名不被支持）：

   ```json
   { "name": "<plugin-name>", "source": "./plugins/<plugin-name>", "description": "..." }
   ```

4. 在 `.agents/plugins/marketplace.json` 的 `plugins` 数组追加一项：

   ```json
   {
     "name": "<plugin-name>",
     "source": { "source": "local", "path": "./plugins/<plugin-name>" },
     "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
     "category": "Productivity"
   }
   ```
