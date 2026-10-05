# agent-relay 参考

实测过的坑，以及新增 CLI 的步骤。各家怎么调用、怎么解析输出，直接看 `scripts/relay.py` 里的 `build_<cli>` / `parse_<cli>`。

## 实测过的坑

- stdin 一律接 `/dev/null`。codex 在 stdin 是管道时会等待额外输入。
- grok 的 `--permission-mode plan` / `dontAsk` 和 `--sandbox read-only` 都拦不住写文件，只有工具白名单有效。内置工具名可以在 `~/.grok/sessions/<目录>/<会话>/tool_definitions.json` 里查。
- agy 的 `--mode plan`、`--sandbox` 和默认权限都拦不住写文件。模型名写错时返回空回答、退出码 0，脚本把空回答判为失败；可用模型用 `agy models` 查。旧版 `--print-timeout` 默认 5 分钟（1.2.16 起默认不限时），所以总是显式传。
- hermes 的工具集里读写文件是同一个 `file`，没法只给读。
- pi 用脚本生成的 UUID 作为 `--session-id`，首轮就能拿到可续接的 ID。
- opencode 会沿父目录查找 `opencode.json` 当配置，工作目录或上级目录里有同名文件会报配置错误。
- grok 的 `text` 是整轮所有助手文字拼起来的，开头常带「我先看一下……」这类过程说明，最终答案在末尾。
- 超时要杀整棵进程树：codex 会把 shell 命令放进新的会话，只杀进程组会留下孤儿进程。
- 运行日志在 `~/.local/state/agent-relay/runs/`，每次运行时自动删掉 7 天前的。
- claude 默认用你配置的模型，简单问题也可能花几毛钱，必要时传 `--model`。

## 新增一家 CLI

在 `scripts/relay.py` 里加一对函数并登记到 `ADAPTERS`：

- `build_<cli>(a, prompt)` 返回 `(argv, 只读是否强制, 预置的会话 ID 或 None)`
- `parse_<cli>(raw_stdout, a, sid)` 返回 `text`、`session_id`、`cost_usd`、`ok`（可选 `error`）

然后跑 `relay.py check <cli>`，确认三项都通过。
