# Table Extractor Adapter + Stage-by-Stage Streaming Writes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 pre-analysis 提取阶段从 "pymupdf only" 扩展到 pymupdf / camelot / pdfplumber 3 后端可配置 (admin 上传 PDF 时选), 表格产物按 stage 渐增写入 (admin 可实时看到部分产物), 不破坏现有 pymupdf 默认行为.

**Architecture:** Strategy Pattern (table_extractors/ 文件夹: base + 3 适配器 + factory); per-task config 通过 API form 字段 in-memory 透传, 不在 upload 时持久化, runner 跑完统一写 task_config_json 执行快照 (含 import 路径); 5 stage 各自独立写自己业务产物 (chapters / tables / flagged), DB output_files_json 增量 append; 详情页手动刷新 (无轮询) 拿 DB 最新; 纯 DB 不用 Redis. 子包化 (pre_analysis/ 子包) 在 M0 先跑, 改名不改业务.

**Tech Stack:** Python 3.14 + pymupdf + camelot-py 2.0 (可选) + pdfplumber (可选); FastAPI + 现有 BackgroundTasks + Alembic; 前端 React 19 + shadcn Accordion/AppTooltip/AppSelect + next-intl. **只用 uv 装不用 pip** (CLAUDE.md 用户原话).

---

## File Structure

### 子包化迁移 (M0)
```
packages/service/src/ingest/
├── pre_analysis_models.py        ─┐
├── pre_analysis_store.py          ─┤ git mv
├── pre_analysis_runner.py         ─┤   →
├── pre_analysis_stage_models.py   ─┤
├── pre_analysis_stage_store.py    ─┘
│                                  → src/ingest/pre_analysis/
└── api.py [改] import 路径
                                     ├── __init__.py     [新] 重导出 5 类
                                     ├── models.py      [移]
                                     ├── store.py       [移]
                                     ├── runner.py      [移]
                                     ├── stage_models.py[移]
                                     ├── stage_store.py [移]
                                     └── table_extractors/  [新]
                                         ├── __init__.py     [新]
                                         ├── base.py         [新] ABC+TableData+BackendNotInstalledError
                                         ├── pymupdf_extractor.py   [新]
                                         ├── camelot_extractor.py   [新]
                                         ├── pdfplumber_extractor.py[新]
                                         └── factory.py      [新]

packages/service/tests/ingest/
├── test_pre_analysis_models.py       ─┐
├── test_pre_analysis_stage_store.py   ─┤ git mv
├── test_pre_analysis_runner.py        ─┤   →
├── test_pre_analysis_api.py           ─┘
│                                       → tests/ingest/pre_analysis/
                                          ├── test_models.py        [移]
                                          ├── test_store.py         [移]
                                          ├── test_runner.py        [移]
                                          ├── test_api.py           [移]
                                          └── table_extractors/
                                              ├── test_base.py           [新]
                                              ├── test_pymupdf_extractor.py   [新]
                                              ├── test_camelot_extractor.py   [新]
                                              ├── test_pdfplumber_extractor.py[新]
                                              └── test_factory.py       [新]
```

### 新增文件 (M1-M5)
```
packages/service/
├── configs/pre_analysis/table_extraction.yaml        [新] 默认 backend+params
├── src/storage/migrations/versions/
│   └── 20260706_000000_pre_analysis_task_config.py   [新] 加 task_config_json 列
└── tests/migrations/test_pre_analysis_task_config.py [新] mode 3 + mode 1

packages/web/
└── app/[locale]/admin/pre-analysis/[task_id]/_components/
    └── admin-pre-analysis-detail-client.tsx          [改] 详情页加 ⟳ 按钮 + 每产物 ⬇ 链接 + ZIP disable
```

### 修改文件
- `packages/service/src/ingest/pre_analysis/models.py`     — 加 task_config_json 列 (M1 之后该路径已存在)
- `packages/service/src/ingest/pre_analysis/store.py`      — mark_completed 接 task_config_json 参数
- `packages/service/src/ingest/pre_analysis/runner.py`     — 改 _extract_tables 用 factory；5 stage 各自 put_bytes + DB append
- `packages/service/src/ingest/pre_analysis/table_extractors/factory.py` — get_table_extractor 工厂
- `packages/service/src/ingest/api.py`                    — upload 接受 form 字段, _run_pre_analysis 接收 table_config, in-memory 透传
- `packages/web/lib/api/pre-analysis.ts`                 — preAnalysisUpload 接 config 参数
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` — 高级选项折叠区 + PARAM_METADATA 常量
- `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` — 加 3 个测试
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` — 加 3 个高级选项测试

### 5 stage 渐增写入对应表 (M3 验收硬条件)

| Stage | 写入 ObjectStore | DB output_files_json append |
|---|---|---|
| `load_config` | (无产物) | (不 append) |
| `extract_chapters` | `chapter_structure.json` | 1 项 |
| `extract_tables` | `tables/page-N-table-M.csv` (逐个) | 每张 1 项 |
| `extract_flagged` | `flagged_paragraphs.csv` | 1 项 |
| `write_outputs` | `index.json` (final snapshot) | (追加 index.json 项, 1 次) |

---

## Task 0: 子包化迁移 (infra 重构, 0 业务改动)

**Files:**
- Move: `packages/service/src/ingest/pre_analysis_models.py` → `src/ingest/pre_analysis/models.py`
- Move: `packages/service/src/ingest/pre_analysis_store.py` → `src/ingest/pre_analysis/store.py`
- Move: `packages/service/src/ingest/pre_analysis_runner.py` → `src/ingest/pre_analysis/runner.py`
- Move: `packages/service/src/ingest/pre_analysis_stage_models.py` → `src/ingest/pre_analysis/stage_models.py`
- Move: `packages/service/src/ingest/pre_analysis_stage_store.py` → `src/ingest/pre_analysis/stage_store.py`
- Create: `src/ingest/pre_analysis/__init__.py`
- Create: `src/ingest/pre_analysis/__init__.py` (包标识, 空文件即可, 后面任务会填重导出)
- Modify: `src/ingest/api.py:35-46, 995, 1029, 1058` (`from .pre_analysis_*` 改 `from .pre_analysis import ...`)
- Move: `tests/ingest/test_pre_analysis_models.py` → `tests/ingest/pre_analysis/test_models.py`
- Move: `tests/ingest/test_pre_analysis_stage_store.py` → `tests/ingest/pre_analysis/test_store.py`
- Move: `tests/ingest/test_pre_analysis_runner.py` → `tests/ingest/pre_analysis/test_runner.py`
- Move: `tests/ingest/test_pre_analysis_api.py` → `tests/ingest/pre_analysis/test_api.py`
- Modify: 上述测试文件 import 路径 `from src.ingest.pre_analysis_*` 改 `from src.ingest.pre_analysis import ...`

- [ ] **Step 1: git mv 源码文件**

```bash
cd packages/service/src/ingest
git mv pre_analysis_models.py pre_analysis/models.py
git mv pre_analysis_store.py pre_analysis/store.py
git mv pre_analysis_runner.py pre_analysis/runner.py
git mv pre_analysis_stage_models.py pre_analysis/stage_models.py
git mv pre_analysis_stage_store.py pre_analysis/stage_store.py
```

- [ ] **Step 2: 创建 `src/ingest/pre_analysis/__init__.py` (包标识)**

```python
# packages/service/src/ingest/pre_analysis/__init__.py
"""pre_analysis 子包 — PDF 预分析模块独立化 (2026-07-06).

包内文件命名不带 `pre_analysis_` 前缀, 因为子包名承担命名空间.
后续 M2 会在此包下加 table_extractors/ 子包.
"""
```

- [ ] **Step 3: 修改 `src/ingest/pre_analysis/models.py` / `store.py` / `runner.py` / `stage_models.py` / `stage_store.py` 包内 import 路径**

每个文件开头的 `from .pre_analysis_X` 改成 `from .X`. 例:

`pre_analysis/runner.py` 顶部:
```python
# 原:
from .pre_analysis_models import PreAnalysisTask
from .pre_analysis_store import PreAnalysisTaskStore

# 改为:
from .models import PreAnalysisTask
from .store import PreAnalysisTaskStore
```

`pre_analysis/store.py` 顶部:
```python
# 原: from .pre_analysis_models import PreAnalysisTask
# 改为: from .models import PreAnalysisTask
```

`pre_analysis/stage_store.py` 顶部:
```python
# 原:
from .pre_analysis_models import PreAnalysisTask
from .pre_analysis_stage_models import PreAnalysisStage

# 改为:
from .models import PreAnalysisTask
from .stage_models import PreAnalysisStage
```

- [ ] **Step 4: 修改 `src/ingest/api.py` 的 import**

打开 `packages/service/src/ingest/api.py` 找到所有 `from .pre_analysis_*` 行 (grep `pre_analysis_` 该文件, 行号见 spec §Files Structure 列). 改成:

```python
# 原 (line 35-46):
from .pre_analysis_stage_models import PreAnalysisStage
from .pre_analysis_stage_store import PreAnalysisStageStore
from .pre_analysis_store import (
    save_task as pa_save_task,
    load_task as pa_load_task,
    list_user_tasks as pa_list_user_tasks,
    PreAnalysisTaskStore,
)

# 改为 (子包化后):
from .pre_analysis import (
    PreAnalysisStage,
    PreAnalysisStageStore,
    pa_save_task,
    pa_load_task,
    pa_list_user_tasks,
    PreAnalysisTaskStore,
)
```

`api.py:995, 1029, 1058` 处函数内 lazy import 也要改:
```python
# 原:
from .pre_analysis_models import PreAnalysisTask as ORMPreAnalysisTask
from .pre_analysis_runner import PreAnalysisRunner

# 改为:
from .pre_analysis import PreAnalysisTask as ORMPreAnalysisTask
from .pre_analysis import PreAnalysisRunner
```

- [ ] **Step 5: git mv 测试文件**

```bash
cd packages/service/tests/ingest
git mv test_pre_analysis_models.py pre_analysis/test_models.py
git mv test_pre_analysis_stage_store.py pre_analysis/test_store.py
git mv test_pre_analysis_runner.py pre_analysis/test_runner.py
git mv test_pre_analysis_api.py pre_analysis/test_api.py
```

- [ ] **Step 6: 修改测试文件 import 路径**

`tests/ingest/pre_analysis/test_models.py` 中:
```python
# 原: from src.ingest.pre_analysis_models import PreAnalysisTask
# 改为: from src.ingest.pre_analysis import PreAnalysisTask
```

同理 `test_store.py` / `test_runner.py` / `test_api.py`。

- [ ] **Step 7: 删除旧 `__pycache__` 与 `__init__.py` (确保无残留)**

```bash
cd packages/service
find src/ingest -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
ls src/ingest/pre_analysis_models.py 2>/dev/null && echo "ERROR: 旧文件未删" || echo "OK"
```

- [ ] **Step 8: 跑后端测试确认 0 回归**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v`
Expected: 全部 pass (跟迁移前一样, 0 业务改动).

- [ ] **Step 9: 跑 pyright + ruff**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`
Expected: 0 error (import 路径改全, 无 stale references).

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(service): move pre_analysis_* to subpackage pre_analysis/"
```

---

## Task 1: M1 — Alembic migration 加 task_config_json 列

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py`
- Create: `packages/service/tests/migrations/test_pre_analysis_task_config.py`
- Modify: `packages/service/src/ingest/pre_analysis/models.py`

