---
name: git-worktree
description: 管理 Git worktree：统一建在 ~/worktrees/<host>/<owner>/<repo>/<分支>/ 下（根目录可用 git config worktree.root 改），创建、列出、删除，可把未提交改动或 stash 迁过去。当用户说「开个 worktree」「新开一个分支目录并行做」「把这些改动挪到另一个 worktree」「清理 worktree」时使用。
allowed-tools: Read(**), Bash(git worktree:*), Bash(git branch:*), Bash(git remote:*), Bash(git config:*), Bash(git checkout:*), Bash(git rev-parse:*), Bash(git stash:*), Bash(cp:*), Bash(which:*), Bash(command:*), Bash(basename:*), Bash(dirname:*), Bash(pwd)
argument-hint: '<add|list|remove|prune|migrate> [path] [-b <branch>] [--track] [--guess-remote] [--detach] [--no-checkout] [--lock] [--from <source-path>] [--stash]'
# examples:
#   - /git-worktree add feature-ui                     # 从 main/master 创建新分支 'feature-ui'
#   - /git-worktree add hotfix -b fix/login            # 创建新分支 'fix/login'，路径为 'hotfix'
#   - /git-worktree migrate feature-ui --from main     # 将主分支未提交内容迁移到 feature-ui
#   - /git-worktree migrate feature-ui --stash         # 将当前 stash 迁移到 feature-ui
---

# Git Worktree

所有仓库的 worktree 集中放在一个根目录下，按远程地址分层（同 ghq / gwq 的布局），不放在仓库内，也不放在仓库旁边。
直接执行并给简洁结果。

```
~/worktrees/                          # 根目录：git config worktree.root，未设置时为 ~/worktrees
├── github.com/hoobnn/hoobnn-skills/  # 来自 origin 地址，不同 owner 的同名仓库不会撞
│   ├── feature-ui/
│   └── fix-login/                    # 分支 fix/login
└── local/scratch/                    # 没有 origin 的仓库：local/<主仓库目录名>
```

## Options

| 选项 | 说明 |
|---|---|
| `add <path>` | 在「路径计算」得出的目录创建 worktree。未指定 `-b` 时用 `<path>` 作新分支名，新分支从 main / master 创建 |
| `list` / `remove <path>` / `prune` | 列出 / 删除（同时清理 git 引用）/ 清理失效记录 |
| `migrate <target>` | 把未提交改动（`--from <source>`）或 stash（`--stash`）迁到目标 worktree |
| `-b <branch>` | 指定新分支名 |
| `--track` / `--guess-remote` | 跟踪远程分支 |
| `--detach` | 分离 HEAD（与 `-b` / 默认建分支互斥） |
| `--no-checkout` / `--lock` | 透传给 `git worktree add` |

## 路径计算

目标路径只用下面这段计算，`NAME` 是 `<path>` 参数。它在主仓库或任一 worktree 里执行结果都一样（主仓库取自
`--git-common-dir`），`/` 会换成 `-` 作目录名，分支名保持原样：

```bash
main=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
root=$(git config --get worktree.root || echo "$HOME/worktrees")
url=$(git remote get-url origin 2>/dev/null)
if [ -n "$url" ]; then
  key=$(printf '%s' "$url" | sed -E 's#^[a-z+]+://##; s#^[^@/]+@##; s#:([0-9]+/)?#/#; s#\.git/?$##; s#/$##')
else
  key="local/$(basename "$main")"
fi
echo "$root/$key/$(printf '%s' "$NAME" | tr / -)"
```

- 根目录要改就 `git config --global worktree.root <绝对路径>`，不要改这段里的默认值；单个仓库可以不带 `--global` 单独设。
- `git worktree add` 会自动创建上级目录。
- 创建前检查目录不存在、分支未被其他 worktree 检出。

## 环境文件

创建后从主仓库复制 `.gitignore` 里列出的 `.env` 与 `.env.*`（跳过 `.env.example` 等模板），保留权限与时间戳，
并报告复制了哪些。这些文件被 git 忽略，新 worktree 里不会自动有。

## add 成功后：切换会话工作目录（仅 Claude Code）

`add` 完成后主动把当前会话切到新 worktree，后续编辑、运行、提交都落在对应分支，不需要用户开新会话。
这一节依赖 Claude Code 的会话级工具；Codex 等其他环境没有对应机制，直接提示用户在新会话里进入该目录。

- Bash 里 `cd` 切不动：每次调用结束后 harness 会把 cwd 重置回原目录。
- 用 harness 内置工具 `EnterWorktree(path: "<绝对路径>")`。它的 `path` 参数支持进入一个**已注册到当前仓库**
  的现有 worktree；这里的目录是用 `git worktree add` 注册的，出现在 `git worktree list` 里，
  所以能通过校验。`EnterWorktree` / `ExitWorktree` 是会话级工具，不是斜杠命令，所以不写进本 skill 的 `allowed-tools`。
- 切换后 `pwd && git branch --show-current` 验证。
- 因为是用 `path` 进入已存在的 worktree（不是用 `name` 新建），`ExitWorktree(action: "keep")` 返回原目录时不会删掉它。
- 若 `EnterWorktree` 拒绝该路径，退回到提示用户在新会话里手动进入该目录。

## migrate

1. 确认源有未提交内容（或有 stash），目标 worktree 干净。
2. 展示即将迁移的改动，用 `git stash` / `git stash apply` 或 `git diff | git apply` 迁过去。
3. 已提交内容不在此范围，用 `git cherry-pick`。

## Notes

- worktree 共享 `.git`，不额外占仓库空间。
- 旧版本把 worktree 建在主仓库旁边的 `<repo>.worktrees/`、`.worktree-<repo>/` 或 `.worktrees/` 下。`list` 时发现注册路径
  不在根目录下，提示可用 `git worktree move <旧路径> <新路径>` 迁过去（移动前确认没有会话正在用它），迁完删掉空的旧目录。
- 删除主仓库前先 `git worktree remove` 掉它的 worktree，否则会留下孤儿目录。
- 依赖 bash；Windows 需 Git Bash / WSL。
