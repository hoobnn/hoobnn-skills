// 格式：type(scope): subject
// 标准 Conventional Commits（无 emoji 版）。校验、changelog/语义化版本均以 type 为准。
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
