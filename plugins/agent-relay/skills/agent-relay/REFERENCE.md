# agent-relay 参考

实测过的坑，以及新增 agent 的步骤。各家怎么启动，直接看 `scripts/relay.py` 里的 `AGENTS` 表。

## 协议版本

- 按 ACP v2 草案（2026-07 发布）实现：`initialize` 请求 `protocolVersion: 2`，同一个请求里也带 v1 的 `clientCapabilities` / `clientInfo`（v2 要求忽略未知字段），对端选 1 就走 v1 线协议，一条连接只协商一次。
- 两个版本的差异集中在 `Session` 里：v1 以 `session/prompt` 响应的 `stopReason` 判结束；v2 的响应只确认插入（返回 `messageId`），结束要等 `state_update` 的 `idle`。v1 续会话优先 `session/resume`，不支持再用 `session/load`（会回放历史，脚本只收发出 prompt 之后的输出）；v2 统一 `session/resume` 不带 `replayFrom`。模式在 v1 走 `session/set_mode`，v2 只有 config option。
- 注册表的协议矩阵（2026-10-26）把 37 家都记成 v1，但实测 codex-acp 2.3.0、claude-agent-acp 0.97.0 已经能协商出 v2，矩阵不能当准。agy 回 `protocolVersion: 2` 却用 v1 结构和 v1 行为，脚本见到这种响应按 v1 走。
- 客户端不声明 fs / terminal 能力，agent 发来这类请求一律回 method-not-found。
- 客户端声明 form 模式的 elicitation（不声明 url 模式，那要人去浏览器里操作）。收到反问时，`--answer` 覆盖了全部必填字段就回 `accept`；否则回 `cancel`、发 `session/cancel` 结束本轮，把问题交回调用方。会话还在，续接即可。实测 claude-agent-acp 只在客户端声明 form 时才把 AskUserQuestion 转成 elicitation，字段名是 `question_0`、`question_0_custom`（自由填写）这种；codex-acp 也实现了 elicitation。
- 附件按 prompt 能力发：图片发 `image` 块；文本文件不超过 1 MB 且对端声明了 `embeddedContext` 时发 `resource` 块嵌入内容，否则发 `resource_link`（baseline，所有 agent 都得支持）。prompt 能力 v1 在 `agentCapabilities.promptCapabilities`（布尔），v2 在 `capabilities.session.prompt`（对象，`{}` 表示支持）。

## 各家实测（2026-10-27）

| agent | 启动 | 协商出的版本 | 嵌入文本 |
| --- | --- | --- | --- |
| grok 1.0.70 | `grok agent stdio` | v1 | 是 |
| agy ACP server 1.4.3 | `relay.py install agy` 装的 `agy_acp_server.par` | 声称 v2，实际 v1 | 是 |
| codex-acp 2.3.0 | `npx @agentclientprotocol/codex-acp@2.3.0` | v2 | 是 |
| opencode 2.1.4 | `opencode acp` | v1 | 是 |
| pi-acp 0.0.34（pi 1.4.0） | `npx pi-acp@0.0.34` | v1 | 否，发链接 |
| mcode 0.6.13 | `mcode acp` | v1 | 否，发链接 |
| hermes 0.22.5 | `hermes acp` | v1 | 否，发链接 |
| dsh 0.2.1-rc.2（deepseek-harness-acp 0.0.1） | `dsh --profile acp` | v1 | 否，发链接 |
| claude-agent-acp 0.97.0 | `npx @agentclientprotocol/claude-agent-acp@0.97.0` | v2 | 是 |

权限沿用各家本机配置：relay 不切模式，agent 按自己的配置决定哪些操作要问。问到时 `--asks allow` 选 `allow_once` / `allow_always`，`--asks deny` 选 `reject_once` / `reject_always`，没有对应选项时回 `cancelled`，所以不会卡在等确认上。实测本机配置下会来问的有 agy（建文件）和 hermes（改文件），其余几家按各自配置直接执行。要彻底限制某家能做什么，改它自己的配置。

## 改动统计与卡住判定

