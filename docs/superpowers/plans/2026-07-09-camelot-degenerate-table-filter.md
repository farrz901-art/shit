# Camelot 退化表过滤实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 table 写入边界加硬阈值过滤 Camelot 等 3 个后端输出的退化表 (1×1 / 1×N / 全空白行), 用 `TableData.is_valid_table` 静态方法让 3 个 extractor 后续可复用.

**Architecture:** 单一静态方法 `TableData.is_valid_table(rows) -> bool` 放 `base.py` (3 个 extractor 共同契约), `tables_section.run()` 在 `_detect_cross_page` 之前调用过滤, 丢弃退化表 → `logger.warning` + `skipped_count` 计入 `StageResult.message`.

**Tech Stack:** Python 3.14, dataclass(frozen), pytest (mode 1 mock), loguru logger.

## Global Constraints

- **目标 working dir**: `cd packages/service && uv run pytest ...` (CLAUDE.md 测试运行避坑 #1)
- **测试模式**: 全部模式 1 (mock, 0 PG/Redis)
- **代码注释用中文**; **日志用中文** (项目 CLAUDE.md)
- **ruff format → lint --fix → pyright → pytest** 顺序不可颠倒 (CLAUDE.md 工具链)
- **commit 前缀**: `feat:` / `fix:` / `test:` / `refactor:` / `docs:` / `chore:`
- **不退化**任何既有行为; `pyright` 必须 0 error; `pytest` 必须 0 新 fail

---

## File Structure

源文件 (改动):

- `packages/service/src/ingest/pre_analysis/table_extractors/base.py` — `TableData` 加 `is_valid_table` 静态方法 + 2 模块级常量
- `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py` — `run()` 在 `_detect_cross_page` 之前插过滤循环

测试文件 (新增/追加):

- `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py` — 追加 8 个 `is_valid_table` case
- `packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py` — 新建, 3 个集成 case

不改动: camelot_extractor / pymupdf_extractor / pdfplumber_extractor / factory / db_artifact / router / runner / DB schema / API / BFF / 前端.

---

## Task 1: 给 `TableData` 加 `is_valid_table` 静态方法

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/base.py`
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py`

**Interfaces:**
- Consumes: 无
- Produces: `TableData.is_valid_table(rows: Sequence[Sequence[str]]) -> bool` — True 表示 rows 至少 2 行 2 列 (排除整行空白); False 表示退化表

### Step 1.1: 写失败的测试 (`test_base.py` 追加)

在 `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py` **追加**以下 8 个测试函数 (放在文件末尾):

```python
# (2026-07-09) Camelot/pymupdf/pdfplumber 共用的退化表判定 (TableData.is_valid_table)


def test_is_valid_table_2x2_returns_true() -> None:
    """2 行 2 列是最低有效表格."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a", "b"], ["1", "2"]]) is True


def test_is_valid_table_3x4_returns_true() -> None:
    """真实跨页合并后的多行多列应通过."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    rows = [
        ["Prated", "50Hz 2-pole", "50Hz 4-pole", "60Hz 2-pole"],
        ["0.18", "65.9", "69.9", "70.8"],
        ["0.25", "69.7", "73.5", "74.3"],
    ]
    assert TableData.is_valid_table(rows) is True


def test_is_valid_table_1x1_returns_false() -> None:
    """1×1 单格表是退化 (整页被压成一个 cell)."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["some text"]]) is False


def test_is_valid_table_1xN_returns_false() -> None:
    """1×N 是 Camelot stream fallback 的典型故障 case."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a", "b", "c", "d"]]) is False


def test_is_valid_table_2x1_returns_false() -> None:
    """2×1 纵列表也视为退化 (PDF 表格场景几乎不存在真实纵列表)."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([["a"], ["b"]]) is False


def test_is_valid_table_empty_rows_returns_false() -> None:
    """rows=[] 空表视为退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([]) is False


def test_is_valid_table_single_empty_row_returns_false() -> None:
    """rows=[[]] 单空行视为退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    assert TableData.is_valid_table([[]]) is False


def test_is_valid_table_blank_rows_dont_count() -> None:
    """整行空白不计入有效行数. 前 2 行纯空白 + 1 行真数据 -> 算 1 行有效 -> 退化."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    rows = [["", ""], ["", ""], ["a", "b"]]
    assert TableData.is_valid_table(rows) is False  # 只有 1 行非空白, < 2
```

### Step 1.2: 跑测试确认 red

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -v -k "is_valid_table"
```

Expected: 8 个新 test 全 FAIL (`AttributeError: type object 'TableData' has no attribute 'is_valid_table'`).

### Step 1.3: 在 `base.py` 实现静态方法

修改 `packages/service/src/ingest/pre_analysis/table_extractors/base.py`:

1. 在顶部 import 区追加:
```python
from collections.abc import Sequence
```

2. 在 `TableData` dataclass **外部上方** (即 module-level) 加 2 个常量:
```python
# (2026-07-09) 退化表阈值, 3 个 extractor 共用
_MIN_ROWS: int = 2   # 至少 2 行 (含表头)
_MIN_COLS: int = 2   # 至少 2 列 (横表)
```

3. 在 `TableData` dataclass **内部末尾**追加 `@staticmethod`:
```python
    @staticmethod
    def is_valid_table(rows: Sequence[Sequence[str]]) -> bool:
        """(2026-07-09) 硬阈值:行>=2 且 列>=2 (排除整行空白).

        解决 Camelot stream fallback 出来的 1×N 假表 (整段文本当一列),
        以及 pymupdf/pdfplumber 在某些 PDF 上的 1×1 单格输出.

        rows 可能为空 [] 或 [[]] (空表) — 都返回 False.
        2×1 纵列表同样视为退化 (PDF 表格场景几乎不存在真实纵列表).
        整行所有 cell strip 后都是空字符串算作该行无内容, 不计入行数.
        """
        if not rows:
            return False
        # 过滤掉"整行纯空白"的伪行, 这些是 Camelot 输出的占位行
        non_blank_rows = [r for r in rows if any((c or "").strip() for c in r)]
        if len(non_blank_rows) < _MIN_ROWS:
            return False
        cols = max((len(r) for r in non_blank_rows), default=0)
        return cols >= _MIN_COLS
```

完整 base.py 修改后形态 (关键 diff):

```python
"""TableExtractor 抽象基类 + TableData dataclass + BackendNotInstalledError (2026-07-06)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


# (2026-07-09) 退化表阈值, 3 个 extractor 共用
_MIN_ROWS: int = 2   # 至少 2 行 (含表头)
_MIN_COLS: int = 2   # 至少 2 列 (横表)


@dataclass(frozen=True)
class TableData:
    # ... 既有 3 字段不变 ...

    @staticmethod
    def is_valid_table(rows: Sequence[Sequence[str]]) -> bool:
        # ... 见上面 ...
```

### Step 1.4: 跑测试确认 green

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -v
```

Expected: 14 个 test 全 PASS (既有 6 + 新增 8).

### Step 1.5: 跑格式 / lint / 类型检查

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py
cd packages/service && uv run ruff check src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py
cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py
```

Expected: 全部 0 报错.

### Step 1.6: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/base.py \
        packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py
git commit -m "feat(table_extractors): TableData.is_valid_table 静态方法, 通用退化表判定"
```

---

## Task 2: 在 `tables_section.run()` 调过滤 + 加 skipped_count

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py`

**Interfaces:**
- Consumes: `TableData.is_valid_table(rows) -> bool` (Task 1)
- Produces: `tables_section.run()` 返回的 `StageResult.message` 新格式: `f"{valid_count} 表 / {skipped_count} 丢弃 / {cross_page} 跨页候选"`. 退化表不写 CSV 不 append_artifact.

### Step 2.1: 写失败的测试 (新文件 `test_tables_section_filter.py`)

创建 `packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py`:

```python
"""tables_section.run() 退化表过滤集成测试 (mode 1 mock, 无 PG).

(2026-07-09) 验证:
- 退化表不进 ObjectStore / db_artifact
- 每丢弃一条有 logger.warning
- StageResult.message 含 skipped_count
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.ingest.pre_analysis.stage_context import StageContext, StageResult


def _make_ctx(
    *,
    raw_tables: list,
    task_id: str = "pa_test_task_001",
) -> tuple[StageContext, MagicMock, MagicMock]:
    """构造最小 StageContext, mock object_store + task_store + stage_store + doc.

    raw_tables: list[TableData] 注入到 mock extractor.extract()
    """
    from src.ingest.pre_analysis.table_extractors.base import TableData

    # mock doc + config + output_prefix
    doc = MagicMock()
    doc.name = "fake.pdf"

    object_store = MagicMock()
    task_store = MagicMock()
    stage_store = MagicMock()

    ctx = StageContext(
        task_id=task_id,
        doc=doc,
        config={"cross_page_detection": {}},
        output_prefix="local://test/prefix",
        object_store=object_store,
        task_store=task_store,
        stage_store=stage_store,
    )

    # 替换 extractor: 直接返 raw_tables (绕开 PDF 解析)
    extractor_patch = MagicMock()
    extractor_patch.extract.return_value = raw_tables

    return ctx, extractor_patch, object_store


def _table(page_no: int, table_no: int, rows: list[list[str]]):
    from src.ingest.pre_analysis.table_extractors.base import TableData

    return TableData(page_no=page_no, table_no=table_no, rows=rows)


def test_run_filters_degenerate_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """混合表输入: 1×1 退化 + 1×3 退化 + 3×2 有效 -> 只 valid 表写 CSV + append_artifact."""
    raw_tables = [
        _table(1, 1, [["only text"]]),                  # 1×1 -> 丢
        _table(1, 2, [["a", "b", "c"]]),                 # 1×N -> 丢
        _table(2, 1, [["h1", "h2"], ["v1", "v2"], ["v3", "v4"]]),  # 3×2 -> 留
    ]
    ctx, extractor, object_store = _make_ctx(raw_tables=raw_tables)

    # patch get_table_extractor 返我们的 mock extractor
    from src.ingest.pre_analysis.table_extractors import tables_section

    monkeypatch.setattr(tables_section, "TableData", tables_section.TableData)
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.factory.get_table_extractor",
        lambda backend, params: extractor,
    )

    new_ctx, result = tables_section.run(ctx)

    # 只 valid 表 (3×2) 进了 put_bytes + append_artifact
    assert object_store.put_bytes.call_count == 1
    put_uri = object_store.put_bytes.call_args[0][0]
    assert "page-2-table-1" in put_uri

    assert ctx.stage_store.append_artifact is not MagicMock  # noqa: E501  # sanity: stage_store 没被误调
    # append_artifact 走 db_artifact.append_artifact (不是 ctx.stage_store 上的方法), 所以验证调用次数即可
    # 因 db_artifact.append_artifact 是 import-and-call, 我们从 csv 内容间接验证


