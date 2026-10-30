---
name: agent-relay
description: 通过 ACP（Agent Client Protocol）在当前 agent 里调用另一个或几个 AI 编程 agent（grok / agy / codex / opencode / pi / mcode / hermes / dsh / claude）派活、给第二意见或并行对比，统一处理协议版本协商、权限应答、模型与推理强度、附件、对方反问、续会话和输出解析，并报告对方改了哪些文件、跑了哪些命令。当用户说「问问 grok」「让 agy / Gemini 看一下」「问问 MiniMax」「问问 DeepSeek / dsh」「找别的模型给个第二意见」「让几个模型分别评审再对比」「把这个任务交给 codex 做」「接着刚才那个 grok 会话」时使用。
---

# agent-relay

`<SKILL_ROOT>` 指本文件所在的目录。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" run <cli[,cli...]> [--model [CLI=]M] [--effort [CLI=]E] \
        [--resume SESSION_ID] [--file F ...] [--answer KEY=VALUE ...] [--asks allow|deny] [--full] \
        [--cwd DIR] [--timeout SEC] [--idle-timeout SEC] [--work-timeout SEC] (PROMPT | - | --prompt-file F)
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
- 输出一个 JSON：`ok`、`text`（最后一段回答）、`session_id`、`cost_usd`、`error`、`error_kind`、`log`、`protocol_version`、`stop_reason`、`timing`、`files_changed`、`commands`、`warnings`（字符串数组），单家运行且 cwd 在 git 仓库里时多一个 `commits` 和 `history_rewritten`，有权限请求时多一个 `permissions`（标题和处理结果），加 `--full` 时多一个 `steps`（按顺序的消息、思考、工具调用）。拿 `session_id` 传给 `--resume` 就能接着聊。
- `files_changed` 合并 git 工作区前后的差异、运行期间提交涉及的文件和工具调用上报的路径（能抓到仓库外的文件）。多家并行时只用工具上报，因为同一目录里分不清是谁改的。
- 单家且在 git 仓库里运行时，`commits` 按新到旧列出运行期间新增的提交。运行前 HEAD 不再是当前 HEAD 的祖先或新增 `refs/original/*` 时，`history_rewritten` 为 true，`warnings` 给出前后 HEAD 和恢复提示。`timing` 给出总耗时、工具/模型耗时及首次工具、编辑、提交的时间，运行中也实时写入 `status.json`。
- `error_kind` 把失败分为 `timeout`、`idle`、`stalled`、`killed`（SIGTERM / SIGINT）、`asked`、`quota`、`rate_limit`、`auth` 或 `error`，没有错误时为 `null`；原始 `error` 文本保持不变。
- 对方反问（ACP elicitation，比如 claude 的 AskUserQuestion）时，relay 结束本轮，`ok` 为 false，问题放在 `questions` 里（字段名、说明、可选值）。回答方式有两种：一是带 `--resume` 和 `--answer 字段=取值`（多选用逗号分隔）重跑，并在 prompt 里让它接着问，它再问时 relay 自动代答；二是直接在 prompt 里写答案。能自己判断的就自己答，拿不准的再问用户。
- 每次运行的目录（输出里的 `log`）下，`status.json` 是给界面看的进度快照：agent 工作期间约每秒重写一次（当前状态、工具完成数、最近 40 步，以及发起方 Claude Code 会话的 `caller_session`），结束时写最终状态。hoobnn-agent-mods 的 `relay-bar` mod 读它，在 Claude Code 的输入框上方显示派出去的活进行到哪了。
- 调用是阻塞的，默认总超时 1200 秒；连续 300 秒（`--idle-timeout`，0 关闭）没有任何输出、也没有工具在跑，就判定卡住；连续 900 秒（`--work-timeout`，0 关闭）只读或思考、没有写入或执行进展，就判定空转；read / search / fetch / think 和无 kind 且无写入的工具不重置计时，edit / delete / move / execute、明确写入 diff 或新提交才算进展。三者都会先 `session/cancel` 再关进程，会话还在，可以重跑或续接。只要意见、不动手的任务（`--asks deny`）要传 `--work-timeout 0`，否则长思考会被误判空转。SIGTERM / SIGINT 也会先取消会话、关闭子进程，再输出已有结果并写终态；第二次信号直接退出。长任务放到宿主的后台机制里跑，relay 在后台命令里前台运行，不要再加 `&` / `nohup`。

对方看不到当前对话，prompt 要自带背景，相关文件用 `--file` 附上；只想要意见时，在 prompt 里写明，再加 `--asks deny`。

调用失败、agent 升级或要新增一家时，先跑 `check`，再看 [REFERENCE.md](REFERENCE.md)。
