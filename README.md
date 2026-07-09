# hoobnn-skills

hoobnn 的个人 skills / 插件集合，用于分发可复用的 agent skills。目前包含 `git-kit` 插件与
`gitmoji-commitlint-setup` skill。

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