- 各家上报工具调用的方式差别很大：codex、claude 常用 shell 写文件，工具调用只有 `kind: execute` 和命令，没有文件路径；mcode 先发一串空的 `tool_call_update` 再补内容；hermes 的路径是相对路径，审批还会另起一个只有状态的工具调用。所以 `files_changed` 以 git 工作区前后快照为主（`status --porcelain -uall` 里每个文件的内容哈希，比对前后差异），再并上 `kind` 为 edit / delete / move 且已完成的工具调用里的 `locations`、v1 diff 的 `path`、v2 diff 的 `changes`。不是 git 仓库时只有后者。
- `commands` 取 `kind: execute` 的工具调用，命令优先用 `rawInput.command`（codex、claude 都有），没有就用标题。
- 空闲超时只在没有工具处于 pending / in_progress 时计时，避免把跑长测试误判成卡住；代价是某家把工具调用一直挂在 pending 时，只能等总超时。

## 实测过的坑

- agy 每次会话都会在会话目录建 `skills/system/run-workflow/SKILL.md`（物化内置 skill，没有开关），relay 跑完只删本次新建的部分。认证用 `oauth-personal` 复用本机 agy 的 Google 登录，首次会在 `~/.gemini/antigravity-acp/settings.json` 记下认证方式。
- pi-acp 会先发一段启动横幅（版本和 skill 列表）作为无 `messageId` 的消息，脚本遇到思考、工具调用等更新就切段，只取最后一段当回答。
- codex 偶尔在接受 prompt（返回 `messageId`、报 `running`）后长时间没有输出，空闲超时会提前结束这一轮；重跑即可。本机 codex 开着开发中的特性 `local_thread_store_compression`，会话恢复时它会发 notice 提醒可能不稳定。
- claude 用 ACP 时默认模型是 opus，一次 check 大约 0.5 美元，日常可传 `--model sonnet` / `haiku`。
- opencode 的模型 config option 有两百多个取值，同名模型分属多个 provider（`magpie/auto/...`、`minimax/...`），只写末段会有歧义，要写全。
- hermes 没有 config option，模型走 v1 的 unstable `session/set_model`，没有推理强度选项。
- dsh 的模型取值是 JSON 数组字符串 `["provider","model"]`，`--model` 按 `provider/model` 匹配，可只写 `model` 部分（如 `auto/deepseek-v4-pro`）；只写 `deepseek-v4-pro` 会同时命中多个 provider。ACP 会话的默认模型取自 `acp` 插件自己的 `provider` / `model`（模板里是 `deepseek-official`），不读其它 profile 用的 `agent-default-model`，要改默认就在 `$DSH_HOME/profiles/acp/cordis.patch.yml` 里对 `id: acp` 打补丁。默认模型不收图片时，图片附件会直接报错。
- grok 的 `set_config_option` 只接受字符串取值，布尔选项还没实现。
- npx 拉起的适配器是 ACP server，不认 `--version` 之类参数，会一直等 stdin。第一次要下载，`check` 每次调用默认 300 秒，首次可能不够，先跑一次 `options` 预热。
- 超时要杀整棵进程树：agent 会把 shell 命令放进新的会话，只杀进程组会留下孤儿进程。
- 运行日志在 `~/.local/state/agent-relay/runs/`，`acp.jsonl` 是完整的 JSON-RPC 往来，每次运行时自动删掉 7 天前的。

## 新增一家 agent

在 `scripts/relay.py` 的 `AGENTS` 里加一项：`cmd`（ACP 注册表 `agentclientprotocol/registry` 里的启动方式，npx 包钉版本），需要的话加 `auth`（预先认证的方法 ID）；走 npx 或注册表二进制分发的再加 `registry`（注册表里的 id），`outdated` 才查得到。然后跑 `relay.py check <cli>`，四项通过后补上面的表。

## 升级钉住的适配器

`relay.py outdated` 拉注册表（`cdn.agentclientprotocol.com/registry/v1/latest/registry.json`，默认的 Python-urllib UA 会被拒，脚本带了自己的 UA），对比 codex、pi、claude 的 npx 包版本和 agy 的二进制版本，有新版时给出替换值：npx 是新的 `cmd`，agy 是新的 `AGY_ACP`（各平台归档、sha256、启动参数，linux 要带 `--uid=`）。改完跑 `check`，agy 还要重新 `install agy`。grok、opencode、mcode、hermes、dsh 用的是本机 CLI 自带的 ACP，跟着它们自己的更新走，注册表里的版本也不准。
