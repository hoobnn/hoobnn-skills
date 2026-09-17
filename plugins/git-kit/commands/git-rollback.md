---
description: 交互式回滚 Git 分支到历史版本；列分支、列版本、二次确认后执行 reset / revert
allowed-tools: Read(**), Exec(git fetch, git branch, git tag, git log, git reflog, git checkout, git reset, git revert, git switch), Write()
argument-hint: [--branch <branch>] [--target <rev>] [--mode reset|revert] [--depth <n>] [--dry-run] [--yes]
# examples:
#   - /git-rollback                # 全交互模式，dry-run
#   - /git-rollback --branch dev   # 直接选 dev，其他交互
#   - /git-rollback --branch dev --target v1.2.0 --mode reset --yes
---

# Claude Command: Git Rollback

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

1. `git fetch --all --prune`。
2. 列分支 `git branch -a` → 选分支。
3. 列版本 `git log --oneline -n <depth>` + `git tag --merged` + `git reflog -n <depth>` → 选目标。
4. 选模式 → 最终确认（除非 `--yes`）。
5. 执行：
   - `reset`：`git switch <branch> && git reset --hard <target>`
   - `revert`：`git switch <branch> && git revert --no-edit <target>..HEAD`
6. 提示推送方式：reset 后用 `git push --force-with-lease`，revert 后普通 `git push`。

## 安全护栏

- 执行前当前 HEAD 已在 reflog 里，可用 `git switch -c backup/<timestamp>` 保留一份分支再操作。
- `main` / `master` / `production` 等受保护分支走 `reset` 时要求额外确认，因为会改写共享历史并影响协作者。
- 不提供 `--force` 推送；需要强推由用户手动输入 `git push --force-with-lease`。
- 带 LFS / 子模块的仓库回滚前确认两者状态一致；启用 CI 强制校验的仓库回滚可能自动触发流水线，先确认不会误部署旧版本。