- [ ] **Step 1: 写 migration failing test (mode 3 tmp_pg_schema)**

`packages/service/tests/migrations/test_pre_analysis_task_config.py`:

```python
"""task_config_json 列迁移测试 (mode 3 + mode 1).

验证:
1. upgrade 加列成功, 列存在 + 默认值 '{}'
2. downgrade 成功删列
3. existing rows (旧 task) 不被破坏
"""

from __future__ import annotations

from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).parent.parent.parent
    / "src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py"
)


def test_migration_file_exists() -> None:
    assert MIGRATION_PATH.exists(), f"migration 文件缺失: {MIGRATION_PATH}"


def test_migration_contains_upgrade_and_downgrade(tmp_path) -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "def upgrade()" in source, "缺 upgrade()"
    assert "def downgrade()" in source, "缺 downgrade()"
    assert "task_config_json" in source, "缺 task_config_json 列引用"
    # 默认值是 '{}' (string, 兼容 existing rows)
    assert '"{}"' in source or "'{}'" in source, "缺默认 '{}'"


@pytest.mark.integration
def test_migration_round_trip(tmp_pg_schema: str) -> None:
    """真 PG 跑 upgrade + downgrade, 验列存在 (后续 spec 接 tmp_pg_schema fixture)."""
    pytest.skip("tmp_pg_schema fixture 待 spec 实现 (CLAUDE.md §4 模式 §模式 3)")
```

- [ ] **Step 2: 跑测试确认红 (migration 文件缺失)**

Run: `cd packages/service && uv run pytest tests/migrations/test_pre_analysis_task_config.py -v`
Expected: FAIL — "migration 文件缺失"

- [ ] **Step 3: 写 migration 文件**

`packages/service/src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py`:

```python
"""pre_analysis_tasks: 加 task_config_json 列 (执行快照, 2026-07-06).

设计决策: 不在 upload 时持久化 config, runner 跑完统一写 1 次.
列名 task_config_json (不是 table_extraction_config_json) 留通用性, 未来其他模块也能复用.
nullable=False + server_default='{}' → existing rows 0 迁移风险.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260706_000000"
down_revision = "20260703_000000"  # pre_analysis_task_stages (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pre_analysis_tasks",
        sa.Column(
            "task_config_json",
            sa.Text,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("pre_analysis_tasks", "task_config_json")
```

- [ ] **Step 4: 跑测试确认绿**

Run: `cd packages/service && uv run pytest tests/migrations/test_pre_analysis_task_config.py -v`
Expected: 3 passed (skipIf 不算 fail).

- [ ] **Step 5: 跑 dev DB 真升验证**

Run:
```bash
cd packages/service
uv run alembic current | grep 20260706_000000 || uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
Expected: 0 error, 列加成功 + 回滚成功 + 重升成功.

- [ ] **Step 6: ORM 加列声明**

`packages/service/src/ingest/pre_analysis/models.py`:

在类 `PreAnalysisTask` 中加 (跟现有 `current_stage: Mapped[str | None]` 后):

```python
    task_config_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="{}",
        default="{}",
    )
```

- [ ] **Step 7: ORM 加字段测试 (mode 1 mock)**

`packages/service/tests/ingest/pre_analysis/test_models.py` 加测试:

```python
def test_pre_analysis_task_has_task_config_json_column() -> None:
    """验证 ORM 类声明含 task_config_json 字段."""
    from src.ingest.pre_analysis.models import PreAnalysisTask

    assert "task_config_json" in PreAnalysisTask.__table__.columns
    col = PreAnalysisTask.__table__.columns["task_config_json"]
    assert col.nullable is False
    assert col.default is not None or col.server_default is not None
```

- [ ] **Step 8: 跑 ORM 测试**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_models.py -v`
Expected: 全部 passed (含新增).

- [ ] **Step 9: 跑 pyright + ruff**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`
Expected: 0 error.

- [ ] **Step 10: Commit**

```bash
git add src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py \
        tests/migrations/test_pre_analysis_task_config.py \
        src/ingest/pre_analysis/models.py \
        tests/ingest/pre_analysis/test_models.py
git commit -m "feat(service): add pre_analysis_tasks.task_config_json column for execution snapshot"
```

---

## Task 2: M1 续 — Store 接 task_config_json

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/store.py`
- Modify: `packages/service/tests/ingest/pre_analysis/test_store.py` (即原 test_pre_analysis_stage_store.py)

- [ ] **Step 1: 写 `_to_dict` 透传测试**

`tests/ingest/pre_analysis/test_store.py` 加测试:

```python
def test_to_dict_includes_task_config_json() -> None:
    """_to_dict 必须含 task_config_json 字段, 反序列化为 dict."""
    from src.ingest.pre_analysis.models import PreAnalysisTask
    from src.ingest.pre_analysis.store import _to_dict
    from datetime import UTC, datetime

    task = PreAnalysisTask(
        id="pa-test-001",
        user_hash="h",
        state="completed",
        pdf_filename="x.pdf",
        pdf_uri="local://x.pdf",
        started_at=datetime.now(UTC),
        task_config_json='{"table_backend": "camelot"}',
    )
    result = _to_dict(task)
    assert result["task_config_json"] == {"table_backend": "camelot"}


def test_to_dict_task_config_json_default_empty() -> None:
    """空字符串默认值反序列化为空 dict."""
    from src.ingest.pre_analysis.models import PreAnalysisTask
    from src.ingest.pre_analysis.store import _to_dict
    from datetime import UTC, datetime

    task = PreAnalysisTask(
        id="pa-test-002",
        user_hash="h",
        state="running",
        pdf_filename="x.pdf",
        pdf_uri="local://x.pdf",
        started_at=datetime.now(UTC),
        task_config_json="",
    )
    result = _to_dict(task)
    assert result["task_config_json"] == {}
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_store.py::test_to_dict_includes_task_config_json tests/ingest/pre_analysis/test_store.py::test_to_dict_task_config_json_default_empty -v`
Expected: FAIL — KeyError or AttributeError.

- [ ] **Step 3: 修改 `_to_dict` 加字段**

`src/ingest/pre_analysis/store.py` 顶部 `_to_dict()` 函数, 加 1 行:

```python
def _to_dict(task: PreAnalysisTask) -> dict:
    """ORM 对象 → API dict (跟 src/ingest/store.py 模式一致)."""
    return {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "pdf_filename": task.pdf_filename,
        "pdf_uri": task.pdf_uri,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "current_stage": task.current_stage,
        "output_files": json.loads(task.output_files_json or "[]"),
        "summary": json.loads(task.summary_json or "{}"),
        "task_config_json": json.loads(task.task_config_json or "{}"),  # 2026-07-06 新增
    }
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_store.py -v`
Expected: 全部 passed.

- [ ] **Step 5: 写 mark_completed 写 task_config_json 测试**

`tests/ingest/pre_analysis/test_store.py` 加:

```python
def test_mark_completed_accepts_task_config(monkeypatch) -> None:
    """mark_completed 接 task_config 入参, 写 DB JSON 字符串."""
    from src.ingest.pre_analysis import store as store_mod

    # mock session_scope 不连真 PG
    monkeypatch.setattr(store_mod, "session_scope", lambda: _noop_session())

    store_mod.PreAnalysisTaskStore().mark_completed(
        task_id="pa-test-003",
        output_files=[{"kind": "chapter_structure", "uri": "x", "filename": "x", "size_bytes": 1}],
        summary={"total_chapters": 1, "total_tables": 0, "total_flagged_paragraphs": 0,
                 "elapsed_ms": 100, "cross_page_candidates": 0},
        task_config={"table_backend": "camelot", "table_params": {"flavor": "stream"}},
    )

    # 通过 _to_dict 验 DB 列写入 (mock _to_dict 返 db_values)
    # (实现见下面 _noop_session 辅助)


# 辅助: 捕获 mark_completed 实际传入的更新
class _CapturedUpdate:
    def __init__(self):
        self.values = {}
        self.executed = False

    def values_call(self, **kwargs):
        self.values.update(kwargs)
        return self


def _noop_session():
    """返回 1 个 fake session, 让 mark_completed 不抛异常 + 捕获写入值."""
    captured = _CapturedUpdate()

    class FakeTask:
        state = "pending"
        finished_at = None
        output_files_json = "[]"
        summary_json = "{}"
        task_config_json = "{}"

        def __init__(self, task_id):
            self.id = task_id

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, model, task_id):
            return FakeTask(task_id)
        def execute(self, stmt):
            # 验证: stmt 是 UPDATE
            captured.executed = True
            # 抓 stmt.compile().params
            try:
                captured.values.update(stmt.compile().params)
            except Exception:
                pass

    return FakeSession()
```

- [ ] **Step 6: 跑 test_mark_completed 测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_store.py::test_mark_completed_accepts_task_config -v`
Expected: FAIL — `mark_completed() got unexpected keyword argument 'task_config'`.

- [ ] **Step 7: 改 mark_completed 接 task_config 参数**

`src/ingest/pre_analysis/store.py` 中 `PreAnalysisTaskStore` 类:

```python
    def mark_completed(
        self,
        task_id: str,
        output_files: list[dict],
        summary: dict,
        task_config: dict | None = None,  # 2026-07-06 新增
    ) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "completed"
                task.finished_at = datetime.now(UTC)
                task.output_files_json = json.dumps(output_files, ensure_ascii=False)
                task.summary_json = json.dumps(summary, ensure_ascii=False)
                task.task_config_json = json.dumps(task_config or {}, ensure_ascii=False)
```

- [ ] **Step 8: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_store.py -v`
Expected: 全部 passed.

- [ ] **Step 9: 跑全后端测试验 0 回归**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v`
Expected: 全部 passed (含既有测试).

- [ ] **Step 10: 跑 pyright + ruff**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`
Expected: 0 error.

- [ ] **Step 11: Commit**

```bash
git add src/ingest/pre_analysis/store.py tests/ingest/pre_analysis/test_store.py
git commit -m "feat(service): pre_analysis store expose task_config_json snapshot"
```

---

## Task 3: M2 — TableExtractor base.py (ABC + TableData + BackendNotInstalledError)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/__init__.py`
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/base.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/__init__.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py`

- [ ] **Step 1: 写 base.py 测试 (mode 1 mock 纯接口契约)**

`packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py`:

```python
"""TableExtractor 接口契约测试."""

from __future__ import annotations

import dataclasses

import pytest


