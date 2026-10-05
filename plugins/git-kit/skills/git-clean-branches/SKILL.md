---
name: git-clean-branches
description: 安全清理已合并（含 squash / rebase 合并）或长期未动的 Git 分支，默认只预览，支持保护分支与远程清理。当用户说「清理一下分支」「删掉已经合并的分支」「PR 合了本地分支还在」「分支太多了」「清理 fork 上的旧分支」时使用。
allowed-tools: Read(**), Bash(git fetch:*), Bash(git config --get-all:*), Bash(git remote -v:*), Bash(git branch -a:*), Bash(git branch -r:*), Bash(git branch --merged:*), Bash(git branch --no-merged:*), Bash(git for-each-ref:*), Bash(git log:*), Bash(git cherry:*), Bash(git commit-tree:*), Bash(git merge-base:*), Bash(git rev-parse:*), Bash(git worktree list:*), Bash(gh pr list:*)
argument-hint: '[--base <branch>] [--stale <days>] [--remote] [--force] [--dry-run] [--yes]'
# examples:
#   - /git-clean-branches --dry-run
#   - /git-clean-branches --base release/v2.1 --stale 90
#   - /git-clean-branches --remote --yes
---

# Clean Branches

识别并清理**已合并**或**长期未更新**的分支。默认只读预览（`--dry-run`），删除需要用户明确确认或 `--yes`。

## Options

- `--base <branch>`：合并判定的基准分支，默认自动识别 `main` / `master`。维护长期 release 分支时用它清理已合并到该 release 的 feature / hotfix。
- `--stale <days>`：同时清理最后一次提交在 N 天前的分支（默认不启用）。
- `--remote`：也清理远程分支（`git push origin --delete`）。
- `--dry-run`：默认行为，只列不删。
- `--yes`：跳过逐一确认，适合脚本。
- `--force`：本地用 `git branch -D` 删未合并分支。除非确定该分支是无用功，否则不要用。

## 流程

1. `git fetch --all --prune` 刷新状态；读取保护分支列表（见下）；确定基准分支。
   fork 仓库（同时有 `upstream` 与 `origin`）的基准取 `upstream/<默认分支>`，否则 fork 自己的 main 落后时会漏判。
2. 找已合并分支，三种来源合并去重：
   - `git branch --merged <base>`（远程用 `-r`）：普通 merge / fast-forward。
   - squash / rebase 合并：提交哈希变了，`--merged` 认不出；逐提交的 `git cherry <base> <branch>` 也认不出多提交 squash。
     先把分支压成一个临时提交再比对，输出以 `-` 开头即已合并（`commit-tree` 只写一个悬空对象，不动任何 ref）：
     ```bash
     git cherry <base> "$(git commit-tree "$(git rev-parse <branch>^{tree})" -p "$(git merge-base <base> <branch>)" -m _)"
     ```
     合并后基准上又改过同一处时这招会判 `+`；有 `gh` 就再用 `gh pr list --state merged --head <branch>` 查是否有已合并 PR。
   - `--stale` 时用 `git for-each-ref --format='%(committerdate:unix) %(refname:short)'` 按时间过滤，
     避免 `date -d` 等跨平台不一致的命令。
   排除基准分支、当前分支、保护分支，以及**被任何 worktree 检出的分支**（`git worktree list --porcelain` 的 `branch` 行），
   后者 `git branch -d` 会拒绝，要先 `git worktree remove`。
3. 分「已合并」「squash 合并（依据）」「过期」三组列出，附最后提交时间与是否有未推送提交。无 `--yes` 时到此结束，等用户确认。
4. 逐一删除：本地已合并用 `git branch -d`；squash 合并的分支 `-d` 会拒绝，确认后用 `-D`；`--force` 才删未合并分支。
   远程只删**自己有推送权**的远程（通常是 `origin`）：`git push origin --delete <branch>`，绝不删 `upstream` 上的分支。
5. 报告删了哪些及每个分支删除前的提交哈希，误删可用 `git branch <name> <hash>` 恢复。

## 保护分支（一次配置，永久生效）

命令从 Git 配置读取不应清理的分支，支持通配符：

```bash
git config --add branch.cleanup.protected develop
git config --add branch.cleanup.protected 'release/*'
git config --get-all branch.cleanup.protected
```

清理共享的远程分支前先在团队里知会一声。
