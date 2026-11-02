---
name: agent-relay
description: 在当前 agent 里调用另一个或几个 AI 编程 agent（grok / agy / codex / opencode / pi / mcode / hermes / dsh / claude）派活、给第二意见、续会话或并行对比，并报告对方改了哪些文件、跑了哪些命令。当用户说「问问 grok」「让 agy / Gemini 看一下」「问问 MiniMax」「问问 DeepSeek / dsh」「找别的模型给个第二意见」「让几个模型分别评审再对比」「把这个任务交给 codex 做」「接着刚才那个 grok 会话」时使用。
---

# agent-relay

`<SKILL_ROOT>` 指本文件所在目录。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" run <cli[,cli...]> [-t reviewer|implementer] [--worktree] \
        [--model [CLI=]M] [--effort [CLI=]E] [--resume SID] [--file F ...] [--answer KEY=VALUE ...] \
        [--auto-answer recommended|first] [--asks allow|deny] [--cwd DIR] \
        [--timeout SEC] [--idle-timeout SEC] [--work-timeout SEC] [--full] (PROMPT | - | --prompt-file F)
python3 "<SKILL_ROOT>/scripts/relay.py" show [OUT_JSON_OR_RUN_DIR] [--latest [CLI]] [--tail N] [--json]
python3 "<SKILL_ROOT>/scripts/relay.py" options <cli>
```

- `<cli>`：`grok` `agy` `codex` `opencode` `pi` `mcode`（MiniMax Code）`hermes` `dsh`（DeepSeek Harness）`claude`；逗号分隔多家时并行跑同一个 prompt，输出数组。
- `-t reviewer` 只读评审，拒绝需要确认的权限；`-t implementer` 用于实现任务：限定范围、不反问、边测边提交、按固定格式回报，总超时 3600 秒。命令行显式参数优先于模板；续接时不用再带 `-t`。
- `--worktree`：每家在 `<仓库>.worktrees/relay-<cli>-<id>/` 的新分支上跑，带上未提交改动和小的被忽略文件，被忽略的目录会在 prompt 里提醒对方自己装依赖。对方没改动就自动删掉 worktree 和分支（结果里 `worktree: null`），有改动就保留，审完自行删除。多家都要改代码时必须用它。
- `--model` / `--effort` 不区分大小写匹配取值或名称，模型可只写末段；`CLI=值` 只给一家。匹配失败按报错候选修正，或先跑 `options`。
- `--asks allow`（默认）代答本机配置要求确认的权限，`deny` 拒绝；本机配置本来就拒绝的操作不会放行。`--file` 附件里图片需要对端模型支持。
- 结果先看 `ok`、`text`、`error_kind`、`hint`、`warnings`，退出码随 `error_kind` 区分。验收看 `files_changed`、`commands`、`commits`、`uncommitted`、`history_rewritten`，再核对 `cost_usd`、`auto_answers`。`session_id` 用于 `--resume`；`show` 查看摘要或进度；`--full` 附完整过程。
- `error_kind=asked` 时读 `questions`；能自己判断就代答，拿不准再问用户。续接写 `--resume SID --answer 字段=取值`，并在 prompt 里要求对方重新提问（多选用逗号），或者直接把答案写进 prompt。`--auto-answer` 的识别规则见 REFERENCE.md。
- 默认总超时 1200 秒、空闲超时 300 秒（设 0 关闭空闲超时），不按空转取消。`since_progress_s` 记录距上次写入、执行或提交过了多久，是否卡住由调用方判断；确实需要自动取消时再设 `--work-timeout`。超时后会话还在，先审视产物，再续接或重跑。

## 派长任务

- 用宿主的后台机制运行，relay 本身在前台跑，不要加 `&` / `nohup`；配合 `-t implementer`，prompt 写明背景、权威文件、可改范围和交付检查，相关文件用 `--file` 附上。
- 超时后先查 `commits`、`uncommitted`，再决定续接还是换家；`history_rewritten=true` 时按 `warnings` 恢复。

排障、各家怪癖、退出码、模板格式及 `check` / `install` / `outdated` 见 [REFERENCE.md](REFERENCE.md)。
