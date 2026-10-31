---
name: agent-relay
description: 在当前 agent 里调用另一个或几个 AI 编程 agent（grok / agy / codex / opencode / pi / mcode / hermes / dsh / claude）派活、给第二意见、续会话或并行对比，并报告对方改了哪些文件、跑了哪些命令。当用户说「问问 grok」「让 agy / Gemini 看一下」「问问 MiniMax」「问问 DeepSeek / dsh」「找别的模型给个第二意见」「让几个模型分别评审再对比」「把这个任务交给 codex 做」「接着刚才那个 grok 会话」时使用。
---

# agent-relay

`<SKILL_ROOT>` 指本文件所在目录。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" run <cli[,cli...]> [--model [CLI=]M] [--effort [CLI=]E] \
        [--resume SID] [--file F ...] [--answer KEY=VALUE ...] [--auto-answer recommended|first] \
        [--asks allow|deny] [--cwd DIR] [--timeout SEC] [--idle-timeout SEC] [--work-timeout SEC] \
        [--full] (PROMPT | - | --prompt-file F)
python3 "<SKILL_ROOT>/scripts/relay.py" show [OUT_JSON_OR_RUN_DIR] [--latest [CLI]] [--tail N] [--json]
python3 "<SKILL_ROOT>/scripts/relay.py" options <cli>
```

- `<cli>`：`grok` `agy` `codex` `opencode` `pi` `mcode`（MiniMax Code）`hermes` `dsh`（DeepSeek Harness）`claude`；逗号分隔多家会并行执行同一 prompt，并输出数组。
- `--model` / `--effort` 匹配取值或名称（大小写不敏感，模型可写末段）；`CLI=值` 只用于一家，否则用于所有家。匹配不到或有歧义时按报错候选修正，或先跑 `options`。
- `--asks allow`（默认）代答本机配置要求确认的权限，`deny` 拒绝这些请求；本机配置本来拒绝的操作不会放行。
- `--file` 可重复附加文件；图片需对端模型支持，文本可能内嵌，也可能只发文件链接让对方读取。
- 结果先看 `ok`、`text`、`error_kind`、`warnings`；`session_id` 供 `--resume`，`log` 是运行目录，`show` 可看摘要或进度，`--full` 另附完整 `steps`。
- 验收看 `files_changed`、`commands`；单家 git 任务还看 `commits`、`uncommitted`、`history_rewritten`。多家并行时改动仅靠工具上报，不能当作完整 diff。
- `error_kind=asked` 时读 `questions`，用 `--resume SID` 续接，再以 `--answer 字段=取值` 代答（多选用逗号）或在 prompt 里直接回答；能自行判断就代答，拿不准再问用户。
- `--answer` 优先于自动代答；`--auto-answer recommended` 只选标题明确标注推荐且不否定的选项，`first` 无推荐项时选第一项，无法覆盖必填字段仍返回 `questions`。
- `timeout` / `idle` / `stalled` 会取消本轮但保留会话；先审视产物再续接或重跑。`quota` 换家，`rate_limit` 可重试，`auth` 先登录，`resume_cwd` 换目录须开新会话；其他失败看 `error` 和日志。
- 默认总 / 空闲 / 空转超时为 1200 / 300 / 900 秒；空转只把写入、执行或新提交当进展，空闲与空转超时均可设 0 关闭。评审等只读任务用 `--asks deny --work-timeout 0`，避免长思考被误杀。

## 派长任务

- 用宿主的后台机制运行，relay 在后台命令里保持前台，勿再加 `&` / `nohup`；实现任务的总超时设 45–60 分钟。
- prompt 给足背景与权威文件，限定可改范围，要求每完成一块就提交、不要反问、边做边测；写明交付检查和回报格式，相关文件用 `--file` 附上。
- 超时后先查 `commits`、`uncommitted` 和 worktree，再决定续接或换家；`history_rewritten=true` 时按 `warnings` 保存现场并恢复。

排障、各家怪癖及 `check` / `install` / `outdated` 见 [REFERENCE.md](REFERENCE.md)。
