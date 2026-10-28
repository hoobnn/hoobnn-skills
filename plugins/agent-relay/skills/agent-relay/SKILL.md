---
name: agent-relay
description: 通过 ACP（Agent Client Protocol）在当前 agent 里调用另一个或几个 AI 编程 agent（grok / agy / codex / opencode / pi / mcode / hermes / dsh / claude）派活、给第二意见或并行对比，统一处理协议版本协商、权限应答、模型与推理强度、附件、对方反问、续会话和输出解析，并报告对方改了哪些文件、跑了哪些命令。当用户说「问问 grok」「让 agy / Gemini 看一下」「问问 MiniMax」「问问 DeepSeek / dsh」「找别的模型给个第二意见」「让几个模型分别评审再对比」「把这个任务交给 codex 做」「接着刚才那个 grok 会话」时使用。
---

# agent-relay

`<SKILL_ROOT>` 指本文件所在的目录。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" run <cli[,cli...]> [--model [CLI=]M] [--effort [CLI=]E] \
        [--resume SESSION_ID] [--file F ...] [--answer KEY=VALUE ...] [--asks allow|deny] [--full] \
        [--cwd DIR] [--timeout SEC] [--idle-timeout SEC] (PROMPT | - | --prompt-file F)
python3 "<SKILL_ROOT>/scripts/relay.py" options <cli>  # 列出可选的模型、推理强度、模式
python3 "<SKILL_ROOT>/scripts/relay.py" check [cli...]  # 冒烟测试：回复、续会话、写文件、附件
python3 "<SKILL_ROOT>/scripts/relay.py" install agy    # agy 的 ACP server 要单独下载
python3 "<SKILL_ROOT>/scripts/relay.py" outdated       # 对照 ACP 注册表看钉住的适配器有没有新版本
```

- `<cli>`：`grok` `agy` `codex` `opencode` `pi` `mcode`（MiniMax Code）`hermes` `dsh`（DeepSeek Harness）`claude`。逗号分隔多家时并行跑同一个 prompt，输出数组（每项多一个 `cli`）；`--model claude=haiku` 这种写法只给那一家，不带前缀的给所有家。
- relay 是 ACP 客户端：按 v2 草案请求协议版本 2，对端只会 v1 时自动回落（目前 codex、claude 已协商出 v2，其余是 v1）；`--protocol 1` 可强制 v1。
- 权限沿用各家本机自己的配置（如 opencode.json、`~/.claude/settings.json`），relay 不改模式。配置里写成「要问」的操作，默认 `--asks allow` 代为放行（relay 是非交互的）；`--asks deny` 把它们当成拒绝，适合只想要意见的场景。配置里本来就拒绝的，两种都不会放行。
- `--model` / `--effort` 匹配会话的 config option（取值或名称，大小写不敏感，可只写模型名的末段）；匹配不到或有歧义时报错并列出候选，先用 `options` 查。
- `--file` 可重复，用来把文件随 prompt 送过去：图片直接内联（九家都收），文本文件在对端支持时嵌入内容，否则发文件链接让它自己读。
- 输出一个 JSON：`ok`、`text`（最后一段回答）、`session_id`、`cost_usd`、`error`、`log`、`protocol_version`、`stop_reason`、`files_changed`、`commands`，有权限请求时多一个 `permissions`（标题和处理结果），加 `--full` 时多一个 `steps`（按顺序的消息、思考、工具调用）。拿 `session_id` 传给 `--resume` 就能接着聊。
- `files_changed` 合并两路来源：git 工作区前后的差异（能抓到 shell 写的文件）和工具调用上报的路径（能抓到仓库外的文件）。多家并行时只用后者，因为同一目录里分不清是谁改的。
- 对方反问（ACP elicitation，比如 claude 的 AskUserQuestion）时，relay 结束本轮，`ok` 为 false，问题放在 `questions` 里（字段名、说明、可选值）。回答方式有两种：一是带 `--resume` 和 `--answer 字段=取值`（多选用逗号分隔）重跑，并在 prompt 里让它接着问，它再问时 relay 自动代答；二是直接在 prompt 里写答案。能自己判断的就自己答，拿不准的再问用户。
- 调用是阻塞的，默认总超时 1200 秒；连续 300 秒（`--idle-timeout`，0 关闭）没有任何输出、也没有工具在跑，就判定卡住提前结束。两种情况都会先 `session/cancel` 再关进程，会话还在，可以重跑或续接。长任务放到宿主的后台机制里跑。

对方看不到当前对话，prompt 要自带背景，相关文件用 `--file` 附上；只想要意见时，在 prompt 里写明，再加 `--asks deny`。

调用失败、agent 升级或要新增一家时，先跑 `check`，再看 [REFERENCE.md](REFERENCE.md)。
