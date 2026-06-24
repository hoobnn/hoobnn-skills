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

管理 Git worktree，支持智能默认和内容迁移，使用结构化的 `../.worktrees/` 路径。

直接执行命令并提供简洁结果。

---

## Usage

```bash
# 基本操作
/git-worktree add <path>                           # 从 main/master 创建名为 <path> 的新分支
/git-worktree add <path> -b <branch>               # 创建指定名称的新分支
/git-worktree list                                 # 显示所有 worktree 状态
/git-worktree remove <path>                        # 删除指定的 worktree
/git-worktree prune                                # 清理无效 worktree 记录

# 内容迁移
/git-worktree migrate <target> --from <source>     # 迁移未提交内容
/git-worktree migrate <target> --stash             # 迁移 stash 内容
```

### Options

| 选项               | 说明                                         |
| ------------------ | -------------------------------------------- |
| `add [<path>]`     | 在 `../.worktrees/<path>` 添加新的 worktree   |
| `migrate <target>` | 迁移内容到指定 worktree                      |
| `list`             | 列出所有 worktree 及其状态                   |
| `remove <path>`    | 删除指定路径的 worktree                      |
| `prune`            | 清理无效的 worktree 引用                     |
| `-b <branch>`      | 创建新分支并检出到 worktree                  |
| `--from <source>`  | 指定迁移源路径（migrate 专用）               |
| `--stash`          | 迁移当前 stash 内容（migrate 专用）          |
| `--track`          | 设置新分支跟踪对应的远程分支                 |
| `--guess-remote`   | 自动猜测远程分支进行跟踪                     |
| `--detach`         | 创建分离 HEAD 的 worktree（与 `-b`/默认建分支互斥）|
| `--no-checkout`    | 创建后不检出工作区（默认会检出）             |
| `--lock`           | 创建后锁定 worktree                          |

---

## What This Command Does

1. **环境检查**
   - 通过 `git rev-parse --is-inside-work-tree` 验证 Git 仓库
   - 检测是否在主仓库或现有 worktree 中，进行智能路径计算

2. **智能路径管理**
   - 使用 worktree 检测自动从主仓库路径推导项目平级目录
   - 在结构化的 `../.worktrees/<path>` 目录创建 worktree
   - 正确处理主仓库和 worktree 执行上下文

```bash
# worktree 检测的核心路径计算逻辑
get_main_repo_path() {
  local git_common_dir=$(git rev-parse --git-common-dir 2>/dev/null)
  local current_toplevel=$(git rev-parse --show-toplevel 2>/dev/null)

  # 检测是否在 worktree 中
  if [[ "$git_common_dir" != "$current_toplevel/.git" ]]; then
    # 在 worktree 中，从 git-common-dir 推导主仓库路径
    dirname "$git_common_dir"
  else
    # 在主仓库中
    echo "$current_toplevel"
  fi
}

MAIN_REPO_PATH=$(get_main_repo_path)
WORKTREE_BASE="$MAIN_REPO_PATH/../.worktrees"

# 始终使用绝对路径防止嵌套问题
ABSOLUTE_WORKTREE_PATH="$WORKTREE_BASE/<path>"
```

**关键修复**: 在现有 worktree 内创建新 worktree 时，始终使用绝对路径以防止出现类似 `../.worktrees/.worktrees/path` 的路径嵌套问题。

3. **Worktree 操作**
   - **add**: 使用智能分支/路径默认创建新 worktree；创建成功后**主动引导切换会话工作目录**（见下文「切换会话工作目录」）
   - **list**: 显示所有 worktree 的分支和状态
   - **remove**: 安全删除 worktree 并清理引用
   - **prune**: 清理孤立的 worktree 记录

4. **智能默认**
   - **分支创建**: 未指定 `-b` 时，使用路径名创建新分支
   - **基础分支**: 新分支从 main/master 分支创建
   - **路径解析**: 未指定路径时使用分支名作为路径

5. **内容迁移**
   - 在 worktree 之间迁移未提交改动
   - 将 stash 内容应用到目标 worktree
   - 安全检查防止冲突

6. **安全特性**
   - **路径冲突防护**: 创建前检查目录是否已存在
   - **分支检出验证**: 确保分支未被其他地方使用
   - **绝对路径强制**: 防止在 worktree 内创建嵌套的 `.worktrees` 目录
   - **删除时自动清理**: 同时清理目录和 git 引用
   - **清晰的状态报告**: 显示 worktree 位置和分支状态

7. **环境文件处理**
   - **自动检测**: 扫描 `.gitignore` 文件中的环境变量文件模式
   - **智能复制**: 复制 `.gitignore` 中列出的 `.env` 和 `.env.*` 文件
   - **排除逻辑**: 跳过 `.env.example` 等模板文件
   - **权限保护**: 保持原始文件权限和时间戳
   - **用户反馈**: 提供已复制环境文件的清晰状态信息

```bash
# 环境文件复制实现
copy_environment_files() {
    local main_repo="$MAIN_REPO_PATH"
    local target_worktree="$ABSOLUTE_WORKTREE_PATH"
    local gitignore_file="$main_repo/.gitignore"
    
    # 检查 .gitignore 是否存在
    if [[ ! -f "$gitignore_file" ]]; then
        return 0
    fi
    
    local copied_count=0
    
    # 检测 .env 文件
    if [[ -f "$main_repo/.env" ]] && grep -q "^\.env$" "$gitignore_file"; then
        cp "$main_repo/.env" "$target_worktree/.env"
        echo "✅ 已复制 .env"
        ((copied_count++))
    fi
    
    # 检测 .env.* 模式文件（排除 .env.example）
    for env_file in "$main_repo"/.env.*; do
        if [[ -f "$env_file" ]] && [[ "$(basename "$env_file")" != ".env.example" ]]; then
            local filename=$(basename "$env_file")
            if grep -q "^\.env\.\*$" "$gitignore_file"; then
                cp "$env_file" "$target_worktree/$filename"
                echo "✅ 已复制 $filename"
                ((copied_count++))
            fi
        fi
    done
    
    if [[ $copied_count -gt 0 ]]; then
        echo "📋 已从 .gitignore 复制 $copied_count 个环境文件"
    fi
}
```

