---
description: 管理 Git worktree，在项目平级的 ../.worktrees/ 目录下创建，支持智能默认和内容迁移
allowed-tools: Read(**), Exec(git worktree add, git worktree list, git worktree remove, git worktree prune, git branch, git checkout, git rev-parse, git stash, cp, which, command, basename, dirname, pwd)
argument-hint: <add|list|remove|prune|migrate> [path] [-b <branch>] [--track] [--guess-remote] [--detach] [--no-checkout] [--lock] [--from <source-path>] [--stash]
# examples:
#   - /git-worktree add feature-ui                     # 从 main/master 创建新分支 'feature-ui'
#   - /git-worktree add hotfix -b fix/login            # 创建新分支 'fix/login'，路径为 'hotfix'
#   - /git-worktree migrate feature-ui --from main     # 将主分支未提交内容迁移到 feature-ui
#   - /git-worktree migrate feature-ui --stash         # 将当前 stash 迁移到 feature-ui
---

# Claude Command: Git Worktree

在项目平级的 `../.worktrees/<path>` 下管理 worktree。直接执行并给简洁结果。

```
parent-directory/
├── your-project/        # 主项目
└── .worktrees/          # 与项目平级
    ├── feature-ui/
    └── hotfix/
```

## Options

| 选项 | 说明 |
|---|---|
| `add <path>` | 在 `../.worktrees/<path>` 创建 worktree。未指定 `-b` 时用 `<path>` 作新分支名，新分支从 main / master 创建 |
| `list` / `remove <path>` / `prune` | 列出 / 删除（同时清理 git 引用）/ 清理失效记录 |
| `migrate <target>` | 把未提交改动（`--from <source>`）或 stash（`--stash`）迁到目标 worktree |
| `-b <branch>` | 指定新分支名 |
| `--track` / `--guess-remote` | 跟踪远程分支 |
| `--detach` | 分离 HEAD（与 `-b` / 默认建分支互斥） |
| `--no-checkout` / `--lock` | 透传给 `git worktree add` |

## 路径计算

`add` 可能在主仓库里执行，也可能在某个已有 worktree 里执行。先用 `git rev-parse --git-common-dir`
与 `--show-toplevel` 比较：两者不等于 `<toplevel>/.git` 说明当前在 worktree 里，主仓库路径取
`dirname <git-common-dir>`。目标路径始终用**绝对路径** `<main-repo>/../.worktrees/<path>`，
否则在 worktree 内创建会得到 `../.worktrees/.worktrees/path` 这种嵌套。

创建前检查目录不存在、分支未被其他 worktree 检出。

## 环境文件

创建后从主仓库复制 `.gitignore` 里列出的 `.env` 与 `.env.*`（跳过 `.env.example` 等模板），保留权限与时间戳，
并报告复制了哪些。这些文件被 git 忽略，新 worktree 里不会自动有。

## add 成功后：切换会话工作目录（仅 Claude Code）

`add` 完成后主动把当前会话切到新 worktree，后续编辑、运行、提交都落在对应分支，不需要用户开新会话。
这一节依赖 Claude Code 的会话级工具；Codex 等其他环境没有对应机制，直接提示用户在新会话里进入该目录。

- Bash 里 `cd` 切不动：每次调用结束后 harness 会把 cwd 重置回原目录。
- 用 harness 内置工具 `EnterWorktree(path: "<绝对路径>")`。它的 `path` 参数支持进入一个**已注册到当前仓库**
  的现有 worktree；`../.worktrees/<path>` 是用 `git worktree add` 注册的，出现在 `git worktree list` 里，
  所以能通过校验。`EnterWorktree` / `ExitWorktree` 是会话级工具，不是斜杠命令，所以不写进本命令的 `allowed-tools`。
- 切换后 `pwd && git branch --show-current` 验证。
- 因为是用 `path` 进入已存在的 worktree（不是用 `name` 新建），`ExitWorktree(action: "keep")` 返回原目录时不会删掉它。
- 少数 harness 版本声称 `path` 必须在 `.claude/worktrees/` 下；若确实被拒，退回到提示用户在新会话里手动进入该目录。

## migrate

1. 确认源有未提交内容（或有 stash），目标 worktree 干净。
2. 展示即将迁移的改动，用 `git stash` / `git stash apply` 或 `git diff | git apply` 迁过去。
3. 已提交内容不在此范围，用 `git cherry-pick`。

## Notes

- worktree 共享 `.git`，不额外占仓库空间。
- 依赖 bash；Windows 需 Git Bash / WSL。
