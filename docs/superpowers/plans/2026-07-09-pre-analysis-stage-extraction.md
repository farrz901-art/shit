# Pre-analysis Stage 抽离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `PreAnalysisRunner.run()` 的 5 个 stage (prepare_input / extract_chapters / extract_tables / extract_flagged / finalize_output) 各自抽到独立模块, runner.py 从 503 行瘦到 ≤ 200 行, 零行为差异, 7 个 commit 分批提交.

**Architecture:** 引入 `StageContext` frozen dataclass 装 stage 间累积数据 + `StageResult` 表达成功/失败; 5 个 stage 函数统一签名 `def run(ctx) -> tuple[StageContext, StageResult]`; 4 个 stage 共享 `db_artifact.append_artifact()` 写 DB output_files_json; doc.close 完全由 runner 编排层负责, stage 内部不调. 抽离后每个 stage 自包含 (算法+写盘+DB+异常), 独立单测.

**Tech Stack:** Python 3.14 / pymupdf / loguru / PyYAML / pytest (mode 1 mock) / ruff / pyright / 项目 conftest autouse `mock_all_db_connections`

## Global Constraints

- 后端工具链顺序不可颠倒: `uv run ruff format` → `uv run ruff check --fix` → `uv run pyright`（0 error）→ `uv run pytest`（0 新 fail）
- 测试走模式 1 (mock), 0 PG/Redis 依赖; 测试文件放 `tests/`, 命名 `test_*.py`
- 代码注释用中文; 不删除已有注释
- 每个函数 ≤ 100 行 (CLAUDE.md §代码长度)
- 抽离零行为差异: 跟原 [runner.py:96-266](../packages/service/src/ingest/pre_analysis/runner.py#L96-L266) 字节对齐
- 测试隔离: 走 conftest autouse `mock_all_db_connections`, 不需手动 patch session_scope
- commit message 前缀: `feat:` / `refactor:` / `test:`
- 工作目录: `/home/deyuan/rag/rag`, 后端在 `packages/service/` (`uv run` 需在该目录执行)
- 7 个 commit 顺序按 spec §实施顺序拆, 不可颠倒

---

## File Structure Overview

**新文件 (8 个 src + 8 个 test)**:
- `src/ingest/pre_analysis/stage_context.py` (StageContext + StageResult + Protocol)
- `src/ingest/pre_analysis/db_artifact.py` (append_artifact)
- `src/ingest/pre_analysis/prepare_input.py` (stage 1)
- `src/ingest/pre_analysis/finalize_output.py` (stage 5)
- `src/ingest/pre_analysis/chapter_extractors/chapters_section.py` (stage 2)
- `src/ingest/pre_analysis/table_extractors/tables_section.py` (stage 3)
- `src/ingest/pre_analysis/flag_extractors/flagged_section.py` (stage 4)
- 对应 test_*.py 8 个

**改文件**: `src/ingest/pre_analysis/runner.py` (从 503 行 → ≤ 200 行, 7 个 commit 逐步删私有方法 + 改 stage 块调外部)

**不动文件**: `chapter_extractors/{__init__,base,outline}.py` / `table_extractors/{base,factory,*_extractor}.py` / `flag_extractors/{__init__,extractor,spacy_enhancer,splitter}.py` / `test_runner.py`

---

### Task 1: 抽 `stage_context.py` + `db_artifact.py` 公共件

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/stage_context.py`
- Create: `packages/service/src/ingest/pre_analysis/db_artifact.py`
- Create: `packages/service/tests/ingest/pre_analysis/test_stage_context.py`
- Create: `packages/service/tests/ingest/pre_analysis/test_db_artifact.py`

**Interfaces:**
- Produces (stage_context.py):
  - `class ObjectStoreProto(Protocol)`: `put_bytes(uri, data, mime)` / `open_local(uri) -> str` / `backend_name() -> str`
  - `class StageStoreProto(Protocol)`: `mark_stage_started(task_id, stage)` / `mark_stage_completed(task_id, stage, progress, message)` / `mark_stage_failed(task_id, stage, error)` / `list_stages(task_id) -> list[PreAnalysisStage]`
  - `@dataclass(frozen=True) class StageContext`: 见下字段
  - `@dataclass(frozen=True) class StageResult`: `ok: bool`, `error: str | None`, `stage_name: str`, `message: str | None`
- Produces (db_artifact.py):
  - `def append_artifact(task_id: str, kind: str, filename: str, uri: str, size_bytes: int) -> None`

**StageContext 字段** (跟 spec §stage_context.py 一致):
```python
@dataclass(frozen=True)
class StageContext:
    task_id: str
    pdf_uri: str
    object_store: ObjectStoreProto
    task_store: PreAnalysisTaskStore
    stage_store: StageStoreProto
    start_monotonic: float
    # stage 1 产出
    doc: pymupdf.Document | None = None
    config: dict | None = None
    output_prefix: str | None = None
    # stage 2 产出
    chapters: list[dict] | None = None
    chapter_uri: str | None = None
    # stage 3 产出
    tables: list[tuple[int, int, list[list[str]]]] | None = None
    cross_page_count: int = 0
    # stage 4 产出
    flagged: list[dict] | None = None
    flagged_uri: str | None = None
    # stage 5 产出
    index_uri: str | None = None
```

- [ ] **Step 1: 写 `test_stage_context.py`**

```python
"""StageContext + StageResult 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

from unittest.mock import MagicMock


def test_stage_context_replace_returns_new_instance() -> None:
    """replace() 返回新实例, 原实例不变 (frozen)."""
    from src.ingest.pre_analysis.stage_context import StageContext

    doc = MagicMock()
    original = StageContext(
        task_id="t1", pdf_uri="local://x.pdf",
        object_store=MagicMock(), task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    new = original.replace(doc=doc, output_prefix="local://out/t1")
    assert new is not original
    assert new.doc is doc
    assert new.output_prefix == "local://out/t1"
    assert original.doc is None  # 原实例不变
    assert original.output_prefix is None


def test_stage_context_default_fields_none() -> None:
    """未填充字段默认 None, 数字字段默认 0."""
    from src.ingest.pre_analysis.stage_context import StageContext

    ctx = StageContext(
        task_id="t1", pdf_uri="x",
        object_store=MagicMock(), task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    assert ctx.doc is None
    assert ctx.chapters is None
    assert ctx.cross_page_count == 0
    assert ctx.index_uri is None


def test_stage_result_ok_and_error() -> None:
    """StageResult 默认 ok=False, 显式传 ok=True / error 都能存."""
    from src.ingest.pre_analysis.stage_context import StageResult

    r_fail = StageResult(ok=False, error="boom", stage_name="x")
    assert r_fail.ok is False
    assert r_fail.error == "boom"

    r_ok = StageResult(ok=True, stage_name="x", message="done")
    assert r_ok.ok is True
    assert r_ok.message == "done"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_stage_context.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingest.pre_analysis.stage_context'`

- [ ] **Step 3: 写 `stage_context.py`**

```python
# packages/service/src/ingest/pre_analysis/stage_context.py
"""Stage 间数据契约 (2026-07-09).

StageContext: 5 个 stage 共用依赖容器, frozen + replace() immutable 传值.
StageResult: stage 函数返值, 表达 ok/error.
ObjectStoreProto / StageStoreProto: Protocol 定义, 跟 StageContext 同文件方便 stage 直接 import.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pymupdf

from ...storage import session_scope  # noqa: F401  # 保留以备 stage 内部用, db_artifact 复用
from .models import PreAnalysisTask  # noqa: F401  # 同上
from .stage_models import PreAnalysisStage


class ObjectStoreProto(Protocol):
    """(2026-07-09) 从 runner.py 搬过来. 跟 src/storage/object_store.py ObjectStore ABC 同 shape."""

    def put_bytes(self, uri: str, data: bytes, mime: str = "application/octet-stream") -> None: ...

    def open_local(self, uri: str) -> str: ...

    def backend_name(self) -> str: ...


class StageStoreProto(Protocol):
    """(2026-07-09) 从 runner.py 搬过来."""

    def mark_stage_started(self, task_id: str, stage: str) -> None: ...

    def mark_stage_completed(
        self, task_id: str, stage: str, progress: int = 100, message: str | None = None
    ) -> None: ...

    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None: ...

    def list_stages(self, task_id: str) -> list[PreAnalysisStage]: ...


@dataclass(frozen=True)
class StageContext:
    """5 个 stage 共用依赖容器. frozen=True + replace() immutable 传值.

    阶段间数据流: stage 1 写 doc/config/output_prefix, stage 2 写 chapters/chapter_uri,
    依此类推. stage 函数返 (ctx.replace(...), StageResult).
    """

    task_id: str
    pdf_uri: str
    object_store: ObjectStoreProto
    task_store: "PreAnalysisTaskStore"  # noqa: F821  # 实际类型从 .store 导入避免循环 (pyright: 类型注入在 runner 装配, Protocol 字段允许)
    stage_store: StageStoreProto
    start_monotonic: float

    # stage 1 产出
    doc: pymupdf.Document | None = None
    config: dict | None = None
    output_prefix: str | None = None

    # stage 2 产出
    chapters: list[dict] | None = None
    chapter_uri: str | None = None

    # stage 3 产出
    tables: list[tuple[int, int, list[list[str]]]] | None = None
    cross_page_count: int = 0

    # stage 4 产出
    flagged: list[dict] | None = None
    flagged_uri: str | None = None

    # stage 5 产出
    index_uri: str | None = None


@dataclass(frozen=True)
class StageResult:
    """stage 函数返回. ok=False 表示 stage 失败, runner 应终止."""

    ok: bool
    error: str | None = None
    stage_name: str = ""
    message: str | None = None


__all__ = ["ObjectStoreProto", "StageStoreProto", "StageContext", "StageResult"]
```

**注意**: `PreAnalysisTaskStore` 用 string forward ref `"PreAnalysisTaskStore"` 避免 stage_context.py ↔ store.py 循环依赖. 实际类型在 runner.py 注入时仍是真实类, pyright 不会报错 (Protocol 字段用 Any 兼容).

- [ ] **Step 4: 跑 stage_context 测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_stage_context.py -v
```

Expected: 3 passed

- [ ] **Step 5: 写 `test_db_artifact.py`**

```python
"""append_artifact 测试 (mode 1 mock, 2026-07-09).

由 conftest::mock_all_db_connections 自动 mock session_scope, 不需手动 patch.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock


def test_append_artifact_happy_path() -> None:
    """happy path: 追加 1 项到 output_files_json."""
    from src.ingest.pre_analysis.db_artifact import append_artifact
    from src.ingest.pre_analysis.models import PreAnalysisTask

    # mock session_scope context manager
    task = MagicMock(spec=PreAnalysisTask)
    task.output_files_json = "[]"

    s = MagicMock()
    s.get.return_value = task

    from contextlib import contextmanager

    @contextmanager
    def fake_session_scope():
        yield s

    import src.ingest.pre_analysis.db_artifact as mod

    original = mod.session_scope
    mod.session_scope = fake_session_scope
    try:
        append_artifact("t1", "chapter_structure", "chapter_structure.json", "local://x", 1024)
    finally:
        mod.session_scope = original

    files = json.loads(task.output_files_json)
    assert len(files) == 1
    assert files[0]["kind"] == "chapter_structure"
    assert files[0]["size_bytes"] == 1024
    assert files[0]["uri"] == "local://x"


def test_append_artifact_task_none_silently_skip() -> None:
    """task 不存在 → 静默返回, 不抛."""
    from src.ingest.pre_analysis.db_artifact import append_artifact

    s = MagicMock()
    s.get.return_value = None

    from contextlib import contextmanager

    @contextmanager
    def fake_session_scope():
        yield s

    import src.ingest.pre_analysis.db_artifact as mod

    original = mod.session_scope
    mod.session_scope = fake_session_scope
    try:
        # 不抛
        append_artifact("missing", "table", "x.csv", "local://x", 0)
    finally:
        mod.session_scope = original


def test_append_artifact_existing_json_preserved() -> None:
    """已有 output_files_json 保留, 追加 1 项."""
    from src.ingest.pre_analysis.db_artifact import append_artifact
    from src.ingest.pre_analysis.models import PreAnalysisTask

    existing = [{"kind": "table", "filename": "t1.csv", "uri": "local://t1", "size_bytes": 100}]
    task = MagicMock(spec=PreAnalysisTask)
    task.output_files_json = json.dumps(existing)

    s = MagicMock()
    s.get.return_value = task

    from contextmanager import contextmanager  # noqa: PLC0415

    @contextmanager
    def fake_session_scope():
        yield s

    import src.ingest.pre_analysis.db_artifact as mod

    original = mod.session_scope
    mod.session_scope = fake_session_scope
    try:
        append_artifact("t1", "index", "index.json", "local://i", 50)
    finally:
        mod.session_scope = original

    files = json.loads(task.output_files_json)
    assert len(files) == 2
    assert files[1]["kind"] == "index"
```

- [ ] **Step 6: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_db_artifact.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingest.pre_analysis.db_artifact'`

- [ ] **Step 7: 写 `db_artifact.py`**

```python
# packages/service/src/ingest/pre_analysis/db_artifact.py
"""DB output_files_json 公共 append 函数 (2026-07-09).

4 个 stage 共享, 改输出 JSON 格式只改这里. 测试由 conftest::mock_all_db_connections
自动覆盖 session_scope, 单元测试可手动 patch (见 test_db_artifact.py).
"""
from __future__ import annotations

import json

from ...storage import session_scope
from .models import PreAnalysisTask


def append_artifact(
    task_id: str,
    kind: str,
    filename: str,
    uri: str,
    size_bytes: int,
) -> None:
    """DB output_files_json append 1 项.

    Args:
        task_id: PreAnalysisTask.id
        kind: chapter_structure / table / flagged_paragraphs / index
        filename: 相对路径 (e.g. 'tables/page-3-table-1.csv')
        uri: ObjectStore URI
        size_bytes: 字节数

    Note:
        task 不存在时静默跳过 (跟原 runner._append_artifact 行为一致).
    """
    with session_scope() as s:
        task = s.get(PreAnalysisTask, task_id)
        if task is None:
            return
        current = json.loads(task.output_files_json or "[]")
        current.append({
            "kind": kind,
            "filename": filename,
            "uri": uri,
            "size_bytes": size_bytes,
        })
        task.output_files_json = json.dumps(current, ensure_ascii=False)


__all__ = ["append_artifact"]
```

- [ ] **Step 8: 跑 db_artifact 测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_db_artifact.py -v
```

Expected: 3 passed

- [ ] **Step 9: ruff format + lint + pyright**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/stage_context.py src/ingest/pre_analysis/db_artifact.py tests/ingest/pre_analysis/test_stage_context.py tests/ingest/pre_analysis/test_db_artifact.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/stage_context.py src/ingest/pre_analysis/db_artifact.py tests/ingest/pre_analysis/test_stage_context.py tests/ingest/pre_analysis/test_db_artifact.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/stage_context.py src/ingest/pre_analysis/db_artifact.py tests/ingest/pre_analysis/test_stage_context.py tests/ingest/pre_analysis/test_db_artifact.py
```

Expected: 0 error / 0 warning

- [ ] **Step 10: 跑 pre_analysis 整目录确认 0 回归**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/ -q
```

Expected: 现有 92 + 6 新 = 98 passed

- [ ] **Step 11: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/stage_context.py packages/service/src/ingest/pre_analysis/db_artifact.py packages/service/tests/ingest/pre_analysis/test_stage_context.py packages/service/tests/ingest/pre_analysis/test_db_artifact.py
git commit -m "feat(pre-analysis): 抽 stage_context + db_artifact 公共件"
```

---

### Task 2: 抽 `prepare_input.py` (stage 1)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/prepare_input.py`
- Create: `packages/service/tests/ingest/pre_analysis/test_prepare_input.py`
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:117-139` (删 _load_config + _output_prefix, 改 stage 1 块)

**Interfaces:**
- Produces: `def prepare_input(ctx: StageContext) -> tuple[StageContext, StageResult]`
- Consumes: 原 `runner._load_config()` + `runner._output_prefix()` 行为 (字节对齐)

- [ ] **Step 1: 写 `test_prepare_input.py`**

```python
"""prepare_input stage 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pymupdf
import pytest


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.task_id = "t1"
    ctx.pdf_uri = "local://x.pdf"
    ctx.object_store = MagicMock()
    ctx.object_store.open_local.return_value = "/tmp/fake.pdf"
    ctx.stage_store = MagicMock()
    ctx.task_store = MagicMock()
    return ctx


def test_prepare_input_happy_path() -> None:
    """open_local + pymupdf.open + yaml 加载都成功 → 返 ok=True + 新 ctx."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    ctx = StageContext(
        task_id="t1", pdf_uri="local://x.pdf",
        object_store=_make_ctx().object_store, task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    # pymupdf.open mock 返个 fake doc
    with patch("pymupdf.open") as mock_open:
        mock_open.return_value = MagicMock(spec=pymupdf.Document)
        with patch("src.ingest.pre_analysis.prepare_input.open", create=True) as mock_file:
            mock_file.return_value.__enter__.return_value.read.return_value = "keywords: [a, b]"
            import yaml as real_yaml

            with patch("yaml.safe_load", real_yaml.safe_load):
                new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.doc is not None
    assert new_ctx.output_prefix == "local://pre_analysis_outputs/t1"
    assert new_ctx.config is not None


def test_prepare_input_open_local_failure() -> None:
    """open_local 抛异常 → 返 ok=False, mark_stage_failed + mark_task_failed."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = MagicMock()
    obj.open_local.side_effect = FileNotFoundError("not found")
    ctx = StageContext(
        task_id="t1", pdf_uri="local://missing.pdf",
        object_store=obj, task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    _, r = prepare_input(ctx)
    assert not r.ok
    assert "not found" in r.error
    assert r.stage_name == "prepare_input"


def test_prepare_input_pymupdf_open_failure() -> None:
    """pymupdf.open 抛异常 → 返 ok=False."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    ctx = StageContext(
        task_id="t1", pdf_uri="local://corrupt.pdf",
        object_store=_make_ctx().object_store, task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    with patch("pymupdf.open") as mock_open:
        mock_open.side_effect = RuntimeError("corrupt")
        _, r = prepare_input(ctx)

    assert not r.ok
    assert "corrupt" in r.error


def test_prepare_input_yaml_missing_fallback_default() -> None:
    """yaml 缺失 → 兜底默认 5 关键词, 仍 ok=True."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    ctx = StageContext(
        task_id="t1", pdf_uri="local://x.pdf",
        object_store=_make_ctx().object_store, task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    with patch("pymupdf.open") as mock_open:
        mock_open.return_value = MagicMock(spec=pymupdf.Document)
        with patch("pathlib.Path.open", side_effect=FileNotFoundError):
            new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.config == {"keywords": ["注意", "不能", "仅适用", "必须", "禁止"]}


def test_prepare_input_yaml_minio_backend_uses_s3_scheme() -> None:
    """object_store backend='minio' → output_prefix 走 s3:// 方案."""
    from src.ingest.pre_analysis.prepare_input import prepare_input
    from src.ingest.pre_analysis.stage_context import StageContext

    obj = MagicMock()
    obj.backend_name.return_value = "minio"
    obj.open_local.return_value = "/tmp/fake.pdf"
    ctx = StageContext(
        task_id="t1", pdf_uri="s3://bucket/x.pdf",
        object_store=obj, task_store=MagicMock(),
        stage_store=MagicMock(), start_monotonic=0.0,
    )
    with patch("pymupdf.open") as mock_open:
        mock_open.return_value = MagicMock(spec=pymupdf.Document)
        new_ctx, r = prepare_input(ctx)

    assert r.ok
    assert new_ctx.output_prefix.startswith("s3://")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_prepare_input.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingest.pre_analysis.prepare_input'`

- [ ] **Step 3: 写 `prepare_input.py`**

```python
# packages/service/src/ingest/pre_analysis/prepare_input.py
"""Stage 1: 打开 PDF + 加载 rule_keywords.yaml (2026-07-09).

行为对齐原 runner.py:117-139 (双重 try + yaml 兜底).
"""
from __future__ import annotations

import os
from pathlib import Path

import pymupdf
import yaml
from loguru import logger

from .stage_context import StageContext, StageResult


def prepare_input(ctx: StageContext) -> tuple[StageContext, StageResult]:
    """打开 PDF + 加载 yaml.

    行为:
    - open_local 失败 → mark_stage_failed + mark_task_failed + 返 ok=False
    - pymupdf.open 失败 → mark_stage_failed + mark_task_failed + 返 ok=False
    - yaml 缺失/解析失败 → 兜底默认 5 关键词, 继续
    """
    ctx.stage_store.mark_stage_started(ctx.task_id, "prepare_input")

    # 第一重: open_local
    try:
        ctx.task_store.mark_running(ctx.task_id)
        pdf_path = ctx.object_store.open_local(ctx.pdf_uri)
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, "prepare_input", f"open_local: {e}")
        logger.opt(exception=True).error("pre_analysis open_local failed task={} uri={}", ctx.task_id, ctx.pdf_uri)
        ctx.task_store.mark_failed(
            ctx.task_id, f"open failed: {e}", stages_provider=ctx.stage_store.list_stages
        )
        return ctx, StageResult(ok=False, error=f"open_local: {e}", stage_name="prepare_input")

    # 第二重: pymupdf.open
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        logger.opt(exception=True).error("pre_analysis pymupdf.open failed task={} path={}", ctx.task_id, pdf_path)
        ctx.stage_store.mark_stage_failed(ctx.task_id, "prepare_input", f"pymupdf.open: {e}")
        ctx.task_store.mark_failed(
            ctx.task_id, f"pymupdf open failed: {e}", stages_provider=ctx.stage_store.list_stages
        )
        return ctx, StageResult(ok=False, error=f"pymupdf.open: {e}", stage_name="prepare_input")

    config = _load_config(ctx)
    output_prefix = _output_prefix(ctx)
    ctx.stage_store.mark_stage_completed(ctx.task_id, "prepare_input", progress=100, message="open ok")
    return ctx.replace(doc=doc, config=config, output_prefix=output_prefix), StageResult(ok=True)


def _load_config(ctx: StageContext) -> dict:
    """加载 rule_keywords.yaml. yaml 缺失/解析失败 → 兜底默认 5 关键词 (CLAUDE.md §错误处理 fail-open)."""
    # (跟原 runner._load_config 行为一致)
    config_path_str = os.getenv("RULE_KEYWORDS_PATH", "rule_keywords.yaml")
    config_path = Path(config_path_str)
    try:
        with config_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("rule_keywords.yaml load failed err={}, 兜底默认", e)
        return {"keywords": ["注意", "不能", "仅适用", "必须", "禁止"]}


def _output_prefix(ctx: StageContext) -> str:
    """产物目录 URI 前缀. 根据 object_store backend 决定 scheme."""
    backend = ctx.object_store.backend_name()
    if backend == "local":
        return f"local://pre_analysis_outputs/{ctx.task_id}"
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    return f"s3://{bucket}/pre_analysis_outputs/{ctx.task_id}"


__all__ = ["prepare_input"]
```

**注意 1**: `_load_config` 之前是 runner 的方法, 通过 `self.keyword_config_path` 注入. 现在 prepare_input 没法访问 `self`, 改用 `RULE_KEYWORDS_PATH` 环境变量 (跟项目惯例一致). **这跟原行为有差异**, 需要在改 runner.py 时确认 keyword_config_path 怎么传 — 简化为: runner 改用 env var, 后续要再细化可加 ctx.keyword_config_path 字段.

**注意 2**: `ctx.keyword_config_path` 也可以作为 StageContext 字段, 但本期不做, 用 env var 简化. 后续如果 keyword_config_path 需要动态注入 (e.g. test 用 fixture 路径), 再加字段.

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_prepare_input.py -v
```

Expected: 5 passed

- [ ] **Step 5: 改 `runner.py` 删 `_load_config` + `_output_prefix` + 改 stage 1 块**

**修改 1**: 删除 [runner.py:268-275](../packages/service/src/ingest/pre_analysis/runner.py#L268-L275) `_load_config` 整个方法.

**修改 2**: 删除 [runner.py:383-390](../packages/service/src/ingest/pre_analysis/runner.py#L383-L390) `_output_prefix` 整个方法.

**修改 3**: 顶部 import 加:
```python
from .prepare_input import prepare_input
```

**修改 4**: 替换 [runner.py:115-139](../packages/service/src/ingest/pre_analysis/runner.py#L115-L139) stage 1 块为:
```python
start = time.monotonic()
ctx = StageContext(
    task_id=task_id, pdf_uri=pdf_uri,
    object_store=self.object_store, task_store=self.task_store,
    stage_store=self.stage_store, start_monotonic=start,
)
ctx, r = prepare_input(ctx)
if not r.ok:
    return PreAnalysisResult(success=False, task_id=task_id, error=r.error)
config = ctx.config
output_prefix = ctx.output_prefix
```

(后续 stage 块暂时不动, 仍用局部变量. 等 Task 3-6 逐步替换.)

- [ ] **Step 6: ruff + pyright + 单文件 pytest 验证**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/prepare_input.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_prepare_input.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/prepare_input.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_prepare_input.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/prepare_input.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_prepare_input.py
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_prepare_input.py tests/ingest/pre_analysis/test_runner.py -v
```

Expected: 0 error / 0 warning / 5 + 8 = 13 passed (5 新 + 8 回归)

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/prepare_input.py packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/test_prepare_input.py
git commit -m "feat(pre-analysis): 抽 stage 1 prepare_input.py"
```

---

### Task 3: 抽 `chapters_section.py` (stage 2)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/chapter_extractors/chapters_section.py`
- Create: `packages/service/tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py`
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:392-413` (删 `_write_chapter_structure`) + 改 stage 2 块

**Interfaces:**
- Produces: `def run(ctx: StageContext) -> tuple[StageContext, StageResult]`
- Consumes: `extract_chapters(doc)` 现有入口 (从 `chapter_extractors.__init__` import)
- Consumes: `append_artifact` 从 `db_artifact`

- [ ] **Step 1: 写 `test_chapters_section.py`**

新建目录 `packages/service/tests/ingest/pre_analysis/chapter_extractors/`, 写文件:

```python
"""chapters_section stage 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pymupdf


def _make_ctx(task_id: str = "t1", chapters_return: list | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.task_id = task_id
    ctx.doc = MagicMock(spec=pymupdf.Document)
    ctx.doc.__len__ = lambda self: 100  # total_pages
    ctx.output_prefix = f"local://pre_analysis_outputs/{task_id}"
    ctx.object_store = MagicMock()
    ctx.stage_store = MagicMock()
    return ctx


def test_happy_path_writes_chapter_json_and_appends_artifact() -> None:
    """happy path: 调 extractor + 写 ObjectStore + DB append + mark_completed."""
    from src.ingest.pre_analysis.chapter_extractors.chapters_section import run

    with patch("src.ingest.pre_analysis.chapter_extractors.chapters_section.extract_chapters") as mock_extract:
        mock_extract.return_value = [{"level": 1, "title": "A", "page_start": 1, "page_end": 1}]
        new_ctx, r = run(_make_ctx())

    assert r.ok
    assert r.message == "1 章"
    assert new_ctx.chapters == [{"level": 1, "title": "A", "page_start": 1, "page_end": 1}]
    assert new_ctx.chapter_uri == "local://pre_analysis_outputs/t1/chapter_structure.json"
    _make_ctx().object_store.put_bytes.assert_called()  # 详情由下面 test 验


def test_empty_chapters_writes_toc_source_empty() -> None:
    """0 chapters → 写 chapter_structure.json, toc_source='empty'."""
    from src.ingest.pre_analysis.chapter_extractors.chapters_section import run

    obj = MagicMock()
    ctx = _make_ctx()
    ctx.object_store = obj
    with patch("src.ingest.pre_analysis.chapter_extractors.chapters_section.extract_chapters") as mock_extract:
        mock_extract.return_value = []
        new_ctx, r = run(ctx)

    assert r.ok
    payload = json.loads(obj.put_bytes.call_args[0][1].decode())
    assert payload["toc_source"] == "empty"
    assert payload["total_chapters"] == 0
    assert new_ctx.chapter_uri is not None


def test_extract_chapters_failure_returns_stage_result_false() -> None:
    """extract_chapters 抛异常 → 返 ok=False, mark_stage_failed."""
    from src.ingest.pre_analysis.chapter_extractors.chapters_section import run

    ctx = _make_ctx()
    with patch("src.ingest.pre_analysis.chapter_extractors.chapters_section.extract_chapters") as mock_extract:
        mock_extract.side_effect = RuntimeError("boom")
        _, r = run(ctx)

    assert not r.ok
    assert "boom" in r.error
    assert r.stage_name == "extract_chapters"
    ctx.stage_store.mark_stage_failed.assert_called_once()
    ctx.object_store.put_bytes.assert_not_called()


def test_write_json_failure_propagates() -> None:
    """ObjectStore.put_bytes 失败 → 整 stage 失败, 调 mark_stage_failed."""
    from src.ingest.pre_analysis.chapter_extractors.chapters_section import run

    ctx = _make_ctx()
    ctx.object_store.put_bytes.side_effect = OSError("disk full")
    with patch("src.ingest.pre_analysis.chapter_extractors.chapters_section.extract_chapters") as mock_extract:
        mock_extract.return_value = [{"level": 1, "title": "A", "page_start": 1, "page_end": 1}]
        _, r = run(ctx)

    assert not r.ok
    assert "disk full" in r.error
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写 `chapters_section.py`**

```python
# packages/service/src/ingest/pre_analysis/chapter_extractors/chapters_section.py
"""Stage 2: 章节提取 + 写 chapter_structure.json + DB append (2026-07-09).

行为对齐原 runner.py:141-159 + _write_chapter_structure.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from loguru import logger

from ..db_artifact import append_artifact
from ..stage_context import StageContext, StageResult
from . import extract_chapters


def run(ctx: StageContext) -> tuple[StageContext, StageResult]:
    """调 chapter_extractors + 写 chapter_structure.json + DB append."""
    assert ctx.doc is not None and ctx.output_prefix is not None
    ctx.stage_store.mark_stage_started(ctx.task_id, "extract_chapters")
    try:
        chapters = extract_chapters(ctx.doc)
        chapter_uri, _size = _write_chapter_json(ctx, chapters)
        append_artifact(
            ctx.task_id, "chapter_structure", "chapter_structure.json", chapter_uri, _size
        )
        ctx.stage_store.mark_stage_completed(
            ctx.task_id, "extract_chapters", progress=100, message=f"{len(chapters)} 章"
        )
        return ctx.replace(chapters=chapters, chapter_uri=chapter_uri), StageResult(
            ok=True, message=f"{len(chapters)} 章"
        )
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, "extract_chapters", str(e))
        logger.opt(exception=True).error("pre_analysis extract_chapters failed task={}", ctx.task_id)
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"extract_chapters failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        return ctx, StageResult(ok=False, error=str(e), stage_name="extract_chapters")