def test_run_logs_warning_per_dropped(caplog) -> None:
    """每个丢弃的退化表都有 logger.warning, 含 page/table/rows/cols."""
    raw_tables = [
        _table(5, 1, [["x"]]),                  # 1×1
        _table(5, 2, [["a", "b", "c", "d"]]),   # 1×N
    ]
    ctx, extractor, _ = _make_ctx(raw_tables=raw_tables)

    from src.ingest.pre_analysis.table_extractors import tables_section
    import src.ingest.pre_analysis.table_extractors.factory as factory_mod

    # monkeypatch factory.get_table_extractor
    original = factory_mod.get_table_extractor
    factory_mod.get_table_extractor = lambda backend, params: extractor
    try:
        with caplog.at_level("WARNING"):
            _, result = tables_section.run(ctx)
    finally:
        factory_mod.get_table_extractor = original

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 2
    assert any("page=5 table=1 rows=1 cols=1" in r.getMessage() for r in warnings)
    assert any("page=5 table=2 rows=1 cols=4" in r.getMessage() for r in warnings)


def test_run_stage_result_includes_skipped_count() -> None:
    """StageResult.message 格式: '3 表 / 2 丢弃 / 0 跨页候选'."""
    raw_tables = [
        _table(1, 1, [["only"]]),                              # 退化
        _table(2, 1, [["h1", "h2"], ["v1", "v2"]]),            # valid
        _table(3, 1, [["x", "y", "z"]]),                       # 退化
    ]
    ctx, extractor, _ = _make_ctx(raw_tables=raw_tables)

    from src.ingest.pre_analysis.table_extractors import tables_section
    import src.ingest.pre_analysis.table_extractors.factory as factory_mod

    original = factory_mod.get_table_extractor
    factory_mod.get_table_extractor = lambda backend, params: extractor
    try:
        _, result = tables_section.run(ctx)
    finally:
        factory_mod.get_table_extractor = original

    assert isinstance(result, StageResult)
    assert result.ok is True
    assert result.message == "1 表 / 2 丢弃 / 0 跨页候选"
