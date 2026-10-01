# hoobnn-skills

hoobnn 的个人 skills / 插件集合，用于分发可复用的 agent skills。目前包含：

- **git-kit** — Git 工作流工具集：`gitmoji-commitlint-setup`（提交规范落地）、`git-commit`、`git-rollback`、`git-clean-branches`、`git-worktree`。
- **comp-kit** — 数据竞赛作战工具集：`comp-init`（仓库初始化、验证协议、上下界与单步分辨率）、`comp-experiment`（单变量、同口径、预登记门禁、零成本诊断）、`comp-submit`（校验器 + 准入门禁、三层提交证据、回执、B 榜冻结）、`comp-retrospective`（阶段复盘、标定库、答辩）、`comp-campaign`（多赛题并行总控、子代理纪律、资源仲裁、守夜），外加 `comp-gate`、`comp-log`、`comp-retro` 三个手动入口，方法论提炼自时间序列决策赛与七题并行 CV / 语音赛两轮完整实战。
- **math-modeling** — 数学建模竞赛（CUMCM / MCM / ICM）三阶段工作流 skill：建模分析 → 代码实现 → 论文撰写，含算法资源库、三角色工作细则与论文模板（基于上游 MIT 开源 skill 瘦身收录）。

所有能力都以 skill（`SKILL.md`）提供，没有单独的斜杠命令文件。支持 skill 的工具会把它们注册成斜杠入口：
`npx skills` 安装后是 `/git-worktree`，Claude Code 插件安装后是 `/git-kit:git-worktree`。

## 安装

### 首选：npx skills

用 [`skills`](https://www.npmjs.com/package/skills) CLI 安装，一条命令覆盖 Claude Code、Codex、opencode、Antigravity 等 agent：

```
npx skills add hoobnn/hoobnn-skills --list                       # 列出全部 skill
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y
```

常用参数：`-g` 全局安装；`-a <agent>` 指定 agent（`'*'` 为全部）；`--skill <name>` 指定 skill（`'*'` 为全部）；`--copy` 复制而不是软链。
更新：`npx skills update`。

注意：

- 同一个工具不要既用 `npx skills` 又装本仓库的插件，同名 skill 会重复出现。
- 公共目录 `~/.agents/skills` 会被 Codex、opencode 等多个工具同时读取；装到这里的 skill 对这些工具都生效。
- Antigravity CLI（agy）全局不读 `~/.agents/skills`，需要在 `~/.gemini/config/skills.json` 里登记一次（路径写绝对路径，`~` 不展开）：

  ```json
  { "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
  ```

### 插件市场（备选）

需要随插件自动更新时使用。

Claude Code：

```
/plugin marketplace add hoobnn/hoobnn-skills
/plugin install <plugin-name>@hoobnn-skills
```

更新：`/plugin marketplace update hoobnn-skills`。

Codex：

```
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

更新：`codex plugin marketplace upgrade hoobnn-skills`，然后新开会话。

Grok：

```
grok plugin marketplace add hoobnn/hoobnn-skills
grok plugin install git-kit@hoobnn-skills
```

## 仓库结构

```
hoobnn-skills/
├── .claude-plugin/
│   └── marketplace.json     # 市场清单，列出所有插件
├── .agents/
│   └── plugins/
│       └── marketplace.json # Codex marketplace 清单
└── plugins/
    └── <plugin-name>/       # 每个插件一个目录
        ├── .codex-plugin/
        │   └── plugin.json  # Codex 插件定义
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── <skill-name>/
                └── SKILL.md
```

## 新增一个插件

1. 在 `plugins/<plugin-name>/.claude-plugin/plugin.json` 定义插件。
2. 在 `plugins/<plugin-name>/.codex-plugin/plugin.json` 定义 Codex 插件，并声明 `"skills": "./skills/"`。
3. 在 `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` 编写 skill。frontmatter 必须有 `name`（小写加连字符，与目录名一致）和 `description`；需要斜杠入口的能力也写成 skill，不再写 `commands/`。
4. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组追加一项：

   ```json
   { "name": "<plugin-name>", "source": "./plugins/<plugin-name>", "description": "..." }
   ```

   （`source` 必须是以 `./` 开头、相对于市场根目录的插件路径；裸目录名不被支持。）
5. 在 `.agents/plugins/marketplace.json` 的 `plugins` 数组追加一项：

   ```json
   {
     "name": "<plugin-name>",
     "source": { "source": "local", "path": "./plugins/<plugin-name>" },
     "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
     "category": "Productivity"
   }
   ```