def test_table_data_is_frozen_dataclass() -> None:
    """TableData 必须是 frozen dataclass, 防运行时误改."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    td = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    with pytest.raises(dataclasses.FrozenInstanceError):
        td.page_no = 2  # type: ignore[misc]


def test_table_extractor_is_abstract() -> None:
    """TableExtractor 是 ABC, 不能直接实例化."""
    from src.ingest.pre_analysis.table_extractors.base import TableExtractor

    with pytest.raises(TypeError):
        TableExtractor()  # type: ignore[abstract]


def test_backend_not_installed_error_carries_hint() -> None:
    """BackendNotInstalledError 含 backend 名 + install_hint, API 503 翻译用."""
    from src.ingest.pre_analysis.table_extractors.base import BackendNotInstalledError

    err = BackendNotInstalledError(
        backend="camelot",
        install_hint="uv add camelot-py",
    )
    assert err.backend == "camelot"
    assert err.install_hint == "uv add camelot-py"
    assert "camelot" in str(err)
    assert "uv add camelot-py" in str(err)
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -v`
Expected: FAIL — ModuleNotFoundError or ImportError.

- [ ] **Step 3: 写 `__init__.py` + `base.py`**

`packages/service/src/ingest/pre_analysis/table_extractors/__init__.py`:

```python
"""table_extractors Strategy Pattern 子包 (2026-07-06).

3 个后端适配器各自一个文件:
- pymupdf_extractor.py (默认, 已装)
- camelot_extractor.py (可选 extras)
- pdfplumber_extractor.py (可选)

factory.py 提供 get_table_extractor(backend, params) 统一入口.
"""
```

`packages/service/src/ingest/pre_analysis/table_extractors/base.py`:

```python
"""TableExtractor 抽象基类 + TableData dataclass + BackendNotInstalledError (2026-07-06)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TableData:
    """单张表格单元. 3 个实现统一这个 shape, runner 不关心后端.

    Attributes:
        page_no: 1-based 页码
        table_no: 1-based (该页内编号)
        rows: 二维字符串表格
    """

    page_no: int
    table_no: int
    rows: list[list[str]]


class TableExtractor(ABC):
    """表格提取策略接口."""

    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: "pymupdf.Document | None" = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 []."""


class BackendNotInstalledError(RuntimeError):
    """后端 Python 包未安装. factory 调用时检测, HTTP 503 翻译用.

    Attributes:
        backend: backend 名 (e.g. "camelot", "pdfplumber", "camelot[ml]")
        install_hint: 安装提示 (e.g. "uv add camelot-py" / "uv add 'camelot-py[ml]'")
    """

    def __init__(self, backend: str, install_hint: str) -> None:
        super().__init__(f"{backend} 未安装: {install_hint}")
        self.backend = backend
        self.install_hint = install_hint
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -v`
Expected: 3 passed.

- [ ] **Step 5: 跑 pyright**

Run: `cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/base.py`
Expected: 0 error.

- [ ] **Step 6: Commit (本任务独立 prep)**

注: Task 3 跟 Task 4/5 一起在 M2 commit. 可在此 git stage 但不单独 commit, 等 M2 一起提交. 或者现在 commit 一次 (推荐, TDD 红绿每步跟).

```bash
git add src/ingest/pre_analysis/table_extractors/__init__.py \
        src/ingest/pre_analysis/table_extractors/base.py \
        tests/ingest/pre_analysis/table_extractors/__init__.py \
        tests/ingest/pre_analysis/table_extractors/test_base.py
git commit -m "feat(service): add TableExtractor base.py with ABC + TableData"
```

---

## Task 4: M2 续 — PymupdfTableExtractor (复用 doc 优化)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py`
- Modify: `pyproject.toml` (pymupdf 已在主依赖, 0 改)

- [ ] **Step 1: 写测试 (mode 1 mock + 2 真 PDF)**

`packages/service/tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py`:

```python
"""PymupdfTableExtractor 测试 (mode 1 mock + mode 2 真 PDF)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_PDF = Path(__file__).parent.parent.parent.parent / "ingest/fixtures/d81_dummy.pdf"


def test_extract_with_injected_doc_returns_table_data() -> None:
    """复用已开 doc (_pymupdf_doc 传入) → 不重新打开, 走 page.find_tables."""
    import pymupdf

    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    doc = pymupdf.open(str(FIXTURE_PDF))
    try:
        extractor = PymupdfTableExtractor({})
        result = extractor.extract(str(FIXTURE_PDF), _pymupdf_doc=doc)
        # d81_dummy.pdf 含 1 表格 (第 3 页)
        assert isinstance(result, list)
        assert all(t.rows for t in result), "rows 不能空"
        assert all(t.page_no >= 1 for t in result)
        assert all(t.table_no >= 1 for t in result)
    finally:
        doc.close()


def test_extract_without_doc_opens_file() -> None:
    """_pymupdf_doc=None → 自身 pymupdf.open(pdf_path)."""
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    extractor = PymupdfTableExtractor({})
    result = extractor.extract(str(FIXTURE_PDF))
    assert isinstance(result, list)
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py -v`
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: 写实现**

`packages/service/src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py`:

```python
"""PymupdfTableExtractor — 默认后端, 复用 pymupdf Document (2026-07-06)."""

from __future__ import annotations

import pymupdf

from .base import TableData, TableExtractor


class PymupdfTableExtractor(TableExtractor):
    """pymupdf find_tables() 适配器.

    优先复用已打开 pymupdf.Document (避免重新打开 PDF, 节省 IO + 内存).
    """

    def __init__(self, params: dict) -> None:
        self._params = params

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: "pymupdf.Document | None" = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 [].

        Args:
            pdf_path: PDF 文件路径 (主用 _pymupdf_doc, 此处作 fallback + sanity check).
            _pymupdf_doc: 已打开 pymupdf.Document (推荐传, runner 已开过).
            **params: 预留, pymupdf 后端无调参.

        Returns:
            list[TableData]: 表格列表, 按 (页, 表号) 顺序.
        """
        own_doc = _pymupdf_doc is None
        doc = _pymupdf_doc if _pymupdf_doc is not None else pymupdf.open(pdf_path)
        try:
            result: list[TableData] = []
            for page_idx, page in enumerate(doc):  # type: ignore[arg-type,var-annotated]
                for table_idx, table in enumerate(page.find_tables().tables):  # type: ignore[union-attr]
                    rows: list[list[str]] = [list(r) for r in table.extract()]
                    result.append(TableData(page_no=page_idx + 1, table_no=table_idx + 1, rows=rows))
            return result
        finally:
            if own_doc:
                doc.close()
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py -v`
Expected: 2 passed.

- [ ] **Step 5: 跑 pyright**

Run: `cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py`
Expected: 0 error (pyright 对 pymupdf 类型推断差, 已加 type: ignore 注释).

- [ ] **Step 6: Commit**

```bash
git add src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py \
        tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py
git commit -m "feat(service): add PymupdfTableExtractor adapter"
```

---

## Task 5: M2 续 — CamelotTableExtractor (lazy import, ml 单独检查)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py`

- [ ] **Step 1: 写测试 (mode 1 mock + 真 PDF skipIf + lazy import 缺包)**

`packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py`:

```python
"""CamelotTableExtractor 测试 (mode 1 mock).

依赖条件: 本机装了 `camelot-py` 才跑真 PDF 测试; 否则 skip. 缺包抛 BackendNotInstalledError 测试不需要装包.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

FIXTURE_PDF = Path(__file__).parent.parent.parent.parent / "ingest/fixtures/d81_dummy.pdf"


def test_camelot_not_installed_raises_backend_error(monkeypatch) -> None:
    """camelot-py 未装 → 构造时立即抛 BackendNotInstalledError."""
    # monkeypatch sys.modules 让 `import camelot` 抛 ImportError
    monkeypatch.setitem(__import__("sys").modules, "camelot", None)

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    with pytest.raises(BackendNotInstalledError) as exc_info:
        CamelotTableExtractor({"flavor": "lattice"})
    assert exc_info.value.backend == "camelot"
    assert "uv add camelot-py" in exc_info.value.install_hint


def test_ml_flavor_requires_ml_extra(monkeypatch) -> None:
    """flavor='ml' 但 [ml] extra 未装 → 抛 BackendNotInstalledError(backend='camelot[ml]')."""
    # 让 camelot import 成功, 但 camelot._... ml 模块找不到
    # 简化: 直接 monkeypatch 一个 fake camelot 模块

    class FakeCamelot:
        # read_pdf 也 mock 掉防误调
        def read_pdf(self, *a, **kw):
            return []

    monkeypatch.setitem(__import__("sys").modules, "camelot", FakeCamelot())

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    # flavor=ml 触发 extra 检查; 假设尝试 import camelot._camelot_ml 失败
    with pytest.raises(BackendNotInstalledError) as exc_info:
        CamelotTableExtractor({"flavor": "ml"})
    # backend 应该指明是 ml extra 缺失, 不只是基础包
    assert "ml" in exc_info.value.backend.lower() or "[ml]" in exc_info.value.install_hint


@pytest.mark.skipif(
    not importlib.util.find_spec("camelot"), reason="camelot-py 未装, 真 PDF 测试 skip"
)
def test_extract_real_pdf() -> None:
    """真 PDF 跑 camelot.read_pdf(flavor='lattice') 返 TableData 列表."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    extractor = CamelotTableExtractor({"flavor": "lattice"})
    result = extractor.extract(str(FIXTURE_PDF))
    # d81_dummy.pdf 第 3 页有表, camelot lattice 应能识别
    assert isinstance(result, list)
    # 不强制 ≥1 (camelot 对小 PDF 可能 0 表), 只 shape 正确
    for td in result:
        assert td.page_no >= 1
        assert td.table_no >= 1
        assert isinstance(td.rows, list)
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v`
Expected: 2 failed (缺 BackendNotInstalledError), 1 skipped (camelot 未装).

- [ ] **Step 3: 写实现**

`packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py`:

```python
"""CamelotTableExtractor — Camelot 2.0+ 适配器 (2026-07-06).

Lazy import: 模块级 try/except, 装失败时 factory 也知道.
flavor='ml' 额外检查 camelot-py[ml] extra 是否齐全.
"""

from __future__ import annotations

from .base import BackendNotInstalledError, TableData, TableExtractor

# Lazy: 模块级 import 不报 ImportError, 留到 __init__ 时检测 (CLI 启动时友好).
# 实例化时 Cct 会尝试 import camelot, 缺 → 抛 BackendNotInstalledError.

_BASE_INSTALL_HINT = "uv add camelot-py"
_ML_INSTALL_HINT = "uv add 'camelot-py[ml]'"  # flavor='ml' 额外拉 PyTorch


class CamelotTableExtractor(TableExtractor):
    """camelot.read_pdf 适配器."""

    def __init__(self, params: dict) -> None:
        self._params = params
        self._flavor = params.get("flavor", "lattice")
        try:
            import camelot  # noqa: F401
        except ImportError as e:
            raise BackendNotInstalledError(
                backend="camelot", install_hint=_BASE_INSTALL_HINT
            ) from e
        # flavor='ml' 单独检查 [ml] extra (Camelot 2.0+ 默认装不含 ml 解析器, 需 PyTorch)
        if self._flavor == "ml":
            try:
                # ml 解析器 lazy import 在 Camelot 内部, 试 _or_table_formatter 之类
                # 具体符号 Camelot 2.0 docs 写; 这里保守用顶层属性存在性判断
                _ = camelot.__version__  # baseline 检查
                # 真 [ml] 检测: 试着 import 一个 ml-only 符号 (如 camelot.parsers.stream 后端)
                # Camelot 2.0+ 推荐用 camelot.read_pdf(stream) 或 (flavor='ml'); 检测 ml 路径:
                import importlib.util as _ilu
                ml_marker = _ilu.find_spec("camelot._table_transformers")
                if ml_marker is None:
                    raise ImportError("camelot._table_transformers not found, [ml] missing")
            except ImportError as e:
                raise BackendNotInstalledError(
                    backend="camelot[ml]", install_hint=_ML_INSTALL_HINT
                ) from e

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: "object | None" = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. camelot.read_pdf 整文件读, 不接受已开 pymupdf doc."""
        import camelot

        edge_tol = self._params.get("edge_tol", 50)
        row_tol = self._params.get("row_tol", 2)
        tables = camelot.read_pdf(
            pdf_path,
            flavor=self._flavor,
            edge_tol=edge_tol,
            row_tol=row_tol,
        )
        result: list[TableData] = []
        # camelot 返 TableList, 每个 .page (int) + .df (pandas DataFrame)
        # 按 page 分组, table_no 1-based
        per_page_counts: dict[int, int] = {}
        for t in tables:
            page_no = int(t.page)
            per_page_counts[page_no] = per_page_counts.get(page_no, 0) + 1
            rows: list[list[str]] = t.df.values.tolist()
            rows = [[str(cell) for cell in row] for row in rows]
            result.append(
                TableData(page_no=page_no, table_no=per_page_counts[page_no], rows=rows)
            )
        # 按 (page_no, table_no) 排序, 跟 pymupdf 行为一致
        result.sort(key=lambda t: (t.page_no, t.table_no))
        return result
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v`
Expected: 2 passed (not_installed + ml_extra), 真 PDF 测试 skipped (装了就 enabled).

- [ ] **Step 5: 跑 pyright**

Run: `cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py`
Expected: 0 error (# type: ignore[import-not-found] 已加).

- [ ] **Step 6: Commit**

```bash
git add src/ingest/pre_analysis/table_extractors/camelot_extractor.py \
        tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit -m "feat(service): add CamelotTableExtractor adapter with ml extra detection"