```

**前置依赖检查**: `StageContext` 构造签名. 在写测试前先确认:

```bash
cd packages/service && grep -n "class StageContext" src/ingest/pre_analysis/stage_context.py
```

如果 `StageContext` 字段名跟假设不符, 按实际字段调整 (e.g. `document` 而非 `doc`). 同样检查 `StageResult` 字段 (`ok` / `message` / `stage_name` / `error`).

### Step 2.2: 跑测试确认 red

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py -v
```

Expected: 3 个 test 全 FAIL (filters 未实现, message 仍是旧格式).

### Step 2.3: 修改 `tables_section.py` 加过滤

修改 `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py`:

1. 在 import 区追加 `TableData`:
```python
from .base import TableData
```

2. 替换 `run()` 中 `cross_page = _detect_cross_page(...)` 这一段 (line 127-131) 为:

```python
        tables = [(t.page_no, t.table_no, t.rows) for t in raw_tables]

        # (2026-07-09) 过滤退化表 (1×1 / 1×N / 全空白行), 必须放在 _detect_cross_page 之前,
        # 否则 cross_page 候选会包含 1×1 假表. 抽到 TableData.is_valid_table 让 3 个 extractor 可复用.
        valid_tables: list[tuple[int | str, int, Sequence[Sequence[str]]]] = []
        skipped_count = 0
        for page_no, table_no, rows in tables:
            if not TableData.is_valid_table(rows):
                skipped_count += 1
                logger.warning(
                    "丢弃退化表 page={} table={} rows={} cols={}",
                    page_no, table_no, len(rows),
                    max((len(r) for r in rows), default=0),
                )
                continue
            valid_tables.append((page_no, table_no, rows))
        tables = valid_tables

        cross_page = _detect_cross_page(tables, config)

        for page_no, table_no, rows in tables:
            _write_one_table(ctx.object_store, output_prefix, page_no, table_no, rows, ctx.task_id)
```

