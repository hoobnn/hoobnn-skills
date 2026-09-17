---
description: 仅用 Git 分析改动并自动生成 Conventional Commits 信息（风格跟随项目 commitlint.config.js，无配置时默认带 emoji）；必要时建议拆分提交，默认运行本地 Git 钩子（可 --no-verify 跳过）
allowed-tools: Read(**), Exec(git status, git diff, git add, git restore --staged, git commit, git rev-parse, git config, git log), Write(.git/COMMIT_EDITMSG)
argument-hint: [--no-verify] [--all] [--amend] [--signoff] [--no-emoji] [--scope <scope>] [--type <type>]
# examples:
#   - /git-commit                           # 分析当前改动，生成提交信息（默认带 emoji）
#   - /git-commit --all                     # 暂存所有改动并提交
#   - /git-commit --no-emoji                # 纯 Conventional（不带 emoji 前缀）
#   - /git-commit --scope ui --type feat    # 指定作用域和类型
#   - /git-commit --amend --signoff         # 修补上次提交并签名
---

# Claude Command: Commit (Git-only)

只用 Git 读取改动、判断是否拆分、生成 Conventional Commits 信息并提交。不调用包管理器或构建命令，
不编辑工作区文件，只读写暂存区与 `.git/COMMIT_EDITMSG`。

## Options

- `--no-verify`：跳过本地钩子（默认运行）。
- `--all`：暂存区为空时 `git add -A`。
- `--amend`：修补上一次提交。
- `--signoff`：附加 `Signed-off-by`（DCO 流程）。
- `--no-emoji`：强制纯 Conventional 头部（未传时风格跟随项目配置，见下）。
- `--scope <scope>` / `--type <type>`：覆盖自动推断。scope 大写会自动转小写。

## 流程

1. **校验状态**：`git rev-parse --is-inside-work-tree`；处于 rebase / merge 冲突或 detached HEAD 时先提示处理再继续。
2. **读改动**：`git status --porcelain` + `git diff`（staged 与 unstaged）。暂存区为空且无 `--all` 时，
   提示用户选择：只分析未暂存改动并给建议，或取消后手动分组暂存。
3. **拆分建议**：按关注点 / 文件模式 / 改动类型聚类。多组独立变更、混合 type、或 diff 过大
   （约 > 300 行或跨多个顶级目录）时建议拆分，并给出每组的 pathspec。每个提交应能独立回退。
4. **生成信息**（见下节），写入 `.git/COMMIT_EDITMSG`。
5. **提交**：`git commit [--amend] [--no-verify] [-s] -F .git/COMMIT_EDITMSG`；接受拆分时按组
   `git add <paths> && git commit ...` 逐一完成。误暂存用 `git restore --staged <paths>` 撤回。

## 风格跟随项目配置

先读仓库根的 `commitlint.config.js`（git-kit 的 gitmoji-commitlint-setup 落地的就是它）：

- 配置里有 `emoji-type-match` 规则 → 带 emoji，emoji↔type 表以配置里的 `TYPE_EMOJI` 为准。
- 有配置但没有 emoji 规则（plain 版）→ 不带 emoji，带了会被钩子拒。
- 没有配置 → 默认带 emoji（下表），`--no-emoji` 可关。

只有钩子真正校验的东西才是硬约束；配置里 `type-enum` / `header-max-length` 等取值与下文不同时以配置为准。

## 提交信息格式

header：`<emoji> <type>(<scope>)?: <subject>`，≤ 72 字符，祈使语气。

- `scope` 小写。这不是风格偏好，git-kit 的 commit-msg 钩子以 error 级强制校验，大写会被拒。
- **语言**跟随仓库历史：看 `git log -n 50 --pretty=%s` 判断中 / 英文；判断不了就按仓库主要语言，再退到英文。
- **body**：subject 后空一行，`-` 列表，每项动词开头的祈使句（add… / fix… / update…），3 项以内，说明动机、要点或影响范围。
  不用冒号分隔格式（如 `Feature: description`）。
- **footer**：body 后空一行。破坏性变更写 `BREAKING CHANGE: <description>` 或在 type 后加 `!`（`feat!:`）；
  其余用 git trailer（`Closes #123`、`Refs: #456`）。
- **破坏性变更不是独立 type**：`✨ feat(api)!: …`，emoji 仍按 type 走。

### type ↔ emoji（严格 1:1，与 git-kit `commitlint.config.js` 逐项对应）

| emoji | type | 用途 |
|------|------|------|
| ✨ | `feat` | 新增功能 |
| 🐛 | `fix` | 缺陷修复（含紧急修复、安全修复、修 CI，一律 🐛）|
| 📝 | `docs` | 文档与注释 |
| 🎨 | `style` | 风格 / 格式（不改语义）|
| ♻️ | `refactor` | 重构（不新增功能、不修缺陷）|
| ⚡️ | `perf` | 性能优化 |
| ✅ | `test` | 测试、快照 |
| 📦️ | `build` | 构建系统 / 外部依赖 |
| 👷 | `ci` | CI/CD 配置与脚本 |
| 🔧 | `chore` | 杂务 / 工具 / 配置（依赖 pin、.gitignore 等）|
| ⏪️ | `revert` | 回滚提交 |

配错 emoji 会被钩子拒绝；`--no-emoji` 时省略 emoji 前缀，其余不变。

## 示例

```text
✨ feat(auth): add OAuth2 login flow

- implement Google and GitHub third-party login
- add user authorization callback handling

Closes #42
```

```text
✨ feat(api)!: redesign authentication API

- migrate from session-based to JWT authentication
- remove deprecated login methods

BREAKING CHANGE: all clients must update their integration
```

拆分示例：`✨ feat(types): add payment method type defs` / `📝 docs: update API docs for new types` / `✅ test: add unit tests for payment types`。