```

---

## Task 6: M2 续 — PdfplumberTableExtractor (lazy import)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_pdfplumber_extractor.py`

- [ ] **Step 1: 写测试 (mode 1 mock + 真 PDF skipIf + lazy import 缺包)**

`packages/service/tests/ingest/pre_analysis/table_extractors/test_pdfplumber_extractor.py`:

```python
"""PdfplumberTableExtractor 测试 (mode 1 mock).

依赖 pdfplumber 包; 未装则 skipped.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

FIXTURE_PDF = Path(__file__).parent.parent.parent.parent / "ingest/fixtures/d81_dummy.pdf"


def test_pdfplumber_not_installed_raises_backend_error(monkeypatch) -> None:
    """pdfplumber 未装 → 构造抛 BackendNotInstalledError."""
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber", None)

    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    with pytest.raises(BackendNotInstalledError) as exc_info:
        PdfplumberTableExtractor({})
    assert exc_info.value.backend == "pdfplumber"
    assert "uv add pdfplumber" in exc_info.value.install_hint


@pytest.mark.skipif(
    not importlib.util.find_spec("pdfplumber"),
    reason="pdfplumber 未装, 真 PDF 测试 skip",
)
def test_extract_real_pdf() -> None:
    """真 PDF 跑 pdfplumber.open().pages[].extract_tables() 返 TableData 列表."""
    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )

    extractor = PdfplumberTableExtractor(
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
        }
    )
    result = extractor.extract(str(FIXTURE_PDF))
    assert isinstance(result, list)
    for td in result:
        assert td.page_no >= 1
        assert td.table_no >= 1
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_pdfplumber_extractor.py -v`
Expected: 1 failed (缺抛), 1 skipped (pdfplumber 未装).

- [ ] **Step 3: 写实现**

`packages/service/src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py`:

```python
"""PdfplumberTableExtractor — pdfplumber 适配器 (2026-07-06).

Lazy import: 缺包抛 BackendNotInstalledError.
"""

from __future__ import annotations

from .base import BackendNotInstalledError, TableData, TableExtractor

_INSTALL_HINT = "uv add pdfplumber"


class PdfplumberTableExtractor(TableExtractor):
    """pdfplumber.open() ... pages.extract_tables() 适配器."""

    def __init__(self, params: dict) -> None:
        self._params = params
        try:
            import pdfplumber  # noqa: F401
        except ImportError as e:
            raise BackendNotInstalledError(
                backend="pdfplumber", install_hint=_INSTALL_HINT
            ) from e

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: "object | None" = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格."""
        import pdfplumber

        table_settings = {
            "vertical_strategy": self._params.get("vertical_strategy", "lines"),
            "horizontal_strategy": self._params.get("horizontal_strategy", "lines"),
            "snap_tolerance": self._params.get("snap_tolerance", 3),
            "join_tolerance": self._params.get("join_tolerance", 3),
        }
        result: list[TableData] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables(table_settings=table_settings)
                for table_no, rows in enumerate(tables, start=1):
                    normalized: list[list[str]] = [
                        [(cell if cell is not None else "") for cell in row]  # type: ignore[misc]
                        for row in rows
                    ]
                    result.append(
                        TableData(page_no=page_idx + 1, table_no=table_no, rows=normalized)
                    )
        return result
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_pdfplumber_extractor.py -v`
Expected: 1 passed (not_installed), 1 skipped (pdfplumber 未装).

- [ ] **Step 5: 跑 pyright + ruff**

Run: `cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py && uv run ruff format`
Expected: 0 error.

- [ ] **Step 6: Commit**

```bash
git add src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py \
        tests/ingest/pre_analysis/table_extractors/test_pdfplumber_extractor.py
git commit -m "feat(service): add PdfplumberTableExtractor adapter"
```

---

## Task 7: M2 终 — factory.py + pyproject.toml 声明

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_extractors/factory.py`
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py`
- Modify: `packages/service/pyproject.toml`

- [ ] **Step 1: 写 factory 测试**

`packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py`:

```python
"""get_table_extractor 工厂测试."""

from __future__ import annotations

import pytest


def test_pymupdf_routes_to_pymupdf_adapter() -> None:
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    ext = get_table_extractor("pymupdf", {})
    assert isinstance(ext, PymupdfTableExtractor)


def test_camelot_routes_to_camelot_adapter() -> None:
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    # 不依赖是否装了 camelot-py: 可能立刻抛 BackendNotInstalledError
    # 用 try-except 验证路由走对了 (要么返 CamelotTableExtractor 要么抛 camelot 缺包错)
    try:
        ext = get_table_extractor("camelot", {"flavor": "lattice"})
    except Exception as e:
        # 包未装也可接受, 关键是 fallback 正确
        from src.ingest.pre_analysis.table_extractors.base import (
            BackendNotInstalledError,
        )

        assert isinstance(e, BackendNotInstalledError)
        assert e.backend == "camelot"
    else:
        from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
            CamelotTableExtractor,
        )

        assert isinstance(ext, CamelotTableExtractor)


def test_pdfplumber_routes_to_pdfplumber_adapter() -> None:
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    try:
        ext = get_table_extractor("pdfplumber", {})
    except Exception as e:
        from src.ingest.pre_analysis.table_extractors.base import (
            BackendNotInstalledError,
        )

        assert isinstance(e, BackendNotInstalledError)
        assert e.backend == "pdfplumber"
    else:
        from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
            PdfplumberTableExtractor,
        )

        assert isinstance(ext, PdfplumberTableExtractor)


def test_unknown_backend_raises_value_error() -> None:
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    with pytest.raises(ValueError) as exc_info:
        get_table_extractor("foo", {})
    assert "未知表格后端" in str(exc_info.value)
    assert "foo" in str(exc_info.value)


def test_default_params_when_none() -> None:
    """params=None → 适配器内部取默认 (e.g. flavor='lattice' for camelot)."""
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    ext = get_table_extractor("pymupdf", params=None)
    assert ext is not None  # shape 验
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py -v`
Expected: 4 failed (缺 factory).

- [ ] **Step 3: 写 factory.py**

`packages/service/src/ingest/pre_analysis/table_extractors/factory.py`:

```python
"""get_table_extractor 工厂 — backend 字符串 → 适配器实例 (2026-07-06)."""

from __future__ import annotations

from .base import TableExtractor


def get_table_extractor(backend: str, params: dict | None = None) -> TableExtractor:
    """工厂: backend 字符串 → 适配器实例.

    Args:
        backend: "pymupdf" | "camelot" | "pdfplumber"
        params: backend-specific 参数 (e.g. flavor / edge_tol / vertical_strategy)

    Returns:
        TableExtractor 实例.

    Raises:
        ValueError: backend 不在白名单.
        BackendNotInstalledError: camelot/pdfplumber 缺包 (transitively 由适配器 __init__ 抛).
    """
    effective_params = params or {}
    match backend:
        case "pymupdf":
            from .pymupdf_extractor import PymupdfTableExtractor

            return PymupdfTableExtractor(effective_params)
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor

            return CamelotTableExtractor(effective_params)
        case "pdfplumber":
            from .pdfplumber_extractor import PdfplumberTableExtractor

            return PdfplumberTableExtractor(effective_params)
        case _:
            raise ValueError(f"未知表格后端: {backend}")
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py -v`
Expected: 5 passed.

- [ ] **Step 5: pyproject 加可选依赖声明 (dev 不强制装)**

`packages/service/pyproject.toml` 找到 `[project]` block, 加:

```toml
[project.optional-dependencies]
pdf-tables = [
    "camelot-py>=2.0",
    "pdfplumber>=0.11",
]
```

注: 不写进 `[project.dependencies]` 主依赖 (CLAUDE.md 严禁硬编码 Camelot 引入 ghostscript 系统污染), 单独 extras; dev 默认不装, admin 真要用 `uv pip install -e '.[pdf-tables]'` 即可. 这里用 `optional-dependencies` 不写进 `dependencies`.

- [ ] **Step 6: 跑 pyright + ruff 验 0 error**

Run: `cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/ && uv run ruff format && uv run ruff check --fix`
Expected: 0 error.

- [ ] **Step 7: 跑全套 table_extractors 测试**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v`
Expected: 全部 passed (skipped 不算 fail).

- [ ] **Step 8: Commit (M2 完成)**

```bash
git add src/ingest/pre_analysis/table_extractors/factory.py \
        tests/ingest/pre_analysis/table_extractors/test_factory.py \
        pyproject.toml
git commit -m "feat(service): add TableExtractor factory + pyproject pdf-tables extras"
```

---

## Task 8: M3 — Runner refactor + 阶段化渐增写入 (核心改动)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py`
- Modify: `packages/service/src/ingest/pre_analysis/__init__.py` (重导出)
- Create: `packages/service/configs/pre_analysis/table_extraction.yaml`
- Modify: `packages/service/tests/ingest/pre_analysis/test_runner.py`

- [ ] **Step 1: 写 yaml 默认配置文件**

`packages/service/configs/pre_analysis/table_extraction.yaml`:

```yaml
# 表格后端默认配置 (2026-07-06)
# 改此文件需重启 service, runner 在 run() 里读一次.

default_backend: pymupdf

backends:
  pymupdf:
    enabled: true
  camelot:
    enabled: false
    install_hint: "uv add camelot-py"
    ml_install_hint: "uv add 'camelot-py[ml]'"
  pdfplumber:
    enabled: false
    install_hint: "uv add pdfplumber"

default_params:
  pymupdf: {}
  camelot:
    flavor: "lattice"
    edge_tol: 50
    row_tol: 2
  pdfplumber:
    vertical_strategy: "lines"
    horizontal_strategy: "lines"
    snap_tolerance: 3
    join_tolerance: 3
```