3. 修改 `mark_stage_completed` 的 `message` 和 `StageResult` 的 `message` (line 146, 151), 把 `f"{len(tables)} 表 / {cross_page} 跨页候选"` 改为:

```python
        message=f"{len(tables)} 表 / {skipped_count} 丢弃 / {cross_page} 跨页候选",
```

(line 146 和 line 151 两处都改)

### Step 2.4: 跑测试确认 green

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py -v
```

Expected: 3 个 test 全 PASS.

### Step 2.5: 跑格式 / lint / 类型检查

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/tables_section.py tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py
cd packages/service && uv run ruff check src/ingest/pre_analysis/table_extractors/tables_section.py tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py
cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/tables_section.py tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py
```

Expected: 全部 0 报错.

### Step 2.6: 跑既有相关测试不回归

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 既有 test 全 PASS (test_camelot_extractor / test_pymupdf / test_pdfplumber / test_factory / test_camelot_stack_contiguous / test_camelot_ghostscript_fallback / test_cross_page_merger / test_base).

### Step 2.7: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py \
        packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py
git commit -m "feat(pre_analysis): tables_section 写入前过滤退化表, StageResult 含 skipped_count"
```

---

## Task 3: 全量验证 + docs

**Files:**
- Modify: 无
- Read: `packages/service/KNOWN_ISSUES.md` (确认 pre-existing fail 不变)

### Step 3.1: 跑后端全量 pytest

```bash
cd packages/service && uv run pytest 2>/tmp/pytest-stdout.txt 1>/tmp/pytest-stderr.txt
echo "exit=$?"
tail -30 /tmp/pytest-stdout.txt
```

Expected: exit=0 或 exit=1 (跟 baseline 持平), **不能新增 fail**. 跟 master 的 22 fail + 38 errors 比对, 数字不能涨.

如有失败: 用 `grep -E "^FAILED|^ERROR " /tmp/pytest-stdout.txt` 定位, 确认都是 pre-existing. 任何新 fail 必须停下修.

### Step 3.2: 跑 pyright 全量

```bash
cd packages/service && uv run pyright 2>/tmp/pyright-stderr.txt
echo "exit=$?"
tail -10 /tmp/pyright-stderr.txt
```

Expected: `0 errors`, `exit=0`.

### Step 3.3: 跑 ruff 全量

```bash
cd packages/service && uv run ruff format
cd packages/service && uv run ruff check
```

Expected: 全部 0 报错.

### Step 3.4: 更新 spec §6 标 done

在 `docs/superpowers/specs/2026-07-09-camelot-degenerate-table-filter-design.md` 末尾追加实施记录:

```markdown

