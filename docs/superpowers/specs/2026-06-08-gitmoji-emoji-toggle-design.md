# 设计：gitmoji-commitlint-setup 支持「是否启用 emoji」

日期：2026-06-08
范围：`plugins/git-kit/skills/gitmoji-commitlint-setup`

## 背景

现有 `gitmoji-commitlint-setup` skill 把一套「gitmoji + commitlint」提交规范一次性配置到目标项目，emoji 是**强制**的：`commitlint.config.js` 通过自定义 `headerPattern`（要求 emoji 前缀）和 `emoji-type-match` 插件规则强制 emoji 与 type 1:1 配对。

目标：让该 skill 支持在落地时选择**是否启用 emoji**。

## 设计决策

1. **开关时机：配置时一次性选定**（非运行时切换）。skill 落地时询问用户一次，据此生成对应风格的 config，项目从此固定该风格。契合本 skill「把统一规范一次性落地」的定位。
2. **不启用 emoji 时退化为标准 Conventional Commits**，且**除 emoji 外规则与 emoji 版完全一致**（type 白名单、scope 小写、subject 非空、header ≤72、body/footer 空行均相同）。让两版本切换的心智负担最小。
3. **两个独立模板文件**，落地时按选择复制其一到项目根，目标项目始终是一个干净的 `commitlint.config.js`。保持「原样复制、逐字一致」的可靠性。

## 资产组织

```
assets/
  commitlint.config.emoji.js   ← 由现有 commitlint.config.js 改名而来（内容不变）
  commitlint.config.plain.js   ← 新增：无 emoji 版
```

现有 `commitlint.config.js` 改名为 `commitlint.config.emoji.js`（对齐两模板的命名语义；为 skill 内部资产，无外部引用风险）。

### commitlint.config.plain.js（新增）

在 emoji 版基础上去掉 emoji 相关部分，其余逐字一致：

```js
// 格式：type(scope): subject
// 标准 Conventional Commits（无 emoji 版）。校验、changelog、语义化版本均以 type 为准。

// Conventional type 白名单（与 emoji 版的 type 集合一致）
const TYPES = [
  'feat', 'fix', 'docs', 'style', 'refactor',
  'perf', 'test', 'build', 'ci', 'chore', 'revert',
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

与 emoji 版的差异**仅**：去掉 `norm` / `TYPE_EMOJI` / `parserPreset`（自定义 headerPattern）/ `plugins`（emoji-type-match）以及 `rules` 里的 `'emoji-type-match'`。其余 7 条规则与阈值（header 72、scope 小写、subject-case 不限）全部保持一致。header 用 commitlint 默认 parser 即可正确解析 `type(scope): subject`。

## SKILL.md 改动

改动集中在 3 处，其余流程（探查、装依赖、husky 钩子、交接、边界情况）不变。

### ① 新增「步骤 0：选择是否启用 emoji」

放在「探查目标项目」之后、「放置 config」之前。落地时主动询问一次：

- **带 emoji**：`<emoji> <type>(<scope>): <subject>`，emoji 与 type 强制 1:1（默认风格）
- **不带 emoji**：标准 Conventional Commits `<type>(<scope>): <subject>`，其余规则完全一致

说明：两者除 emoji 外规则一致；一旦选定，该项目固定此风格。

### ② 改写「步骤 4：放置 commitlint.config.js」

复制源二选一，目标始终是干净的 `commitlint.config.js`：

```bash
# 带 emoji
cp <skill>/assets/commitlint.config.emoji.js <项目根>/commitlint.config.js
# 不带 emoji
cp <skill>/assets/commitlint.config.plain.js <项目根>/commitlint.config.js
```

### ③ 改写「步骤 6：验证」

按所选版本给对应测试用例：

- **emoji 版**：保持现有两条（`🐛 fix(core): ...` 应过；`🐛 feat(Core): ...` 应拒）。
- **plain 版**：`fix(core): fix crash on launch` 应过；`fix(Core): bad message`（scope 大写）或 `nope: bad type`（非法 type）应拒。

### 其余文档同步更新

- 开头「这套规范长什么样」补一句：支持 emoji / 无 emoji 两种，以 emoji 版为主、plain 版为去 emoji 的等价版。
- frontmatter `description` 补触发词（如「不要 emoji 的 conventional commits」「纯 conventional 规范」），让用户明说不要 emoji 时也能命中本 skill。
- 「配置完成后交接」按所选版本描述 header 格式。

## 非目标

- 不引入运行时 emoji 开关。
- 不改动已落地项目的迁移逻辑（边界情况「已有不同规范」仍按现有「不静默覆盖、先确认」处理）。
- 不改 husky / 包管理器探测 / 依赖安装等其余流程。
