# agent-relay 参考

记录协议差异、实测怪癖与维护方法；日常派活只看 `SKILL.md`。

```bash
python3 "<SKILL_ROOT>/scripts/relay.py" check [cli...]  # 回复、续会话、写文件、附件四项冒烟
python3 "<SKILL_ROOT>/scripts/relay.py" install agy
python3 "<SKILL_ROOT>/scripts/relay.py" outdated
```

`check` 会实际调用 agent 并产生费用，单次调用默认限时 300 秒；首次使用 npx 适配器可先跑 `options` 预热下载。

## 协议与能力

- 按 ACP v2 草案（2026-07）请求版本 2，同时携带 v1 字段；对端选 1 就走 v1，一条连接只协商一次。`--protocol 1` 可强制 v1。
- v1 以 `session/prompt` 响应的 `stopReason` 判结束；v2 的响应只确认插入，要等 `state_update=idle`。v1 续会话优先 `session/resume`，不支持才用会回放历史的 `session/load`；v2 统一 `session/resume` 且不带 `replayFrom`。模式在 v1 走 `session/set_mode`，v2 只有 config option。
- 注册表的协议矩阵（2026-10-26）把 37 家都记成 v1，但实测 codex、claude 已支持 v2，矩阵不能当准。agy 声称 v2 却返回 v1 结构并按 v1 工作，relay 会按实际结构降级。
- 客户端不声明 fs / terminal 能力，相关请求一律回 method-not-found；elicitation 只声明 form，不声明需要人工浏览器的 url。claude 只在声明 form 后把 AskUserQuestion 转成 elicitation，字段形如 `question_0`、`question_0_custom`；codex 也实现了 elicitation。
- 图片以 `image` 块内联。文本不超过 1 MB 且对端支持 `embeddedContext` 时嵌入，否则发 `resource_link`；v1 的 prompt 能力是布尔值，v2 是对象（`{}` 也表示支持）。

## 各家实测（2026-10-27）

| agent | 实测版本 | 协议 | 嵌入文本 |
| --- | --- | --- | --- |
| grok | 1.0.70 | v1 | 是 |
| agy ACP server | 1.4.3 | 声称 v2，实际 v1 | 是 |
| codex-acp | 2.3.0 | v2 | 是 |
| opencode | 2.1.4 | v1 | 是 |
| pi-acp（pi） | 0.0.34（1.4.0） | v1 | 否，发链接 |
| mcode | 0.6.13 | v1 | 否，发链接 |
| hermes | 0.22.5 | v1 | 否，发链接 |
| dsh（deepseek-harness-acp） | 0.2.1-rc.2（0.0.1） | v1 | 否，发链接 |
| claude-agent-acp | 0.97.0 | v2 | 是 |

- 实测本机配置下 agy 建文件、hermes 改文件会请求权限。
- agy 每次会话都会物化 `skills/system/run-workflow/SKILL.md`，没有开关，relay 只清理本次新建的部分。认证用 `oauth-personal` 复用本机 Google 登录，首次会在 `~/.gemini/antigravity-acp/settings.json` 记录认证方式。
- pi-acp 会把版本和 skill 列表等启动横幅作为无 `messageId` 的消息发出，不能与最终回答混为一段。
- codex 偶尔接受 prompt 后长时间无输出。本机若开启开发中的 `local_thread_store_compression`，续会话时可能收到不稳定提醒。
- claude 的 ACP 默认模型是 opus，一次 `check` 约 0.5 美元；日常可指定 sonnet / haiku。
- opencode 的模型选项有两百多个，同名模型可能属于不同 provider。
- hermes 没有 config option，模型走 v1 unstable `session/set_model`，没有推理强度选项。
- dsh 的模型值是 JSON 数组 `["provider","model"]`，relay 按 `provider/model` 匹配。ACP 默认模型取自 `acp` 插件自己的 `provider` / `model`，要改 `$DSH_HOME/profiles/acp/cordis.patch.yml` 中 `id: acp` 的配置；默认模型不收图片时，图片附件会报错。
- grok 的 `set_config_option` 只接受字符串值，布尔选项尚未实现。
- npx 拉起的适配器是 ACP server，不认 `--version`，会等待 stdin。

## 结果字段

- `text` 只取最后一段非空回答，不包含完整消息、思考和工具过程。
- `uncommitted` 只含本轮发生变化且结束时仍未提交的路径，不是完整工作区状态。
- `cost_usd` 用于核对对端上报的美元费用，未上报时为 `null`。
- `permissions` 记录权限请求的标题与处理结果，用于审计放行或拒绝。
- `auto_answers` 记录自动代答的问题和内容，用于核对 relay 代选了什么。
- `questions` 保存未能代答的字段、说明和可选值，供续接时回答。
- `timing` 用于查看总耗时、工具 / 模型耗时及首次工具、编辑、提交时间；按秒记账，短工具可能记为 0。

## 改动、日志与超时

- codex、claude 常通过 shell 写文件，工具调用没有路径；mcode 会先发空调用再补内容；hermes 报相对路径，审批还会另起调用。因此工具上报的路径不能单独代表全部改动，单家 git 运行需结合工作区与提交差异。
- 有工具处于 pending / in_progress 时不计空闲或空转，避免误杀长测试；代价是 agent 若把调用一直挂起，只能由总超时终止。
- 日志在 `~/.local/state/agent-relay/runs/`：`acp.jsonl` 记录 JSON-RPC，超过 4 KB 的 base64 / data 只留大小和 SHA-256 前 12 位；运行目录保留 7 天。`status.json` 约每秒原子更新，含 `caller_session`、进度和最近 40 步，结束时写终态，供 hoobnn-agent-mods 的 relay-bar 读取。
- 超时或信号会取消会话并杀整棵进程树，因为 agent 启动的命令可能已离开原进程组；第二次 SIGTERM / SIGINT 直接退出。

## 长任务实测

- mcode 多次出现长时间只思考或阅读、很晚才首次编辑且不提交的情况；它更适合范围窄、目标明确的任务。同机多个 agent 同时跑重测试会互相拖慢并引发偶发失败，应错开。
- pi 曾改写约 30 个 main 提交。发现历史改写时，先把当前 HEAD 保存为临时分支，再按警告恢复运行前 HEAD，最后从临时分支摘取 tree 并重新提交。
- 新建 git worktree 只带受版本控制的文件；被 exclude 的 `.node-version`、`node_modules` 等需自行补齐。工作树删除后不要续接原会话。

## 新增或升级 agent

- 新增时在 `AGENTS` 填启动命令，按需填预认证方法 ID 和注册表 ID，再跑 `check <cli>` 并补实测表；npx 包与注册表二进制要钉版本。
- `outdated` 对照 ACP 注册表检查 codex、pi、claude 的 npx 包和 agy 二进制，并给出替换值。更新后跑 `check`，agy 还要重新 `install agy`；其他家随本机 CLI 升级，注册表版本不一定准确。

离线回归测试（在仓库根运行）：`python3 -m unittest discover -s plugins/agent-relay/skills/agent-relay/scripts -p 'test_relay.py'`。
