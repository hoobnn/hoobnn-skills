# gitmoji emoji 开关 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `gitmoji-commitlint-setup` skill 在落地时可选择是否启用 emoji，不启用时退化为规则等价的标准 Conventional Commits。

**Architecture:** 把现有单一 emoji 版 config 改名为 `commitlint.config.emoji.js`，新增一份去掉 emoji 校验、其余规则逐字一致的 `commitlint.config.plain.js`；SKILL.md 增加「步骤 0：选择是否启用 emoji」并把复制源改为二选一，同步更新验证用例与触发词。

**Tech Stack:** commitlint config（CommonJS）、Markdown skill 文档。本仓库是 Claude Code 插件市场，无构建/测试框架；验证靠人工核对 + commitlint 行为描述。

参考 spec：`docs/superpowers/specs/2026-06-08-gitmoji-emoji-toggle-design.md`

---

### Task 1: 重命名 emoji 版 config

把现有 `assets/commitlint.config.js` 改名为 `assets/commitlint.config.emoji.js`，内容不变。用 `git mv` 保留历史。

**Files:**
- Rename: `plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.js` → `plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.emoji.js`

- [ ] **Step 1: 用 git mv 改名**

```bash
git mv plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.js \
       plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.emoji.js
```

- [ ] **Step 2: 验证改名结果**

Run:
```bash
ls plugins/git-kit/skills/gitmoji-commitlint-setup/assets/
```
Expected: 输出包含 `commitlint.config.emoji.js`，不再有 `commitlint.config.js`。

- [ ] **Step 3: 验证内容未变**

Run:
```bash
git show HEAD:plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.js \
  | diff - plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.emoji.js
```
Expected: 无差异输出（exit 0）。仅路径变化，内容逐字一致。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: 将 emoji 版 commitlint config 改名以对齐语义"
```

---

### Task 2: 新增 plain（无 emoji）版 config

新增 `assets/commitlint.config.plain.js`：标准 Conventional Commits，去掉 emoji 强制，其余规则与 emoji 版逐字一致。

**Files:**
- Create: `plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.plain.js`

- [ ] **Step 1: 创建 plain 版 config**

写入 `plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.plain.js`，内容**完全如下**：

```js
// 格式：type(scope): subject
// 标准 Conventional Commits（无 emoji 版）。校验、changelog、语义化版本均以 type 为准。
// 这是 commitlint.config.emoji.js 的去 emoji 等价版：除 emoji 强制外，规则逐字一致。

// Conventional type 白名单（与 emoji 版的 type 集合一致）
const TYPES = [
  'feat',     // 新功能
  'fix',      // 缺陷修复
  'docs',     // 文档
  'style',    // 代码风格 / 格式（不改语义）
  'refactor', // 重构
  'perf',     // 性能
  'test',     // 测试
  'build',    // 构建系统 / 外部依赖
  'ci',       // CI 配置与脚本
  'chore',    // 杂务 / 工具 / 配置
  'revert',   // 回滚提交
];

module.exports = {
  rules: {
    'type-enum': [2, 'always', TYPES],
    'type-empty': [2, 'never'],
    'scope-case': [2, 'always', 'lower-case'],
    'subject-empty': [2, 'never'],
    'subject-case': [0],
    'header-max-length': [2, 'always', 72],
    'body-leading-blank': [1, 'always'],
    'footer-leading-blank': [1, 'always'],
  },
};
```

- [ ] **Step 2: 核对与 emoji 版的规则一致性**

人工对照 `commitlint.config.emoji.js` 与新文件的 `rules` 块，确认：
- 两者共有的 7 条规则（`type-empty`、`scope-case`、`subject-empty`、`subject-case`、`header-max-length`、`body-leading-blank`、`footer-leading-blank`）的级别与参数**逐字相同**。
- plain 版的 `type-enum` 白名单与 emoji 版 `TYPE_EMOJI` 的 key 集合相同：`feat fix docs style refactor perf test build ci chore revert`（11 个，顺序一致）。
- plain 版**不含** `emoji-type-match`、`parserPreset`、`plugins`、`norm`、`TYPE_EMOJI`。

Expected: 全部满足。

- [ ] **Step 3: 验证 JS 语法有效**

Run:
```bash
node -e "const c=require('./plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.plain.js'); console.log(Object.keys(c.rules).length, c.rules['header-max-length'][2])"
```
Expected: 输出 `8 72`（8 条规则，header 上限 72）。无语法错误。

- [ ] **Step 4: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/assets/commitlint.config.plain.js
git commit -m "feat: 新增无 emoji 版 commitlint config 模板"
```

---

### Task 3: 更新 SKILL.md frontmatter 触发词

在 `description` 里补上「不要 emoji / 纯 conventional」相关触发词，让用户明说不要 emoji 时也能命中本 skill。

**Files:**
- Modify: `plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md`（frontmatter `description`，约 3-10 行）

- [ ] **Step 1: 改写 description**

将 frontmatter 中 `description:` 现有这段：