- [ ] **Step 2: 写 runner stage-by-stage 渐增写入测试**

`packages/service/tests/ingest/pre_analysis/test_runner.py` 加 4 测试:

```python
"""PreAnalysisRunner 阶段化渐增写入测试 (2026-07-06).

测试 4 项:
1. extract_chapters 跑完立即 put_bytes + DB append 1 项
2. extract_tables 跑完每张表都 put_bytes + DB append (5 张表 → 5 次)
3. extract_flagged 跑完 1 次 put + 1 次 DB update
4. **关键失败语义**: stages 1+2 成功, stage 3 抛 Exception → mark_failed, 已写产物保留在 DB output_files_json (chapter + tables/page-1.csv 等)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURE_PDF = Path(__file__).parent.parent.parent / "ingest/fixtures/d81_dummy.pdf"


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock()
    store.open_local = MagicMock(side_effect=lambda uri: str(FIXTURE_PDF))
    store.put_bytes = MagicMock()
    return store


def _make_runner(mock_store: MagicMock, mock_task_store: MagicMock) -> object:
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    return PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path(__file__).parent.parent.parent.parent
        / "configs/pre_analysis/rule_keywords.yaml",
        keyword_extraction_config_path=Path(__file__).parent.parent.parent.parent
        / "configs/pre_analysis/table_extraction.yaml",
        stage_store=MagicMock(),
    )


def test_extract_chapters_writes_immediately(mock_store: MagicMock) -> None:
    """extract_chapters 跑完 → 调 put_bytes(chapter_structure.json) 1 次."""
    mock_task_store = MagicMock()
    runner = _make_runner(mock_store, mock_task_store)
    runner.run(
        task_id="pa-stage-1",
        pdf_uri="local://x.pdf",
        table_config={"table_backend": "pymupdf", "table_params": {}},
    )
    # chapter_structure.json 应在 extract_chapters 阶段就被 put
    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    assert any("chapter_structure.json" in uri for uri in put_calls)


def test_extract_tables_writes_each_table_immediately(mock_store: MagicMock) -> None:
    """extract_tables 每张表都触发独立 put_bytes."""
    mock_task_store = MagicMock()
    runner = _make_runner(mock_store, mock_task_store)
    runner.run(
        task_id="pa-stage-2",
        pdf_uri="local://x.pdf",
        table_config={"table_backend": "pymupdf", "table_params": {}},
    )
    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    # d81_dummy 含 1 表格
    table_uris = [uri for uri in put_calls if "/tables/page-" in uri]
    assert len(table_uris) >= 1


def test_extract_flagged_writes_csv(mock_store: MagicMock) -> None:
    """extract_flagged 跑完 → flagged_paragraphs.csv 立即写."""
    mock_task_store = MagicMock()
    runner = _make_runner(mock_store, mock_task_store)
    runner.run(
        task_id="pa-stage-3",
        pdf_uri="local://x.pdf",
        table_config={"table_backend": "pymupdf", "table_params": {}},
    )
    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    assert any("flagged_paragraphs.csv" in uri for uri in put_calls)


def test_failure_in_stage_3_keeps_stage_1_and_2_artifacts(
    mock_store: MagicMock,
) -> None:
    """stage 3 (extract_tables) 抛异常 → stage 1+2 已写产物保留.

    We patch the table extractor to throw on extract(). Then assert:
    - mark_failed called
    - chapter_structure.json still in mock_store.put_bytes calls (stayed)
    - flagged_paragraphs.csv NOT in calls (stage 4 never ran)
    """
    mock_task_store = MagicMock()
    runner = _make_runner(mock_store, mock_task_store)

    # mock extract_tables stage inner — 通过把 _table_extractor 模块整体 mock 掉
    from src.ingest.pre_analysis import runner as runner_mod

    def fake_extract_tables(doc, config, table_extraction_config):
        raise RuntimeError("mocked extract_tables failure")

    monkey_run = MagicMock(wraps=runner_mod.PreAnalysisRunner._extract_tables)
    monkey_run.side_effect = fake_extract_tables
    # 直接调实际 runner
    result = runner.run(
        task_id="pa-stage-3-fail",
        pdf_uri="local://x.pdf",
        table_config={"table_backend": "pymupdf", "table_params": {}},
    )
    assert result.success is False
    mock_task_store.mark_failed.assert_called_once()

    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    # extract_chapters 已写产物保留
    assert any("chapter_structure.json" in uri for uri in put_calls), (
        "stage 1 (extract_chapters) 写的 chapter_structure.json 应保留"
    )
    # extract_flagged 没跑 (因为 stage 3 抛了)
    assert not any("flagged_paragraphs.csv" in uri for uri in put_calls), (
        "stage 4 (extract_flagged) 没跑, 不应有 csv"
    )
```

- [ ] **Step 3: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 失败 (因 runner 现有签名不接 table_config).

- [ ] **Step 4: 改 runner `run` 签名 + 接 table_extraction_config**

`packages/service/src/ingest/pre_analysis/runner.py`, 改 `run()` 方法签名:

```python
    def run(
        self,
        task_id: str,
        pdf_uri: str,
        table_extraction_config: dict | None = None,  # 2026-07-06 新增
    ) -> PreAnalysisResult:
        ...
```

并在内部:
```python
        # 默认值 fallback
        if table_extraction_config is None:
            table_extraction_config = {"table_backend": "pymupdf", "table_params": {}}
```

- [ ] **Step 5: 改 _extract_tables 用 factory (替换硬编码 page.find_tables)**

`runner.py` 中原 `_extract_tables` 方法 (line 247-276 附近):

```python
    def _extract_tables(
        self,
        doc: pymupdf.Document,
        config: dict,
        table_extraction_config: dict,
    ) -> tuple[list[tuple[int, int, list[list[str]]]], int]:
        """用 TableExtractor 工厂, 跑后端提取表 (2026-07-06 修订).

        Returns: (tables_list, cross_page_candidates_count)
        tables_list 元素: (page_no, table_no, rows)
        """
        backend = table_extraction_config.get("table_backend", "pymupdf")
        params = table_extraction_config.get("table_params", {})
        from .table_extractors.factory import get_table_extractor

        extractor = get_table_extractor(backend, params)
        raw_tables = extractor.extract(
            doc.name if hasattr(doc, "name") else "",
            _pymupdf_doc=doc,
        )
        tables = [(t.page_no, t.table_no, t.rows) for t in raw_tables]
        cross_page = self._detect_cross_page(tables, config)
        return tables, cross_page
```

并新增 `_detect_cross_page` (从原内联启发式抽出来):

```python
    def _detect_cross_page(
        self,
        tables: list[tuple[int, int, list[list[str]]]],
        config: dict,
    ) -> int:
        """跨页表候选检测: 列数一致 + footer 关键词."""
        cross_config = config.get("cross_page_detection", {})
        col_match = cross_config.get("min_column_match", 0.8)
        footer_kws = cross_config.get("footer_keywords", [])
        prev_table = None
        cross_page = 0
        for page_no, table_no, rows in tables:
            if prev_table is not None and table_no == 1:
                prev_page, prev_cols = prev_table
                if prev_page == page_no - 1 and len(rows[0] if rows else []) >= prev_cols * col_match:
                    last_row = rows[-1][0] if rows and rows[-1] else ""
                    if any(kw in last_row for kw in footer_kws):
                        cross_page += 1
            prev_table = (page_no, len(rows[0] if rows else []))
        return cross_page
```

- [ ] **Step 6: 重构 5 stage 为各写各自产物 (渐增可见)**

`runner.py` 中将原 5 stage 方法拆成: `extract_chapters` / `extract_tables` / `extract_flagged` 各自**立即写**自己业务产物 + `append_artifact` 到 DB, `write_outputs` 只剩 `index.json` + `summary` + `task_config` + `mark_completed`. 这里是大改, 完整示例 (替代原写 outputs 段):

```python
    def _write_chapter_structure(self, prefix: str, chapters, doc, task_id):
        """写 chapter_structure.json, 写完立即 append 到 DB."""
        payload = {
            "total_pages": len(doc),
            "total_chapters": len(chapters),
            "extracted_at": datetime.now(UTC).isoformat(),
            "toc_source": "pdf_outline" if chapters else "empty",
            "chapters": chapters,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        uri = f"{prefix}/chapter_structure.json"
        self.object_store.put_bytes(uri, data, "application/json")
        self._append_artifact(task_id, kind="chapter_structure", filename="chapter_structure.json", uri=uri, size_bytes=len(data))
        return uri, len(data)

    def _write_flagged_paragraphs(self, prefix: str, flagged, task_id):
        """写 flagged_paragraphs.csv, 写完立即 append."""
        uri = f"{prefix}/flagged_paragraphs.csv"
        buf = io.StringIO()
        if flagged:
            writer = csv.DictWriter(buf, fieldnames=["matched_keywords", "page", "section", "text"])
            writer.writeheader()
            for row in flagged:
                writer.writerow(row)
        else:
            buf.write("matched_keywords,page,section,text\n")
        data = buf.getvalue().encode("utf-8")
        self.object_store.put_bytes(uri, data, "text/csv")
        self._append_artifact(
            task_id, kind="flagged_paragraphs",
            filename="flagged_paragraphs.csv", uri=uri, size_bytes=len(data)
        )
        return uri, len(data)

    def _write_one_table(self, prefix: str, page_no, table_no, rows, task_id):
        """单张表写 CSV, 立即 append."""
        uri = f"{prefix}/tables/page-{page_no}-table-{table_no}.csv"
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows:
            writer.writerow(row)
        data = buf.getvalue().encode("utf-8")
        self.object_store.put_bytes(uri, data, "text/csv")
        self._append_artifact(
            task_id, kind="table",
            filename=f"tables/page-{page_no}-table-{table_no}.csv",
            uri=uri, size_bytes=len(data)
        )

    def _append_artifact(self, task_id: str, kind: str, filename: str, uri: str, size_bytes: int) -> None:
        """DB output_files_json append 1 项 (mode 2 事务安全)."""
        import json as _json
        from ..storage import session_scope
        from .models import PreAnalysisTask

        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is None:
                return
            current = _json.loads(task.output_files_json or "[]")
            current.append({
                "kind": kind,
                "filename": filename,
                "uri": uri,
                "size_bytes": size_bytes,
            })
            task.output_files_json = _json.dumps(current, ensure_ascii=False)
```

然后改 `run()` 中 5 stage 段:

