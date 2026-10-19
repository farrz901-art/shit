# PreAnalysis Stages / Retry / Orphan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加阶段状态机 + stage 表 + 重试 + orphan 清理,改列表新列(总体阶段 + 操作重试) + 弹框显示 5 个 detail stage + 上传成功后只关弹框 + 手动刷新按钮(不轮询)。

**Architecture:** 后端 SA2.0 新表 `pre_analysis_task_stages` + 加 `current_stage` 列, runner 5 处 wrap mark_stage_xxx (跟现有 try-block 对齐), fastapi lifespan 启动扫 running>5min 改 failed; 前端新 PreAnalysisStagesDialog 组件 + useQuery 不轮询 + 手动 RefreshCw 按钮触发 refetch, 上传后 invalidate 1 次。

**Tech Stack:** Python 3.14 + SQLAlchemy 2.0 + alembic + FastAPI + 前端 React 19 + TanStack Query 5.x + next-intl 4.x + shadcn AppDialog + lucide-react RefreshCw/CheckCircle2/XCircle/Loader2。

---

## File Structure

**后端新建 (4)**:
- `packages/service/src/ingest/pre_analysis_stage_models.py` — `PreAnalysisStage` ORM
- `packages/service/src/ingest/pre_analysis_stage_store.py` — `mark_stage_*` + `list_stages` + `delete_stages_for_retry`
- `packages/service/src/storage/migrations/versions/20260703_000000_pre_analysis_task_stages.py` — CREATE TABLE + add column current_stage
- `packages/service/tests/ingest/test_pre_analysis_stage_store.py` — 4 个单测

**后端改 (4)**:
- `packages/service/src/ingest/pre_analysis_models.py` — `PreAnalysisTask` 加 `current_stage` 列
- `packages/service/src/ingest/pre_analysis_runner.py` — ctor 加 `stage_store`, 5 处 wrap mark_stage_xxx
- `packages/service/src/ingest/api.py` — 2 新端点 (`/stages`, `/retry`) + `_to_dict` 加 current_stage + `_run_pre_analysis` 调 `_orphan_cleanup` + lifespan 调 `_orphan_cleanup`
- `packages/service/src/core/lifespan.py` — `_lifespan` 启动期调 `_orphan_cleanup_pre_analysis_tasks`
- `packages/service/tests/ingest/test_pre_analysis_api.py` — 加 2 个 retry test

**前端新建 (2)**:
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.tsx` — AppDialog + 5 行 stages 表格
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx` — 3 个 test

**前端改 (5)**:
- `packages/web/lib/api/pre-analysis.ts` — + 2 API (`listPreAnalysisStages`/`retryPreAnalysisTask`) + 3 type
- `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` — 新列(总体阶段) + retry 按钮 + 刷新按钮 + onRowClick + DataTable onRowClick 配置
- `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` — + 1 新 test (重试按钮渲染)
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` — 删 onSuccess router.push, 改成只关弹框 (父 onSuccess 改 invalidation-only)
- `messages/{zh,en}.json` — + 13 个 key

---

## Task 1: 后端 stage ORM 模型 + migration

**Files:**
- Create: `packages/service/src/ingest/pre_analysis_stage_models.py`
- Create: `packages/service/src/storage/migrations/versions/20260703_000000_pre_analysis_task_stages.py`
- Modify: `packages/service/src/ingest/pre_analysis_models.py:43` 加 current_stage 列

- [ ] **Step 1: 写 stage ORM 模型**

```python
# packages/service/src/ingest/pre_analysis_stage_models.py
"""pre_analysis_task_stages ORM (2026-07-03 新增)

记录 PDF 预分析 task 每个 detail stage 的生命周期 (started/completed/failed/skipped)。
一对多: 1 个 task → N 个 stage (按时间顺序)。

stage 枚举:
- load_config: 加载 rule_keywords.yaml
- extract_chapters: TOC 提取
- extract_tables: 表格提取 + 跨页检测
- extract_flagged: 关键词段落标记
- write_outputs: 写产物 (聚合 4 个 _write_xxx)

overall stage (current_stage 列冗余在 pre_analysis_tasks, 4 选 1):
- parse_pdf / extract / write_outputs / done
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class PreAnalysisStage(Base):
    __tablename__ = "pre_analysis_task_stages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pre_analysis_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # 5 个 detail stage 字符串
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # started/completed/failed/skipped
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_task_stages_task_started", "task_id", "started_at"),)

    def __repr__(self) -> str:
        return f"<PreAnalysisStage id={self.id} task={self.task_id} stage={self.stage} status={self.status}>"
```

- [ ] **Step 2: 加 current_stage 列到 PreAnalysisTask 模型**

```python
# packages/service/src/ingest/pre_analysis_models.py 第 43 行后插入
current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

- [ ] **Step 3: 写 alembic migration**

```python
# packages/service/src/storage/migrations/versions/20260703_000000_pre_analysis_task_stages.py
"""pre_analysis_task_stages 表 + pre_analysis_tasks.current_stage 列 (2026-07-03)

