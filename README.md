# hoobnn-skills

hoobnn 的个人 [Claude Code](https://code.claude.com) 插件市场（plugin marketplace），用于分发 skills 等插件。

## 使用

在 Claude Code 中添加本市场：

```
/plugin marketplace add hoobnn/hoobnn-skills
```

然后安装其中的插件：

```
/plugin install <plugin-name>@hoobnn-skills
```

查看已添加的市场：`/plugin marketplace list`，更新：`/plugin marketplace update hoobnn-skills`。

## 仓库结构

```
hoobnn-skills/
├── .claude-plugin/
│   └── marketplace.json     # 市场清单，列出所有插件
└── plugins/
    └── <plugin-name>/       # 每个插件一个目录
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── <skill-name>/
                └── SKILL.md
```

## 新增一个插件

1. 在 `plugins/<plugin-name>/.claude-plugin/plugin.json` 定义插件。
2. 在 `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` 编写 skill。
3. 在 `.claude-plugin/marketplace.json` 的 `plugins` 数组追加一项：

   ```json
   { "name": "<plugin-name>", "source": "./plugins/<plugin-name>", "description": "..." }
   ```

   （`source` 必须是以 `./` 开头、相对于市场根目录的插件路径；裸目录名不被支持。）
