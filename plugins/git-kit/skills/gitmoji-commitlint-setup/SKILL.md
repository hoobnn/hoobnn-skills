---
name: gitmoji-commitlint-setup
description: >-
  把一套 Conventional Commits + emoji 提交规范落地到一个项目里：生成 commitlint.config.js（标准
  Conventional type 与 emoji 强制 1:1 配对、scope 小写、header ≤72 字符）、设置 husky 的 commit-msg 钩子、装好
  @commitlint/cli / @commitlint/config-conventional / husky 依赖，让该项目从此强制这套提交风格。
  当用户说「给这个项目配上 gitmoji 提交规范」「装一下 commitlint / commit 校验」「配置 commit
  message 规范」「上 husky commit-msg 钩子」「想要那种带 emoji 的规范提交」「不要 emoji 的
  conventional commits」「配纯 conventional 提交规范」「husky / commitlint 装了钩子没生效、
  不拦截」的排查修复，「commitlint / husky 配置该放哪」（含 monorepo 放仓库根），或在一个还
  没有提交规范的仓库里要求统一 commit 风格时，都应使用本 skill —— 即使用户没有逐字说出
  commitlint 或 gitmoji，排查类问题也不例外。本 skill 支持
  带 emoji 与不带 emoji 两种风格、落地时二选一，负责「配置落地」，不负责日常生成 commit message。
---

# gitmoji-commitlint-setup

把 **commitlint + husky** 提交校验一次性配到目标项目。配好后每次 `git commit` 经 `commit-msg`
钩子校验，不合规的 message 直接被拒。

## 规范

两种风格二选一，落地后该项目固定：

- **带 emoji**（默认）：`<emoji> <type>(<scope>): <subject>`，emoji 与 type 强制 1:1 配对。
- **不带 emoji**：`<type>(<scope>): <subject>`，标准 Conventional Commits。

除 emoji 前缀与配对校验外，两套规则逐字一致：type 限标准 Conventional 类型
（feat / fix / docs / style / refactor / perf / test / build / ci / chore / revert）、scope 小写、
subject 非空、header ≤ 72 字符、body / footer 前留空行（warning 级）。
完整 type↔emoji 表以 `assets/commitlint.config.emoji.js` 为准，不要手敲。

示例：`🐛 fix(ui): close popover when app loses focus`

## 落地流程

每一步先看现状再动手，目标项目可能已部分配置过。

### 0. 选风格

问用户一次带不带 emoji；没表态就默认带 emoji。这个选择决定第 4 步复制哪个模板、第 6 步用哪组验证用例。

### 1. 探查

```bash
ls package.json pnpm-lock.yaml yarn.lock package-lock.json commitlint.config.js .husky 2>/dev/null
```

- **包管理器**：按 lockfile 判断；都没有默认 pnpm（这套规范源自 pnpm 项目），向用户说明可改。
  后续安装命令与钩子内容都随包管理器走：

  | | pnpm | npm | yarn |
  |---|---|---|---|
  | 装 devDep | `pnpm add -D <pkgs>` | `npm i -D <pkgs>` | `yarn add -D <pkgs>` |
  | 钩子里执行 | `pnpm exec commitlint --edit "$1"` | `npx --no-install commitlint --edit "$1"` | `yarn commitlint --edit "$1"` |

- **非 Node 项目也能用**：commitlint / husky 只依赖 Node 工具链，Swift / Go / Rust / Python 项目
  加一个最小 `package.json` 即可（原始项目就是一个 Swift app）。
- **已有 `commitlint.config.js` 或 `.husky/commit-msg`**：先读，把差异讲给用户，问清覆盖、合并还是跳过。
  尤其当已有规范是无 emoji 的 conventional commits 时，说明本规范会强制 emoji，与旧提交不兼容。

### 2. package.json

没有就写一个最小的；有就只补 `scripts.prepare = "husky"`，其余保留。`prepare` 让 husky 在 `install` 时自动装钩子。

```json
{ "name": "<项目名>", "private": true, "type": "commonjs", "scripts": { "prepare": "husky" } }
```

### 3. 安装依赖

```bash
pnpm add -D @commitlint/cli @commitlint/config-conventional husky
```

`@commitlint/config-conventional` 没在 config 里 `extends`，保留它作为约定基线、方便日后扩展；用户要极简可省。

### 4. 放置 config

按第 0 步的选择，把 `assets/commitlint.config.emoji.js` 或 `assets/commitlint.config.plain.js`
**原样复制**到项目根目录的 `commitlint.config.js`，照抄模板才能保证与规范逐字一致。项目里只保留这一个 config。

### 5. husky 与 commit-msg 钩子

husky v9+ 不需要旧版的 `husky install` 与 shebang 样板：

```bash
pnpm exec husky init   # 或 npx husky init
```

`husky init` 会默认生成一个 `.husky/pre-commit`（内容类似 `npm test`），本规范只需要 `commit-msg`，
把它删掉或清空。然后创建 `.husky/commit-msg`，内容只有一行（按包管理器选）：

```sh
pnpm exec commitlint --edit "$1"
```

确认钩子可执行（`chmod +x .husky/commit-msg`）。

### 6. 验证（不要跳过）

配置的价值在于「拦得住坏的、放得过好的」，落地后实测：

```bash
# 带 emoji 版
echo "🐛 fix(core): fix crash on launch" | pnpm exec commitlint   # 通过，exit 0
echo "🐛 feat(Core): bad message" | pnpm exec commitlint          # 被拒：scope 大写 + emoji 与 type 不配

# 不带 emoji 版
echo "fix(core): fix crash on launch" | pnpm exec commitlint      # 通过
echo "fix(Core): bad message" | pnpm exec commitlint              # 被拒：scope 大写
echo "nope: bad message" | pnpm exec commitlint                   # 被拒：非法 type
```

把结果如实告诉用户；条件允许再跑一次真实 `git commit` 端到端确认。

## 交接

- 告诉用户此后的 header 格式与 config 位置；钩子报错就改 message，不要 `--no-verify` 绕过。
- AI 署名（`Co-Authored-By` 等）与本配置无关，按各项目自己的约定处理，本 skill 不写死。

## 边界情况

- **monorepo**：config 放在 `.git` 所在的仓库根，不是子包目录。
- **CI 校验**：可加 `commitlint --from <base> --to <head>` 校验 PR 范围；本 skill 默认只配本地钩子。
- **钩子没生效**：通常是没跑过 `prepare`（`pnpm install` / `husky init`），或当前目录没有 `.git`。