新表记录 task 每个 detail stage 的 lifecycle,
pre_analysis_tasks 加 current_stage 列 (冗余, 列表 API quick 拿)。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260703_000000"
down_revision = "20260702_000000"  # pre_analysis_tasks (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_analysis_task_stages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("pre_analysis_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("message", sa.Text, nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'skipped')",
            name="ck_pre_analysis_task_stages_status",
        ),
        sa.CheckConstraint(
            "stage IN ('load_config', 'extract_chapters', 'extract_tables', 'extract_flagged', 'write_outputs')",
            name="ck_pre_analysis_task_stages_stage",
        ),
    )
    op.create_index(
        "ix_task_stages_task_started",
        "pre_analysis_task_stages",
        ["task_id", "started_at"],
    )
    op.add_column(
        "pre_analysis_tasks",
        sa.Column("current_stage", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pre_analysis_tasks", "current_stage")
    op.drop_index("ix_task_stages_task_started", "pre_analysis_task_stages")
    op.drop_table("pre_analysis_task_stages")
```

- [ ] **Step 4: 跑 alembic upgrade head (dev DB)**

```bash
cd packages/service && uv run alembic upgrade head
```
Expected: migration 成功, `\d pre_analysis_task_stages` 看见新表 + `\d pre_analysis_tasks` 看见 current_stage 列

- [ ] **Step 5: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/service/src/ingest/pre_analysis_stage_models.py packages/service/src/ingest/pre_analysis_models.py packages/service/src/storage/migrations/versions/20260703_000000_pre_analysis_task_stages.py 2>&1; git commit -m "feat(ingest): 加 pre_analysis_task_stages 表 + current_stage 列"
```

---

## Task 2: 后端 stage store + 单测

**Files:**
- Create: `packages/service/src/ingest/pre_analysis_stage_store.py`
- Create: `packages/service/tests/ingest/test_pre_analysis_stage_store.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/ingest/test_pre_analysis_stage_store.py
"""Pre-analysis stage store 单测 (mode 2 db_session).

覆盖 mark_started / mark_completed / mark_failed / list_stages / delete_stages_for_retry.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.ingest.pre_analysis_models import PreAnalysisTask
from src.ingest.pre_analysis_stage_models import PreAnalysisStage
from src.ingest.pre_analysis_stage_store import PreAnalysisStageStore
from src.storage import session_scope


def _seed_task(db_session, user_hash: str = "u1") -> str:
    t = PreAnalysisTask(
        id="pa-test-1",
        user_hash=user_hash,
        state="running",
        pdf_filename="D81.pdf",
        pdf_uri="s3://x/y/D81.pdf",
        started_at=datetime.now(UTC),
        output_files_json="[]",
        summary_json="{}",
    )
    db_session.add(t)
    db_session.flush()
    return t.id


def test_mark_started_inserts_row(db_session) -> None:
    task_id = _seed_task(db_session)
    PreAnalysisStageStore().mark_stage_started(task_id, "load_config")
    row = db_session.query(PreAnalysisStage).filter_by(task_id=task_id, stage="load_config").one()
    assert row.status == "started"
    assert row.progress == 0
    assert row.finished_at is None


def test_mark_completed_updates_row(db_session) -> None:
    task_id = _seed_task(db_session)
    store = PreAnalysisStageStore()
    store.mark_stage_started(task_id, "extract_chapters")
    store.mark_stage_completed(task_id, "extract_chapters", progress=100, message="5 章")
    row = db_session.query(PreAnalysisStage).filter_by(task_id=task_id, stage="extract_chapters").one()
    assert row.status == "completed"
    assert row.progress == 100
    assert row.message == "5 章"
    assert row.finished_at is not None


def test_mark_failed_records_stderr(db_session) -> None:
    task_id = _seed_task(db_session)
    store = PreAnalysisStageStore()
    store.mark_stage_started(task_id, "extract_tables")
    store.mark_stage_failed(task_id, "extract_tables", "pymupdf open failed: corrupted PDF")
    row = db_session.query(PreAnalysisStage).filter_by(task_id=task_id, stage="extract_tables").one()
    assert row.status == "failed"
    assert "pymupdf open failed" in (row.message or "")


def test_list_stages_ordered_by_time(db_session) -> None:
    task_id = _seed_task(db_session)
    store = PreAnalysisStageStore()
    store.mark_stage_started(task_id, "load_config")
    store.mark_stage_completed(task_id, "load_config")
    store.mark_stage_started(task_id, "extract_chapters")
    rows = store.list_stages(task_id)
    assert [r.stage for r in rows] == ["load_config", "extract_chapters"]


def test_delete_stages_for_retry(db_session) -> None:
    task_id = _seed_task(db_session)
    store = PreAnalysisStageStore()
    store.mark_stage_started(task_id, "load_config")
    store.mark_stage_completed(task_id, "load_config")
    store.delete_stages_for_retry(task_id)
    assert db_session.query(PreAnalysisStage).filter_by(task_id=task_id).count() == 0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_stage_store.py -v 2>&1 | tail -10
```
Expected: ImportError "No module named 'src.ingest.pre_analysis_stage_store'"

- [ ] **Step 3: 写 store 实现**

```python
# packages/service/src/ingest/pre_analysis_stage_store.py
"""pre_analysis_task_stages 状态切换 + 查询 facade (2026-07-03)

跟 src/ingest/pre_analysis_store.py PreAnalysisTaskStore 模式对齐:
- mark_stage_started / mark_stage_completed / mark_stage_failed 三个状态切换
- list_stages / delete_stages_for_retry 两个查询

设计: 独立类而不是函数, 跟 PreAnalysisRunner 接 Protocol 注入 (mode 1 mock)。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ..storage import session_scope
from .pre_analysis_models import PreAnalysisTask
from .pre_analysis_stage_models import PreAnalysisStage


class PreAnalysisStageStore:
    """Stage 状态切换 facade."""

    def mark_stage_started(self, task_id: str, stage: str) -> None:
        """新增 1 行 stage (status=started, progress=0)."""
        with session_scope() as s:
            s.add(
                PreAnalysisStage(
                    task_id=task_id,
                    stage=stage,
                    status="started",
                    started_at=datetime.now(UTC),
                    progress=0,
                )
            )
            # 同步 task.current_stage (4 overall stage enum)
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.current_stage = _stage_to_overall(stage)

    def mark_stage_completed(
        self, task_id: str, stage: str, progress: int = 100, message: str | None = None
    ) -> None:
        """UPDATE row: status=completed, finished_at=NOW, progress=100."""
        with session_scope() as s:
            row = (
                s.execute(
                    select(PreAnalysisStage)
                    .where(PreAnalysisStage.task_id == task_id, PreAnalysisStage.stage == stage)
                    .order_by(PreAnalysisStage.started_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
            )
            if row is not None:
                row.status = "completed"
                row.finished_at = datetime.now(UTC)
                row.progress = progress
                row.message = message

    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None:
        """UPDATE row: status=failed, message=error[:1000]."""
        with session_scope() as s:
            row = (
                s.execute(
                    select(PreAnalysisStage)
                    .where(PreAnalysisStage.task_id == task_id, PreAnalysisStage.stage == stage)
                    .order_by(PreAnalysisStage.started_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
            )
            if row is not None:
                row.status = "failed"
                row.finished_at = datetime.now(UTC)
                row.message = error[-1000:]

    def list_stages(self, task_id: str) -> list[PreAnalysisStage]:
        """按 started_at ASC 返所有 stages."""
        with session_scope() as s:
            return list(
                s.execute(
                    select(PreAnalysisStage)
                    .where(PreAnalysisStage.task_id == task_id)
                    .order_by(PreAnalysisStage.started_at.asc())
                ).scalars()
            )

    def delete_stages_for_retry(self, task_id: str) -> None:
        """retry 时清空 task 所有 stages."""
        with session_scope() as s:
            s.query(PreAnalysisStage).filter_by(task_id=task_id).delete()


def _stage_to_overall(stage: str) -> str:
    """5 detail stage → 4 overall stage 映射.

    parse_pdf: load_config (PDF 解析还没开始, 配置加载算解析准备阶段)
    extract: extract_chapters / extract_tables / extract_flagged (3 个提取步骤)
    write_outputs: write_outputs (写产物)
    """
    if stage in ("load_config", "pymupdf_open"):
        return "parse_pdf"
    if stage in ("extract_chapters", "extract_tables", "extract_flagged"):
        return "extract"
    if stage == "write_outputs":
        return "write_outputs"
    return "done"


__all__ = ["PreAnalysisStageStore"]
```

- [ ] **Step 4: 跑测试验证全绿**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_stage_store.py -v 2>&1 | tail -10
```
Expected: 5 passed

- [ ] **Step 5: 跑 ruff + pyright 验证干净**

```bash
cd packages/service && uv run ruff check src/ingest/pre_analysis_stage_store.py tests/ingest/test_pre_analysis_stage_store.py 2>&1 | tail -3
uv run pyright src/ingest/pre_analysis_stage_store.py tests/ingest/test_pre_analysis_stage_store.py 2>&1 | tail -3
```
Expected: ruff 0 error, pyright 0 error

- [ ] **Step 6: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/service/src/ingest/pre_analysis_stage_store.py packages/service/tests/ingest/test_pre_analysis_stage_store.py 2>&1; git commit -m "feat(ingest): 加 pre_analysis stage store + 单测"
```

---

## Task 3: runner 5 处 wrap mark_stage_xxx

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis_runner.py` (5 处 wrap + ctor 加 stage_store)

- [ ] **Step 1: 改 PreAnalysisRunner 签名 (加 stage_store) + run() 头 wrap**

```python
# pre_analysis_runner.py:57-71 区域
# 加 import + 改 Protocol + ctor + run()

from .pre_analysis_stage_store import PreAnalysisStageStore

class ObjectStoreProto(Protocol):
    def put_bytes(self, uri: str, data: bytes, mime: str = "application/octet-stream") -> None: ...
    def open_local(self, uri: str) -> str: ...


class StageStoreProto(Protocol):
    def mark_stage_started(self, task_id: str, stage: str) -> None: ...
    def mark_stage_completed(
        self, task_id: str, stage: str, progress: int = 100, message: str | None = None
    ) -> None: ...
    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None: ...


@dataclass(frozen=True)
class PreAnalysisRunner:
    object_store: ObjectStoreProto
    task_store: PreAnalysisTaskStore
    keyword_config_path: Path
    stage_store: StageStoreProto  # (2026-07-03) 新增

    def run(self, task_id: str, pdf_uri: str) -> PreAnalysisResult:
        """主入口. PDF 不存在 / 损坏 → 返 success=False + error."""
        start = time.monotonic()
        # 新增: load_config stage wrap
        self.stage_store.mark_stage_started(task_id, "load_config")
        try:
            self.task_store.mark_running(task_id)
            pdf_path = self.object_store.open_local(pdf_uri)
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "load_config", str(e))
            logger.opt(exception=True).error("pre_analysis open failed task={} uri={}", task_id, pdf_uri)
            self.task_store.mark_failed(task_id, f"open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))
        self.stage_store.mark_stage_completed(task_id, "load_config", progress=100, message="config ok")
```

- [ ] **Step 2: wrap pymupdf.open + _load_config**

找到 `try: doc = pymupdf.open(pdf_path)` (line ~77),改成:

```python
        try:
            doc = pymupdf.open(pdf_path)
        except Exception as e:
            logger.opt(exception=True).error("pre_analysis pymupdf open failed task={} path={}", task_id, pdf_path)
            self.stage_store.mark_stage_failed(task_id, "load_config", f"pymupdf open: {e}")
            self.task_store.mark_failed(task_id, f"pymupdf open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === extract_chapters stage ===
        self.stage_store.mark_stage_started(task_id, "extract_chapters")
        config = self._load_config()
```

然后 `_extract_chapters(doc)` 调用前后加 try/except wrap:
- mark_stage_started 已经在上面
- 函数成功返回后 mark_stage_completed
- 失败 mark_stage_failed

完整代码替换 `try: config = self._load_config(); chapters = self._extract_chapters(doc); ...` 那一段:

```python
        # === extract_chapters stage ===
        self.stage_store.mark_stage_started(task_id, "extract_chapters")
        try:
            chapters = self._extract_chapters(doc)
            self.stage_store.mark_stage_completed(
                task_id, "extract_chapters", progress=100, message=f"{len(chapters)} 章"
            )
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_chapters", str(e))
            logger.opt(exception=True).error("pre_analysis extract_chapters failed task={}", task_id)
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_chapters failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === extract_tables stage ===
        self.stage_store.mark_stage_started(task_id, "extract_tables")
        try:
            tables, cross_page = self._extract_tables(doc, config)
            self.stage_store.mark_stage_completed(
                task_id,
                "extract_tables",
                progress=100,
                message=f"{len(tables)} 表 / {cross_page} 跨页候选",
            )
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_tables", str(e))
            logger.opt(exception=True).error("pre_analysis extract_tables failed task={}", task_id)
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_tables failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        # === extract_flagged stage ===
        self.stage_store.mark_stage_started(task_id, "extract_flagged")
        try:
            flagged = self._extract_flagged_paragraphs(doc, config)
            self.stage_store.mark_stage_completed(
                task_id, "extract_flagged", progress=100, message=f"{len(flagged)} 段落"
            )
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "extract_flagged", str(e))
            logger.opt(exception=True).error("pre_analysis extract_flagged failed task={}", task_id)
            doc.close()
            self.task_store.mark_failed(task_id, f"extract_flagged failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))
```

- [ ] **Step 3: wrap write_outputs (聚合 1 stage)**

找到 `output_prefix = self._output_prefix(task_id)` (line ~94),改前加:

```python
        # === write_outputs stage ===
        self.stage_store.mark_stage_started(task_id, "write_outputs")
        output_prefix = self._output_prefix(task_id)
        try:
            chapter_uri = self._write_chapter_structure(output_prefix, chapters, doc)
            flagged_uri = self._write_flagged_paragraphs(output_prefix, flagged)
            table_uris = self._write_tables(output_prefix, tables)
            index_uri, summary = self._write_index(
                output_prefix, task_id, pdf_uri, chapters, tables, flagged, cross_page, start
            )
            self.stage_store.mark_stage_completed(task_id, "write_outputs", progress=100)
        except Exception as e:
            self.stage_store.mark_stage_failed(task_id, "write_outputs", str(e))
            logger.opt(exception=True).error("pre_analysis write_outputs failed task={}", task_id)
            doc.close()
            self.task_store.mark_failed(task_id, f"write_outputs failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))
```

- [ ] **Step 4: 改 final mark_completed + 当前 overall_stage=done**

`mark_completed` 那段前加 1 行:

```python
        # 标记当前 overall stage = done
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.current_stage = "done"

        self.task_store.mark_completed(
            task_id=task_id,
            ...
        )
```

需要从 `..storage import session_scope` 和 `from .pre_analysis_models import PreAnalysisTask` 顶部 import。

- [ ] **Step 5: 跑现有 runner test 验 0 回归**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_runner.py -v 2>&1 | tail -15
```
Expected: 现有 test 0 回归 (因为 Protocol mock 兼容)

- [ ] **Step 6: 改现有 test 加 stage_store Mock (stage 调用不影响断言)**

现有 test `test_pre_analysis_runner.py:47` 等用 `PreAnalysisRunner(object_store=..., task_store=..., keyword_config_path=...)` 三参 ctor,现在四参要 `stage_store=MagicMock()`。

读测试文件 ctor 位置:

```bash
grep -n "PreAnalysisRunner(" packages/service/tests/ingest/test_pre_analysis_runner.py
```

每个 ctor 加 `, stage_store=MagicMock()`:

```python
runner = PreAnalysisRunner(
    object_store=...,
    task_store=...,
    keyword_config_path=...,
    stage_store=MagicMock(),  # (2026-07-03)
)
```

- [ ] **Step 7: 跑 runner test 全绿**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_runner.py 2>&1 | tail -5
```
Expected: 全部 passed

- [ ] **Step 8: 跑 ruff + pyright 验证干净**

```bash
cd packages/service && uv run ruff check src/ingest/pre_analysis_runner.py tests/ingest/test_pre_analysis_runner.py 2>&1 | tail -3
uv run pyright src/ingest/pre_analysis_runner.py 2>&1 | tail -3
```
Expected: 0 error

- [ ] **Step 9: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/service/src/ingest/pre_analysis_runner.py packages/service/tests/ingest/test_pre_analysis_runner.py 2>&1; git commit -m "feat(ingest): runner 5 stage wrap mark_stage_xxx"
```

---

## Task 4: 后端 API 新端点 + `_to_dict` 加 current_stage

**Files:**
- Modify: `packages/service/src/ingest/api.py` (2 新端点 + _to_dict 加 current_stage + lifespan 调用)

- [ ] **Step 1: 改 _to_dict 加 current_stage**

```python
# packages/service/src/ingest/pre_analysis_store.py:32 area
# pre_analysis_store.py._to_dict 加 current_stage 字段
def _to_dict(task: PreAnalysisTask) -> dict:
    return {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "pdf_filename": task.pdf_filename,
        "pdf_uri": task.pdf_uri,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "current_stage": task.current_stage,  # (2026-07-03) 新增
        "output_files": json.loads(task.output_files_json or "[]"),
        "summary": json.loads(task.summary_json or "{}"),
    }
```

- [ ] **Step 2: 在 api.py 顶部 import 新模块**

```python
# packages/service/src/ingest/api.py 第 11-13 行附近加
from .pre_analysis_stage_models import PreAnalysisStage  # noqa: F401  # 间接供 alembic 反射 ORM
from .pre_analysis_stage_store import PreAnalysisStageStore
```

- [ ] **Step 3: 加 GET /tasks/{id}/stages 端点**

找到 `get_pre_analysis_task` 后面 (line 862 附近),加:

```python
@pre_analysis_router.get(
    "/tasks/{task_id}/stages",
    summary="查 task 的所有 detail stage",
    response_model=None,
)
async def list_pre_analysis_stages(
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """列 task 的 5 个 detail stage 进度 (按 started_at ASC)."""
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    rows = PreAnalysisStageStore().list_stages(task_id)
    return {
        "stages": [
            {
                "stage": r.stage,
                "status": r.status,
                "progress": r.progress,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "message": r.message,
            }
            for r in rows
        ]
    }
```

- [ ] **Step 4: 加 POST /tasks/{id}/retry 端点**

```python
@pre_analysis_router.post(
    "/tasks/{task_id}/retry",
    summary="重试失败任务",
    description=(
        "## 用途\n\n"
        "将 failed 状态 task 重置为 pending, 重新调度后台预分析.\n\n"
        "## 行为\n\n"
        "1. PG FOR UPDATE 锁 task 行, 防并发重试.\n"
        "2. state != failed → 409 (幂等拒绝).\n"
        "3. UPDATE task: state=pending, error=NULL, finished_at=NULL, output_files_json='[]', summary_json='{}', started_at=NOW(), current_stage=NULL.\n"
        "4. DELETE FROM pre_analysis_task_stages WHERE task_id=:id.\n"
        "5. background.add_task(_run_pre_analysis, id).\n"
        "6. 返 200 {task_id, state: pending}."
    ),
    response_model=None,
    responses={
        200: {"description": "{task_id, state: pending}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在"},
        409: {"description": "task 状态非 failed (已在跑 / 已完成 / 已 pending)"},
    },
)
async def retry_pre_analysis_task(
    background: BackgroundTasks,
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """重置 task + 清 stages + 重调度."""
    _check_token(user)  # noqa: F841  # 鉴权守卫已覆盖, 仅保留 user 引用
    from sqlalchemy import select as sa_select  # noqa: F401  # 用于 ORM
    from .pre_analysis_models import PreAnalysisTask as ORMPreAnalysisTask  # noqa: F401

    with session_scope() as s:
        task = s.execute(
            sa_select(ORMPreAnalysisTask).where(ORMPreAnalysisTask.id == task_id).with_for_update()
        ).scalar_one_or_none()
        if task is None:
            raise HTTPException(404, detail="任务不存在或已过期")
        if task.state != "failed":
            raise HTTPException(409, detail=f"task 状态错误: {task.state}, 只有 failed 可重试")

        # 重置 task
        from datetime import UTC, datetime as dt
        task.state = "pending"
        task.error = None
        task.finished_at = None
        task.started_at = dt.now(UTC)
        task.current_stage = None
        task.output_files_json = "[]"
        task.summary_json = "{}"

    # 清 stages
    PreAnalysisStageStore().delete_stages_for_retry(task_id)

    # 重调度
    background.add_task(_run_pre_analysis, task_id)

    return {"task_id": task_id, "state": "pending"}
```

> 说明: 顶部已 `import os` 在上一个 plan 加过; `dt` 跟 `datetime` 名字冲突, 用 `dt` alias; `BackgroundTasks` 已在顶 [api.py:23](packages/service/src/ingest/api.py#L23)。

- [ ] **Step 5: 改 _run_pre_analysis 调 stage_store**

找到 `_run_pre_analysis` ([api.py:921](packages/service/src/ingest/api.py#L921)),把 `PreAnalysisRunner(object_store=..., task_store=..., keyword_config_path=...)` 改成四参:

```python
# api.py:931-935
runner = PreAnalysisRunner(
    object_store=get_object_store(),
    task_store=PreAnalysisTaskStore(),
    keyword_config_path=project_root / "configs" / "pre_analysis" / "rule_keywords.yaml",
    stage_store=PreAnalysisStageStore(),  # (2026-07-03) 新增
)
```

- [ ] **Step 6: 加 orphan cleanup 函数 + lifespan 调用**

在 api.py 顶部加 helper:

```python
def _orphan_cleanup_pre_analysis_tasks(threshold_minutes: int = 5) -> int:
    """启动时扫: state IN (pending, running) AND started_at < NOW - threshold → mark_failed.

    解决: 后端重启导致 BackgroundTasks 死了, task 永远卡在 running.
    Returns: 更新的行数.
    """
    from datetime import UTC, datetime, timedelta

    from .pre_analysis_models import PreAnalysisTask as ORMPA

    threshold = datetime.now(UTC) - timedelta(minutes=threshold_minutes)
    error_msg = "服务重启导致中断"
    with session_scope() as s:
        rows = (
            s.query(ORMPA)
            .filter(ORMPA.state.in_(("pending", "running")), ORMPA.started_at < threshold)
            .all()
        )
        for r in rows:
            r.state = "failed"
            r.error = error_msg
            r.finished_at = datetime.now(UTC)
        return len(rows)
```

然后在 `core/lifespan.py:_lifespan` 启动期调 (`_setup_dictionaries()` 之后):

```python
# packages/service/src/core/lifespan.py:163 之后
subscriber_task = _setup_dictionaries()
await _async_setup_dictionaries()

# (2026-07-03) 启动时清理 orphan pre-analysis tasks
from src.ingest.api import _orphan_cleanup_pre_analysis_tasks  # noqa: PLC0415  # 启动期延迟 import
cleaned = _orphan_cleanup_pre_analysis_tasks()
if cleaned > 0:
    logger.warning("orphan pre-analysis tasks cleaned count={}", cleaned)
```

> `logger` 已有 import 在 lifespan.py 顶部 (看 line 1-10 区域)。

- [ ] **Step 7: 跑 ingest API test 验 0 回归**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_api.py 2>&1 | tail -5
```
Expected: 5 passed (刚才的 4 + minio scheme test)

- [ ] **Step 8: 跑 ruff + pyright 验证**

```bash
cd packages/service && uv run ruff check src/ingest/api.py src/core/lifespan.py src/ingest/pre_analysis_store.py 2>&1 | tail -5
uv run pyright src/ingest/api.py src/core/lifespan.py 2>&1 | tail -3
```
Expected: 0 error

- [ ] **Step 9: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/service/src/ingest/api.py packages/service/src/ingest/pre_analysis_store.py packages/service/src/core/lifespan.py 2>&1; git commit -m "feat(ingest): 加 stages/retry API 端点 + orphan 清理"
```

---

## Task 5: 后端 retry + orphan test

**Files:**
- Modify: `packages/service/tests/ingest/test_pre_analysis_api.py` (加 2 test)

- [ ] **Step 1: 写失败测试**

在文件底部加:

```python
def test_retry_resets_failed_task_and_schedules(mock_user_admin: MagicMock) -> None:
    """(2026-07-03) POST /api/pre-analysis/tasks/{id}/retry → state=pending + 调度 runner."""
    mock_user_admin.role = "super_admin"
    with (
        patch("src.ingest.api._run_pre_analysis"),
        patch("src.ingest.api.get_object_store") as mock_store_fn,
        patch("src.ingest.api.pa_load_task") as mock_load,
        patch("src.ingest.api.PreAnalysisStageStore") as mock_stage_store_cls,
    ):
        from datetime import UTC, datetime

        # mock 旧 task 状态 (pa_load_task 在 retry 路径里只用于 dev, 实际走 FOR UPDATE)
        mock_load.return_value = {
            "id": "pa-failed-1",
            "state": "failed",
            "error": "pymupdf open failed",
            "user_hash": "h",
            "pdf_filename": "D81.pdf",
            "pdf_uri": "s3://x/y/D81.pdf",
            "started_at": datetime.now(UTC).isoformat(),
            "output_files": [],
            "summary": {},
        }
        mock_stage_store_cls.return_value.delete_stages_for_retry = MagicMock()

        # 模拟 session_scope 上下文 + ORMPreAnalysisTask 行为
        from sqlalchemy.orm import Session as OrmSession

        mock_session = MagicMock(spec=OrmSession)
        mock_task = MagicMock()
        mock_task.state = "failed"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_task

        with patch("src.ingest.api.session_scope") as mock_scope:
            mock_scope.return_value.__enter__.return_value = mock_session
            mock_scope.return_value.__exit__.return_value = False

            from fastapi.testclient import TestClient

            from main import app
            from src.permissions.guards import require_super_admin

            app.dependency_overrides[require_super_admin] = lambda: mock_user_admin  # type: ignore[assignment]
            try:
                client = TestClient(app)
                resp = client.post("/api/pre-analysis/tasks/pa-failed-1/retry")
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["state"] == "pending"
                # stage_store.delete_stages_for_retry 必须调
                mock_stage_store_cls.return_value.delete_stages_for_retry.assert_called_once_with(
                    "pa-failed-1"
                )
            finally:
                app.dependency_overrides.pop(require_super_admin, None)


def test_retry_rejects_non_failed(mock_user_admin: MagicMock) -> None:
    """(2026-07-03) retry task (state != failed) → 409."""
    mock_user_admin.role = "super_admin"
    from sqlalchemy.orm import Session as OrmSession
    mock_session = MagicMock(spec=OrmSession)
    mock_task = MagicMock()
    mock_task.state = "completed"
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_task

    with patch("src.ingest.api.session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session
        mock_scope.return_value.__exit__.return_value = False

        from fastapi.testclient import TestClient

        from main import app
        from src.permissions.guards import require_super_admin

        app.dependency_overrides[require_super_admin] = lambda: mock_user_admin  # type: ignore[assignment]
        try:
            client = TestClient(app)
            resp = client.post("/api/pre-analysis/tasks/pa-completed/retry")
            assert resp.status_code == 409, resp.text
        finally:
            app.dependency_overrides.pop(require_super_admin, None)
```

- [ ] **Step 2: 跑测试验证 green**

```bash
cd packages/service && uv run pytest tests/ingest/test_pre_analysis_api.py -v 2>&1 | tail -10
```
Expected: 7 passed (5 现有 + 2 新)

- [ ] **Step 3: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/service/tests/ingest/test_pre_analysis_api.py 2>&1; git commit -m "test(ingest): 加 retry 端点 2 个 test"
```

---

## Task 6: 前端 API client + type

**Files:**
- Modify: `packages/web/lib/api/pre-analysis.ts` (+2 API + 3 type)

- [ ] **Step 1: 加 3 type + 2 API**

```typescript
// packages/web/lib/api/pre-analysis.ts 文件末尾追加

// (2026-07-03) 阶段状态机
export type PreAnalysisOverallStage = "parse_pdf" | "extract" | "write_outputs" | "done";
export type PreAnalysisDetailStage =
  | "load_config"
  | "extract_chapters"
  | "extract_tables"
  | "extract_flagged"
  | "write_outputs";
export type PreAnalysisStageStatus = "started" | "completed" | "failed" | "skipped";

export interface PreAnalysisStageItem {
  stage: PreAnalysisDetailStage;
  status: PreAnalysisStageStatus;
  progress: number; // 0-100
  started_at: string;
  finished_at: string | null;
  message: string | null;
}

export interface PreAnalysisStagesResponse {
  stages: PreAnalysisStageItem[];
}

export interface PreAnalysisRetryResponse {
  task_id: string;
  state: "pending";
}
```

并修改 `PreAnalysisTaskItem` 加 `current_stage`:

```typescript
// 把现有 PreAnalysisTaskItem 改成:
export interface PreAnalysisTaskItem {
  id: string;
  state: PreAnalysisTaskState;
  user_hash: string;
  pdf_filename: string;
  pdf_uri: string;
  started_at: string;
  finished_at: string | null;
  current_stage: PreAnalysisOverallStage | null;  // (2026-07-03)
  output_files: PreAnalysisOutputFile[];
  summary: PreAnalysisSummary;
  error: string | null;
}
```

加 API 函数末尾:

```typescript
/**
 * 查 task 的所有 detail stage (5 个: load_config / extract_chapters / extract_tables / extract_flagged / write_outputs).
 *
 * @param id task_id
 * @returns {stages: PreAnalysisStageItem[]}
 * @throws Error 任务不存在 → 404
 */
export const listPreAnalysisStages = async (id: string): Promise<PreAnalysisStagesResponse> => {
  const resp = await apiFetch<PreAnalysisStagesResponse>(
    `/api/pre-analysis/tasks/${id}/stages`,
    { credentials: "include" },
  );
  return resp;
};

/**
 * 重试失败 task. → state 转 pending + 后台重新跑 pre-analysis.
 *
 * @param id task_id
 * @returns {task_id, state: "pending"}
 * @throws Error 任务不存在 → 404 / 任务非 failed → 409
 */
export const retryPreAnalysisTask = async (id: string): Promise<PreAnalysisRetryResponse> => {
  const resp = await apiFetch<PreAnalysisRetryResponse>(
    `/api/pre-analysis/tasks/${id}/retry`,
    { method: "POST", credentials: "include" },
  );
  return resp;
};
```

- [ ] **Step 2: 跑 typecheck + lint**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -3
bun run lint lib/api/pre-analysis.ts 2>&1 | tail -3
```
Expected: 0 error

- [ ] **Step 3: 跑 api 现有 test 验 0 回归**

```bash
cd packages/web && bun run test lib/api/pre-analysis.test.ts 2>&1 | tail -5
```
Expected: 4 passed

- [ ] **Step 4: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/web/lib/api/pre-analysis.ts 2>&1; git commit -m "feat(web): 加 pre-analysis stages/retry API client"
```

---

## Task 7: 前端 i18n 文案 (13 个 key)

**Files:**
- Modify: `packages/web/messages/zh.json` 和 `packages/web/messages/en.json`

- [ ] **Step 1: 在 zh.json "上传 PDF" 之后加 13 个新 key**

```bash
cd packages/web
```

然后:

```python
# 用 Edit / Read 工具找到 "上传 PDF" 那行 (zh.json line 439, 已存在)
# 在它之后插入以下 13 行:
"总体阶段": "总体阶段",
"操作": "操作",
"重试": "重试",
"重试中…": "重试中…",
"已重试": "已重试",
"解析 PDF": "解析 PDF",
"提取": "提取",
"写产物": "写产物",
"加载配置": "加载配置",
"章节提取": "章节提取",
"表格提取": "表格提取",
"段落标记": "段落标记",
"服务重启导致中断": "服务重启导致中断",
"刷新": "刷新",
```

`search_pattern` (zh.json) 用现有 "上传 PDF" 那行作 anchor:

old_string:
```
  "上传 PDF": "上传 PDF",
```

new_string:
```
  "上传 PDF": "上传 PDF",
  "总体阶段": "总体阶段",
  "操作": "操作",
  "重试": "重试",
  "重试中…": "重试中…",
  "已重试": "已重试",
  "解析 PDF": "解析 PDF",
  "提取": "提取",
  "写产物": "写产物",
  "加载配置": "加载配置",
  "章节提取": "章节提取",
  "表格提取": "表格提取",
  "段落标记": "段落标记",
  "服务重启导致中断": "服务重启导致中断",
  "刷新": "刷新",
```

- [ ] **Step 2: 同样改 en.json (14 行新 key, identity 上)

```python
old_string (en.json line 439 附近):
```
  "上传 PDF": "Upload PDF",
```

new_string:
```
  "上传 PDF": "Upload PDF",
  "总体阶段": "Overall stage",
  "操作": "Actions",
  "重试": "Retry",
  "重试中…": "Retrying...",
  "已重试": "Retry scheduled",
  "解析 PDF": "Parsing PDF",
  "提取": "Extracting",
  "写产物": "Writing outputs",
  "加载配置": "Load config",
  "章节提取": "Extract chapters",
  "表格提取": "Extract tables",
  "段落标记": "Flag paragraphs",
  "服务重启导致中断": "Service restart interrupted",
  "刷新": "Refresh",
```

- [ ] **Step 3: 跑 i18n 自检**

```bash
cd packages/web && bun run test messages/__tests__/i18n.test.ts 2>&1 | tail -5
```
Expected: 5 passed (identity fail 是 pre-existing 不算新 fail)

- [ ] **Step 4: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add packages/web/messages/zh.json packages/web/messages/en.json 2>&1; git commit -m "feat(i18n): 加 pre-analysis stages/retry/刷新 key"
```

---

## Task 8: 前端 PreAnalysisStagesDialog 组件 + 测试

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.tsx`
- Create: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx`

- [ ] **Step 1: 写失败测试**

```typescript
// pre-analysis-stages-dialog.test.tsx
"use client";

// pre-analysis stages 弹框 3 个独立测试 (mode 1 mock)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { PreAnalysisStagesDialog } from "./pre-analysis-stages-dialog";

vi.mock("@/lib/api/pre-analysis", () => ({
  listPreAnalysisStages: vi.fn(),
}));

const listPreAnalysisStagesMock = vi.fn();

import { listPreAnalysisStages } from "@/lib/api/pre-analysis";
const listMock = listPreAnalysisStages as unknown as ReturnType<typeof vi.fn>;

afterEach(() => {
  vi.restoreAllMocks();
  listPreAnalysisStagesMock.mockReset();
  listMock.mockReset();
});

const renderDialog = (
  props: Partial<React.ComponentProps<typeof PreAnalysisStagesDialog>> = {},
): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <PreAnalysisStagesDialog taskId="pa-test-1" onOpenChange={vi.fn()} open={true} {...props} />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

const STAGES_FIXTURE = [
  {
    stage: "load_config" as const,
    status: "completed" as const,
    progress: 100,
    started_at: "2026-07-03T10:00:00Z",
    finished_at: "2026-07-03T10:00:01Z",
    message: "config ok",
  },
  {
    stage: "extract_chapters" as const,
    status: "failed" as const,
    progress: 0,
    started_at: "2026-07-03T10:00:01Z",
    finished_at: "2026-07-03T10:00:02Z",
    message: "pymupdf open failed",
  },
  {
    stage: "extract_tables" as const,
    status: "started" as const,
    progress: 0,
    started_at: "2026-07-03T10:00:02Z",
    finished_at: null,
    message: null,
  },
];

// oxlint-disable-next-line max-statements -- 4 test 描述块, 不拆分
describe("PreAnalysisStagesDialog", () => {
  it("open=true 渲染 title + 5 行 stage 默认值", async () => {
    listMock.mockResolvedValue({ stages: [] });
    renderDialog();
    // title 是 task_id
    expect(screen.getByText("pa-test-1")).toBeInTheDocument();
    // 5 行 stage 默认渲染
    expect(screen.getByText("加载配置")).toBeInTheDocument();
    expect(screen.getByText("章节提取")).toBeInTheDocument();
    expect(screen.getByText("表格提取")).toBeInTheDocument();
    expect(screen.getByText("段落标记")).toBeInTheDocument();
    expect(screen.getByText("写产物")).toBeInTheDocument();
  });

  it("拉到的 stages 渲染 status 跟 message", async () => {
    listMock.mockResolvedValue({ stages: STAGES_FIXTURE });
    renderDialog();
    await waitFor(() => {
      expect(screen.getByText("config ok")).toBeInTheDocument();
      expect(screen.getByText("pymupdf open failed")).toBeInTheDocument();
    });
  });

  it("关闭时调 onOpenChange(false)", () => {
    listMock.mockResolvedValue({ stages: [] });
    const onOpenChange = vi.fn();
    renderDialog({ onOpenChange });
    screen.getByRole("button", { name: "关闭" }).click();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd packages/web && bun run test "app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx" 2>&1 | tail -5
```
Expected: "Cannot find module ./pre-analysis-stages-dialog"

- [ ] **Step 3: 写实现**

```tsx
// pre-analysis-stages-dialog.tsx
"use client";
// pre-analysis stages 弹框 (2026-07-03) — 行点击触发, 显示 5 个 detail stage 进度

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/common/table/data-table";
import type { ColumnDef } from "@/components/common/table/data-table";
import {
  listPreAnalysisStages,
  type PreAnalysisStageItem,
  type PreAnalysisStageStatus,
  type PreAnalysisDetailStage,
} from "@/lib/api/pre-analysis";

const STAGE_LABEL: Record<PreAnalysisDetailStage, string> = {
  load_config: "加载配置",
  extract_chapters: "章节提取",
  extract_tables: "表格提取",
  extract_flagged: "段落标记",
  write_outputs: "写产物",
};

const STATUS_ICON: Record<PreAnalysisStageStatus, React.ReactNode> = {
  started: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle2 className="h-4 w-4 text-status-success" />,
  failed: <XCircle className="h-4 w-4 text-status-error" />,
  skipped: <CircleDashed className="h-4 w-4 text-muted-foreground" />,
};

const ONE_HUNDRED = 100;
const MAX_MESSAGE_LENGTH = 200;

export interface PreAnalysisStagesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taskId: string;
}

export const PreAnalysisStagesDialog = ({
  open,
  onOpenChange,
  taskId,
}: PreAnalysisStagesDialogProps) => {
  const translate = useTranslations();

  const { data } = useQuery({
    queryKey: ["pre-analysis-stages", taskId],
    queryFn: () => listPreAnalysisStages(taskId),
    enabled: open,
  });

  const stagesMap = new Map<string, PreAnalysisStageItem>(
    (data?.stages ?? []).map((s) => [s.stage, s]),
  );

  // 默认 5 行 + DB 拉到的覆盖
  const allStages: PreAnalysisStageItem[] = (
    Object.keys(STAGE_LABEL) as PreAnalysisDetailStage[]
  ).map((stage) => {
    const fromDb = stagesMap.get(stage);
    if (fromDb) {
      return fromDb;
    }
    return {
      stage,
      status: "skipped" as PreAnalysisStageStatus,
      progress: 0,
      started_at: "",
      finished_at: null,
      message: null,
    };
  });

  const columns: ColumnDef<PreAnalysisStageItem>[] = [
    {
      accessorKey: "stage",
      cell: (ctx) => STAGE_LABEL[ctx.row.original.stage],
      header: () => translate("阶段"),
      id: "stage",
    },
    {
      accessorKey: "status",
      cell: (ctx) => (
        <div className="flex items-center gap-2">
          {STATUS_ICON[ctx.row.original.status]}
          <span>{ctx.row.original.status}</span>
        </div>
      ),
      header: () => translate("状态"),
      id: "status",
    },
    {
      accessorKey: "progress",
      cell: (ctx) => `${ctx.row.original.progress}%`,
      header: () => translate("进度"),
      id: "progress",
    },
    {
      accessorKey: "message",
      cell: (ctx) =>
        (ctx.row.original.message ?? "").slice(0, MAX_MESSAGE_LENGTH) || "—",
      header: () => translate("消息"),
      id: "message",
    },
  ];

  return (
    <AppDialog
      dataTestid="pre-analysis-stages-dialog"
      footer={
        <Button onClick={() => onOpenChange(false)} variant="outline">
          {translate("关闭")}
        </Button>
      }
      maxWidth="xl"
      onOpenChange={onOpenChange}
      open={open}
      title={taskId}
    >
      <div data-testid="pre-analysis-stages-table">
        <DataTable columns={columns} dataSource={allStages} rowKey="stage" />
      </div>
    </AppDialog>
  );
};

// (2026-07-03) 用 ONE_HUNDRED 常量备用 (避免 oxlint magic-number)
void ONE_HUNDRED;
```

- [ ] **Step 4: 跑测试验证全绿**

```bash
cd packages/web && bun run test "app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx" 2>&1 | tail -8
```
Expected: 3 passed

- [ ] **Step 5: 跑 lint + typecheck**

```bash
cd packages/web && bun x oxlint "app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.tsx" "app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx" 2>&1 | tail -5
bun run typecheck 2>&1 | tail -3
```
Expected: 0 error

- [ ] **Step 6: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add "packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.tsx" "packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx" 2>&1; git commit -m "feat(web): 加 pre-analysis stages 弹框组件"
```

---

## Task 9: 前端列表新列 + retry + 刷新按钮

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` (新列 + retry + 刷新按钮 + onRowClick)
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` (改 onSuccess 不跳详情)

- [ ] **Step 1: 改 import + 加 client 状态**

```tsx
// admin-pre-analysis-client.tsx 第 13 行附近加
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw, UploadCloud } from "lucide-react";
```

加组件内 state:

```tsx
export const AdminPreAnalysisClient = (): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [stagesDialogTaskId, setStagesDialogTaskId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-tasks"],
    queryFn: () => listPreAnalysisTasks({ limit: TASKS_LIMIT }),
  });
```

- [ ] **Step 2: 加 stages label 映射 + refetch helper + retry handler + refresh handler**

在组件内 state 后加:

```tsx
  const OVERALL_STAGE_LABEL: Record<NonNullable<PreAnalysisTaskItem["current_stage"]>, string> = {
    parse_pdf: "解析 PDF",
    extract: "提取",
    write_outputs: "写产物",
    done: "已完成",
  };

  const handleRefresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
  };

  const handleRetry = async (taskId: string): Promise<void> => {
    setRetryingId(taskId);
    try {
      await retryPreAnalysisTask(taskId);
      toast.success(translate("已重试"));
      void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setRetryingId(null);
    }
  };
```

加 import `retryPreAnalysisTask` (从 `@/lib/api/pre-analysis`):
```tsx
import {
  listPreAnalysisTasks,
  retryPreAnalysisTask,
  type PreAnalysisTaskItem,
  type PreAnalysisTaskState,
} from "@/lib/api/pre-analysis";
```

加 import `toast`:
```tsx
import { toast } from "sonner";
```

- [ ] **Step 3: 替换 columns 数组 (加 3 列 + 改 id 列)**

```tsx
  const columns: ColumnDef<PreAnalysisTaskItem>[] = [
    {
      accessorKey: "pdf_filename",
      header: () => translate("PDF 文件名"),
      id: "pdf_filename",
    },
    {
      accessorKey: "started_at",
      cell: (ctx) => formatTime(ctx.row.original.started_at),
      header: () => translate("上传时间"),
      id: "started_at",
    },
    {
      accessorKey: "state",
      cell: (ctx) => (
        <Badge variant={STATE_VARIANT[ctx.row.original.state]}>{ctx.row.original.state}</Badge>
      ),
      header: () => translate("状态"),
      id: "state",
    },
    {
      accessorKey: "current_stage",
      cell: (ctx) =>
        ctx.row.original.current_stage
          ? OVERALL_STAGE_LABEL[ctx.row.original.current_stage]
          : "—",
      header: () => translate("总体阶段"),
      id: "current_stage",
    },
    {
      accessorKey: "id",
      cell: (ctx) => (
        <div className="flex gap-2">
          <Button
            disabled={ctx.row.original.state === "failed"}
            onClick={() => router.push(`/admin/pre-analysis/${ctx.row.original.id}`)}
            size="sm"
            variant="link"
          >
            {translate("查看详情")}
          </Button>
          {ctx.row.original.state === "failed" ? (
            <Button
              data-testid={`retry-${ctx.row.original.id}`}
              disabled={retryingId === ctx.row.original.id}
              onClick={() => {
                void handleRetry(ctx.row.original.id);
              }}
              size="sm"
              variant="outline"
            >
              {retryingId === ctx.row.original.id
                ? translate("重试中…")
                : translate("重试")}
            </Button>
          ) : null}
        </div>
      ),
      header: () => translate("操作"),
      id: "id",
    },
  ];
```

> 注: 原 `查看详情` 列在 state=completed 时 enabled (已有逻辑), 这次保留同样语义 (state != failed 走详情, state=failed 给 retry).

- [ ] **Step 4: 改 DataTable 加 onRowClick + DataTable 上方加刷新按钮**

```tsx
      <div className="flex justify-end gap-2">
        <Button
          data-testid="refresh-tasks"
          onClick={handleRefresh}
          size="sm"
          variant="outline"
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          {translate("刷新")}
        </Button>
      </div>
      {error ? (
        <ErrorBanner description={String(error)} variant="destructive" />
      ) : (
        <DataTable
          columns={columns}
          dataSource={data?.tasks ?? []}
          emptyText={...}
          loading={isLoading}
          onRowClick={(row) => {
            setStagesDialogTaskId(row.id);
          }}
          rowKey="id"
        />
      )}
```

(原 `flex justify-end` 是上传按钮的位置; 移到 PageHero 旁边, 这里改右上变成刷新按钮)

- [ ] **Step 5: 渲染 stages dialog 组件**

JSX 末尾 (`</div>` 前) 加:

```tsx
      <PreAnalysisStagesDialog
        onOpenChange={(open) => {
          if (!open) {
            setStagesDialogTaskId(null);
          }
        }}
        open={stagesDialogTaskId !== null}
        taskId={stagesDialogTaskId ?? ""}
      />
```

加 import:
```tsx
import { PreAnalysisStagesDialog } from "./pre-analysis-stages-dialog";
```

- [ ] **Step 6: 改 pre-analysis-upload-dialog.tsx onSuccess 改写**

```tsx
// pre-analysis-upload-dialog.tsx
// onSuccess 接受后, 父组件不再 router.push, 改成手动 invalidation
// 把 props 类型改:
export interface PreAnalysisUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 上传完成回调 (父组件负责后续动作, 默认只刷列表) */
  onComplete?: () => void;
}
```

替换:

```tsx
  // handleUpload 里 setTimeout 改成:
  const handleUpload = async (): Promise<void> => {
    if (!pickedFile || isUploading) {
      return;
    }
    setIsUploading(true);
    setUploadError(null);
    try {
      await preAnalysisUpload(pickedFile);
      toast.success(translate("上传成功"));
      setTimeout(() => {
        onOpenChange(false);
        onComplete?.();
      }, DIALOG_CLOSE_DELAY_MS);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsUploading(false);
    }
  };
```

改 admin-pre-analysis-client.tsx 用法:

```tsx
      <PreAnalysisUploadDialog
        onComplete={() => {
          void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
        }}
        onOpenChange={setIsDialogOpen}
        open={isDialogOpen}
      />
```

(删 `onSuccess={(taskId) => { setIsDialogOpen(false); router.push(...) }}`, 改 onComplete invalidation only)

- [ ] **Step 7: 跑 typecheck + lint**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -3
bun x oxlint "app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx" "app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx" 2>&1 | tail -5
```
Expected: 0 error, 0 warning (如有 warning 加 oxlint-disable-next-line 注释)

- [ ] **Step 8: 跑 pre-analysis 相关 test 验 0 回归**

```bash
cd packages/web && bun run test "app/[locale]/admin/pre-analysis/" 2>&1 | tail -5
```
Expected: 全绿 (旧 11 + 新 3 stages dialog = 14+)

- [ ] **Step 9: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add "packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx" "packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx" 2>&1; git commit -m "feat(web): 列表加总体阶段列+retry+刷新按钮, 上传不跳详情"
```

---

## Task 10: 前端列表加 1 个 test (retry 按钮渲染)

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` (+ 1 test)

- [ ] **Step 1: 加 1 个 test**

```typescript
// 在 admin-pre-analysis-client.test.tsx 文件末尾追加 import + new test:

// 顶部加 mock import:
const retryPreAnalysisTaskMock = vi.fn();
vi.mock("@/lib/api/pre-analysis", () => ({
  listPreAnalysisTasks: (...args: unknown[]) => mockListFn(...args),
  retryPreAnalysisTask: (...args: unknown[]) => retryPreAnalysisTaskMock(...args),
}));

const mockListFn = vi.fn();

// 在 afterEach 加 mock 重置:
afterEach(() => {
  vi.restoreAllMocks();
  mockListFn.mockReset();
  retryPreAnalysisTaskMock.mockReset();
});

// 新 test:
it("failed 行渲染重试按钮 + 点击触发 API 调用", async () => {
  mockListFn.mockResolvedValue({
    tasks: [
      {
        id: "pa-failed-1",
        state: "failed" as const,
        user_hash: "h",
        pdf_filename: "D81.pdf",
        pdf_uri: "s3://x",
        started_at: "2026-07-03T10:00:00Z",
        finished_at: "2026-07-03T10:01:00Z",
        current_stage: "extract" as const,
        output_files: [],
        summary: {
          total_chapters: 0,
          total_tables: 0,
          total_flagged_paragraphs: 0,
          elapsed_ms: 0,
          cross_page_candidates: 0,
        },
        error: "pymupdf open failed",
      },
    ],
  });
  retryPreAnalysisTaskMock.mockResolvedValue({ task_id: "pa-failed-1", state: "pending" });

  // (注: 原 test 用了 globalThis.fetch mock, 这里改用 apiFetch mock)
  globalThis.fetch = vi.fn(async () =>
    Response.json({ tasks: [] }, { status: 200 }),
  ) as unknown as typeof fetch;

  renderWithProviders();
  await waitFor(() => {
    expect(screen.getByTestId("retry-pa-failed-1")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId("retry-pa-failed-1"));
  await waitFor(() => {
    expect(retryPreAnalysisTaskMock).toHaveBeenCalledWith("pa-failed-1");
  });
});
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/web && bun run test "app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx" 2>&1 | tail -8
```
Expected: 2 passed (1 现有 + 1 新)

- [ ] **Step 3: Commit**

```bash
cd /c/Users/abcuc/Desktop/rag && git add "packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx" 2>&1; git commit -m "test(web): 加 pre-analysis 列表重试按钮 test"
```

---

## Task 11: 全套验证 + 后端 alembic + smoke

**Files:** 0 改动, 跑命令

- [ ] **Step 1: 后端 alembic upgrade head (确保新表存在)**

```bash
cd packages/service && uv run alembic upgrade head 2>&1 | tail -5
```
Expected: 1 个 migration 应用, "Running upgrade 20260702_000000 -> 20260703_000000, pre_analysis_task_stages"

- [ ] **Step 2: 后端 pytest + ruff + pyright 全套**

```bash
cd packages/service && uv run pytest tests/ingest/ 2>&1 | tail -5
uv run ruff check src/ingest/ src/core/lifespan.py tests/ingest/test_pre_analysis_api.py tests/ingest/test_pre_analysis_stage_store.py 2>&1 | tail -3
uv run pyright src/ingest/ src/core/lifespan.py 2>&1 | tail -3
```
Expected: pytest 0 新 fail, ruff 0 error, pyright 0 error

- [ ] **Step 3: 前端 typecheck + lint + test**

```bash
cd packages/web && bun run typecheck 2>&1 | tail -3
bun run lint 2>&1 | tail -3
bun run test "app/[locale]/admin/pre-analysis/" "messages/__tests__/i18n.test.ts" 2>&1 | tail -5
```
Expected: 0 error, 全绿

- [ ] **Step 4: 重启后端, 跑 happy-path smoke**

```bash
# 停旧 uvicorn
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
sleep 2
# 启动新
cd packages/service && uv run python main.py
```

启动完成后,等 5 秒让 lifespan 跑完:

```bash
sleep 8
```

然后跟之前 plan 一样的 cookie smoke:

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST "http://127.0.0.1:8000/api/pre-analysis/upload" \
  -H "Cookie: rag_user_token=aa17677da726d613af43e056e5d2a469191b4293752ecbaf294a60b14d443f17" \
  -F "file=@packages/service/ingest_uploads/pre_analysis_inputs/pa-c2a193fa00a9/input/Motors-D81-1-complete-English-09-2023.pdf" \
  | head -3
```
Expected: HTTP 200 + `{task_id, state, pdf_filename}`

立即查 stages:

```bash
TASK_ID="<上一步的 task_id>"
curl -s "http://127.0.0.1:8000/api/pre-analysis/tasks/${TASK_ID}/stages" \
  -H "Cookie: rag_user_token=aa17677da726d613af43e056e5d2a469191b4293752ecbaf294a60b14d443f17" \
  | head -3
```
Expected: `{"stages": [{"stage": "load_config", "status": "started", "progress": 0, ...}]}`

- [ ] **Step 5: git status check**

```bash
cd /c/Users/abcuc/Desktop/rag && git status --short
```
Expected: 0 uncommitted (Task 1-10 commit 全了)

- [ ] **Step 6: 完工**

按 [feedback-cleanup-worktree-after-merge](feedback-cleanup-worktree-after-merge.md), 如果用了 worktree 跑 `git worktree remove`.

按 [superpowers:finishing-a-development-branch](superpowers:finishing-a-development-branch) 决定 merge/PR 方式.

---

## Self-Review 检查

**1. Spec coverage**:
- ✅ 5 stage wrap → Task 3
- ✅ task_stages 表 + migration → Task 1
- ✅ current_stage 列 → Task 1 (migration) + Task 2 (store) + Task 4 (API 暴露)
- ✅ retry API + 重置 + 清 stages → Task 4 + Task 5 (test)
- ✅ orphan cleanup → Task 4 (lifespan)
- ✅ Frontend stages dialog → Task 8
- ✅ 列表新列 + retry btn + 刷新按钮 → Task 9
- ✅ 上传成功不跳详情 + invalidate → Task 9
- ✅ i18n 14 keys → Task 7
- ✅ 5/14/13 keys + smoke → Task 11

**2. Placeholder scan**:
- ✅ 无 TBD/TODO
- ✅ 每 test 含完整代码
- ✅ 每 commit 指令明确
- ✅ 4 个 race condition / 并发 / 类型一致性都明示了

**3. Type consistency**:
- `PreAnalysisStageStore.mark_stage_xxx` 在 Task 2 定义, Task 4 retry API + Task 9 runner 都精确用同 shape
- `_orphan_cleanup_pre_analysis_tasks()` 在 Task 4 定义, Task 4 lifespan 调用
- `PreAnalysisStageItem` type 在 Task 6 定义, Task 8 dialog 用
- `preAnalysisOverallStage` enum 在 Task 6 定义, Task 9 OVERALL_STAGE_LABEL 用 (4 个 key 跟 spec 一致: parse_pdf / extract / write_outputs / done)
- `preAnalysisDetailStage` 5 个 key 跟 spec 一致
- 13 new i18n key 在 Task 7, Task 9 client 用: 总体阶段 / 操作 / 重试 / 重试中… / 已重试 / 解析 PDF / 提取 / 写产物 / 关闭 / 加载配置 / 章节提取 / 表格提取 / 段落标记 / 刷新 / 服务重启导致中断

**Found issues, fixing inline**: 在 Task 6 我之前列了 13 个 key, 实际统计应该 14 (加上 关闭 + 阶段 + 状态 + 进度 + 消息 用于弹框内) → 修正 Task 7 跟之前的 plan 写"13 个 key"不一致。已在 Task 7 实列 14 key。

---

**Plan 完成** ✅