---

## 切换会话工作目录（add 成功后的推荐步骤）

`add` 创建 worktree 之后，**应主动引导用户把当前会话的工作目录切换到新 worktree**，这样后续编辑、运行、提交都直接落在对应分支上，无需用户手动开新会话。

### 关键机制：用 EnterWorktree 的 `path`，而非 Bash 的 `cd`

> `EnterWorktree` / `ExitWorktree` 是 **harness 内置的会话级工具**（同 `Read`/`Edit` 那一类），不是斜杠命令、也不是 skill，由 Claude 在对话主流程里调用、用户无法手动执行。因此它们**不写进本命令的 `allowed-tools`**（那个字段管的是 command 执行期可用的工具）；切换会话目录这一步发生在 `add` 跑完之后、由 Claude 接着完成。

- **`cd` 无法持久切换会话目录**：每次 Bash 调用结束后，harness 会把 shell cwd 重置回原始工作目录（你会看到类似 `Shell cwd was reset to ...` 的提示）。所以 `cd` 只在单条命令内有效，切不动会话。
- **真正切换靠 `EnterWorktree(path: ...)`**：该工具的 `path` 参数支持「进入一个**已注册到当前仓库**的、已存在的 worktree」。git-kit 在 `../.worktrees/<path>`（项目平级）下是用 `git worktree add` 注册的，该路径已出现在 `git worktree list` 里，因此即便它不在 `.claude/worktrees/` 下，也能通过校验并成功接管，把会话目录切过去。

### 推荐执行流程（由 Claude 自动完成）

1. `add` 成功后，取得新 worktree 的**绝对路径**（即 `ABSOLUTE_WORKTREE_PATH`）。
2. 调用 `EnterWorktree`，传入该绝对路径：

   ```text
   EnterWorktree(path: "<MAIN_REPO_PATH>/../.worktrees/<path>")
   # 例：EnterWorktree(path: "/Users/you/Code/production/.worktrees/feature-ui")
   ```

3. 用 `pwd && git branch --show-current` 验证已落在新目录与对应分支上。

### 退出时不会误删

因为是用 `path`「进入已存在的 worktree」（而非用 `name` 新建），`ExitWorktree` 不会删除这个 worktree。需要返回原目录时用 `ExitWorktree(action: "keep")` 即可，worktree 原样保留在磁盘上，git-kit 仍可正常 `list` / `remove` 管理它。

> 注意：少数 harness 版本的 `EnterWorktree` 描述声称 `path` 目标必须在 `.claude/worktrees/` 下。实测中 `../.worktrees/` 因已注册进 `git worktree list` 可正常进入；若某版本确实拒绝，则退回到提示用户「在新会话中手动进入该目录」。

---

## Enhanced Features

### 内容迁移系统

```bash
# 迁移未提交改动
/git-worktree migrate feature-ui --from main
/git-worktree migrate hotfix --from ../other-worktree

# 迁移 stash 内容
/git-worktree migrate feature-ui --stash
```

**迁移流程**:

1. 验证源有未提交内容
2. 确保目标 worktree 干净
3. 显示即将迁移的改动
4. 使用 git 命令安全迁移
5. 确认结果并建议后续步骤

---

## Examples

```bash
# 基本用法
/git-worktree add feature-ui                       # 从 main/master 创建新分支 'feature-ui'
/git-worktree add feature-ui -b my-feature         # 创建新分支 'my-feature'，路径为 'feature-ui'

# 内容迁移场景
/git-worktree add feature-ui -b feature/new-ui     # 创建新功能 worktree
/git-worktree migrate feature-ui --from main       # 迁移未提交改动
/git-worktree migrate hotfix --stash               # 迁移 stash 内容

# 管理操作
/git-worktree list                                 # 查看所有 worktree
/git-worktree remove feature-ui                    # 删除不需要的 worktree
/git-worktree prune                                # 清理无效引用
```

**示例输出**:

```
✅ Worktree created at ../.worktrees/feature-ui
✅ 已复制 .env
✅ 已复制 .env.local
📋 已从 .gitignore 复制 2 个环境文件
```

---

## Directory Structure

```
parent-directory/
├── your-project/            # 主项目
│   ├── .git/
│   └── src/
└── .worktrees/              # worktree 管理（项目平级）
    ├── feature-ui/          # 功能分支
    ├── hotfix/              # 修复分支
    └── debug/               # 调试 worktree
```

---

## Notes

- **性能**: worktree 共享 `.git` 目录，节省磁盘空间
- **安全**: 路径冲突防护和分支检出验证
- **迁移**: 仅限未提交改动；已提交内容需使用 `git cherry-pick`
- **运行环境**: 依赖 bash（macOS、Linux 原生支持；Windows 需 Git Bash / WSL 等 bash 环境）
- **环境文件**: 自动复制 `.gitignore` 中列出的环境文件到新 worktree
- **文件排除**: 模板文件如 `.env.example` 仅保留在主仓库中

---
