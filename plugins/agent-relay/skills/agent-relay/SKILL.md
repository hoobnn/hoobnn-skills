---
name: agent-relay
description: 在当前 agent 里调用另一个 AI 编程 CLI（grok / agy / codex / opencode / pi / hermes / claude）派活或给第二意见，统一处理各家的 headless 参数、只读 / 可写权限、续会话和输出解析。当用户说「问问 grok」「让 agy / Gemini 看一下」「找别的模型给个第二意见」「让几个模型分别评审再对比」「把这个任务交给 codex 做」「接着刚才那个 grok 会话」时使用。
---

# agent-relay

`<SKILL_ROOT>` 指本文件所在的目录。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" run <cli> [--write] [--model M] [--effort E] \
        [--resume SESSION_ID] [--cwd DIR] [--timeout SEC] (PROMPT | - | --prompt-file F)
python3 "<SKILL_ROOT>/scripts/relay.py" check [cli...]  # 冒烟测试：回复、续会话、只读挡写
```

- `<cli>`：`grok` `agy` `codex` `opencode` `pi` `hermes` `claude`。
- 默认只读，`--write` 才允许改文件和跑命令。`--model` / `--effort` 按各家 CLI 自己的写法原样传。
- 输出一个 JSON：`ok`、`text`、`session_id`、`cost_usd`、`read_only_enforced`、`error`、`log`（原始输出目录）。拿 `session_id` 传给 `--resume` 就能接着聊。
- 调用是阻塞的，默认超时 1200 秒；长任务放到宿主的后台机制里跑。

对方看不到当前对话，prompt 要自带背景。只读模式下 grok、pi、claude 没有 shell，跑不了 `git diff` 这类命令，需要的内容直接放进 prompt；agy 和 hermes 没有只读开关（`read_only_enforced: false`），脚本不会替你改 prompt。

调用失败、参数可能过时，或要新增一家 CLI 时，先跑 `check`，再看 [REFERENCE.md](REFERENCE.md)。
