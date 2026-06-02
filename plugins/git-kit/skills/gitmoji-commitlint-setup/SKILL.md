---
name: gitmoji-commitlint-setup
description: >-
  把一套 gitmoji + commitlint 提交规范落地到一个项目里：生成 commitlint.config.js（emoji 与
  type 强制 1:1 配对、scope 小写、header ≤72 字符）、设置 husky 的 commit-msg 钩子、装好
  @commitlint/cli / @commitlint/config-conventional / husky 依赖，让该项目从此强制这套提交风格。
  当用户说「给这个项目配上 gitmoji 提交规范」「装一下 commitlint / commit 校验」「配置 commit
  message 规范」「上 husky commit-msg 钩子」「想要那种带 emoji 的规范提交」，或在一个还没有提交
  规范的仓库里要求统一 commit 风格时，都应使用本 skill —— 即使用户没有逐字说出 commitlint 或
  gitmoji。本 skill 负责「配置落地」，不负责日常生成 commit message。
---

# gitmoji-commitlint-setup

把一套经过实战验证的 **gitmoji + commitlint** 提交规范一次性配置到目标项目里。配好之后，该项目
每次 `git commit` 都会经 husky 的 `commit-msg` 钩子调用 commitlint 校验，不合规的 message 会被直接拒绝。

## 这套规范长什么样

提交 header 必须匹配：

```
<emoji> <type>(<scope>): <subject>
```

强制规则（由 `assets/commitlint.config.js` 实现）：

- **emoji 必须存在，且与 type 1:1 配对**。`🐛 bug(...)`、`✨ sparkles(...)`、`🚚 truck(...)`。配错 emoji 会被拒。
- `type` 必须是配置中 gitmoji 名称表里的一个（`bug`、`sparkles`、`wrench`、`recycle`、`test-tube`、`zap` 等，完整表见 `assets/commitlint.config.js`）。
- `scope` 必须**小写**。
- `subject` 非空；header **≤ 72 字符**。
- `subject-case` 不限制；body / footer 前应留空行（warning 级）。

常用 emoji ↔ type 速查（全表在 config 里）：

| emoji | type | 用途 |
|------|------|------|
| ✨ | sparkles | 新功能 |
| 🐛 | bug | 修 bug |
| ♻ | recycle | 重构 |
| ⚡ | zap | 性能 |
| 📝 | memo | 文档 |
| 🔧 | wrench | 配置 / 工具 |
| ✅ | white-check-mark | 测试通过 / 加测试 |
| 🧪 | test-tube | 加失败的测试 |
| 💄 | lipstick | UI / 样式 |
| 🚀 | rocket | 部署 / 发布 |
| 🚚 | truck | 移动 / 重命名文件 |
| 🔥 | fire | 删除代码 / 文件 |
| 🎉 | tada | 初始提交 |
| 🔖 | bookmark | 版本 tag |
| 👷 | construction-worker | CI |

示例（来自原始项目）：`🐛 bug(ui): close popover when app loses focus`

## 落地流程

按顺序执行。每一步先观察现状再动手——目标项目可能已经部分配置过，不要盲目覆盖用户已有的东西。

### 1. 探查目标项目

```bash
ls package.json pnpm-lock.yaml yarn.lock package-lock.json commitlint.config.js .husky 2>/dev/null
```

判断三件事：

- **包管理器**：有 `pnpm-lock.yaml` → pnpm；`yarn.lock` → yarn；`package-lock.json` → npm；都没有则默认 **pnpm**（这套规范源自 pnpm 项目），但向用户说明你的选择，允许改。后续命令和钩子内容都要随包管理器走（见下表）。
- **是否已是 Node 项目**：没有 `package.json` 也没关系——commitlint/husky 走 Node 工具链，纯 Swift / Go / Rust / Python 项目同样可以用，只需初始化一个最小 `package.json`（第 2 步处理）。这正是原始项目（一个 Swift app）的做法。
- **是否已配置过**：若已存在 `commitlint.config.js` 或 `.husky/commit-msg`，**先读它们**，把差异讲给用户，问清是覆盖、合并还是跳过，不要直接覆盖。

包管理器对应命令：

