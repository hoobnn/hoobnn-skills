#!/usr/bin/env python3
"""提交物校验脚手架（comp-kit / comp-submit）。

由 comp-init 拷贝到竞赛仓库的 `src/check_submission.py`。提交物支持三种形态：
单文件（如 output.csv）、目录、ZIP 包（如"四文件提交包"）。按比赛定制三处：

    1. MANIFEST      提交物形态与包内清单（必需条目 / 禁止条目 / 体积上限）
    2. 条目 Spec     每个条目的内容约定：Table（列/行数/解析/取值/缺失/demo diff）
                     或 File（存在性/体积/自定义 loader）
    3. @rule         领域合法性规则，一个假设一个函数；按组断言用 @per_group 包装

用法：

    uv run python src/check_submission.py submissions/<方案名>/output.csv
    uv run python src/check_submission.py dist/submission.zip --log-snippet

设计原则：

    - 所有校验脚本化，不靠肉眼；任一 FAIL 退出码为 1，可挂 pre-submit hook / CI。
    - 全量断言而非抽查：合法性规则逐组检查，输出 `59/59 组合法` 这类全量结论。
    - 校验通过后输出产物指纹（MD5 / 体积）与 experiment-log 粘贴块，产物不入 git、指纹留痕。
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

# ======================================================================
# 1. 条目 Spec 类型 —— 无需修改，供 MANIFEST 使用。
# ======================================================================


@dataclass
class File:
    """普通文件条目：存在性 + 体积上限 + 可选自定义 loader。

    loader(fh) -> object：解析内容并返回（如 np.load、json.load、源码文本），
    返回值存入 ctx[条目名]，供 @rule 使用；解析抛错即 FAIL。
    """

    required: bool = True
    max_mb: float | None = None
    loader: Callable | None = None


@dataclass
class Table(File):
    """表格条目（CSV）：格式层校验 + 可选官方 demo diff。"""

    encoding: str = "utf-8"
    columns: list[str] | None = None          # 精确列名与顺序（顺序也算格式）
    n_rows: int | None = None                 # 行数公式
    parse: dict = field(default_factory=dict)  # 列名 -> (解析函数, 描述)
    allowed_values: dict = field(default_factory=dict)  # 列名 -> 允许取值集合
    no_nan: list[str] = field(default_factory=list)     # 不允许缺失/空值的列
    # 分组：列名 或 (列名, 变换函数)，@per_group 规则按它分组断言
    group_by: object = None
    demo: str | None = None                   # 官方 demo 文件路径；逐列 diff 是最强格式校验
    lock_to_demo: list[str] = field(default_factory=list)  # 与 demo 逐行一致的列（时间轴/ID）


# ======================================================================
# 2. MANIFEST —— 按比赛修改。默认示例：单 CSV（储能收益优化实战的约定）。
# ======================================================================

MANIFEST = {
    "kind": "file",                # "file" | "dir" | "zip"
    "filename": "output.csv",      # 官方要求的提交物名字
    "max_size_mb": None,           # 提交物总体积上限（MB）；None 不限
    "forbid": [],                  # 禁止出现的条目（glob），单文件形态忽略
    "entries": {
        "output.csv": Table(
            columns=["times", "实时价格", "power"],
            n_rows=96 * 59,
            parse={
                "times": (lambda s: pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S"), "北京时间字符串"),
                "实时价格": (lambda s: pd.to_numeric(s, errors="raise"), "数值"),
                "power": (lambda s: pd.to_numeric(s, errors="raise"), "数值"),
            },
            allowed_values={"power": {-1000.0, 0.0, 1000.0}},
            no_nan=["times", "实时价格", "power"],
            group_by=("times", lambda s: pd.to_datetime(s).dt.date),
            demo=None,             # 如 "example/output_demo.csv"
            lock_to_demo=[],       # 如 ["times"]
        ),
    },
}

# --- ZIP 包示例（多文件提交包，如"严格四文件提交包"）----------------------
# MANIFEST = {
#     "kind": "zip",
#     "filename": "submission.zip",
#     "max_size_mb": 100,
#     "forbid": ["__pycache__/*", "*.pyc", ".DS_Store", "__MACOSX/*"],
#     "entries": {
#         "model.py": File(max_mb=1),
#         "weights.pt": File(max_mb=95),
#         "config.json": File(loader=lambda fh: __import__("json").load(fh)),
#         "results.csv": Table(columns=["id", "score"], no_nan=["id", "score"]),
#     },
# }

# ======================================================================
# 3. 领域合法性规则 —— fn(ctx) -> 错误列表。ctx[条目名] 是该条目解析后的内容
#    （Table 为 DataFrame，File 为 loader 返回值）。
# ======================================================================

RULES = []


def rule(fn):
    RULES.append(fn)
    return fn


def per_group(entry: str):
    """把「单组 DataFrame -> 错误列表」提升为对某表格条目的全量分组检查。"""

    def deco(check_group):
        def wrapped(ctx) -> list[str]:
            df = ctx.get(entry)
            if df is None:
                return [f"条目 {entry} 未成功加载，无法执行规则"]
            gb = MANIFEST["entries"][entry].group_by
            if gb is None:
                return [f"Table('{entry}').group_by 未配置，无法按组断言"]
            col, transform = gb if isinstance(gb, tuple) else (gb, lambda s: s)
            groups = df.groupby(transform(df[col]), sort=True)
            errors, bad = [], 0
            for key, g in groups:
                errs = check_group(g)
                bad += bool(errs)
                errors.extend(f"[{key}] {e}" for e in errs)
            wrapped.summary = f"{groups.ngroups - bad}/{groups.ngroups} 组合法"
            return errors

        wrapped.__name__ = check_group.__name__
        return wrapped

    return deco


# --- 示例规则（来自实战，替换为你的比赛的硬约束） -------------------------
# @rule
# @per_group("output.csv")
# def 充放电窗口合法(g: pd.DataFrame) -> list[str]:
#     """每天最多一充一放，各为连续 8 点，先充后放，可全跳过。"""
#     p = g["power"].to_numpy()
#     errs = []
#     charge = [i for i, v in enumerate(p) if v < 0]
#     discharge = [i for i, v in enumerate(p) if v > 0]
#     for name, idx in [("充电", charge), ("放电", discharge)]:
#         if idx and (len(idx) != 8 or idx[-1] - idx[0] != 7):
#             errs.append(f"{name}非连续 8 点: {idx}")
#     if charge and discharge and charge[-1] >= discharge[0]:
#         errs.append("放电早于充电（初始 SOC=0 必须先充后放）")
#     return errs


# ======================================================================
# 4. 校验引擎 —— 一般无需修改。
# ======================================================================


class CheckFailed(AssertionError):
    pass


def require(cond, msg: str):
    if not cond:
        raise CheckFailed(msg)


class Artifact:
    """单文件 / 目录 / ZIP 的统一访问接口。"""

    def __init__(self, path: Path):
        self.path = path

    def names(self) -> list[str]: ...
    def open(self, name: str): ...
    def size(self, name: str) -> int: ...

    def total_size(self) -> int:
        return sum(self.size(n) for n in self.names())

    def md5(self) -> str:
        h = hashlib.md5()
        if self.path.is_file():
            with open(self.path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        else:  # 目录：按名字序对每个条目内容做链式 hash
            for n in sorted(self.names()):
                h.update(n.encode())
                with self.open(n) as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def load(path: Path, kind: str) -> "Artifact":
        return {"file": SingleFile, "dir": DirArtifact, "zip": ZipArtifact}[kind](path)


class SingleFile(Artifact):
    def names(self):
        return [self.path.name]

    def open(self, name):
        return open(self.path, "rb")

    def size(self, name):
        return self.path.stat().st_size


class DirArtifact(Artifact):
    def names(self):
        return [str(p.relative_to(self.path)) for p in self.path.rglob("*") if p.is_file()]

    def open(self, name):
        return open(self.path / name, "rb")

    def size(self, name):
        return (self.path / name).stat().st_size


class ZipArtifact(Artifact):
    def __init__(self, path):
        super().__init__(path)
        self.zf = zipfile.ZipFile(path)

    def names(self):
        return [i.filename for i in self.zf.infolist() if not i.is_dir()]

    def open(self, name):
        return self.zf.open(name)

    def size(self, name):
        return self.zf.getinfo(name).file_size


class Runner:
    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, fn):
        try:
            detail = fn()
            self.results.append((name, True, detail or ""))
        except Exception as e:  # 校验器里任何异常都按 FAIL 处理
            self.results.append((name, False, str(e)))

    @property
    def all_ok(self) -> bool:
        return all(ok for _, ok, _ in self.results)


def check_table(r: Runner, tag: str, spec: Table, fh, ctx: dict, entry: str):
    df = pd.read_csv(fh, encoding=spec.encoding, dtype=str)

    if spec.columns is not None:
        r.check(f"{tag}列名与顺序", lambda: require(list(df.columns) == spec.columns, f"{list(df.columns)} != {spec.columns}"))
    if spec.n_rows is not None:
        r.check(f"{tag}行数 = {spec.n_rows}", lambda: require(len(df) == spec.n_rows, f"实际 {len(df)} 行"))
    for col in spec.no_nan:
        def no_nan(c=col):
            bad = df[c].isna() | (df[c].astype(str).str.strip() == "")
            require(not bad.any(), f"{int(bad.sum())} 个缺失/空值，首个在 index={int(bad.idxmax())}")
        r.check(f"{tag}无缺失: {col}", no_nan)

    parsed = df.copy()
    for col, (parser, desc) in spec.parse.items():
        def do_parse(c=col, p=parser):
            parsed[c] = p(df[c])
        r.check(f"{tag}解析: {col}（{desc}）", do_parse)
    for col, allowed in spec.allowed_values.items():
        def check_values(c=col, a=allowed):
            bad = set(parsed[c].unique()) - a
            require(not bad, f"非法取值 {[float(v) for v in sorted(bad)[:10]]}")
        r.check(f"{tag}取值合法: {col}", check_values)

    if spec.demo:
        demo = pd.read_csv(spec.demo, encoding=spec.encoding, dtype=str)
        r.check(f"{tag}demo: 列结构一致", lambda: require(list(df.columns) == list(demo.columns), f"{list(df.columns)} != {list(demo.columns)}"))
        r.check(f"{tag}demo: 行数一致", lambda: require(len(df) == len(demo), f"{len(df)} != {len(demo)}"))
        for col in spec.lock_to_demo:
            def lock_col(c=col):
                diff = df[c] != demo[c]
                require(not diff.any(), f"{int(diff.sum())} 行不一致，首个在 index={int(diff.idxmax())}")
            r.check(f"{tag}demo: 逐行一致: {col}", lock_col)

    ctx[entry] = parsed


def run_checks(path: Path) -> tuple[Runner, Artifact]:
    r = Runner()
    kind = MANIFEST["kind"]

    r.check("提交物名字", lambda: require(path.name == MANIFEST["filename"], f"{path.name} != {MANIFEST['filename']}"))
    art = Artifact.load(path, kind)
    names = art.names()

    # -- 包层 --
    if kind == "zip":
        def zip_safety():
            bad = [n for n in names if n.startswith("/") or ".." in Path(n).parts]
            require(not bad, f"路径不安全的条目: {bad[:5]}")
        r.check("zip 路径安全", zip_safety)
    if kind != "file":
        for pattern in MANIFEST.get("forbid", []):
            def forbid(pat=pattern):
                bad = fnmatch.filter(names, pat)
                require(not bad, f"{bad[:5]}" + (f" …共 {len(bad)} 个" if len(bad) > 5 else ""))
            r.check(f"无禁止条目: {pattern}", forbid)
        def no_extra():
            extra = set(names) - set(MANIFEST["entries"])
            require(not extra, f"清单外条目: {sorted(extra)[:10]}")
        r.check("无清单外条目", no_extra)
    if MANIFEST.get("max_size_mb"):
        limit = MANIFEST["max_size_mb"]
        r.check(
            f"总体积 ≤ {limit}MB",
            lambda: require((sz := art.total_size() / 2**20) <= limit, f"实际 {sz:.1f}MB"),
        )

    # -- 条目层 --
    ctx: dict = {}
    for entry, spec in MANIFEST["entries"].items():
        tag = f"{entry}: " if kind != "file" else ""
        if entry not in names:
            if spec.required:
                r.check(f"{tag}存在", lambda e=entry: require(False, f"缺少必需条目 {e}"))
            continue
        if spec.max_mb is not None:
            r.check(
                f"{tag}体积 ≤ {spec.max_mb}MB",
                lambda e=entry, m=spec.max_mb: require((sz := art.size(e) / 2**20) <= m, f"实际 {sz:.1f}MB"),
            )
        if isinstance(spec, Table):
            def load_table(e=entry, s=spec, t=tag):
                with art.open(e) as fh:
                    check_table(r, t, s, fh, ctx, e)
            r.check(f"{tag}可读取", load_table)
        elif spec.loader is not None:
            def load_file(e=entry, s=spec):
                with art.open(e) as fh:
                    ctx[e] = s.loader(fh)
            r.check(f"{tag}解析", load_file)

    # -- 领域规则层 --
    for fn in RULES:
        def run_rule(f=fn):
            errors = f(ctx)
            if errors:
                head = "; ".join(errors[:5])
                more = f" …共 {len(errors)} 条" if len(errors) > 5 else ""
                raise CheckFailed(head + more)
            return getattr(f, "summary", "")
        r.check(f"规则: {fn.__name__}", run_rule)

    return r, art


def main() -> int:
    ap = argparse.ArgumentParser(description="提交物校验（comp-kit）")
    ap.add_argument("file", type=Path, help="待校验的提交物（文件 / 目录 / zip）")
    ap.add_argument("--log-snippet", action="store_true", help="输出 experiment-log 粘贴块")
    args = ap.parse_args()
    path: Path = args.file

    if not path.exists():
        print(f"[FAIL] 提交物存在 — {path} 不存在")
        return 1

    runner, art = run_checks(path)

    for name, ok, detail in runner.results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    n_ok = sum(ok for _, ok, _ in runner.results)
    print(f"\n{n_ok}/{len(runner.results)} 项通过")

    if not runner.all_ok:
        print("存在 FAIL：禁止提交。")
        return 1

    digest = art.md5()
    size = art.total_size()
    print(f"MD5  {digest}")
    print(f"体积 {size:,} bytes")
    if args.log_snippet:
        print("\n----- experiment-log 粘贴块 -----")
        print(f"- 产物：`{path}`，{len(runner.results)} 项校验全部通过，MD5 `{digest}`。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