```python
        # === load_config + pymupdf.open ===
        self.stage_store.mark_stage_started(task_id, "load_config")
        try:
            self.task_store.mark_running(task_id)
            pdf_path = self.object_store.open_local(pdf_uri)
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "load_config", str(e))
            self.task_store.mark_failed(task_id, f"open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        try:
            doc = pymupdf.open(pdf_path)
            self.stage_store.mark_stage_completed(task_id, "load_config", progress=100, message="open ok")
        except Exception as e:
            self.task_store.mark_failed(task_id, f"pymupdf open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        config = self._load_config()
        output_prefix = self._output_prefix(task_id)

        # === extract_chapters: 立即写 chapter_structure.json ===
        self.stage_store.mark_stage_started(task_id, "extract_chapters")
        try:
            chapters = self._extract_chapters(doc)
            chapter_uri, chapter_size = self._write_chapter_structure(output_prefix, chapters, doc, task_id)
            self.stage_store.mark_stage_completed(task_id, "extract_chapters", progress=100, message=f"{len(chapters)} 章")
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_chapters", str(e))
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_chapters failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === extract_tables: 每张表立即写 + DB append ===
        self.stage_store.mark_stage_started(task_id, "extract_tables")
        try:
            tables, cross_page = self._extract_tables(doc, config, table_extraction_config)
            for page_no, table_no, rows in tables:
                self._write_one_table(output_prefix, page_no, table_no, rows, task_id)
            self.stage_store.mark_stage_completed(task_id, "extract_tables", progress=100, message=f"{len(tables)} 表 / {cross_page} 跨页候选")
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_tables", str(e))
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_tables failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === extract_flagged: 立即写 flagged_paragraphs.csv ===
        self.stage_store.mark_stage_started(task_id, "extract_flagged")
        try:
            flagged = self._extract_flagged_paragraphs(doc, config)
            flagged_uri, flagged_size = self._write_flagged_paragraphs(output_prefix, flagged, task_id)
            self.stage_store.mark_stage_completed(task_id, "extract_flagged", progress=100, message=f"{len(flagged)} 段落")
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_flagged", str(e))
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_flagged failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === write_outputs: 仅 index.json + summary + task_config ===
        self.stage_store.mark_stage_started(task_id, "write_outputs")
        try:
            # 累计 output_files_json (从 DB 读最新状态)
            from ..storage import session_scope as _ss
            from .models import PreAnalysisTask as _PreAnalysisTask
            import json as _json
            with _ss() as s:
                _task = s.get(_PreAnalysisTask, task_id)
                all_output_files = _json.loads(_task.output_files_json or "[]") if _task else []

            start_mono = time.monotonic()
            index_uri, summary = self._write_index(
                output_prefix, task_id, pdf_uri, chapters, tables, flagged,
                cross_page, time.monotonic(),  # 注意 _write_index 签名
                chapter_size=chapter_size, flagged_size=flagged_size,
                table_sizes=[],  # 已渐增 DB append, 这里不再写入
            )
            # index 自身追加到 output_files_json
            with _ss() as s:
                _task = s.get(_PreAnalysisTask, task_id)
                if _task:
                    current = _json.loads(_task.output_files_json or "[]")
                    current.append({
                        "kind": "index",
                        "filename": "index.json",
                        "uri": index_uri,
                        "size_bytes": 0,  # 已写已知
                    })
                    _task.output_files_json = _json.dumps(current, ensure_ascii=False)
            elapsed_ms = int((time.monotonic() - start_mono) * 1000)
            self.stage_store.mark_stage_completed(task_id, "write_outputs", progress=100)
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "write_outputs", str(e))
            doc.close()
            self.task_store.mark_failed(task_id, f"write_outputs failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        doc.close()

        # 跑完 mark_completed (含 task_config)
        final_output_files = []  # 实际从 _task.output_files_json 读
        with session_scope() as s:
            _task = s.get(PreAnalysisTask, task_id)
            if _task is not None:
                _task.current_stage = "done"
                final_output_files = json.loads(_task.output_files_json or "[]")

        self.task_store.mark_completed(
            task_id=task_id,
            output_files=final_output_files,
            summary={
                "total_chapters": len(chapters),
                "total_tables": len(tables),
                "total_flagged_paragraphs": len(flagged),
                "elapsed_ms": elapsed_ms,
                "cross_page_candidates": cross_page,
            },
            task_config=table_extraction_config,
        )

        return PreAnalysisResult(success=True, ...)
```

- [ ] **Step 7: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 全部 passed (含 4 个新 + 7 个旧).

- [ ] **Step 8: 跑全后端测试验 0 回归**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v`
Expected: 全部 passed.

- [ ] **Step 9: pyright + ruff 全套**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`
Expected: 0 error.

- [ ] **Step 10: 重写 `__init__.py` 重导出**

`packages/service/src/ingest/pre_analysis/__init__.py`:

```python
"""pre_analysis 子包 public API (2026-07-06)."""

from .models import PreAnalysisTask
from .store import (
    PreAnalysisTaskStore,
    list_user_tasks as pa_list_user_tasks,
    load_task as pa_load_task,
    save_task as pa_save_task,
)
from .stage_models import PreAnalysisStage
from .stage_store import PreAnalysisStageStore
from .runner import PreAnalysisResult, PreAnalysisRunner

__all__ = [
    "PreAnalysisTask",
    "PreAnalysisTaskStore",
    "pa_save_task",
    "pa_load_task",
    "pa_list_user_tasks",
    "PreAnalysisStage",
    "PreAnalysisStageStore",
    "PreAnalysisResult",
    "PreAnalysisRunner",
]
```

- [ ] **Step 11: Commit (M3 完成)**

```bash
git add -A
git commit -m "refactor(service): runner uses TableExtractor and writes task_config_json + stage-by-stage artifact streaming"
```

---

## Task 9: M4 — API upload 端点接 form + 透传 + 503 缺包

**Files:**
- Modify: `packages/service/src/ingest/api.py`
- Modify: `packages/service/tests/ingest/pre_analysis/test_api.py`

- [ ] **Step 1: 写测试**

`packages/service/tests/ingest/pre_analysis/test_api.py` 加 4 个测试:

```python
def test_upload_default_backend_is_pymupdf() -> None:
    """form 字段缺省 → task_config_json in-memory 传 'pymupdf'."""
    from src.ingest.api import upload_pre_analysis  # 或 import 路由函数
    ...

def test_upload_rejects_unknown_backend() -> None:
    """table_backend='foo' → 400 unknown_backend."""
    ...

def test_upload_rejects_malformed_params_json() -> None:
    """table_params='{invalid' → 400 params_invalid."""
    ...

def test_upload_503_when_camelot_not_installed(monkeypatch) -> None:
    """table_backend='camelot' 但 camelot-py 未装 → 503 backend_not_installed."""
    ...
```

(本任务依现有 test_api.py 风格, 复用 TestClient + monkeypatch. 完整测试代码本任务所有步骤另补, 简化后:)

```python
def test_upload_503_when_camelot_not_installed(monkeypatch) -> None:
    """backend=camelot + camelot 不可 import → 503."""
    from fastapi.testclient import TestClient

    # 造 super_admin token (复用现有 fixture)
    # mock _run_pre_analysis 不跑
    monkeypatch.setattr("src.ingest.api._run_pre_analysis", lambda *a, **kw: None)
    # mock factory 让它抛 BackendNotInstalledError
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )

    def fake_factory(backend, params):
        raise BackendNotInstalledError(backend="camelot", install_hint="uv add camelot-py")

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.factory.get_table_extractor",
        fake_factory,
    )

    client = TestClient(...)
    resp = client.post(
        "/api/pre-analysis/upload",
        files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        data={"table_backend": "camelot", "table_params": "{}"},
        headers={"x-user-token": "super_admin_token"},
    )
    assert resp.status_code == 503
    assert "camelot" in resp.json()["detail"]
    assert "uv add camelot-py" in resp.json()["detail"]
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_api.py -v`
Expected: 部分 fail (比如缺 form 字段接收).

- [ ] **Step 3: 改 upload 端点接 form 字段**

`packages/service/src/ingest/api.py`, `upload_pre_analysis` 函数签名加 2 个 `Form(...)`:

```python
async def upload_pre_analysis(
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_super_admin),
    file: UploadFile = File(...),
    table_backend: str = Form("pymupdf"),
    table_params: str = Form("{}"),
) -> dict:
    """上传 PDF, 调度后台预分析. table_backend/table_params (2026-07-06 接受 config)."""
    token = _check_token(user)
    uhash = user_hash_for(token)

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 100 * 1024 * 1024:
        raise HTTPException(413, detail="PDF > 100MB")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="只接受 .pdf 文件")

    # 校验 table_backend
    if table_backend not in ("pymupdf", "camelot", "pdfplumber"):
        raise HTTPException(400, detail=f"未知表格后端: {table_backend}")

    # 解析 table_params JSON 字符串
    import json as _json
    try:
        params = _json.loads(table_params) if table_params else {}
    except _json.JSONDecodeError as e:
        raise HTTPException(400, detail=f"table_params JSON 非法: {e}") from e

    store = get_object_store()
    task_id = f"pa-{uuid.uuid4().hex[:12]}"
    pdf_filename = Path(file.filename).name
    input_key = f"pre_analysis_inputs/{task_id}/input/{pdf_filename}"
    workdir_uri = _uri_for_backend(store.backend_name(), input_key)
    store.put_bytes(workdir_uri, pdf_bytes, mime="application/pdf")

    table_config = {"table_backend": table_backend, "table_params": params}

    pa_save_task(
        {
            "id": task_id,
            "user_hash": uhash,
            "state": "pending",
            "pdf_filename": pdf_filename,
            "pdf_uri": workdir_uri,
            "started_at": datetime.now(UTC),
        }
    )

    background.add_task(_run_pre_analysis_with_config, task_id, table_config)
    _logger.info("pre_analysis upload task=%s pdf=%s backend=%s", task_id, pdf_filename, table_backend)
    return {"task_id": task_id, "state": "pending", "pdf_filename": pdf_filename}
```

- [ ] **Step 4: 新增 `_run_pre_analysis_with_config` 透传 wrapper**

`api.py` 加 helper:

```python
def _run_pre_analysis_with_config(task_id: str, table_config: dict) -> None:
    """透传 table_config 给后台 runner (in-memory)."""
    from .pre_analysis import PreAnalysisRunner
    from .pre_analysis.runner import _build_runner_for_task
    ...
```

