---
description: 安全查找并清理已合并或过期的 Git 分支，支持 dry-run 模式与自定义基准/保护分支
allowed-tools: Read(**), Exec(git fetch, git config, git branch, git remote, git push, git for-each-ref, git log), Write()
argument-hint: [--base <branch>] [--stale <days>] [--remote] [--force] [--dry-run] [--yes]
# examples:
#   - /git-cleanBranches --dry-run
#   - /git-cleanBranches --base release/v2.1 --stale 90
#   - /git-cleanBranches --remote --yes
---

# Claude Command: Clean Branches

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
2. 用 `git branch --merged <base>`（远程用 `-r`）找已合并分支；`--stale` 时用 `git for-each-ref` 取各分支最后提交时间过滤。
   避免 `date -d` 等跨平台不一致的命令。排除基准分支、当前分支与保护分支。
3. 分「已合并」「过期」两组列出。无 `--yes` 时到此结束，等用户确认后再执行。
4. 逐一删除：本地 `git branch -d`（`--force` 则 `-D`），远程 `git push origin --delete <branch>`。

## 保护分支（一次配置，永久生效）

命令从 Git 配置读取不应清理的分支，支持通配符：

```bash
git config --add branch.cleanup.protected develop
git config --add branch.cleanup.protected 'release/*'
git config --get-all branch.cleanup.protected
```

清理共享的远程分支前先在团队里知会一声。