```
  message 规范」「上 husky commit-msg 钩子」「想要那种带 emoji 的规范提交」，或在一个还没有提交
  规范的仓库里要求统一 commit 风格时，都应使用本 skill —— 即使用户没有逐字说出 commitlint 或
  gitmoji。本 skill 负责「配置落地」，不负责日常生成 commit message。
```

替换为：

```
  message 规范」「上 husky commit-msg 钩子」「想要那种带 emoji 的规范提交」「不要 emoji 的
  conventional commits」「配纯 conventional 提交规范」，或在一个还没有提交规范的仓库里要求统一
  commit 风格时，都应使用本 skill —— 即使用户没有逐字说出 commitlint 或 gitmoji。本 skill 支持
  带 emoji 与不带 emoji 两种风格、落地时二选一，负责「配置落地」，不负责日常生成 commit message。
```

- [ ] **Step 2: 验证 frontmatter 仍合法**

Run:
```bash
sed -n '1,12p' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: frontmatter 以 `---` 开头结尾，`name:` 与 `description:` 完整，YAML 缩进正确（description 续行保持 2 空格缩进）。

- [ ] **Step 3: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
git commit -m "docs: 补充无 emoji 风格的 skill 触发词"
```

---

### Task 4: SKILL.md 增加「步骤 0：选择是否启用 emoji」

在「### 1. 探查目标项目」之前插入一个新步骤，落地时主动询问 emoji 开关。

**Files:**
- Modify: `plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md`（「## 落地流程」与「### 1. 探查目标项目」之间）

- [ ] **Step 1: 插入步骤 0**

在 `## 落地流程` 段落的引导句「按顺序执行。每一步先观察现状再动手……」之后、`### 1. 探查目标项目` 之前，插入：

```markdown
### 0. 选择是否启用 emoji

落地前先问用户一次，决定这个项目用哪种风格（二选一，落地后该项目固定此风格）：

- **带 emoji（默认）**：header 为 `<emoji> <type>(<scope>): <subject>`，emoji 与 type 强制 1:1。这是本规范的标志性风格。
- **不带 emoji**：标准 Conventional Commits，header 为 `<type>(<scope>): <subject>`。

两种风格**除 emoji 外规则完全一致**——type 白名单、scope 小写、subject 非空、header ≤72、body/footer 空行都相同。区别仅在于带不带 emoji 前缀及 emoji↔type 配对校验。

用户没有明确表态时，默认带 emoji（这套规范的初衷）。选定结果会决定第 4 步复制哪个 config 模板、第 6 步用哪组验证用例。
```

- [ ] **Step 2: 验证插入位置与编号顺序**

Run:
```bash
grep -n '^### [0-9]' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: 依次输出 `### 0. 选择是否启用 emoji`、`### 1. 探查目标项目`、`### 2.`…`### 6.`，编号 0-6 连续无跳号。

- [ ] **Step 3: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
git commit -m "docs: 落地流程新增 emoji 开关选择步骤"
```

---

### Task 5: SKILL.md 改写「步骤 4：放置 config」为二选一复制

复制源根据步骤 0 的选择二选一，目标始终是项目根的 `commitlint.config.js`。

**Files:**
- Modify: `plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md`（「### 4. 放置 commitlint.config.js」整段）

- [ ] **Step 1: 改写步骤 4 正文**

将现有这段（cp 命令用三个反引号围栏）：

> 把本 skill 的 `assets/commitlint.config.js` **原样复制**到项目根目录。不要手敲那张 80 多条的 emoji-type 表——照抄模板才能保证和原始规范逐字一致。
>
> cp `<skill 目录>/assets/commitlint.config.js` `<项目根>/commitlint.config.js`

替换为：

> 按步骤 0 的选择，把对应模板**原样复制**到项目根目录的 `commitlint.config.js`。不要手敲规则表——照抄模板才能保证和规范逐字一致。
>
> （bash 代码块，三反引号围栏）
> `# 带 emoji（默认）`
> `cp <skill 目录>/assets/commitlint.config.emoji.js <项目根>/commitlint.config.js`
> （空行）
> `# 不带 emoji`
> `cp <skill 目录>/assets/commitlint.config.plain.js <项目根>/commitlint.config.js`
>
> 无论选哪种，目标项目里始终只有一个干净的 `commitlint.config.js`。

写入时务必用真实的三反引号 ```` ```bash ```` 代码围栏包住两条 cp 命令。

- [ ] **Step 2: 验证两个模板路径都被提及**

Run:
```bash
grep -n 'commitlint.config.emoji.js\|commitlint.config.plain.js' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: 两个文件名各至少出现一次（在步骤 4 的 cp 命令里）。

- [ ] **Step 3: 验证 cp 复制源不再用旧的裸 config 名**

Run:
```bash
grep -n 'cp .*assets/commitlint.config.js ' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: 无输出（步骤 4 的 cp 复制源已替换为 emoji/plain 二选一）。

> 注意：文件里另有两处**描述性引用** `assets/commitlint.config.js`（行 26「强制规则（由 assets/commitlint.config.js 实现）」、行 29「完整 type↔emoji 表见 assets/commitlint.config.js」）。这两处不是复制源，**预期保留、不要改动**——它们泛指规范的配置文件，与本任务无关。因此不要用裸 `grep 'assets/commitlint.config.js'` 断言「无输出」，那会误报。

- [ ] **Step 4: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
git commit -m "docs: 放置 config 步骤改为按 emoji 开关二选一复制"
```