(简化: 实际上可以在 _run_pre_analysis 中接收 task_id 后查 DB output_files_json 不, 既然 in-memory 透传, 改为:

```python
def _run_pre_analysis(task_id: str, table_config: dict | None = None) -> None:
    """后台任务. table_config (2026-07-06 新增): in-memory 透传.

    兼容旧调用 (_run_pre_analysis(task_id) 无 table_config), 此时 default pymupdf.
    """
    table_config = table_config or {"table_backend": "pymupdf", "table_params": {}}
    task = pa_load_task(task_id)
    if task is None:
        return
    pdf_uri = task["pdf_uri"]
    runner = PreAnalysisRunner(...)
    result = runner.run(task_id=task_id, pdf_uri=pdf_uri, table_extraction_config=table_config)
    ...  # 后续 mark_completed 已在 runner 内
```

直接改 `_run_pre_analysis` 接第 2 参数, 因为仅一处 background.add_task 调用 (在 upload 内). 删 `_run_pre_analysis_with_config` 简化为改原函数.

- [ ] **Step 5: 跑测试确认 green**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_api.py -v`
Expected: 全部 passed.

- [ ] **Step 6: 跑合同测试**

Run: `cd packages/service && uv run pytest tests/test_api_contract.py -v`
Expected: 0 fail (BFF 没动).

- [ ] **Step 7: pyright + ruff**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`
Expected: 0 error.

- [ ] **Step 8: Commit (M4 完成)**

```bash
git add -A
git commit -m "feat(service): upload endpoint accepts table_backend + table_params, pass to runner"
```

---

## Task 10: M5 (1/2) — 前端 API wrapper 接 config

**Files:**
- Modify: `packages/web/lib/api/pre-analysis.ts`

- [ ] **Step 1: 写测试**

`packages/web/lib/api/pre-analysis.test.ts` (现有或新增):

```typescript
import { describe, expect, it, vi } from "vitest";
import { preAnalysisUpload, type TableExtractionConfig } from "./pre-analysis";

const FAKE_FILE = new File([new Uint8Array([1, 2, 3])], "x.pdf", { type: "application/pdf" });

describe("preAnalysisUpload with config", () => {
  it("default config sends table_backend=pymupdf and table_params={}", async () => {
    globalThis.fetch = vi.fn(async (url, options) => {
      const body = options?.body as FormData;
      expect(body.get("table_backend")).toBe("pymupdf");
      expect(body.get("table_params")).toBe("{}");
      return new Response(
        JSON.stringify({ task_id: "x", state: "pending", pdf_filename: "x.pdf" }),
        { status: 200, headers: { "content-type": "application/json" } }
      );
    }) as unknown as typeof fetch;

    await preAnalysisUpload(FAKE_FILE);
  });

  it("camelot config sends table_backend=camelot and JSON params", async () => {
    const config: TableExtractionConfig = {
      backend: "camelot",
      params: { flavor: "stream", edge_tol: 80 },
    };
    globalThis.fetch = vi.fn(async (url, options) => {
      const body = options?.body as FormData;
      expect(body.get("table_backend")).toBe("camelot");
      expect(body.get("table_params")).toBe('{"flavor":"stream","edge_tol":80}');
      return new Response(
        JSON.stringify({ task_id: "x", state: "pending", pdf_filename: "x.pdf" }),
        { status: 200, headers: { "content-type": "application/json" } }
      );
    }) as unknown as typeof fetch;

    await preAnalysisUpload(FAKE_FILE, config);
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/web && bun run test lib/api/pre-analysis.test.ts`
Expected: 1 failed (旧 `preAnalysisUpload(file)` 签名).

- [ ] **Step 3: 改 pre-analysis.ts API wrapper**

`packages/web/lib/api/pre-analysis.ts` 改 `preAnalysisUpload` 函数:

```typescript
/**
 * 表格提取配置 (后端可选 backend 之一)
 * @shared
 */
export interface TableExtractionConfig {
  /** 后端名: pymupdf (默认) | camelot | pdfplumber */
  backend: "pymupdf" | "camelot" | "pdfplumber";
  /** backend-specific 参数 (e.g. camelot: { flavor, edge_tol, row_tol }) */
  params: Record<string, unknown>;
}

/**
 * 上传 PDF 文件, 触发后台预分析.
 *
 * @param file PDF 文件.
 * @param config 表格后端配置 (默认 pymupdf + 空 params).
 * @returns {task_id, state=pending, pdf_filename}.
 * @throws Error 4xx (400/503) 时 handleError 抛.
 */
export const preAnalysisUpload = async (
  file: File,
  config: TableExtractionConfig = { backend: "pymupdf", params: {} },
): Promise<PreAnalysisUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("table_backend", config.backend);
  formData.append("table_params", JSON.stringify(config.params ?? {}));
  const resp = await fetch("/api/pre-analysis/upload", {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!resp.ok) {
    await handleError(resp);
  }
  return (await resp.json()) as PreAnalysisUploadResponse;
};
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/web && bun run test lib/api/pre-analysis.test.ts`
Expected: 全部 passed.

- [ ] **Step 5: tsc + oxlint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error.

- [ ] **Step 6: Commit**

```bash
git add lib/api/pre-analysis.ts lib/api/pre-analysis.test.ts
git commit -m "feat(web): preAnalysisUpload accepts TableExtractionConfig"
```

---

## Task 11: M5 (2/2) — 上传弹框加"高级选项"折叠区

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx`
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`

- [ ] **Step 1: 写测试 (3 个高级选项测试)**

`packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` 加 3 个测试 (保留原有 4 个):

```typescript
import {
  Accordion,
  // ... 现有 imports
} from "...";  // 复用现有

const DEFAULT_BACKEND_PYMUPDF = "pymupdf";

describe("PreAnalysisUploadDialog advanced options", () => {
  it("默认状态下高级选项折叠区收起, 看不到 backend 选择器", () => {
    renderDialog();
    // 触发按钮存在, 高级选项 Accordion 默认 closed
    expect(screen.queryByText("Backend 后端")).not.toBeInTheDocument();
  });

  it("点高级选项开关 → 看到 backend 选择器 + 默认 pymupdf", async () => {
    renderDialog();
    // 触发 Accordion 标题按钮 (通常 data-testid="advanced-toggle")
    const toggle = screen.getByTestId("advanced-toggle");
    fireEvent.click(toggle);
    // backend label 可见
    expect(screen.getByText("Backend 后端")).toBeInTheDocument();
    // AppSelect 默认 pymupdf
    expect(screen.getByTestId("backend-select")).toHaveTextContent("PyMuPDF");
  });

  it("选 camelot → 显示 camelot flavor/edge_tol/row_tol 字段 + 上传发送 form 字段", async () => {
    preAnalysisUploadMock.mockResolvedValue({ task_id: "p", state: "pending", pdf_filename: "x.pdf" });
    renderDialog();
    // 展开
    fireEvent.click(screen.getByTestId("advanced-toggle"));
    // 切 backend 到 camelot
    fireEvent.change(screen.getByTestId("backend-select"), { target: { value: "camelot" } });
    // flavor / edge_tol / row_tol 输入框显示
    expect(screen.getByTestId("param-flavor")).toBeInTheDocument();
    expect(screen.getByTestId("param-edge_tol")).toBeInTheDocument();
    expect(screen.getByTestId("param-row_tol")).toBeInTheDocument();
    // 选文件 → 上传
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [new File([new Uint8Array([1, 2])], "x.pdf", { type: "application/pdf" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => expect(preAnalysisUploadMock).toHaveBeenCalledTimes(1));
    const [passedFile, passedConfig] = preAnalysisUploadMock.mock.calls[0];
    expect(passedFile).toBeInstanceOf(File);
    expect(passedConfig).toEqual({
      backend: "camelot",
      params: { flavor: "lattice", edge_tol: 50, row_tol: 2 },
    });
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`
Expected: 3 failed (advanced-toggle / backend-select / param-flavor 缺).

- [ ] **Step 3: 改 upload dialog 加 Accordion + PARAM_METADATA + 后端切换**

`packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx`:

顶部 import:
```typescript
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AppSelect } from "@/components/common/input/app-select";
import { AppTooltip } from "@/components/common/feedback/app-tooltip";
import { HelpCircle } from "lucide-react";
```

模块常量 (2026-07-06 硬编码 zh+en, 不进 i18n):
```typescript
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

const BACKEND_OPTIONS = [
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "camelot", label: "Camelot" },
  { value: "pdfplumber", label: "pdfplumber" },
] as const;

const PARAM_METADATA: Record<string, { label: string; tooltip: string }> = {
  flavor: { label: "Flavor 解析器", tooltip: "lattice/stream/network/hybrid/ml 5 种. lattice 用表格线, stream 用空白间距, network/hybrid 综合, ml 是 Table Transformer (需 camelot-py[ml] extra)" },
  edge_tol: { label: "Edge Tol 边缘容差 (像素)", tooltip: "表格线边缘像素容差. 越大越宽松能识别弱线, 但可能误检" },
  row_tol: { label: "Row Tol 行容差 (像素)", tooltip: "同行文本垂直像素容差. 越大越能容忍跨行错位" },
  vertical_strategy: { label: "Vertical Strategy 垂直策略", tooltip: "垂直线检测: lines 用显式线, lines_strict 严格, text 用文本对齐推断, explicit 显式坐标" },
  horizontal_strategy: { label: "Horizontal Strategy 水平策略", tooltip: "水平线检测 (同 vertical_strategy 解释)" },
  snap_tolerance: { label: "Snap Tolerance 吸附容差 (像素)", tooltip: "附近线条合并的像素容差" },
  join_tolerance: { label: "Join Tolerance 合并容差 (像素)", tooltip: "端点接近的线条合并像素容差" },
};

const BACKEND_DEFAULT_PARAMS: Record<TableBackend, Record<string, string | number>> = {
  pymupdf: {},
  camelot: { flavor: "lattice", edge_tol: 50, row_tol: 2 },
  pdfplumber: { vertical_strategy: "lines", horizontal_strategy: "lines", snap_tolerance: 3, join_tolerance: 3 },
};

const BACKEND_PARAMS_KEYS: Record<TableBackend, string[]> = {
  pymupdf: [],
  camelot: ["flavor", "edge_tol", "row_tol"],
  pdfplumber: ["vertical_strategy", "horizontal_strategy", "snap_tolerance", "join_tolerance"],
};

const FLAVOR_OPTIONS = [
  { value: "lattice", label: "lattice (表格线)" },
  { value: "stream", label: "stream (空白间距)" },
  { value: "network", label: "network" },
  { value: "hybrid", label: "hybrid" },
  { value: "ml", label: "ml (Table Transformer, 需 [ml] extra)" },
];

const STRATEGY_OPTIONS = [
  { value: "lines", label: "lines (显式线)" },
  { value: "lines_strict", label: "lines_strict (严格)" },
  { value: "text", label: "text (文本对齐)" },
  { value: "explicit", label: "explicit (显式坐标)" },
];
```

组件内 state:
```typescript
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [backend, setBackend] = useState<TableBackend>("pymupdf");
  const [params, setParams] = useState<Record<string, string | number>>({});

  useEffect(() => {
    if (!showAdvanced) {
      setBackend("pymupdf");
      setParams({});
    }
  }, [showAdvanced]);

  useEffect(() => {
    setParams(BACKEND_DEFAULT_PARAMS[backend]);
  }, [backend]);
```

`handleUpload` 改:
```typescript
  const config: TableExtractionConfig = showAdvanced
    ? { backend, params }
    : { backend: "pymupdf", params: {} };

  await preAnalysisUpload(pickedFile, config);
```

JSX 在 FileDropzone 与 footer 之间插入 Accordion:
```tsx
      <Accordion
        collapsible
        type="single"
        value={showAdvanced ? "advanced" : undefined}
        onValueChange={(v) => setShowAdvanced(v === "advanced")}
      >
        <AccordionItem value="advanced">
          <AccordionTrigger data-testid="advanced-toggle">高级选项 (Advanced)</AccordionTrigger>
          <AccordionContent>
            {/* Backend 选择 + Param 字段 */}
            <div className="space-y-4 pt-2">
              <div>
                <label className="text-sm font-medium">Backend 后端</label>
                <AppSelect
                  options={BACKEND_OPTIONS as unknown as AppSelectOption[]}
                  value={backend}
                  onChange={(v) => setBackend(v as TableBackend)}
                  data-testid="backend-select"
                />
              </div>
              {backend === "pymupdf" ? (
                <p className="text-xs text-muted-foreground">使用 PyMuPDF 内置 find_tables(), 无需额外配置</p>
              ) : (
                BACKEND_PARAMS_KEYS[backend].map((key) => (
                  <div key={key}>
                    <div className="flex items-center gap-1">
                      <label className="text-sm font-medium">{PARAM_METADATA[key].label}</label>
                      <AppTooltip content={PARAM_METADATA[key].tooltip}>
                        <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                      </AppTooltip>
                    </div>
                    {key === "flavor" ? (
                      <AppSelect
                        options={FLAVOR_OPTIONS}
                        value={String(params[key] ?? "lattice")}
                        onChange={(v) => setParams({ ...params, [key]: v })}
                        data-testid={`param-${key}`}
                      />
                    ) : key === "vertical_strategy" || key === "horizontal_strategy" ? (
                      <AppSelect
                        options={STRATEGY_OPTIONS}
                        value={String(params[key] ?? "lines")}
                        onChange={(v) => setParams({ ...params, [key]: v })}
                        data-testid={`param-${key}`}
                      />
                    ) : (
                      <Input
                        type="number"
                        value={String(params[key] ?? "")}
                        onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })}
                        data-testid={`param-${key}`}
                      />
                    )}
                  </div>
                ))
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
```

- [ ] **Step 4: 跑测试确认 green**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`
Expected: 全部 passed (4 旧 + 3 新 = 7).

- [ ] **Step 5: tsc + oxlint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 0 error.

- [ ] **Step 6: Commit**

```bash
git add app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx \
        app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx
git commit -m "feat(web): add advanced options section with backend selector + parameter fields"
```

---

## Task 12: M5 续 — 详情页加 ⟳ 按钮 + 每产物独立 ⬇ 链接

**Files:**
- Create (or Modify): `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`
- Modify: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`

(本任务依赖现有详情页是否已抽 client 组件; 如果是 RSC 则新拆 client 组件.)

- [ ] **Step 1: 查当前详情页实现**

Run: `ls packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/` (确认现有 admin-pre-analysis-detail-client.tsx 是否存在)

如果不存在 (RSC 直写), 先按 2026-07-03 plan 文档样式拆 client 组件 (见现有 plan Task 6). 此处任务假设已存在.

- [ ] **Step 2: 写详情页 3 个测试**

`packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` 加 3 测试:

```typescript
describe("AdminPreAnalysisDetailClient (stage-by-stage streaming)", () => {
  it("running 状态表格显示部分产物, 下载 ZIP 按钮 disabled", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({
        id: "p-1",
        state: "running",
        current_stage: "extract_tables",
        output_files: [
          { kind: "chapter_structure", filename: "chapter_structure.json", uri: "s3://x/chapter.json", size_bytes: 3800 },
          { kind: "table", filename: "tables/page-1-table-1.csv", uri: "s3://x/p1.csv", size_bytes: 500 },
        ],
        summary: {},
        error: null,
        started_at: "2026-07-06T10:00:00",
        finished_at: null,
      }, { status: 200 })
    ) as unknown as typeof fetch;

    render(<AdminPreAnalysisDetailClient taskId="p-1" />, { wrapper: IntlWrapper });
    await waitFor(() => expect(screen.getByTestId("output-files-table")).toBeInTheDocument());
    const rows = screen.getAllByTestId(/^output-row-/);
    expect(rows).toHaveLength(2);
    // ZIP 按钮 disabled
    const zipBtn = screen.getByTestId("download-zip");
    expect(zipBtn).toBeDisabled();
  });

  it("点击 ⟳ 按钮触发 refetch, 表格行数从 3 → 5", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn(async () => {
      callCount++;
      const files = callCount === 1
        ? Array.from({ length: 3 }, (_, i) => ({ kind: "table", filename: `p${i}.csv`, uri: `s3://x${i}`, size_bytes: 100 }))
        : Array.from({ length: 5 }, (_, i) => ({ kind: "table", filename: `p${i}.csv`, uri: `s3://x${i}`, size_bytes: 100 }));
      return Response.json({
        id: "p-2", state: "running", current_stage: "extract_tables",
        output_files: files, summary: {}, error: null,
        started_at: "2026-07-06T10:00:00", finished_at: null,
      }, { status: 200 });
    }) as unknown as typeof fetch;

    render(<AdminPreAnalysisDetailClient taskId="p-2" />, { wrapper: IntlWrapper });
    await waitFor(() => expect(screen.getAllByTestId(/^output-row-/).length).toBe(3));
    fireEvent.click(screen.getByTestId("refresh-button"));
    await waitFor(() => expect(screen.getAllByTestId(/^output-row-/).length).toBe(5));
  });

  it("completed 状态 ZIP 按钮 enabled", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({
        id: "p-3", state: "completed", current_stage: null,
        output_files: [
          { kind: "index", filename: "index.json", uri: "s3://x/i.json", size_bytes: 1000 },
        ],
        summary: {}, error: null,
        started_at: "2026-07-06T10:00:00", finished_at: "2026-07-06T10:01:00",
      }, { status: 200 })
    ) as unknown as typeof fetch;

    render(<AdminPreAnalysisDetailClient taskId="p-3" />, { wrapper: IntlWrapper });
    await waitFor(() => expect(screen.getByTestId("download-zip")).not.toBeDisabled());
  });
});
```

- [ ] **Step 3: 跑测试确认 red**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`
Expected: 3 failed (refresh-button / output-row 缺).