def _write_chapter_json(ctx: StageContext, chapters: list[dict]) -> tuple[str, int]:
    """(2026-07-09 原 _write_chapter_structure 逻辑搬过来)."""
    payload = {
        "total_pages": len(ctx.doc),
        "total_chapters": len(chapters),
        "extracted_at": datetime.now(UTC).isoformat(),
        "toc_source": "pdf_outline" if chapters else "empty",
        "chapters": chapters,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    uri = f"{ctx.output_prefix}/chapter_structure.json"
    ctx.object_store.put_bytes(uri, data, "application/json")
    return uri, len(data)


__all__ = ["run"]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py -v
```

Expected: 4 passed

- [ ] **Step 5: 改 `runner.py`**

**修改 1**: 删 [runner.py:392-413](../packages/service/src/ingest/pre_analysis/runner.py#L392-L413) `_write_chapter_structure` 整个方法.

**修改 2**: 顶部 import 把 `extract_chapters` 删掉 (现在 runner 不直接调了, 走 chapters_section):
```python
# 删这行:
# from .chapter_extractors import extract_chapters
# 改加:
from .chapter_extractors.chapters_section import run as chapters_section
```

**修改 3**: 替换 [runner.py:141-159](../packages/service/src/ingest/pre_analysis/runner.py#L141-L159) stage 2 块为:
```python
ctx, r = chapters_section(ctx)
if not r.ok:
    ctx.doc.close()
    return PreAnalysisResult(success=False, task_id=task_id, error=r.error)
chapters = ctx.chapters
chapter_uri = ctx.chapter_uri
```

- [ ] **Step 6: ruff + pyright + 单文件 pytest**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/chapter_extractors/chapters_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/chapter_extractors/chapters_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/chapter_extractors/chapters_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py tests/ingest/pre_analysis/test_runner.py -v
```

Expected: 0 error / 0 warning / 4 + 8 = 12 passed

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/chapter_extractors/chapters_section.py packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/chapter_extractors/test_chapters_section.py
git commit -m "feat(pre-analysis): 抽 stage 2 chapters_section.py"
```

---

### Task 4: 抽 `tables_section.py` (stage 3)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section.py`
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:161-180` + 删 `_extract_tables`/`_detect_cross_page`/`_write_one_table`

**Interfaces:**
- Produces: `def run(ctx: StageContext, table_extraction_config: dict) -> tuple[StageContext, StageResult]`
- Consumes: `get_table_extractor(backend, params)` 从 `table_extractors.factory`
- Consumes: `append_artifact` 从 `db_artifact`

- [ ] **Step 1: 写 `test_tables_section.py`**

新建目录 `packages/service/tests/ingest/pre_analysis/table_extractors/`, 写文件:

```python
"""tables_section stage 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

import csv
import io
from unittest.mock import MagicMock, patch

import pymupdf


def _make_ctx(task_id: str = "t1", raw_tables: list | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.task_id = task_id
    ctx.doc = MagicMock(spec=pymupdf.Document)
    ctx.doc.name = "/tmp/fake.pdf"
    ctx.output_prefix = f"local://pre_analysis_outputs/{task_id}"
    ctx.config = {"cross_page_detection": {"min_column_match": 0.8, "footer_keywords": ["continued"]}}
    ctx.object_store = MagicMock()
    ctx.stage_store = MagicMock()
    return ctx


def test_happy_path_writes_csv_per_table() -> None:
    """happy path: 1 张表 → 写 1 个 CSV + DB append 1 项."""
    from src.ingest.pre_analysis.table_extractors.tables_section import run

    raw_table = MagicMock()
    raw_table.page_no = 3
    raw_table.table_no = 1
    raw_table.rows = [["A", "B"], ["1", "2"]]

    with patch("src.ingest.pre_analysis.table_extractors.tables_section.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = [raw_table]
        mock_factory.return_value = mock_extractor
        new_ctx, r = run(_make_ctx(), {"table_backend": "pymupdf", "table_params": {}})

    assert r.ok
    assert r.message == "1 表 / 0 跨页候选"
    assert new_ctx.cross_page_count == 0
    assert len(new_ctx.tables) == 1


def test_empty_tables_returns_zero() -> None:
    """0 表 → 返 ok=True, 0 跨页."""
    from src.ingest.pre_analysis.table_extractors.tables_section import run

    with patch("src.ingest.pre_analysis.table_extractors.tables_section.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = []
        mock_factory.return_value = mock_extractor
        new_ctx, r = run(_make_ctx(), {"table_backend": "pymupdf", "table_params": {}})

    assert r.ok
    assert new_ctx.cross_page_count == 0
    assert new_ctx.tables == []


def test_cross_page_detection_continues_kw() -> None:
    """页 N table N + 页 N+1 table 1 列数 ≥ 80% + footer "continued" → 跨页 +1."""
    from src.ingest.pre_analysis.table_extractors.tables_section import run

    raw_t1 = MagicMock(page_no=3, table_no=1, rows=[["A", "B"], ["1", "2"], ["3", "4"]])
    raw_t2 = MagicMock(page_no=4, table_no=1, rows=[["A", "B"], ["5", "6"], ["continued", ""]])
    raw_t3 = MagicMock(page_no=4, table_no=2, rows=[["X"], ["y"]])

    with patch("src.ingest.pre_analysis.table_extractors.tables_section.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = [raw_t1, raw_t2, raw_t3]
        mock_factory.return_value = mock_extractor
        new_ctx, r = run(_make_ctx(), {"table_backend": "pymupdf", "table_params": {}})

    assert r.ok
    assert new_ctx.cross_page_count == 1
    assert "1 跨页候选" in r.message


def test_write_csv_failure_propagates() -> None:
    """单张表写盘失败 → 整 stage 失败."""
    from src.ingest.pre_analysis.table_extractors.tables_section import run

    raw_table = MagicMock(page_no=3, table_no=1, rows=[["A"]])

    ctx = _make_ctx()
    ctx.object_store.put_bytes.side_effect = OSError("disk full")
    with patch("src.ingest.pre_analysis.table_extractors.tables_section.get_table_extractor") as mock_factory:
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = [raw_table]
        mock_factory.return_value = mock_extractor
        _, r = run(ctx, {"table_backend": "pymupdf", "table_params": {}})

    assert not r.ok
    assert "disk full" in r.error
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_tables_section.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写 `tables_section.py`**

```python
# packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py
"""Stage 3: 表格提取 + 跨页检测 + 逐张写 CSV + DB append (2026-07-09).

行为对齐原 runner.py:161-180 + _extract_tables + _detect_cross_page + _write_one_table.
"""
from __future__ import annotations

import csv
import io

from loguru import logger

from ..db_artifact import append_artifact
from ..stage_context import StageContext, StageResult
from .factory import get_table_extractor


def run(ctx: StageContext, table_extraction_config: dict) -> tuple[StageContext, StageResult]:
    """调 table_extractors factory + 跨页检测 + 逐张写 CSV + DB append."""
    assert ctx.doc is not None and ctx.config is not None
    ctx.stage_store.mark_stage_started(ctx.task_id, "extract_tables")
    try:
        tables, cross_page = _extract_tables_with_cross_page(ctx, table_extraction_config)
        for page_no, table_no, rows in tables:
            uri, size = _write_one_table(ctx, page_no, table_no, rows)
            append_artifact(
                ctx.task_id, "table", f"tables/page-{page_no}-table-{table_no}.csv", uri, size
            )
        ctx.stage_store.mark_stage_completed(
            ctx.task_id,
            "extract_tables",
            progress=100,
            message=f"{len(tables)} 表 / {cross_page} 跨页候选",
        )
        return ctx.replace(tables=tables, cross_page_count=cross_page), StageResult(
            ok=True, message=f"{len(tables)} 表 / {cross_page} 跨页候选"
        )
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, "extract_tables", str(e))
        logger.opt(exception=True).error("pre_analysis extract_tables failed task={}", ctx.task_id)
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"extract_tables failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        return ctx, StageResult(ok=False, error=str(e), stage_name="extract_tables")


def _extract_tables_with_cross_page(
    ctx: StageContext, cfg: dict
) -> tuple[list[tuple[int, int, list[list[str]]]], int]:
    """(原 _extract_tables + _detect_cross_page 逻辑搬过来)."""
    backend = cfg.get("table_backend", "pymupdf")
    params = cfg.get("table_params", {})
    extractor = get_table_extractor(backend, params)
    # pymupdf 后端优先复用已开 doc (避免重开), 其他后端开新 doc
    _doc = ctx.doc if backend == "pymupdf" else None
    raw_tables = extractor.extract(ctx.doc.name or "", _pymupdf_doc=_doc)
    tables = [(t.page_no, t.table_no, t.rows) for t in raw_tables]
    cross_page = _detect_cross_page(tables, ctx.config or {})
    return tables, cross_page


def _detect_cross_page(
    tables: list[tuple[int, int, list[list[str]]]], config: dict
) -> int:
    """(2026-07-09 v3 原 _detect_cross_page 逻辑搬过来)."""
    cross_config = config.get("cross_page_detection", {}) or {}
    col_match = cross_config.get("min_column_match", 0.8)
    footer_kws = cross_config.get("footer_keywords", []) or []
    prev_table: tuple[int, int] | None = None
    cross_page = 0
    seen_footers: set[str] = set()
    for page_no, table_no, rows in tables:
        if prev_table is not None and table_no == 1:
            prev_page, prev_cols = prev_table
            cur_cols = len(rows[0]) if rows else 0
            if prev_page == page_no - 1 and cur_cols >= prev_cols * col_match:
                last_row_first = (rows[-1][0] if rows and rows[-1] else "") or ""
                if last_row_first in seen_footers:
                    continue
                if any(kw in last_row_first for kw in footer_kws):
                    seen_footers.add(last_row_first)
                    cross_page += 1
                    logger.warning("跨页表候选 page={} -> page={}", prev_page, page_no)
        prev_table = (page_no, len(rows[0]) if rows else 0)
    return cross_page


def _write_one_table(
    ctx: StageContext, page_no: int, table_no: int, rows: list[list[str]]
) -> tuple[str, int]:
    """(原 _write_one_table 逻辑搬过来)."""
    uri = f"{ctx.output_prefix}/tables/page-{page_no}-table-{table_no}.csv"
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    data = buf.getvalue().encode("utf-8")
    ctx.object_store.put_bytes(uri, data, "text/csv")
    return uri, len(data)


__all__ = ["run"]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_tables_section.py -v
```

Expected: 4 passed

- [ ] **Step 5: 改 `runner.py`**

**修改 1**: 删 [runner.py:277-333](../packages/service/src/ingest/pre_analysis/runner.py#L277-L333) `_extract_tables` + `_detect_cross_page` 整个方法 (2 个连续 def).

**修改 2**: 删 [runner.py:335-357](../packages/service/src/ingest/pre_analysis/runner.py#L335-L357) `_write_one_table` 整个方法.

**修改 3**: 顶部 import 加:
```python
from .table_extractors.tables_section import run as tables_section
```

**修改 4**: 替换 [runner.py:161-180](../packages/service/src/ingest/pre_analysis/runner.py#L161-L180) stage 3 块为:
```python
ctx, r = tables_section(ctx, table_extraction_config)
if not r.ok:
    ctx.doc.close()
    return PreAnalysisResult(success=False, task_id=task_id, error=r.error)
tables = ctx.tables
cross_page = ctx.cross_page_count
```

- [ ] **Step 6: ruff + pyright + 单文件 pytest**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/tables_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/table_extractors/test_tables_section.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/table_extractors/tables_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/table_extractors/test_tables_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/tables_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/table_extractors/test_tables_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_tables_section.py tests/ingest/pre_analysis/test_runner.py -v
```

Expected: 0 error / 0 warning / 4 + 8 = 12 passed

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section.py
git commit -m "feat(pre-analysis): 抽 stage 3 tables_section.py"
```

---

### Task 5: 抽 `flagged_section.py` (stage 4)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/flag_extractors/flagged_section.py`
- Create: `packages/service/tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py`
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:182-197` + 删 `_write_flagged_paragraphs`

**Interfaces:**
- Produces: `def run(ctx: StageContext) -> tuple[StageContext, StageResult]`
- Consumes: `extract_flagged_paragraphs(doc, config)` 现有入口 (从 `flag_extractors.__init__` import)
- Consumes: `append_artifact` 从 `db_artifact`

- [ ] **Step 1: 写 `test_flagged_section.py`**

新建目录 `packages/service/tests/ingest/pre_analysis/flag_extractors/`, 写文件:

```python
"""flagged_section stage 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

import csv
import io
from unittest.mock import MagicMock, patch

import pymupdf


def _make_ctx(task_id: str = "t1", flagged_return: list | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.task_id = task_id
    ctx.doc = MagicMock(spec=pymupdf.Document)
    ctx.output_prefix = f"local://pre_analysis_outputs/{task_id}"
    ctx.config = {"keywords": ["必须"]}
    ctx.object_store = MagicMock()
    ctx.stage_store = MagicMock()
    return ctx


def test_happy_path_writes_14_columns_csv() -> None:
    """happy path: 1 段 → 写 14 列 CSV + DB append 1 项."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import run

    flagged = [
        {
            "matched_keywords": "必须",
            "page": 1,
            "section": "1.1",
            "text": "必须使用",
            "rule_categories": "[]",
            "density": "0.5",
            "is_dense": "1",
            "raw_density": "0.5",
            "weighted_density": "0.5",
            "safe_hits": "0",
            "rec_hits": "0",
            "lemmas": "[]",
            "token_count": "10",
            "language": "zh",
        }
    ]
    obj = MagicMock()
    ctx = _make_ctx()
    ctx.object_store = obj

    with patch("src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs") as mock_extract:
        mock_extract.return_value = flagged
        new_ctx, r = run(ctx)

    assert r.ok
    assert r.message == "1 段落"
    assert new_ctx.flagged == flagged
    # 验证 14 列 CSV
    csv_data = obj.put_bytes.call_args[0][1].decode()
    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)
    assert len(rows) == 1
    assert len(reader.fieldnames) == 14


def test_empty_flagged_writes_empty_csv() -> None:
    """0 段 → 写空 CSV (header only)."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import run

    obj = MagicMock()
    ctx = _make_ctx()
    ctx.object_store = obj

    with patch("src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs") as mock_extract:
        mock_extract.return_value = []
        new_ctx, r = run(ctx)

    assert r.ok
    assert new_ctx.flagged == []
    csv_data = obj.put_bytes.call_args[0][1].decode()
    reader = csv.DictReader(io.StringIO(csv_data))
    assert len(list(reader)) == 0
    assert len(reader.fieldnames) == 14


def test_extract_failure_returns_stage_result_false() -> None:
    """extract_flagged_paragraphs 抛异常 → 返 ok=False."""
    from src.ingest.pre_analysis.flag_extractors.flagged_section import run

    ctx = _make_ctx()
    with patch("src.ingest.pre_analysis.flag_extractors.flagged_section.extract_flagged_paragraphs") as mock_extract:
        mock_extract.side_effect = RuntimeError("spacy not loaded")
        _, r = run(ctx)

    assert not r.ok
    assert "spacy not loaded" in r.error
    ctx.stage_store.mark_stage_failed.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写 `flagged_section.py`**

```python
# packages/service/src/ingest/pre_analysis/flag_extractors/flagged_section.py
"""Stage 4: 关键词段落提取 + 写 14 列 CSV + DB append (2026-07-09).

行为对齐原 runner.py:182-197 + _write_flagged_paragraphs.
"""
from __future__ import annotations

import csv
import io

from loguru import logger

from ..db_artifact import append_artifact
from ..stage_context import StageContext, StageResult
from . import extract_flagged_paragraphs


def run(ctx: StageContext) -> tuple[StageContext, StageResult]:
    """调 flag_extractors + 写 14 列 CSV + DB append."""
    assert ctx.doc is not None and ctx.config is not None
    ctx.stage_store.mark_stage_started(ctx.task_id, "extract_flagged")
    try:
        flagged = extract_flagged_paragraphs(ctx.doc, ctx.config)
        flagged_uri, size = _write_flagged_csv(ctx, flagged)
        append_artifact(
            ctx.task_id, "flagged_paragraphs", "flagged_paragraphs.csv", flagged_uri, size
        )
        ctx.stage_store.mark_stage_completed(
            ctx.task_id, "extract_flagged", progress=100, message=f"{len(flagged)} 段落"
        )
        return ctx.replace(flagged=flagged, flagged_uri=flagged_uri), StageResult(
            ok=True, message=f"{len(flagged)} 段落"
        )
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, "extract_flagged", str(e))
        logger.opt(exception=True).error("pre_analysis extract_flagged failed task={}", ctx.task_id)
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"extract_flagged failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        return ctx, StageResult(ok=False, error=str(e), stage_name="extract_flagged")


def _write_flagged_csv(ctx: StageContext, flagged: list[dict]) -> tuple[str, int]:
    """(原 _write_flagged_paragraphs 逻辑搬过来, 14 列 CSV)."""
    uri = f"{ctx.output_prefix}/flagged_paragraphs.csv"
    fieldnames = [
        "matched_keywords", "page", "section", "text",  # 旧 4 (DictReader 兼容)
        "rule_categories", "density", "is_dense",  # v2 新增 3
        "raw_density", "weighted_density",  # v2 新增 2
        "safe_hits", "rec_hits",  # v2 新增 2
        "lemmas", "token_count", "language",  # v3 新增 3
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in flagged:
        clean_row = {k: row.get(k, "") for k in fieldnames}
        writer.writerow(clean_row)
    data = buf.getvalue().encode("utf-8")
    ctx.object_store.put_bytes(uri, data, "text/csv")
    return uri, len(data)


__all__ = ["run"]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py -v
```

Expected: 3 passed

- [ ] **Step 5: 改 `runner.py`**

**修改 1**: 删 [runner.py:415-454](../packages/service/src/ingest/pre_analysis/runner.py#L415-L454) `_write_flagged_paragraphs` 整个方法.

**修改 2**: 顶部 import 把 `extract_flagged_paragraphs` 删掉, 改加:
```python
from .flag_extractors.flagged_section import run as flagged_section
```

**修改 3**: 替换 [runner.py:182-197](../packages/service/src/ingest/pre_analysis/runner.py#L182-L197) stage 4 块为:
```python
ctx, r = flagged_section(ctx)
if not r.ok:
    ctx.doc.close()
    return PreAnalysisResult(success=False, task_id=task_id, error=r.error)
flagged = ctx.flagged
flagged_uri = ctx.flagged_uri
```

- [ ] **Step 6: ruff + pyright + 单文件 pytest**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/flag_extractors/flagged_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/flag_extractors/flagged_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/flag_extractors/flagged_section.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py tests/ingest/pre_analysis/test_runner.py -v
```

Expected: 0 error / 0 warning / 3 + 8 = 11 passed

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/flag_extractors/flagged_section.py packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/flag_extractors/test_flagged_section.py
git commit -m "feat(pre-analysis): 抽 stage 4 flagged_section.py"
```

---

### Task 6: 抽 `finalize_output.py` (stage 5)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/finalize_output.py`
- Create: `packages/service/tests/ingest/pre_analysis/test_finalize_output.py`
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:199-222` + 删 `_write_index`

**Interfaces:**
- Produces: `def run(ctx: StageContext, *, elapsed_ms: int) -> tuple[StageContext, StageResult]`
- Consumes: `append_artifact` 从 `db_artifact`
- 副作用: 更新 `task.current_stage='done'` (不调 mark_task_completed, 由 runner 负责)

- [ ] **Step 1: 写 `test_finalize_output.py`**

```python
"""finalize_output stage 测试 (mode 1 mock, 2026-07-09)."""
from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def _make_ctx(task_id: str = "t1") -> MagicMock:
    ctx = MagicMock()
    ctx.task_id = task_id
    ctx.pdf_uri = "local://inputs/t1/x.pdf"
    ctx.output_prefix = f"local://pre_analysis_outputs/{task_id}"
    ctx.chapters = [{"level": 1, "title": "A", "page_start": 1, "page_end": 1}]
    ctx.tables = [(3, 1, [["A", "B"]])]
    ctx.cross_page_count = 1
    ctx.flagged = [{"matched_keywords": "必须", "page": 1, "section": "1.1", "text": "必须"}]
    ctx.flagged_uri = f"local://pre_analysis_outputs/{task_id}/flagged_paragraphs.csv"
    ctx.chapter_uri = f"local://pre_analysis_outputs/{task_id}/chapter_structure.json"
    ctx.object_store = MagicMock()
    ctx.stage_store = MagicMock()
    return ctx


def test_happy_path_writes_index_json() -> None:
    """happy path: 写 index.json + DB append 1 项 + 更新 current_stage='done'."""
    from src.ingest.pre_analysis.finalize_output import run

    obj = MagicMock()
    ctx = _make_ctx()
    ctx.object_store = obj
    # mock session_scope for current_stage update
    task = MagicMock()
    s = MagicMock()
    s.get.return_value = task

    @contextmanager
    def fake_session_scope():
        yield s

    with patch("src.ingest.pre_analysis.finalize_output.session_scope", fake_session_scope):
        new_ctx, r = run(ctx, elapsed_ms=1234)

    assert r.ok
    assert new_ctx.index_uri == "local://pre_analysis_outputs/t1/index.json"
    assert task.current_stage == "done"
    # 验证 index.json payload
    index_data = obj.put_bytes.call_args[0][1].decode()
    payload = json.loads(index_data)
    assert payload["summary"]["total_chapters"] == 1
    assert payload["summary"]["total_tables"] == 1
    assert payload["summary"]["cross_page_candidates"] == 1
    assert payload["elapsed_ms"] == 1234


def test_write_index_failure_propagates() -> None:
    """ObjectStore.put_bytes 失败 → 整 stage 失败."""
    from src.ingest.pre_analysis.finalize_output import run

    ctx = _make_ctx()
    ctx.object_store.put_bytes.side_effect = OSError("disk full")
    _, r = run(ctx, elapsed_ms=1000)
    assert not r.ok
    assert "disk full" in r.error


def test_task_none_silently_skips_current_stage_update() -> None:
    """task 不存在 → 静默跳过 current_stage 更新, 仍 ok=True."""
    from src.ingest.pre_analysis.finalize_output import run

    ctx = _make_ctx()
    s = MagicMock()
    s.get.return_value = None

    @contextmanager
    def fake_session_scope():
        yield s

    with patch("src.ingest.pre_analysis.finalize_output.session_scope", fake_session_scope):
        new_ctx, r = run(ctx, elapsed_ms=1000)

    assert r.ok
    assert new_ctx.index_uri is not None


def test_index_json_includes_summary() -> None:
    """index.json summary 字段含 chapters/tables/flagged/cross_page 4 项."""
    from src.ingest.pre_analysis.finalize_output import run

    obj = MagicMock()
    ctx = _make_ctx()
    ctx.object_store = obj
    s = MagicMock()
    s.get.return_value = None

    @contextmanager
    def fake_session_scope():
        yield s

    with patch("src.ingest.pre_analysis.finalize_output.session_scope", fake_session_scope):
        run(ctx, elapsed_ms=0)

    index_data = obj.put_bytes.call_args[0][1].decode()
    payload = json.loads(index_data)
    summary = payload["summary"]
    assert summary["total_chapters"] == 1
    assert summary["total_tables"] == 1
    assert summary["total_flagged_paragraphs"] == 1
    assert summary["cross_page_candidates"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_finalize_output.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写 `finalize_output.py`**

```python
# packages/service/src/ingest/pre_analysis/finalize_output.py
"""Stage 5: 写 index.json + 更新 task.current_stage='done' (2026-07-09).

不调 mark_task_completed, 由 runner.run() 末尾统一调.
行为对齐原 runner.py:199-222 + _write_index.
"""
from __future__ import annotations

import json

from loguru import logger

from ...storage import session_scope
from ..db_artifact import append_artifact
from ..models import PreAnalysisTask
from ..stage_context import StageContext, StageResult


def run(ctx: StageContext, *, elapsed_ms: int) -> tuple[StageContext, StageResult]:
    """写 index.json + DB append + 更新 task.current_stage='done'."""
    assert ctx.chapters is not None and ctx.tables is not None and ctx.flagged is not None
    assert ctx.chapter_uri is not None and ctx.flagged_uri is not None
    ctx.stage_store.mark_stage_started(ctx.task_id, "finalize_output")
    try:
        index_uri, payload = _write_index_json(ctx, elapsed_ms)
        index_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        append_artifact(ctx.task_id, "index", "index.json", index_uri, len(index_data))
        # 更新 current_stage
        with session_scope() as s:
            task = s.get(PreAnalysisTask, ctx.task_id)
            if task is not None:
                task.current_stage = "done"
        ctx.stage_store.mark_stage_completed(ctx.task_id, "finalize_output", progress=100)
        return ctx.replace(index_uri=index_uri), StageResult(ok=True)
    except Exception as e:
        ctx.stage_store.mark_stage_failed(ctx.task_id, "finalize_output", str(e))
        logger.opt(exception=True).error("pre_analysis finalize_output failed task={}", ctx.task_id)
        ctx.task_store.mark_failed(
            ctx.task_id,
            f"finalize_output failed: {e}",
            stages_provider=ctx.stage_store.list_stages,
        )
        return ctx, StageResult(ok=False, error=str(e), stage_name="finalize_output")


def _write_index_json(ctx: StageContext, elapsed_ms: int) -> tuple[str, dict]:
    """(原 _write_index 逻辑搬过来)."""
    # 累计 output_files_json 来自 DB
    final_files: list[dict] = []
    with session_scope() as s:
        task = s.get(PreAnalysisTask, ctx.task_id)
        if task is not None:
            final_files = json.loads(task.output_files_json or "[]")
    payload = {
        "task_id": ctx.task_id,
        "pdf_filename": ctx.pdf_uri.rsplit("/", 1)[-1],
        "elapsed_ms": elapsed_ms,
        "summary": {
            "total_chapters": len(ctx.chapters or []),
            "total_tables": len(ctx.tables or []),
            "total_flagged_paragraphs": len(ctx.flagged or []),
            "cross_page_candidates": ctx.cross_page_count,
        },
        "files": final_files,
    }
    index_uri = f"{ctx.output_prefix}/index.json"
    index_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ctx.object_store.put_bytes(index_uri, index_data, "application/json")
    return index_uri, payload


__all__ = ["run"]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_finalize_output.py -v
```

Expected: 4 passed

- [ ] **Step 5: 改 `runner.py`**

**修改 1**: 删 [runner.py:456-500](../packages/service/src/ingest/pre_analysis/runner.py#L456-L500) `_write_index` 整个方法.

**修改 2**: 顶部 import 加:
```python
from .finalize_output import run as finalize_output
```

**修改 3**: 替换 [runner.py:199-222](../packages/service/src/ingest/pre_analysis/runner.py#L199-L222) stage 5 块 + 重构末尾 mark_completed 逻辑:

```python
# stage 5
elapsed_ms = int((time.monotonic() - start) * 1000)
ctx, r = finalize_output(ctx, elapsed_ms=elapsed_ms)
if not r.ok:
    ctx.doc.close()
    return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

ctx.doc.close()
return self._build_success_result(ctx, table_extraction_config, start)
```

**修改 4**: 加 `_build_success_result` 私有方法 (从原 [runner.py:226-256](../packages/service/src/ingest/pre_analysis/runner.py#L226-L256) 改写):

```python
def _build_success_result(
    self, ctx: StageContext, table_extraction_config: dict, start: float
) -> PreAnalysisResult:
    """读 DB 拿 final_output_files + 构造 PreAnalysisResult + mark_completed."""
    final_output_files: list[dict] = []
    with session_scope() as s:
        task = s.get(PreAnalysisTask, ctx.task_id)
        if task is not None:
            final_output_files = json.loads(task.output_files_json or "[]")
    elapsed_ms = int((time.monotonic() - start) * 1000)
    result = PreAnalysisResult(
        success=True,
        task_id=ctx.task_id,
        chapter_structure_uri=ctx.chapter_uri,
        flagged_paragraphs_uri=ctx.flagged_uri,
        table_uris=[],
        index_uri=ctx.index_uri,
        total_chapters=len(ctx.chapters or []),
        total_tables=len(ctx.tables or []),
        total_flagged=len(ctx.flagged or []),
        cross_page_candidates=ctx.cross_page_count,
        elapsed_ms=elapsed_ms,
    )
    self.task_store.mark_completed(
        task_id=ctx.task_id,
        output_files=final_output_files,
        summary={
            "total_chapters": result.total_chapters,
            "total_tables": result.total_tables,
            "total_flagged_paragraphs": result.total_flagged,
            "elapsed_ms": result.elapsed_ms,
            "cross_page_candidates": result.cross_page_candidates,
        },
        task_config=table_extraction_config,
    )
    logger.info(
        "pre_analysis done task={} chapters={} tables={} flagged={} elapsed={}ms",
        ctx.task_id,
        result.total_chapters,
        result.total_tables,
        result.total_flagged,
        elapsed_ms,
    )
    return result
```

- [ ] **Step 6: ruff + pyright + 单文件 pytest**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/finalize_output.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_finalize_output.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check --fix src/ingest/pre_analysis/finalize_output.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_finalize_output.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/finalize_output.py src/ingest/pre_analysis/runner.py tests/ingest/pre_analysis/test_finalize_output.py
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/test_finalize_output.py tests/ingest/pre_analysis/test_runner.py -v
```

Expected: 0 error / 0 warning / 4 + 8 = 12 passed

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/finalize_output.py packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/test_finalize_output.py
git commit -m "feat(pre-analysis): 抽 stage 5 finalize_output.py"
```

---

### Task 7: 删 `runner._append_artifact` 改调 `db_artifact.append_artifact`

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:359-381` (删 `_append_artifact` 整个方法)

**说明**: 严格来说, runner._append_artifact 在 Task 3-6 抽完 stage 后**已经没人调了** (4 个 stage 都改调 `db_artifact.append_artifact` 了). 这一 task 只是删掉 runner 里的死代码 + 加 import 链接, 跑回归测试确认零行为差异.

- [ ] **Step 1: 验证 runner._append_artifact 没人调**

```bash
cd /home/deyuan/rag/rag && grep -rn "_append_artifact" packages/service/src/ingest/pre_analysis/runner.py
```

Expected: 只剩方法定义本身 (1 处), 没有 caller

- [ ] **Step 2: 删 `_append_artifact` 整个方法 + 清理无用 import**

删除 [runner.py:359-381](../packages/service/src/ingest/pre_analysis/runner.py#L359-L381) `_append_artifact` 整个方法.

清理 runner.py 顶部不再需要的 import:
- `csv` (line 19) — `_write_one_table` 已删, **删 import**
- `io` (line 20) — `_write_one_table` / `_write_index` 已删, **删 import**
- `datetime` (line 25) — `_write_chapter_structure` 已删, **删 import**
- `UTC` (line 25) — 同上, **删 import**
- `json` (line 21) — `_build_success_result` 仍用 `json.loads` / `json.dumps`, **保留**
- `os` (line 22) — `_output_prefix` 已删, **删 import**
- `session_scope` (line 33) — `_build_success_result` 仍用, **保留**
- `PreAnalysisTask` (line 35) — `_build_success_result` 仍用, **保留**

- [ ] **Step 3: 检查 runner.py 行数**

```bash
wc -l /home/deyuan/rag/rag/packages/service/src/ingest/pre_analysis/runner.py
```

Expected: ≤ 200 行 (验收要求)

- [ ] **Step 4: 跑 pre_analysis 整目录测试**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/ -q
```

Expected: 92 (原) + 26 (新) - 0 = 118 passed

- [ ] **Step 5: ruff + pyright 收尾**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/runner.py
cd /home/deyuan/rag/rag/packages/service && uv run ruff check src/ingest/pre_analysis/runner.py
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 error / 0 warning

- [ ] **Step 6: 跑全量 pytest 验证无新 fail**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest -q 2>/tmp/full-stderr.txt 1>/tmp/full-stdout.txt
tail -50 /tmp/full-stdout.txt
```

Expected: 0 新 fail (跟实施前基线 22 fail + 38 errors 比, fail 数不变)

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/runner.py
git commit -m "refactor(pre-analysis): 删 runner._append_artifact 死代码, 5 stage 统一调 db_artifact"
```

---

## 验收 (完工清单)

- [ ] runner.py ≤ 200 行
- [ ] 7 个新 stage 文件每个 ≤ 100 行
- [ ] 26 个新 test 全绿
- [ ] test_runner.py 集成测试 8 个全绿 (零回归)
- [ ] ruff format + ruff check 0 error
- [ ] pyright 0 error
- [ ] uv run pytest 全量无新 fail (跟基线 22 fail + 38 errors 对比)
- [ ] 7 个 commit 顺序按本 plan 拆 (git log 验证)
- [ ] 8 个新文件 + 1 个改文件 全部 staged + committed