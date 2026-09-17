# hoobnn-skills

hoobnn 的个人 skills / 插件集合，用于分发可复用的 agent skills。目前包含：

- **git-kit** — Git 工作流工具集：`gitmoji-commitlint-setup` skill 与 commit / rollback / cleanBranches / worktree 等命令。
- **comp-kit** — 数据竞赛作战工具集：`comp-init`（仓库初始化、验证协议、上下界与单步分辨率）、`comp-experiment`（单变量、同口径、预登记门禁、零成本诊断）、`comp-submit`（校验器 + 准入门禁、三层提交证据、回执、B 榜冻结）、`comp-retrospective`（阶段复盘、标定库、答辩）、`comp-campaign`（多赛题并行总控、子代理纪律、资源仲裁、守夜）五个 skill，另配 `/comp-gate`、`/comp-log`、`/comp-retro` 三个 Claude 命令入口（skill 本身也可经 `/comp-kit:<skill>` 直接调用），方法论提炼自时间序列决策赛与七题并行 CV / 语音赛两轮完整实战。
- **math-modeling** — 数学建模竞赛（CUMCM / MCM / ICM）三阶段工作流 skill：建模分析 → 代码实现 → 论文撰写，含算法资源库、三角色工作细则与论文模板（基于上游 MIT 开源 skill 瘦身收录）。

## 使用

### Claude Code marketplace

在 Claude Code 中添加本市场：

```
/plugin marketplace add hoobnn/hoobnn-skills
```

然后安装其中的插件：

```
/plugin install <plugin-name>@hoobnn-skills
```

查看已添加的市场：`/plugin marketplace list`，更新：`/plugin marketplace update hoobnn-skills`。

### npx skills

本仓库兼容 [`skills`](https://www.npmjs.com/package/skills) CLI，可安装到 Codex、Claude Code 等 agent：

```
npx skills add hoobnn/hoobnn-skills --list
npx skills add hoobnn/hoobnn-skills --skill gitmoji-commitlint-setup -g -a codex -y
```

常用参数：

- `-a codex`：安装到 Codex。
- `-a claude-code`：安装到 Claude Code。
- `-g`：安装为全局 skill。
- `--copy`：复制文件而不是创建软链。

### Codex marketplace

本仓库也包含 Codex marketplace 清单。添加市场并安装插件：

```
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

安装后新开一个 Codex 会话，让插件里的 skill 元数据重新加载。

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
3. 在 `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` 编写 skill。
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
