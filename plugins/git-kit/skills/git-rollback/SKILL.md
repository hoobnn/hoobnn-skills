---
name: git-rollback
description: 把 Git 分支回滚到历史版本：先备份、预览，再按需 reset（改写历史）或 revert（保留历史）。当用户说「回滚到某个版本 / tag」「撤销最近几次提交」「代码改坏了退回去」「把这个分支恢复到昨天的状态」「reset 错了找回来」时使用。只撤销工作区未提交改动用 git restore，不用本 skill。
allowed-tools: Read(**), Bash(git fetch:*), Bash(git status:*), Bash(git branch -a:*), Bash(git tag --merged:*), Bash(git log:*), Bash(git reflog:*), Bash(git rev-list:*), Bash(git diff --stat:*)
argument-hint: '[--branch <branch>] [--target <rev>] [--mode reset|revert] [--depth <n>] [--dry-run] [--yes]'
# examples:
#   - /git-rollback                # 全交互模式，dry-run
#   - /git-rollback --branch dev   # 直接选 dev，其他交互
#   - /git-rollback --branch dev --target v1.2.0 --mode reset --yes
---

# Git Rollback

把指定分支回滚到旧版本。默认只读预览（`--dry-run`），真正执行需 `--yes` 或交互确认。

## Options

| 选项 | 说明 |
|---|---|
| `--branch <branch>` | 要回滚的分支；缺省交互选择 |
| `--target <rev>` | 目标版本（commit / tag / reflog 引用）；缺省从最近 `--depth` 条记录里选 |
| `--mode reset\|revert` | `reset` 改写历史；`revert` 生成反向提交保留历史。缺省询问 |
| `--depth <n>` | 交互列出最近 n 个版本，默认 20 |
| `--dry-run` | 默认开启，只打印将执行的命令 |
| `--yes` | 跳过确认直接执行 |

## 流程

1. `git fetch --all --prune`；`git status --porcelain` 检查工作区。有未提交改动时停下，让用户选
   stash / 提交 / 放弃，**不要直接 reset --hard**——它会无提示抹掉这些改动，reflog 也救不回来。
2. 选分支（`git branch -a`）。只有远程分支时先 `git switch <branch>` 建本地跟踪分支。
3. 选目标：`git log --oneline -n <depth>` + `git tag --merged` + `git reflog -n <depth>`。
   用户描述「昨天的状态」「reset 之前」时优先查 reflog（`git reflog --date=iso`），它记录的是分支实际指向过的位置。
4. 预览：`git log --oneline <target>..<branch>` 列出将被撤销的提交，`git diff --stat <target> <branch>` 给改动规模。
   默认 dry-run 到此结束，打印将执行的命令。
5. 选模式。分支已推送且别人可能拉过时推荐 `revert`；纯本地或个人分支可用 `reset`。最终确认（除非 `--yes`）。
6. 执行前**自动**建备份：`git branch backup/<branch>-<YYYYMMDD-HHMMSS> <branch>`，并在结果里报告备份名。
7. 执行：
   - `reset`：`git switch <branch> && git reset --hard <target>`
   - `revert`：`git switch <branch> && git revert --no-edit <target>..HEAD`。
     范围里有 merge 提交时（`git rev-list --merges <target>..HEAD` 非空）直接 revert 会失败，
     改用一次性反向提交：`git read-tree -u --reset <target> && git commit -m "revert: 回滚到 <target>"`
     （工作树整体恢复成 `<target>`，历史保留，一个提交即可撤销）。
     冲突时停下报告，不要自动解决。
8. 提示推送方式：reset 后用 `git push --force-with-lease`，revert 后普通 `git push`。

## 安全护栏

- 撤销回滚：`git reset --hard backup/<...>`（或 reflog 里的 `<branch>@{1}`）。确认无误后可删备份分支。
- `main` / `master` / `production` 等受保护分支走 `reset` 时要求额外确认，因为会改写共享历史并影响协作者。
- 不提供 `--force` 推送；需要强推由用户手动输入 `git push --force-with-lease`。
- 带 LFS / 子模块的仓库回滚前确认两者状态一致；启用 CI 强制校验的仓库回滚可能自动触发流水线，先确认不会误部署旧版本。