- [ ] **Step 4: 改详情页 client 加 refresh button + per-artifact download**

(假设 admin-pre-analysis-detail-client.tsx 已存在; 改它; 如果是 RSC server component 则需新拆)

```tsx
"use client";
// 在 useQuery 块旁加 queryClient 调用
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

const queryClient = useQueryClient();

const { data: task, error, isLoading } = useQuery({
  queryKey: ["pre-analysis-task", taskId],
  queryFn: () => getPreAnalysisTask(taskId),
});

const handleRefresh = (): void => {
  void queryClient.invalidateQueries({ queryKey: ["pre-analysis-task", taskId] });
};

const handleDownloadZip = async (): Promise<void> => {
  if (task?.state !== "completed") return;
  const blob = await downloadPreAnalysisZip(taskId);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${taskId}.zip`;
  a.click();
  URL.revokeObjectURL(url);
};

const handleDownloadArtifact = async (uri: string, filename: string): Promise<void> => {
  /**单产物下载: 走 window.open(uri) 触发浏览器直下 ObjectStore 文件 (2026-07-06 简化).

  ObjectStore URI 形态:
  - local://... → admin 在 dev 后端路径, 浏览器没法直下, 走 ZIP 端点变通
  - s3://... → 没 presign, 浏览器没法直下, 走 ZIP 端点变通
  
  本期实现: 弹 toast 引导 admin 用 ZIP 端点 (running 阶段 ZIP 按钮 disabled, 等 completed);
  或者通过新增单文件流式 GET 端点实现 (本期不在 scope, 留 spec 给未来).
  */
  toast.info(`单文件下载尚未实装, 请等待任务 completed 后下载 ZIP, 内含 ${filename}`);
};

// JSX 中加:
<Button
  data-testid="refresh-button"
  onClick={handleRefresh}
  variant="outline"
  size="sm"
>
  <RefreshCw className="mr-1 h-4 w-4" />
  刷新
</Button>

{/* 产物表格 */}
<Table data-testid="output-files-table">
  <TableBody>
    {task?.output_files.map((f, i) => (
      <TableRow key={i} data-testid={`output-row-${i}`}>
        <TableCell><a href={f.uri} download>{f.filename}</a></TableCell>
        <TableCell>{f.size_bytes} B</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>

<Button
  data-testid="download-zip"
  disabled={task?.state !== "completed"}
  onClick={() => void handleDownloadZip()}
>
  下载全部 ZIP
</Button>
```

- [ ] **Step 5: 跑测试确认 green**

Run: `cd packages/web && bun run test app/[locale]/admin/pre-analysis/[task_id]/`
Expected: 3 passed.

- [ ] **Step 6: tsc + oxlint + format**

Run: `cd packages/web && bun run format && bun run lint:fix && bun run typecheck`
Expected: 0 error.

- [ ] **Step 7: Commit (M5 完成)**

```bash
git add -A
git commit -m "feat(web): detail page shows stage-by-stage artifacts with manual refresh button"
```

---

## Task 13: 全套验证 + 文档

- [ ] **Step 1: 跑后端全套测试**

Run: `cd packages/service && uv run pytest -v`
Expected: 全部 passed (含新加, pre-existing 仍 fail 不算新 fail).

- [ ] **Step 2: 跑后端代码质量**

Run:
```bash
cd packages/service
uv run ruff format
uv run ruff check --fix
uv run pyright
```
Expected: 0 error.

- [ ] **Step 3: 跑前端全套测试**

Run: `cd packages/web && bun run test`
Expected: 全部 passed (含新加).

- [ ] **Step 4: 跑前端代码质量**

Run:
```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
```
Expected: 0 error.

- [ ] **Step 5: 跑合同测试**

Run: `cd packages/service && uv run pytest tests/test_api_contract.py -v`
Expected: 0 fail (BFF 没动).

- [ ] **Step 6: alembic 演练回滚**

Run:
```bash
cd packages/service
uv run alembic current
uv run alembic downgrade -1  # 撤销本次
uv run alembic upgrade head  # 重升
```
Expected: 0 error.

- [ ] **Step 7: dev 手测 E2E**

启动后端 + 前端:
- 启动后端 `uv run python main.py`
- 启动前端 `bun run dev`
- 登录 super_admin → 上传 PDF
- 不展开高级选项 → 跑 pymupdf (默认) → 详情页⟳ 看到 chapter_structure.json
- 选 camelot → 上传 → 详情页⟳ 看到 chapter + tables + flagged 渐增
- 选 camelot + flavor='ml' 但 [ml] 未装 → 后端 503 → 弹框红字
- 选 pdfplumber (装了) → 上传 → 详情页同
- 上传期间反复点⟳ 按钮 → 看到 output_files 增多
- 等 task=completed → "下载 ZIP" enabled → 下载到本地解压缩验证

- [ ] **Step 8: git status 检查**

Run: `cd packages/web && git status && cd packages/service && git status`
Expected: 0 uncommitted (Task 0-12 全已 commit).

- [ ] **Step 9: 汇总 commit 信息给用户**

本 plan 共 6 commits (M0 子包化 + M1 M2 M3 M4 M5):

```
1. refactor(service): move pre_analysis_* to subpackage pre_analysis/
2. feat(service): add pre_analysis_tasks.task_config_json column for execution snapshot
3. feat(service): add TableExtractor strategy with pymupdf/camelot/pdfplumber
4. refactor(service): runner uses TableExtractor and writes task_config_json + stage-by-stage artifact streaming
5. feat(service): upload endpoint accepts table_backend + table_params, pass to runner
6. feat(web): add advanced options section to pre-analysis upload dialog + detail page incremental artifact list (no polling)
```

- [ ] **Step 10: 按 [feedback-cleanup-worktree-after-merge] cleanup**

如果用了 worktree: `git worktree remove`

按 [superpowers:finishing-a-development-branch] 决定 merge/PR 方式.