---

### Task 6: SKILL.md 改写「步骤 6：验证」为按风格分组

验证用例按所选风格给两组，plain 版用不带 emoji 的用例。

**Files:**
- Modify: `plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md`（「### 6. 验证」中的两条示例命令及说明）

- [ ] **Step 1: 改写步骤 6 的验证用例**

将现有「应当通过 / 应当被拒」那段（两条 echo 命令 + 其后说明段）替换为按风格分组。写入时每个 bash 代码块用真实三反引号围栏：

**带 emoji 版**两条：
- 应通过：`echo "🐛 fix(core): fix crash on launch" | pnpm exec commitlint`
- 应被拒（大写 scope + emoji 与 type 不配）：`echo "🐛 feat(Core): bad message" | pnpm exec commitlint`

**不带 emoji 版**三条：
- 应通过：`echo "fix(core): fix crash on launch" | pnpm exec commitlint`
- 应被拒（scope 大写）：`echo "fix(Core): bad message" | pnpm exec commitlint`
- 应被拒（非法 type）：`echo "nope: bad message" | pnpm exec commitlint`

说明段保留并改为：「应当通过」的应无输出（exit 0），「应当被拒」的应报错（非 0，并能看到对应规则的提示）。按步骤 0 选的风格选对应一组。把结果如实告诉用户。若条件允许，再跑一次真实的 `git commit` 触发钩子端到端确认。

- [ ] **Step 2: 验证两组用例都在**

Run:
```bash
grep -n 'fix(core): fix crash on launch\|fix(Core): bad message\|nope: bad message' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: 三类都命中——`fix(core): fix crash on launch`（emoji 版与 plain 版各一次，共 2 处）、`fix(Core): bad message`、`nope: bad message`。

- [ ] **Step 3: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
git commit -m "docs: 验证步骤按 emoji 风格分两组用例"
```

---

### Task 7: SKILL.md 顶部说明与交接段同步

「这套规范长什么样」开头补一句两种风格说明；「配置完成后交接」按风格描述 header 格式。

**Files:**
- Modify: `plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md`（「## 这套规范长什么样」开头、「## 配置完成后（交接给用户）」首条）

- [ ] **Step 1: 「这套规范长什么样」开头补说明**

在 `## 这套规范长什么样` 标题之后、「提交 header 必须匹配：」之前，插入一段：

```markdown
本 skill 支持两种风格，落地时（步骤 0）二选一：

- **带 emoji**（默认，下文详述）：header 形如 `<emoji> <type>(<scope>): <subject>`。
- **不带 emoji**：标准 Conventional Commits，header 形如 `<type>(<scope>): <subject>`，是上面这套规范去掉 emoji 的等价版——**其余规则完全一致**。

下面以带 emoji 版为主说明；不带 emoji 版只是少了 emoji 前缀与 emoji↔type 配对校验。
```

- [ ] **Step 2: 改写交接段首条**

将「## 配置完成后（交接给用户）」下的第一条：

```markdown
- 告诉用户：以后这个项目的提交 header 必须是 `<emoji> <type>(<scope>): <subject>`，否则会被钩子拒绝；完整 emoji-type 表在 `commitlint.config.js` 里。
```

替换为：

```markdown
- 告诉用户该项目以后的提交 header 格式（按落地时选的风格）：带 emoji 版是 `<emoji> <type>(<scope>): <subject>`（完整 emoji-type 表在 `commitlint.config.js` 里）；不带 emoji 版是 `<type>(<scope>): <subject>`。不合规会被钩子拒绝。
```

- [ ] **Step 3: 验证两处改动都在**

Run:
```bash
grep -n '不带 emoji\|按落地时选的风格' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected: 顶部说明段与交接段均命中「不带 emoji」；交接段命中「按落地时选的风格」。

- [ ] **Step 4: Commit**

```bash
git add plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
git commit -m "docs: 顶部说明与交接段同步两种 emoji 风格"
```

---

## 收尾验证（全部任务完成后）

- [ ] **整体一致性检查**

Run:
```bash
ls plugins/git-kit/skills/gitmoji-commitlint-setup/assets/
grep -n '^### [0-9]' plugins/git-kit/skills/gitmoji-commitlint-setup/SKILL.md
```
Expected:
- `assets/` 含 `commitlint.config.emoji.js` 与 `commitlint.config.plain.js`，无裸 `commitlint.config.js`。
- 步骤编号 0-6 连续。

- [ ] **确认 spec 全部要求有对应实现**

对照 `docs/superpowers/specs/2026-06-08-gitmoji-emoji-toggle-design.md`：
- 资产改名 → Task 1
- plain 模板 → Task 2
- 触发词 → Task 3
- 步骤 0 → Task 4
- 步骤 4 二选一 → Task 5
- 步骤 6 验证分组 → Task 6
- 顶部说明 + 交接 → Task 7
