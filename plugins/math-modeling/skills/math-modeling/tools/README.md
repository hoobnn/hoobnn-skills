# tools/ — 子 Skill 中文导读

本目录集成六个子 skill，供数学建模三阶段流程（建模分析 → 代码实现 → 论文撰写）调用。

其中 `docx` / `xlsx` / `paper_search` / `figure` / `latex` 由上游作者改写为中文、并针对
竞赛场景做了裁剪；`pdf` 保持 Anthropic 官方英文原文（许可见 `pdf/LICENSE.txt`）。
`docx` / `xlsx` 目录同样保留各自 `LICENSE.txt`。

本文件是给人读的中文导读：**什么时候用哪个、入口在哪、有哪些硬性约束**。
模型执行时以各子目录 `SKILL.md` 原文为准。

---

## 选用速查

| 场景 | 用哪个 | 入口 |
|------|--------|------|
| 出论文 Word 稿、公式、修订批注 | `docx` | `docx/SKILL.md` |
| 出论文 LaTeX 项目、编译校验 | `latex` | `latex/SKILL.md` |
| 画出版级图表（默认交付图） | `figure` | `figure/SKILL.md` |
| 读赛题附件数据表、输出结果表 | `xlsx` | `xlsx/SKILL.md` |
| 读赛题 PDF、读优秀论文、提表格 | `pdf` | `pdf/SKILL.md` |
| 查参考文献、生成可追溯引用 | `paper_search` | `paper_search/SKILL.md` |

---

## docx — Word 论文

**用于**：论文定稿输出、公式写入、解包校验、修订与批注。

- 推荐流程见原文「数学建模论文推荐流程」：借用模板样式后追加正文；
  若官方模板含固定摘要页或编号页，需改为在原位置填充。
- 公式分两条路径：简单公式直接写入，复杂公式走专门流程。
- 支持「完整 LaTeX 论文转 DOCX」，与 `latex` 工具配合使用。
- 原文末尾有**必做验证**清单，出稿前逐条过。

---

## latex — LaTeX 论文

**用于**：从官方或内置模板创建 LaTeX 项目、编译、校验。

- 注意：自 upstream 1.2.0 起，**默认只生成 Word 论文**，LaTeX 仅在用户明确要求时才产出
  （LaTeX 环境配置门槛高）。
- 可配合 `docx` 把完整 LaTeX 论文转 Word。

---

## figure — 科研可视化

**用于**：所有交付图表。这是 1.2.0 新增的重点工具，替代了旧的零散绘图规范。

- 工作流：**数据剖析**（列类型 / 样本量 / 分布 / 异常值 / 分组结构 / 相关性）
  → 结合论证目标**推荐图型** → 出版级绘制 → **程序自检 + AI 读图**闭环 → 多格式导出。
- 会主动拦截科研画图的经典错误，目标是 Nature / Science / IEEE / Elsevier / PNAS
  及中文核心期刊级别的成图。
- 支持 Python 与 R 双后端。
- 参考文档分五类，按需查：`chart-types/`（选图）、`design/`（设计理论与避坑）、
  `api-templates/`（API 与模板）、`quality/`（质检与期刊规范）、`guides/`（教程）。

> 图表数量门禁（upstream 1.1.0 起）：原始数据图 / 模型过程图 / 模型结果图**每类至少 3 张、
> 合计至少 9 张**，且每个子问题在三类中各至少 1 张。由 `figure_audit.py --strict` 确定性拦截。

---

## xlsx — Excel 表格

**用于**：读赛题附件数据表、输出结果表。

**硬性约束**（原文列为原则，务必遵守）：

- 输入表格**只读**，输出写入 `PROJECT_ROOT`；不覆盖赛题原始附件和 Skill 文件。
- 普通结果汇总**优先用 CSV**；仅当题目指定 XLSX、需保留公式、多工作表或模板结构时才用 XLSX。
- **禁止依赖 `pd.read_excel()` 默认的 `header=0` 猜表头**——第一行就是数据时必须显式
  `header=None`，否则首行数据会被当成列名。
- 读取后必须核对首行、末行、有效行数与题目声明的记录数；**行数不符立即报错，
  不得静默继续建模**。
- 交付表格不得含 `#VALUE!` / `#DIV/0!` / `#REF!` / `#NAME?` / `#NULL!` / `#NUM!` / `#N/A`。
- `openpyxl` 不计算公式；改过含公式的工作簿后用 `scripts/recalc.py` 经 LibreOffice 隔离重算。

---

## pdf — PDF 处理（英文原文）

**用于**：读赛题 PDF、阅读优秀论文、提取文本与表格、合并拆分、OCR。

| 任务 | 首选工具 |
|------|----------|
| 提取文本 | `pdfplumber.extract_text()` |
| **提取表格** | `pdfplumber.extract_tables()` |
| 合并 / 拆分 | `pypdf` |
| 生成 PDF | `reportlab` |
| 命令行合并 | `qpdf` |
| 扫描件 OCR | `pytesseract`（需先转图片） |
| 填表单 | 见 `pdf/forms.md` |

赛题附件里的表格若来自 PDF，用 `extract_tables()`，不要对 `extract_text()` 结果做正则切分。
进阶用法与排错见 `pdf/reference.md`。

---

## paper_search — 双引擎论文检索

**用于**：写引言 / 文献综述 / 参考文献时检索并生成可追溯引用。

- **双引擎**：OpenAlex（结构化元数据）+ AnySearch Academic，默认**并行调用**，
  正式检索不得只跑一个引擎（`--openalex-only` / `--anysearch-only` 仅用于诊断）。
- DOI 相同直接交叉验证；无 DOI 时仅在标题高度相似且年份相容时合并。
- 相关性优先于引用量，避免高被引但主题无关的论文挤占结果。
- 物理 / 材料 / 光学类主题应组合材料名 + 机理名 + 模型名检索，
  例如 `Sellmeier 4H-SiC Fabry-Perot`。
- AnySearch 如需鉴权，设 `ANYSEARCH_API_KEY` 环境变量。

**核验规则（重要）**：搜索结果只用于**发现候选文献**；引用前必须打开 DOI 或出版机构页面
核对作者、题名、年份、期刊/会议、卷期页。不得把引用量当正确性证明，
不得根据标题或摘要编造不存在的结论。

---

## 收录与维护

- 上游：[XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)，
  当前收录版本见根目录 `VERSION`，变更见 `CHANGELOG.md`。
- 本目录内容**保持上游原样**，不做翻译或改写，以便后续同步。
  需要补中文说明时写到本文件，不要改动各子目录的 `SKILL.md`。
- `docx` / `pdf` / `xlsx` 含 Anthropic 官方 skill 代码，许可见各目录 `LICENSE.txt`。