| | pnpm | npm | yarn |
|---|---|---|---|
| 装 devDep | `pnpm add -D <pkgs>` | `npm i -D <pkgs>` | `yarn add -D <pkgs>` |
| 钩子里执行 | `pnpm exec commitlint --edit "$1"` | `npx --no-install commitlint --edit "$1"` | `yarn commitlint --edit "$1"` |
| 跑校验 | `pnpm exec commitlint` | `npx commitlint` | `yarn commitlint` |

### 2. 确保有 package.json

若没有，初始化一个最小的（用对应包管理器的 init，或直接写）。关键是要有 `prepare` 脚本让 husky 在 `install` 时自动装钩子：

```json
{
  "name": "<项目名>",
  "private": true,
  "type": "commonjs",
  "scripts": { "prepare": "husky" }
}
```

若已有 `package.json`，只需补上 `scripts.prepare = "husky"`（保留其余内容）。

### 3. 安装依赖

```bash
# pnpm 示例；其它包管理器按上表替换
pnpm add -D @commitlint/cli @commitlint/config-conventional husky
```

`@commitlint/config-conventional` 虽然没在 config 里 `extends`，但保留它作为约定基线依赖、方便日后扩展；如果用户要求极简，可省略它。

### 4. 放置 commitlint.config.js

把本 skill 的 `assets/commitlint.config.js` **原样复制**到项目根目录。不要手敲那张 80 多条的 emoji-type 表——照抄模板才能保证和原始规范逐字一致。

```bash
cp <skill 目录>/assets/commitlint.config.js <项目根>/commitlint.config.js
```

### 5. 设置 husky 与 commit-msg 钩子

husky v9+ 的方式（不需要旧版的 `husky install` / shebang 样板）：

```bash
# 初始化 husky（创建 .husky/ 并写好 prepare）
pnpm exec husky init   # 或 npx husky init
```

`husky init` 会默认生成一个 `.husky/pre-commit`（内容是 `npm test` 之类）。本规范只需要 `commit-msg`，所以：

- 删掉或清空它默认生成的、会干扰的 `pre-commit`（原始项目里 `pre-commit` 是空的）。
- 创建 `.husky/commit-msg`，内容**只有一行**（按包管理器选）：

```sh
pnpm exec commitlint --edit "$1"
```

钩子文件需要可执行：`chmod +x .husky/commit-msg`（husky v9 通常会自动处理，确认一下）。

### 6. 验证（必做，不要跳过）

配置的价值在于「拦得住坏的、放得过好的」。落地后实测两条 message 证明它真的生效：

```bash
# 应当【通过】
echo "🐛 bug(core): fix crash on launch" | pnpm exec commitlint

# 应当【被拒】——大写 scope + emoji 与 type 不配
echo "🐛 sparkles(Core): bad message" | pnpm exec commitlint
```

第一条应无输出（exit 0），第二条应报错（非 0，且能看到 emoji-type 不匹配 / scope 大写的提示）。把结果如实告诉用户。若条件允许，再跑一次真实的 `git commit` 触发钩子端到端确认。

## 配置完成后（交接给用户）

- 告诉用户：以后这个项目的提交 header 必须是 `<emoji> <type>(<scope>): <subject>`，否则会被钩子拒绝；完整 emoji-type 表在 `commitlint.config.js` 里。
- 提醒别用 `git commit --no-verify` 绕过钩子——绕过会让规范形同虚设。钩子报错就改 message。
- **AI 署名**：本 skill 只负责落地规范，是否在 commit 里加入 `Co-Authored-By` / "Generated with Claude Code" 与本配置无关，按各项目自己的约定（如项目 memory 记录）处理，本 skill 不写死。

## 边界情况

- **monorepo / 子包**：commitlint.config.js 放在执行 `git commit` 的仓库根（`.git` 所在处），不是子包目录。
- **已有不同的 commit 规范**（如纯 conventional commits 无 emoji）：不要静默覆盖。说明这套规范会**强制 emoji**，与无 emoji 的提交不兼容，确认用户确实想切换。
- **CI 也想校验**：可在 CI 里加 `commitlint --from <base> --to <head>` 校验 PR 范围的提交；本 skill 默认只配本地钩子。
- **husky 装钩子没生效**：通常是没跑过 `prepare`（即 `pnpm install` / `husky init`），或 `.git` 不在当前目录。先确认仓库已 `git init`。