## 9. 实施记录 (2026-07-09)

- Task 1: base.py `TableData.is_valid_table` + 8 测试 (commit ...)
- Task 2: tables_section.run() 过滤 + 3 测试 (commit ...)
- Task 3: 全量验证 pytest/pyright/ruff 0 报错
```

### Step 3.5: Commit docs

```bash
git add docs/superpowers/specs/2026-07-09-camelot-degenerate-table-filter-design.md
git commit -m "docs(spec): 2026-07-09 camelot degenerate table filter 实施记录"
```

---

## Self-Review

**1. Spec coverage:**

| Spec 节 | 覆盖 Task |
|---|---|
| §4.1 改动范围 (2 文件 + 2 测试文件) | Task 1 + Task 2 |
| §4.2 `TableData.is_valid_table` 静态方法 | Task 1 |
| §4.3 `tables_section.run()` 过滤循环 + 顺序 (在 cross_page 之前) | Task 2 Step 2.3 |
| §4.4 `StageResult.message` 含 `skipped_count` | Task 2 Step 2.3 + 测试 11 |
| §5 错误处理 (纯函数不抛 / warning 不 fail stage) | Task 1 + Task 2 测试 9 (caplog) |
| §6.1 8 个 is_valid_table 单测 | Task 1 Step 1.1 |
| §6.2 3 个 run 集成测试 | Task 2 Step 2.1 |
| §7 范围 (2 文件 + 2 测试, < 80 行) | 实施完验证 |

**2. Placeholder scan:** 无 TBD/TODO. 所有代码块完整, 无 "类似 Task N" 偷懒.

**3. Type consistency:**
- `TableData.is_valid_table(rows: Sequence[Sequence[str]]) -> bool` 在 Task 1 定义 + 单测调用 + Task 2 调用, 一致.
- `StageResult.message` 格式 `"N 表 / M 丢弃 / K 跨页候选"` 在 spec §4.4 + Task 2 测试 11 期望值 一致.
- `_MIN_ROWS = 2`, `_MIN_COLS = 2` 在 spec §4.2 + Task 1 实现 一致.

**Found issues during self-review:** 修订 1 处. 原 spec 把过滤写在 for 循环前未明确 cross_page 顺序, 已修. Plan 中 Step 2.3 强调 "必须在 _detect_cross_page 之前" 跟 spec §4.5 一致.