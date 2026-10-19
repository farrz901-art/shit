# SQLite → pgvector 迁移 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/service/data/*.db` 3 个 SQLite 文件全部迁到 docker 已起的 PostgreSQL (`pgvector/pgvector:pg18`, 端口 5432), 跟 pgvector 共用一个 DB. 删 SQLite 文件 + SQLite 适配代码, 写一次性数据搬运脚本, 全部测试重写为 PG.

**Architecture:** 单一数据源. 业务表 + ingest_tasks + kg_audit 全部用 SQLAlchemy ORM 走 PG. Alembic 重新做一次 consolidated init migration. 现有对外 API (`session_scope()`, `save_task_dict()`, `AuditStore`) 签名 0 改动. 4 批 commit, 每批独立可测/可回滚.

**Tech Stack:** SQLAlchemy 2.0 ORM, Alembic, psycopg3, pgvector, pytest, Docker

**Spec:** [docs/superpowers/specs/2026-06-15-sqlite-to-pgvector-migration-design.md](../specs/2026-06-15-sqlite-to-pgvector-migration-design.md)

---

## 阶段 0: 前置条件

### Task 0: 验证 docker PG 可用

**Files:** 无 (环境验证)

- [ ] **Step 1: 启动 docker PG**

```bash
cd docker
docker compose up -d postgres pgadmin
```

- [ ] **Step 2: 等 PG 就绪**

```bash
docker compose ps postgres
```

Expected: `pgvector` 容器状态 `Up` + `(healthy)`. 如果 30 秒没 healthy, `docker logs pgvector` 看错误.

- [ ] **Step 3: 验证连接**

```bash
cd ../packages/service
echo 'SELECT 1' | docker exec -i pgvector psql -U postgres -d rag -t -A
```

Expected: `1`

如果 docker 没起 / 密码对不上, **停下来排查**, 不要继续 (后续所有 task 都依赖这个).

---

## 阶段 1: ORM model + consolidated migration (Batch 1)

### Task 1: 添加 IngestTask ORM model

**Files:**
- Create: `packages/service/src/ingest/models.py`
- Test: `packages/service/tests/ingest/test_models.py`

- [ ] **Step 1: 写失败测试**

Create `packages/service/tests/ingest/test_models.py`:

```python
"""IngestTask ORM model 单元测试 (无 DB, 纯字段断言)"""

from __future__ import annotations

from sqlalchemy import DateTime, Float, Integer, String, Text


class TestIngestTaskTable:
    """IngestTask 表结构断言"""

    def test_tablename(self):
        from src.ingest.models import IngestTask

        assert IngestTask.__tablename__ == "ingest_tasks"

    def test_columns_present(self):
        from src.ingest.models import IngestTask

        cols = {c.name for c in IngestTask.__table__.columns}
        expected = {
            "id", "user_hash", "state", "total_files", "processed",
            "failed", "started_at", "finished_at", "error", "work_dir",
            "input_files_json", "output_files_json",
        }
        assert expected.issubset(cols), f"缺列: {expected - cols}"

    def test_id_is_string_pk(self):
        from src.ingest.models import IngestTask

        col = IngestTask.__table__.columns.id
        assert isinstance(col.type, String)
        assert col.primary_key is True
        assert col.nullable is False

    def test_user_hash_indexed(self):
        from src.ingest.models import IngestTask

        col = IngestTask.__table__.columns.user_hash
        assert col.nullable is False
        assert col.index is True

    def test_state_not_null(self):
        from src.ingest.models import IngestTask

        col = IngestTask.__table__.columns.state
        assert col.nullable is False
        assert isinstance(col.type, String)

    def test_counts_are_int(self):
        from src.ingest.models import IngestTask

        for c in ["total_files", "processed", "failed"]:
            col = IngestTask.__table__.columns[c]
            assert isinstance(col.type, Integer), f"{c} 应为 Integer"
            assert col.nullable is False

    def test_timestamps_are_datetime(self):
        from src.ingest.models import IngestTask

        assert isinstance(IngestTask.__table__.columns.started_at.type, DateTime)
        assert IngestTask.__table__.columns.started_at.nullable is False
        assert IngestTask.__table__.columns.finished_at.nullable is True

    def test_json_columns_are_text(self):
        """input_files_json / output_files_json 存 JSON 字符串, 用 Text (跟原 SQLite 一致)"""
        from src.ingest.models import IngestTask

        for c in ["input_files_json", "output_files_json"]:
            col = IngestTask.__table__.columns[c]
            assert isinstance(col.type, Text)
            assert col.nullable is False

    def test_composite_index(self):
        """(user_hash, started_at) 复合索引加速按用户查询"""
        from src.ingest.models import IngestTask

        idx_names = {i.name for i in IngestTask.__table__.indexes}
        assert "ix_ingest_tasks_user_started" in idx_names
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
uv run pytest tests/ingest/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.ingest.models'`

- [ ] **Step 3: 实现 IngestTask model**

Create `packages/service/src/ingest/models.py`:

```python
"""ingest 子包 ORM model (2026-06-15).

替原 src/ingest/store.py 里的 sqlite3 raw table. 字段跟旧 schema 1:1 对齐,
保证 save_task_dict / load_task_dict 行为不变.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class IngestTask(Base):
    """ingest task 元数据.

    字段顺序 + 类型跟原 data/ingest_tasks.db schema 一致:
    - id: 业务 UUID 字符串 (不是 DB 自增)
    - user_hash: 用户标识 (cookie hash)
    - state: pending / running / completed / failed
    - total_files / processed / failed: 进度计数
    - started_at / finished_at: 时间戳
    - input_files_json / output_files_json: 列表的 JSON 字符串 (跟原 SQLite 一致, 不用 JSONB)
    """

    __tablename__ = "ingest_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    output_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    __table_args__ = (Index("ix_ingest_tasks_user_started", "user_hash", "started_at"),)

    def __repr__(self) -> str:
        return f"<IngestTask id={self.id} state={self.state} {self.processed}/{self.total_files}>"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
uv run pytest tests/ingest/test_models.py -v
```

Expected: 9 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/ingest/models.py packages/service/tests/ingest/test_models.py
git commit -m "feat(ingest): add IngestTask ORM model"
```

---

### Task 2: 添加 KgAudit ORM model

**Files:**
- Create: `packages/service/src/kg/audit_models.py`
- Test: `packages/service/tests/kg/test_audit_models.py`

- [ ] **Step 1: 写失败测试**

Create `packages/service/tests/kg/test_audit_models.py`:

```python
"""KgAudit ORM model 单元测试"""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text


class TestKgAuditTable:
    """KgAudit 表结构断言"""

    def test_tablename(self):
        from src.kg.audit_models import KgAudit

        assert KgAudit.__tablename__ == "kg_audit"

    def test_columns_present(self):
        from src.kg.audit_models import KgAudit

        cols = {c.name for c in KgAudit.__table__.columns}
        expected = {"id", "ts", "action", "actor", "target", "result", "detail"}
        assert expected.issubset(cols)

    def test_id_is_autoincrement_pk(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.id
        assert isinstance(col.type, Integer)
        assert col.primary_key is True
        assert col.autoincrement is True

    def test_ts_is_float_indexed(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.ts
        assert isinstance(col.type, Float)
        assert col.nullable is False
        assert col.index is True

    def test_action_not_null(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.action
        assert col.nullable is False
        assert isinstance(col.type, String)

    def test_actor_target_nullable(self):
        from src.kg.audit_models import KgAudit

        assert KgAudit.__table__.columns.actor.nullable is True
        assert KgAudit.__table__.columns.target.nullable is True

    def test_result_not_null(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.result
        assert col.nullable is False

    def test_detail_is_text_json_string(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.detail
        assert isinstance(col.type, Text)
        assert col.nullable is False
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
uv run pytest tests/kg/test_audit_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.kg.audit_models'`

- [ ] **Step 3: 实现 KgAudit model**

Create `packages/service/src/kg/audit_models.py`:

```python
"""kg (知识图谱) 子包 ORM model (2026-06-15).

替原 src/kg/audit.py 里的 sqlite3 raw table. 字段跟旧 schema 1:1 对齐,
保证 AuditStore.record / list_recent 行为不变.
"""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class KgAudit(Base):
    """知识图谱审计日志.

    字段顺序 + 类型跟原 data/kg_audit.db schema 一致:
    - id: DB 自增 PK
    - ts: Unix 时间戳 (float, 秒), 原 SQLite schema 用 REAL
    - action: 操作类型 (e.g. "create_triple", "update_node")
    - actor: 操作者标识 (current user id 字符串)
    - target: 操作目标 (triple id / node id 等)
    - result: ok / error
    - detail: 详细信息 JSON 字符串 (跟原 SQLite 一致)
    """

    __tablename__ = "kg_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_kg_audit_ts", "ts"),)

    def __repr__(self) -> str:
        return f"<KgAudit id={self.id} action={self.action} result={self.result}>"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
uv run pytest tests/kg/test_audit_models.py -v
```

Expected: 8 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/kg/audit_models.py packages/service/tests/kg/test_audit_models.py
git commit -m "feat(kg): add KgAudit ORM model"
```

---

### Task 3: 创建 consolidated Alembic migration

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py`

- [ ] **Step 1: 删除 4 个旧 migration**

```bash
cd packages/service
git rm src/storage/migrations/versions/1f49cc6444e1_init.py \
       src/storage/migrations/versions/a3b8c1d2e4f5_add_sources_to_evaluation_samples.py \
       src/storage/migrations/versions/2a3b4c5d6e7f_add_accounts_and_invites.py \
       src/storage/migrations/versions/b7c4e2f1a9d3_add_approvals.py
```

- [ ] **Step 2: 写 consolidated migration**

Create `packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py`:

```python
"""consolidated pg init (2026-06-15)

把 4 个旧 migration (1f49 / a3b8 / 2a3b / b7c4) 合并成 1 个 fresh init.
down_revision = None (起点). 包含所有业务表 + ingest_tasks + kg_audit.

为啥不沿用 4 个旧 migration: SQLite migration 用 sa.JSON() 在 PG 上创建 JSON 列
(不是 JSONB), 且 SQLite batch_alter_table 在 PG 上是 noop. 一次性 fresh init
确保 schema 干净, 跑一次 alembic upgrade head 就到 head.

字段定义跟现有 ORM model 1:1 对齐, 这样 SQLAlchemy ORM 跑读写时不会类型冲突.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260615_000000"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """升级到 consolidated PG schema: 11 张业务表 + 索引."""
    # === 1. users ===
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_last_seen_at"), "users", ["last_seen_at"], unique=False)
    op.create_index(op.f("ix_users_public_token"), "users", ["public_token"], unique=True)
    op.create_index(op.f("ix_users_account_id"), "users", ["account_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_users_account_id_accounts"),
        "users", "accounts",
        ["account_id"], ["id"],
        ondelete="SET NULL",
    )

    # === 2. accounts ===
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("email LIKE '%_@_%._%'", name="ck_accounts_email_format"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_accounts_email"),
    )
    op.create_index(op.f("ix_accounts_email"), "accounts", ["email"], unique=True)
    op.create_index(op.f("ix_accounts_is_active"), "accounts", ["is_active"], unique=False)

    # === 3. invites ===
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("invited_by_account_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_invites_token"),
    )
    op.create_index(op.f("ix_invites_token"), "invites", ["token"], unique=True)
    op.create_index(op.f("ix_invites_email"), "invites", ["email"], unique=False)

    # === 4. password_resets ===
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_password_resets_token"),
    )
    op.create_index(op.f("ix_password_resets_token"), "password_resets", ["token"], unique=True)

    # === 5. conversations ===
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_updated_at"), "conversations", ["updated_at"], unique=False)
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"], unique=False)

    # === 6. messages ===
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conv_created", "messages", ["conversation_id", "created_at"], unique=False)
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)

    # === 7. evaluations ===
    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=200), nullable=False),
        sa.Column("dataset_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("successful", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("avg_metrics", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluations_created_at"), "evaluations", ["created_at"], unique=False)
    op.create_index(op.f("ix_evaluations_status"), "evaluations", ["status"], unique=False)
    op.create_index("ix_evaluations_user_created", "evaluations", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_evaluations_user_id"), "evaluations", ["user_id"], unique=False)

    # === 8. evaluation_samples (含 sources 列) ===
    op.create_table(
        "evaluation_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evaluation_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("ground_truth", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("contexts", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_samples_evaluation_id"), "evaluation_samples", ["evaluation_id"], unique=False)
    op.create_index("ix_samples_eval_index", "evaluation_samples", ["evaluation_id", "index"], unique=False)

    # === 9. approvals ===
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("apply_status", sa.String(length=20), nullable=False, server_default=sa.text("'none'")),
        sa.Column("submitter_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=40), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approvals_kind"), "approvals", ["kind"], unique=False)
    op.create_index(op.f("ix_approvals_review_status"), "approvals", ["review_status"], unique=False)
    op.create_index(op.f("ix_approvals_apply_status"), "approvals", ["apply_status"], unique=False)
    op.create_index(op.f("ix_approvals_submitter_id"), "approvals", ["submitter_id"], unique=False)
    op.create_index(op.f("ix_approvals_reviewer_id"), "approvals", ["reviewer_id"], unique=False)
    op.create_index(op.f("ix_approvals_created_at"), "approvals", ["created_at"], unique=False)
    op.create_index("idx_approvals_review_created", "approvals", ["review_status", "created_at"], unique=False)
    op.create_index("idx_approvals_apply_created", "approvals", ["apply_status", "created_at"], unique=False)
    op.create_index("idx_approvals_submitter_created", "approvals", ["submitter_id", "created_at"], unique=False)

    # === 10. ingest_tasks (新) ===
    op.create_table(
        "ingest_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("work_dir", sa.String(length=500), nullable=True),
        sa.Column("input_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("output_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_tasks_user_hash"), "ingest_tasks", ["user_hash"], unique=False)
    op.create_index(
        "ix_ingest_tasks_user_started",
        "ingest_tasks",
        ["user_hash", "started_at"],
        unique=False,
    )

    # === 11. kg_audit (新) ===
    op.create_table(
        "kg_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kg_audit_ts"), "kg_audit", ["ts"], unique=False)


def downgrade() -> None:
    """倒序删除所有表."""
    op.drop_table("kg_audit")
    op.drop_table("ingest_tasks")
    op.drop_table("approvals")
    op.drop_table("evaluation_samples")
    op.drop_table("evaluations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("password_resets")
    op.drop_table("invites")
    op.drop_table("accounts")
    op.drop_table("users")
```

- [ ] **Step 3: 跑 alembic upgrade 在 docker PG 上**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run alembic upgrade head
```

Expected: 跑到 `20260615_000000` (head). 无 error. 如果 FK 报错检查 `users.account_id` 的 FK 在 accounts 之后建.

- [ ] **Step 4: 验证 schema**

```bash
echo '\dt' | docker exec -i pgvector psql -U postgres -d rag
```

Expected: 11 张业务表 (不含 `alembic_version`).

- [ ] **Step 5: 验证 alembic version**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run alembic current
```

Expected: `20260615_000000 (head)`

- [ ] **Step 6: Commit**

```bash
cd ../..
git add packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py
git commit -m "feat(storage): consolidated PG init migration, drop 4 old SQLite migrations"
```

---

### Task 4: 在 env.py 注册新 model

**Files:**
- Modify: `packages/service/src/storage/migrations/env.py`

- [ ] **Step 1: 读当前 env.py 找 import 位置**

```bash
cd packages/service
grep -n "from src\." src/storage/migrations/env.py
```

确认现有 import 列表. 通常在文件末尾附近.

- [ ] **Step 2: 加 2 行强制注册**

Edit `packages/service/src/storage/migrations/env.py`, 在其他 `from src.<feature>.models import` 后面加:

```python
from src.ingest.models import IngestTask  # noqa: F401  # 注册到 Base.metadata
from src.kg.audit_models import KgAudit  # noqa: F401  # 注册到 Base.metadata
```

- [ ] **Step 3: 验证 alembic 仍能 upgrade head**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run alembic upgrade head
```

Expected: 已是 head, 无变化. 无 ImportError.

- [ ] **Step 4: Commit**

```bash
cd ../..
git add packages/service/src/storage/migrations/env.py
git commit -m "chore(migration): register IngestTask + KgAudit in env.py"
```

---

### 阶段 1 验收

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ingest/test_models.py tests/kg/test_audit_models.py -v
```

Expected: 17 个 test 全 PASS. 旧 SQLite 测试还能跑 (因为 store.py / audit.py 没改).

---

## 阶段 2: 重写 store 层 (Batch 2)

### Task 5: 重写 src/storage/engine.py (删 SQLite 特化)

**Files:**
- Modify: `packages/service/src/storage/engine.py`
- Modify: `packages/service/tests/storage/test_engine.py`

- [ ] **Step 1: 写失败测试**

Read `packages/service/tests/storage/test_engine.py` 全文 (了解现有测试结构).

然后重写为:

```python
"""engine.py 单元测试 (PG only, 2026-06-15)

旧测试用 SQLite URL. 删 SQLite 特化后, 测试改用 RAG_DB_URL env 或 PG 默认值.
"""

from __future__ import annotations

import os


class TestDefaultDbUrl:
    """默认 URL 是 PG (不是 SQLite)"""

    def test_default_url_is_postgresql(self, monkeypatch):
        for k in ["RAG_DB_URL", "RAG_DB_URL_TEST"]:
            monkeypatch.delenv(k, raising=False)
        from src.storage.engine import DEFAULT_DB_URL

        assert DEFAULT_DB_URL.startswith("postgresql"), (
            f"默认 URL 应是 PG, 实际: {DEFAULT_DB_URL}"
        )


class TestResolveDbUrl:
    """_resolve_db_url 读 env"""

    def test_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("RAG_DB_URL", "postgresql+psycopg://custom:x@host:1234/db")
        from src.storage.engine import _resolve_db_url

        assert _resolve_db_url() == "postgresql+psycopg://custom:x@host:1234/db"

    def test_no_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("RAG_DB_URL", raising=False)
        from src.storage.engine import _resolve_db_url

        assert _resolve_db_url() == _resolve_db_url.__globals__["DEFAULT_DB_URL"]


class TestMakeEngine:
    """_make_engine 不再有 SQLite 特化"""

    def test_pg_engine_has_no_check_same_thread(self):
        from sqlalchemy.pool import QueuePool

        from src.storage.engine import _make_engine

        eng = _make_engine("postgresql+psycopg://u:p@localhost:5432/rag")
        # 走 QueuePool (默认) 不用 NullPool
        assert isinstance(eng.pool, QueuePool)
        # pool_pre_ping 必须在
        assert eng.pool._pre_ping is True
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
uv run pytest tests/storage/test_engine.py -v
```

Expected: 至少 `test_default_url_is_postgresql` FAIL (DEFAULT_DB_URL 还是 SQLite).

- [ ] **Step 3: 重写 engine.py**

Replace `packages/service/src/storage/engine.py` 整文件:

```python
"""SQLAlchemy Engine 工厂 (PG only, 2026-06-15)

- _resolve_db_url(): 读 RAG_DB_URL env, 默认连 docker PG
- get_engine(): 惰性单例, pool_pre_ping=True, pool_size=10
- init_db(): dev/test 跑 create_all, 受 RAG_AUTO_CREATE_SCHEMA 开关

旧 SQLite 适配 (journal_mode PRAGMA / check_same_thread) 已删除 — 跟 spec 一致, 无 shim.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .base import Base

# 默认连 docker-compose 起的 PG (密码跟 docker/.env POSTGRES_PASSWORD 一致)
# 生产必须改 env, 别用默认 password=postgres
DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/rag"
_engine: Engine | None = None


def _resolve_db_url() -> str:
    """读 RAG_DB_URL env, 默认连 docker PG."""
    return os.getenv("RAG_DB_URL", DEFAULT_DB_URL)


def _make_engine(url: str) -> Engine:
    """PG-only: 统一 pool 配置.

    pool_pre_ping=True: 防连接过期 (PG idle timeout / 重启)
    pool_size=10: 默认 5 + max_overflow=10, 适合 FastAPI 多 worker
    """
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


def get_engine() -> Engine:
    """惰性单例 Engine."""
    global _engine
    if _engine is None:
        url = _resolve_db_url()
        _engine = _make_engine(url)
        print(f"[storage] engine init: {url}")
    return _engine


def init_db() -> None:
    """建表 (仅 dev/test 用, 生产走 Alembic).

    受 RAG_AUTO_CREATE_SCHEMA=1 开关, 默认关闭 (保护生产).
    """
    if os.getenv("RAG_AUTO_CREATE_SCHEMA") != "1":
        print("[storage] init_db skipped (set RAG_AUTO_CREATE_SCHEMA=1 to enable)")
        return
    print("[storage] WARN: 自动建表, 仅限 dev/test")
    Base.metadata.create_all(get_engine())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
uv run pytest tests/storage/test_engine.py -v
```

Expected: 5 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/storage/engine.py packages/service/tests/storage/test_engine.py
git commit -m "refactor(storage): drop SQLite specialization, PG-only engine"
```

---

### Task 6: 重写 src/ingest/store.py

**Files:**
- Modify: `packages/service/src/ingest/store.py`
- Modify: `packages/service/tests/ingest/test_store.py`

- [ ] **Step 1: 写失败测试 (PG 版)**

Replace `packages/service/tests/ingest/test_store.py` 整文件:

```python
"""ingest store 单元测试 (PG only, 2026-06-15)

测试走真实 PG. 跑前必须 docker compose up -d postgres 且 export RAG_DB_URL.
每个 test 前 reset_for_test() 清表.
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest


@pytest.fixture(autouse=True)
def _clean_table():
    """每个 test 前清 ingest_tasks 表."""
    from src.ingest import store
    store.reset_for_test()
    yield


class TestSaveLoad:
    def test_save_then_load_roundtrip(self):
        from src.ingest import store
        from src.ingest.models import IngestTask

        d = {
            "id": "task-001",
            "user_hash": "abc123",
            "state": "pending",
            "total_files": 3,
            "processed": 0,
            "failed": 0,
            "started_at": datetime(2026, 6, 15, 10, 0, 0).isoformat(),
            "finished_at": None,
            "error": None,
            "work_dir": "/tmp/w",
            "input_files": [{"name": "a.pdf"}],
            "output_files": [],
        }
        store.save_task_dict(d)
        loaded = store.load_task_dict("task-001")
        assert loaded is not None
        assert loaded["id"] == "task-001"
        assert loaded["state"] == "pending"
        assert loaded["total_files"] == 3
        assert loaded["input_files"] == [{"name": "a.pdf"}]
        assert loaded["output_files"] == []

    def test_save_is_upsert(self):
        """save_task_dict 同 id 二次调用 = UPDATE 不是 INSERT."""
        from src.ingest import store

        d1 = {
            "id": "task-002",
            "user_hash": "u",
            "state": "pending",
            "total_files": 1,
            "processed": 0,
            "failed": 0,
            "started_at": datetime(2026, 6, 15, 10, 0, 0).isoformat(),
        }
        store.save_task_dict(d1)
        d2 = {**d1, "state": "completed", "processed": 1, "finished_at": datetime(2026, 6, 15, 10, 5, 0).isoformat()}
        store.save_task_dict(d2)
        loaded = store.load_task_dict("task-002")
        assert loaded["state"] == "completed"
        assert loaded["processed"] == 1

    def test_load_nonexistent_returns_none(self):
        from src.ingest import store

        assert store.load_task_dict("nonexistent-id") is None


class TestList:
    def test_list_user_tasks_ordered_desc(self):
        from src.ingest import store

        for i, ts in enumerate([
            datetime(2026, 6, 15, 9, 0, 0),
            datetime(2026, 6, 15, 10, 0, 0),
            datetime(2026, 6, 15, 11, 0, 0),
        ]):
            store.save_task_dict({
                "id": f"task-{i}",
                "user_hash": "u1",
                "state": "pending",
                "total_files": 1,
                "processed": 0,
                "failed": 0,
                "started_at": ts.isoformat(),
            })
        tasks = store.list_user_task_dicts("u1")
        assert len(tasks) == 3
        # 新的在前
        assert [t["id"] for t in tasks] == ["task-2", "task-1", "task-0"]

    def test_list_filters_by_user_hash(self):
        from src.ingest import store

        for uid in ["u1", "u1", "u2"]:
            store.save_task_dict({
                "id": f"task-{uid}",
                "user_hash": uid,
                "state": "pending",
                "total_files": 1,
                "processed": 0,
                "failed": 0,
                "started_at": datetime(2026, 6, 15, 10, 0, 0).isoformat(),
            })
        u1_tasks = store.list_user_task_dicts("u1")
        assert len(u1_tasks) == 2
        assert all(t["user_hash"] == "u1" for t in u1_tasks)


class TestEmpty:
    def test_save_empty_dict_list(self):
        """无 input_files / output_files 时 JSON 字段默认 []."""
        from src.ingest import store

        store.save_task_dict({
            "id": "task-empty",
            "user_hash": "u",
            "state": "pending",
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "started_at": datetime(2026, 6, 15, 10, 0, 0).isoformat(),
        })
        loaded = store.load_task_dict("task-empty")
        assert loaded["input_files"] == []
        assert loaded["output_files"] == []
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ingest/test_store.py -v
```

Expected: 至少 reset_for_test / save_task_dict 抛错 (旧 store 用 raw sqlite3, 表名 `tasks`, 新 ORM 用 `ingest_tasks`).

- [ ] **Step 3: 重写 ingest/store.py**

Replace `packages/service/src/ingest/store.py` 整文件:

```python
"""ingest task 元数据存储 (ORM 重写, 2026-06-15).

替原 sqlite3 raw 实现. 走 SQLAlchemy ORM (src.ingest.models.IngestTask) +
session_scope() 事务. 现有 save_task_dict / load_task_dict / list_user_task_dicts /
reset_for_test 接口签名 1:1 保留, 调用方 (src/ingest/api.py) 0 改动.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from ..storage import session_scope
from .models import IngestTask


def _to_dt(value: str | datetime | None) -> datetime | None:
    """ISO 字符串 / datetime / None → datetime (or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _to_dict(task: IngestTask) -> dict:
    """ORM 对象 → IngestTask 构造 dict (跟原 sqlite3 _row_to_dict 字段 1:1)."""
    return {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "total_files": task.total_files,
        "processed": task.processed,
        "failed": task.failed,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "work_dir": task.work_dir,
        "input_files": json.loads(task.input_files_json or "[]"),
        "output_files": json.loads(task.output_files_json or "[]"),
    }


def reset_for_test() -> None:
    """测试用: 清空 ingest_tasks 表."""
    from sqlalchemy import text

    with session_scope() as s:
        s.execute(text("DELETE FROM ingest_tasks"))


def save_task_dict(d: dict) -> None:
    """d 必须含 IngestTask.to_dict() 的所有字段. INSERT OR REPLACE (upsert)."""
    task = IngestTask(
        id=d["id"],
        user_hash=d["user_hash"],
        state=d["state"],
        total_files=d["total_files"],
        processed=d.get("processed", 0),
        failed=d.get("failed", 0),
        started_at=_to_dt(d["started_at"]),
        finished_at=_to_dt(d.get("finished_at")),
        error=d.get("error"),
        work_dir=d.get("work_dir"),
        input_files_json=json.dumps(d.get("input_files", []), ensure_ascii=False),
        output_files_json=json.dumps(d.get("output_files", []), ensure_ascii=False),
    )
    with session_scope() as s:
        s.merge(task)


def load_task_dict(task_id: str) -> dict | None:
    """查单条 task, 返 IngestTask 构造 dict (None = 不存在)."""
    with session_scope() as s:
        task = s.get(IngestTask, task_id)
        return _to_dict(task) if task else None


def list_user_task_dicts(user_hash: str) -> list[dict]:
    """列某用户所有 task, 按 started_at DESC (新的在前)."""
    with session_scope() as s:
        rows = s.execute(
            select(IngestTask)
            .where(IngestTask.user_hash == user_hash)
            .order_by(IngestTask.started_at.desc())
        ).scalars().all()
        return [_to_dict(t) for t in rows]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ingest/test_store.py -v
```

Expected: 7 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/ingest/store.py packages/service/tests/ingest/test_store.py
git commit -m "refactor(ingest): rewrite store.py with ORM, drop raw sqlite3"
```

---

### Task 7: 重写 src/kg/audit.py

**Files:**
- Modify: `packages/service/src/kg/audit.py`
- Modify: `packages/service/tests/kg/test_audit.py`

- [ ] **Step 1: 写失败测试**

Replace `packages/service/tests/kg/test_audit.py` 整文件:

```python
"""AuditStore 单元测试 (PG only, 2026-06-15)

走真实 PG. 跑前必须 docker compose up -d postgres 且 export RAG_DB_URL.
"""

from __future__ import annotations

from src.kg.audit import AuditStore


class TestRecord:
    def test_record_inserts_row(self):
        from src.kg.audit_models import KgAudit
        from src.storage import session_scope

        # 先清表
        with session_scope() as s:
            s.query(KgAudit).delete()

        store = AuditStore()
        store.record(
            action="create_triple",
            actor="user-1",
            target="triple-42",
            result="ok",
            detail={"nodes": 3, "edges": 2},
        )

        with session_scope() as s:
            row = s.query(KgAudit).filter_by(action="create_triple").one()
            assert row.actor == "user-1"
            assert row.target == "triple-42"
            assert row.result == "ok"
            import json
            assert json.loads(row.detail) == {"nodes": 3, "edges": 2}


class TestListRecent:
    def test_list_recent_ordered_desc(self):
        import json
        import time

        from src.kg.audit import AuditStore
        from src.kg.audit_models import KgAudit
        from src.storage import session_scope

        with session_scope() as s:
            s.query(KgAudit).delete()

        store = AuditStore()
        for i in range(3):
            store.record(
                action=f"action_{i}",
                actor=None,
                target=None,
                result="ok",
                detail={"i": i},
            )
            time.sleep(0.01)  # 保证 ts 不同

        rows = store.list_recent(limit=10)
        assert len(rows) == 3
        # ts DESC: i=2 在前
        assert rows[0]["action"] == "action_2"
        assert rows[1]["action"] == "action_1"
        assert rows[2]["action"] == "action_0"
        # detail 是 dict (json.loads 后)
        assert rows[0]["detail"] == {"i": 2}

    def test_list_recent_limit(self):
        from src.kg.audit import AuditStore
        from src.kg.audit_models import KgAudit
        from src.storage import session_scope

        with session_scope() as s:
            s.query(KgAudit).delete()

        store = AuditStore()
        for i in range(5):
            store.record(action=f"a{i}", actor=None, target=None, result="ok", detail={})

        rows = store.list_recent(limit=2)
        assert len(rows) == 2


class TestConstructor:
    def test_db_path_arg_ignored(self):
        """向后兼容: AuditStore(db_path) 旧调用不报错 (参数忽略)."""
        store = AuditStore("/some/old/path.db")
        assert store is not None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/kg/test_audit.py -v
```

Expected: `test_record_inserts_row` FAIL (旧 AuditStore 用 sqlite3 写 `data/kg_audit.db`, 没 PG).

- [ ] **Step 3: 重写 audit.py**

Replace `packages/service/src/kg/audit.py` 整文件:

```python
"""知识图谱审计日志 (ORM 重写, 2026-06-15).

替原 sqlite3 raw 实现. 走 SQLAlchemy ORM (src.kg.audit_models.KgAudit) +
session_scope() 事务. 现有 AuditStore.record / list_recent 接口签名 1:1 保留.

构造函数保留 db_path 参数 (向后兼容 src/kg/router.py:25), 但忽略.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import select

from ..storage import session_scope
from .audit_models import KgAudit


class AuditStore:
    """薄壳: 保持旧 record/list_recent 接口, 内部走 session_scope."""

    def __init__(self, db_path: Path | str | None = None):  # noqa: ARG001  # 保留参数兼容调用方
        """db_path 参数已废弃 (旧 SQLite 路径), 保留只为向后兼容.

        实际数据走 PG (RAG_DB_URL), 跟 src.kg.audit_models.KgAudit 一致.
        """
        pass

    def record(
        self,
        *,
        action: str,
        actor: str | None,
        target: str | None,
        result: str,
        detail: dict,
    ) -> None:
        """写一条审计日志."""
        with session_scope() as s:
            s.add(KgAudit(
                ts=time.time(),
                action=action,
                actor=actor,
                target=target,
                result=result,
                detail=json.dumps(detail, ensure_ascii=False),
            ))

    def list_recent(self, limit: int = 50) -> list[dict]:
        """查最近 N 条, 按 ts DESC.

        返回结构跟原 sqlite3 list_recent 一致:
          [{"id": int, "ts": float, "action": str, "actor": str|None,
            "target": str|None, "result": str, "detail": dict}, ...]
        """
        with session_scope() as s:
            rows = s.execute(
                select(KgAudit).order_by(KgAudit.ts.desc()).limit(limit)
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "ts": r.ts,
                    "action": r.action,
                    "actor": r.actor,
                    "target": r.target,
                    "result": r.result,
                    "detail": json.loads(r.detail),
                }
                for r in rows
            ]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/kg/test_audit.py -v
```

Expected: 4 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/kg/audit.py packages/service/tests/kg/test_audit.py
git commit -m "refactor(kg): rewrite AuditStore with ORM, drop raw sqlite3"
```

---

### Task 8: 重写 src/approvals/router.py (删 sqlite URL 转换)

**Files:**
- Modify: `packages/service/src/approvals/router.py`

- [ ] **Step 1: 找 sqlite URL 转换代码**

```bash
cd packages/service
grep -n "sqlite" src/approvals/router.py
```

Expected 看到:
```python
if url.startswith("sqlite://") and not url.startswith("sqlite+"):
    return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
```

- [ ] **Step 2: 读上下文确认**

Read `packages/service/src/approvals/router.py` 整文件 (大约 100 行).

- [ ] **Step 3: 删 sqlite URL 转换**

Edit 文件, 删 `if url.startswith("sqlite://") and not url.startswith("sqlite+"):` 整块 (包含紧跟的 `return` 行). 如果有 helper 函数定义 sqlite 转换逻辑, 一并删.

如果函数体只剩 1 行 `return url`, 直接简化成:

```python
def _resolve_db_url_for_async(url: str) -> str:
    """PG-only: 直接返, 不再 sqlite URL 转换."""
    return url
```

(保留函数名以兼容 import 调用方.)

- [ ] **Step 4: 跑 approvals 测试确认通过**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/approvals/ -v
```

Expected: 所有 approvals 测试通过 (无 sqlite 相关断言应报).

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/src/approvals/router.py
git commit -m "refactor(approvals): drop sqlite URL conversion shim"
```

---

### Task 9: 更新 tests/storage/conftest.py

**Files:**
- Modify: `packages/service/tests/storage/conftest.py`

- [ ] **Step 1: 读现有 conftest**

Read `packages/service/tests/storage/conftest.py` 全文.

- [ ] **Step 2: 删 SQLite fixture, 加 PG fixture**

Replace 整文件 (或按需修改):

```python
"""storage 测试 fixture (PG only, 2026-06-15)

提供 pg_engine + 每次测试清表的 autouse fixture.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def pg_engine():
    """整个测试 session 共用一个 PG engine.

    跑前必须 export RAG_DB_URL=postgresql+psycopg://...
    跑前必须 alembic upgrade head 已跑过.
    """
    from sqlalchemy import create_engine

    url = os.environ.get("RAG_DB_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("需要 RAG_DB_URL 指向 PG 才能跑")
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _truncate_tables(pg_engine):
    """每个 test 前清所有业务表 (CASCADE 解决 FK)."""
    from sqlalchemy import text

    tables = [
        "messages", "conversations",
        "evaluation_samples", "evaluations",
        "approvals",
        "password_resets", "invites", "accounts",
        "users",
        "ingest_tasks", "kg_audit",
    ]
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    yield
```

- [ ] **Step 3: 跑 storage 测试确认 fixture 工作**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/storage/ -v
```

Expected: 现有 test_session.py / test_base.py 测试通过 (test_engine.py 已重写).

- [ ] **Step 4: Commit**

```bash
cd ../..
git add packages/service/tests/storage/conftest.py
git commit -m "test(storage): PG fixture with truncate, drop SQLite setup"
```

---

### Task 10: 重写 tests/storage/test_migrations.py

**Files:**
- Modify: `packages/service/tests/storage/test_migrations.py`

- [ ] **Step 1: 读现有测试**

Read `packages/service/tests/storage/test_migrations.py` 全文.

- [ ] **Step 2: 改写为 PG 验证**

重写测试, 验证:

```python
"""Alembic migration 在 PG 上跑通 (2026-06-15)

要求:
  - RAG_DB_URL 指向 PG
  - alembic_version 表存在
  - alembic upgrade head 之后, version_num == '20260615_000000'
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def pg_url():
    url = os.environ.get("RAG_DB_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("需要 RAG_DB_URL 指向 PG")
    return url


def test_alembic_version_table_exists(pg_url):
    from sqlalchemy import create_engine, text

    eng = create_engine(pg_url)
    with eng.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
        )).scalar()
    assert result == "alembic_version", "alembic_version 表不存在"


def test_alembic_current_is_head(pg_url):
    """跑完 alembic upgrade head 后, version_num == '20260615_000000'"""
    import subprocess

    env = {**os.environ, "RAG_DB_URL": pg_url}
    # 用 --no-sync 避免 uv lock 解析
    subprocess.run(
        ["uv", "run", "--no-sync", "alembic", "current"],
        cwd="packages/service",
        env=env,
        check=True,
        capture_output=True,
    )


def test_all_11_business_tables_exist(pg_url):
    from sqlalchemy import create_engine, text

    eng = create_engine(pg_url)
    expected = {
        "users", "accounts", "invites", "password_resets",
        "conversations", "messages",
        "evaluations", "evaluation_samples",
        "approvals",
        "ingest_tasks", "kg_audit",
    }
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )).scalars().all()
    actual = set(rows) - {"alembic_version"}
    missing = expected - actual
    assert not missing, f"缺表: {missing}"
```

- [ ] **Step 3: 跑测试确认通过**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/storage/test_migrations.py -v
```

Expected: 3 个 test 全 PASS.

- [ ] **Step 4: Commit**

```bash
cd ../..
git add packages/service/tests/storage/test_migrations.py
git commit -m "test(storage): verify consolidated migration on PG"
```

---

### Task 11: 跑全套测试

- [ ] **Step 1: 跑所有非 slow 测试**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow" -v
```

Expected: 所有测试通过 (除已知 slow marker 的).

- [ ] **Step 2: 修任何失败**

如果失败, 停下来 debug. 不要 `--no-verify` 跳过.

---

### 阶段 2 验收

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow" 2>&1 | tail -20
```

Expected: 全 PASS. SQLite .db 文件**还保留**(阶段 3 才搬运 + 删).

---

## 阶段 3: 数据搬运脚本 (Batch 3)

### Task 12: 创建 scripts/migrate_sqlite_to_pg.py

**Files:**
- Create: `packages/service/scripts/migrate_sqlite_to_pg.py`
- Test: `packages/service/tests/scripts/test_migrate_sqlite_to_pg.py`

- [ ] **Step 1: 写失败测试**

Create `packages/service/tests/scripts/test_migrate_sqlite_to_pg.py`:

```python
"""数据搬运脚本单元测试 (PG only, 2026-06-15)

策略:
  - 在 temp dir 建 3 个 SQLite 文件, 各塞 2-3 行 fixture 数据
  - 跑 scripts.migrate_sqlite_to_pg.run(sq_dir=tmp, pg_url=RAG_DB_URL)
  - 校验 PG 表行数 + 抽 1 行字段一致
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def sqlite_dir(tmp_path: Path) -> Path:
    """建 3 个 SQLite 文件 + fixture 数据."""
    # app.db: users (1 行) + conversations (1 行) + messages (1 行)
    app = tmp_path / "app.db"
    conn = sqlite3.connect(str(app))
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_token TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            account_id INTEGER
        );
        INSERT INTO users (public_token, display_name, created_at, last_seen_at)
        VALUES ('token-abc-123', 'Alice', '2026-06-01 10:00:00', '2026-06-15 10:00:00');

        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO conversations VALUES ('conv-1', 1, 'Test chat', 1, '2026-06-15 10:00:00', '2026-06-15 10:01:00');

        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            meta TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO messages (conversation_id, role, content, created_at) VALUES ('conv-1', 'user', 'Hi', '2026-06-15 10:00:00');
    """)
    conn.commit()
    conn.close()

    # ingest_tasks.db
    ing = tmp_path / "ingest_tasks.db"
    conn = sqlite3.connect(str(ing))
    conn.executescript("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            user_hash TEXT NOT NULL,
            state TEXT NOT NULL,
            total_files INTEGER NOT NULL,
            processed INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            error TEXT,
            work_dir TEXT,
            input_files_json TEXT NOT NULL DEFAULT '[]',
            output_files_json TEXT NOT NULL DEFAULT '[]'
        );
        INSERT INTO tasks (id, user_hash, state, total_files, processed, failed, started_at, input_files_json, output_files_json)
        VALUES ('task-1', 'hash-1', 'completed', 2, 2, 0, '2026-06-15 09:00:00', '[]', '[]');
    """)
    conn.commit()
    conn.close()

    # kg_audit.db
    aud = tmp_path / "kg_audit.db"
    conn = sqlite3.connect(str(aud))
    conn.executescript("""
        CREATE TABLE audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            action TEXT NOT NULL,
            actor TEXT,
            target TEXT,
            result TEXT,
            detail TEXT
        );
        INSERT INTO audit (ts, action, actor, target, result, detail) VALUES
            (1718444400.0, 'create_triple', 'user-1', 'triple-1', 'ok', '{"nodes": 3}');
    """)
    conn.commit()
    conn.close()

    return tmp_path


@pytest.fixture(autouse=True)
def _truncate_pg():
    from sqlalchemy import create_engine, text

    from src.storage import get_engine

    eng = get_engine()
    tables = [
        "messages", "conversations",
        "evaluation_samples", "evaluations",
        "approvals",
        "password_resets", "invites", "accounts",
        "users",
        "ingest_tasks", "kg_audit",
    ]
    with eng.begin() as conn:
        conn.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))


def test_run_copies_users(sqlite_dir):
    from scripts.migrate_sqlite_to_pg import run

    run(sqlite_dir=str(sqlite_dir), delete_sqlite=False)

    from sqlalchemy import text
    from src.storage import get_engine

    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT id, public_token, display_name FROM users")).all()
    assert len(rows) == 1
    assert rows[0].public_token == "token-abc-123"
    assert rows[0].display_name == "Alice"


def test_run_copies_conversations_and_messages(sqlite_dir):
    from scripts.migrate_sqlite_to_pg import run

    run(sqlite_dir=str(sqlite_dir), delete_sqlite=False)

    from sqlalchemy import text
    from src.storage import get_engine

    with get_engine().connect() as conn:
        convos = conn.execute(text("SELECT id, title FROM conversations")).all()
        msgs = conn.execute(text("SELECT conversation_id, content FROM messages")).all()
    assert len(convos) == 1
    assert convos[0].title == "Test chat"
    assert len(msgs) == 1
    assert msgs[0].content == "Hi"


def test_run_copies_ingest_tasks(sqlite_dir):
    from scripts.migrate_sqlite_to_pg import run

    run(sqlite_dir=str(sqlite_dir), delete_sqlite=False)

    from sqlalchemy import text
    from src.storage import get_engine

    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT id, state FROM ingest_tasks")).all()
    assert len(rows) == 1
    assert rows[0].id == "task-1"
    assert rows[0].state == "completed"


def test_run_copies_kg_audit(sqlite_dir):
    from scripts.migrate_sqlite_to_pg import run

    run(sqlite_dir=str(sqlite_dir), delete_sqlite=False)

    from sqlalchemy import text
    from src.storage import get_engine

    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT action, result FROM kg_audit")).all()
    assert len(rows) == 1
    assert rows[0].action == "create_triple"


def test_run_advances_pg_sequences(sqlite_dir):
    """跑完后, users.id SEQUENCE 应 >= 1 (后续 INSERT 不会撞 PK)."""
    from scripts.migrate_sqlite_to_pg import run

    run(sqlite_dir=str(sqlite_dir), delete_sqlite=False)

    from sqlalchemy import text
    from src.storage import get_engine

    with get_engine().connect() as conn:
        seq_val = conn.execute(text(
            "SELECT last_value FROM users_id_seq"
        )).scalar()
    assert seq_val >= 1, f"users SEQUENCE 未推进: {seq_val}"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/scripts/test_migrate_sqlite_to_pg.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.migrate_sqlite_to_pg'`

- [ ] **Step 3: 实现搬运脚本**

Create `packages/service/scripts/migrate_sqlite_to_pg.py`:

```python
"""一次性 SQLite → PG 搬运脚本 (2026-06-15).

从 3 个本地 SQLite 文件搬数据到 docker PG:
  - data/app.db          (业务表: users/accounts/.../approvals)
  - data/ingest_tasks.db (ingest task 元数据)
  - data/kg_audit.db     (知识图谱审计日志)

跑前自动备份到 <sqlite_dir>/.archive/<utc_ts>/. 失败自动 rollback + 不删 SQLite.
跑成功且 delete_sqlite=True 时删 SQLite 文件.

用法:
  uv run python scripts/migrate_sqlite_to_pg.py                # 搬 + 备份 + 删 SQLite
  uv run python scripts/migrate_sqlite_to_pg.py --dry-run      # 只打印统计, 不写 PG
  uv run python scripts/migrate_sqlite_to_pg.py --keep-sqlite  # 搬 + 备份, 不删 SQLite

跑完可删 (一次性脚本).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

# === 配置 ===

# 默认 SQLite 源目录 (跟 _DEFAULT_DB_PATH 在 src/storage/engine.py 一致)
DEFAULT_SQLITE_DIR = Path(__file__).resolve().parents[2] / "data"

# 业务表搬运顺序 (FK 依赖序: 父表先)
TABLE_ORDER = [
    # 业务表
    ("app.db", "users", "_migrate_users"),
    ("app.db", "accounts", "_migrate_accounts"),
    ("app.db", "invites", "_migrate_invites"),
    ("app.db", "password_resets", "_migrate_password_resets"),
    ("app.db", "conversations", "_migrate_conversations"),
    ("app.db", "messages", "_migrate_messages"),
    ("app.db", "evaluations", "_migrate_evaluations"),
    ("app.db", "evaluation_samples", "_migrate_evaluation_samples"),
    ("app.db", "approvals", "_migrate_approvals"),
    # 额外 SQLite 表
    ("ingest_tasks.db", "tasks", "_migrate_ingest_tasks"),
    ("kg_audit.db", "audit", "_migrate_kg_audit"),
]


# === SQLite → PG 字段映射 ===

# 注: 这里不靠 ORM, 直接用 SQL 拷, 因为 SQLite / PG 列名一致 + 类型由 SQLAlchemy coerce.
# 每个 _migrate_xxx 返回 (table, row_count)


def _parse_dt(value: str | None) -> str | None:
    """SQLite TEXT datetime → ISO 字符串 (PG 接受 ISO datetime)."""
    if value is None or value == "":
        return None
    # SQLite 存 'YYYY-MM-DD HH:MM:SS', 直接返 (PG TIMESTAMP 也吃这种格式)
    return value


def _rows(sqlite_path: Path, table: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(f"SELECT * FROM {table}"))
    finally:
        conn.close()


def _migrate_users(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "users")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO users (id, public_token, display_name, created_at, last_seen_at, account_id)
                VALUES (:id, :token, :name, :created, :last_seen, :account_id)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "token": r["public_token"], "name": r["display_name"],
                "created": _parse_dt(r["created_at"]), "last_seen": _parse_dt(r["last_seen_at"]),
                "account_id": r["account_id"],
            })
    return len(rows)


def _migrate_accounts(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "accounts")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO accounts (id, email, password_hash, display_name, is_admin, is_active, created_at, last_login_at)
                VALUES (:id, :email, :pwd, :name, :is_admin, :is_active, :created, :last_login)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "email": r["email"], "pwd": r["password_hash"],
                "name": r["display_name"],
                "is_admin": bool(r["is_admin"]), "is_active": bool(r["is_active"]),
                "created": _parse_dt(r["created_at"]),
                "last_login": _parse_dt(r["last_login_at"]),
            })
    return len(rows)


def _migrate_invites(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "invites")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO invites (id, token, email, invited_by_account_id, expires_at, redeemed_at, account_id, created_at)
                VALUES (:id, :token, :email, :by, :expires, :redeemed, :account_id, :created)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "token": r["token"], "email": r["email"],
                "by": r["invited_by_account_id"],
                "expires": _parse_dt(r["expires_at"]),
                "redeemed": _parse_dt(r["redeemed_at"]),
                "account_id": r["account_id"],
                "created": _parse_dt(r["created_at"]),
            })
    return len(rows)


def _migrate_password_resets(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "password_resets")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO password_resets (id, account_id, token, expires_at, used_at, created_at)
                VALUES (:id, :account_id, :token, :expires, :used, :created)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "account_id": r["account_id"], "token": r["token"],
                "expires": _parse_dt(r["expires_at"]),
                "used": _parse_dt(r["used_at"]),
                "created": _parse_dt(r["created_at"]),
            })
    return len(rows)


def _migrate_conversations(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "conversations")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO conversations (id, user_id, title, message_count, created_at, updated_at)
                VALUES (:id, :user_id, :title, :msg_count, :created, :updated)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "user_id": r["user_id"], "title": r["title"],
                "msg_count": r["message_count"],
                "created": _parse_dt(r["created_at"]),
                "updated": _parse_dt(r["updated_at"]),
            })
    return len(rows)


def _migrate_messages(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "messages")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO messages (id, conversation_id, role, content, meta, created_at)
                VALUES (:id, :conv_id, :role, :content, :meta, :created)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "conv_id": r["conversation_id"],
                "role": r["role"], "content": r["content"],
                "meta": r["meta"],  # SQLite TEXT → PG JSON (auto-coerce)
                "created": _parse_dt(r["created_at"]),
            })
    return len(rows)


def _migrate_evaluations(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "evaluations")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO evaluations (id, user_id, dataset_name, dataset_path, status, total_samples,
                                         successful, failed, concurrency, avg_metrics, duration_seconds,
                                         error_message, created_at, finished_at)
                VALUES (:id, :user_id, :ds_name, :ds_path, :status, :total, :ok, :failed, :conc,
                        :avg, :dur, :err, :created, :finished)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "user_id": r["user_id"],
                "ds_name": r["dataset_name"], "ds_path": r["dataset_path"],
                "status": r["status"], "total": r["total_samples"],
                "ok": r["successful"], "failed": r["failed"], "conc": r["concurrency"],
                "avg": r["avg_metrics"], "dur": r["duration_seconds"],
                "err": r["error_message"],
                "created": _parse_dt(r["created_at"]),
                "finished": _parse_dt(r["finished_at"]),
            })
    return len(rows)


def _migrate_evaluation_samples(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "evaluation_samples")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO evaluation_samples (id, evaluation_id, "index", question, ground_truth,
                                                answer, contexts, metrics, sources, error, duration_ms)
                VALUES (:id, :eval_id, :idx, :q, :gt, :ans, :ctx, :metrics, :sources, :err, :dur)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "eval_id": r["evaluation_id"],
                "idx": r["index"],
                "q": r["question"], "gt": r["ground_truth"], "ans": r["answer"],
                "ctx": r["contexts"], "metrics": r["metrics"], "sources": r["sources"],
                "err": r["error"], "dur": r["duration_ms"],
            })
    return len(rows)


def _migrate_approvals(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "approvals")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO approvals (id, kind, payload, review_status, apply_status, submitter_id,
                                       reviewer_id, rejection_reason, rejection_note, error_msg,
                                       created_at, reviewed_at, applied_at)
                VALUES (:id, :kind, :payload, :review, :apply, :submitter, :reviewer,
                        :reason, :note, :err, :created, :reviewed, :applied)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "kind": r["kind"], "payload": r["payload"],
                "review": r["review_status"], "apply": r["apply_status"],
                "submitter": r["submitter_id"], "reviewer": r["reviewer_id"],
                "reason": r["rejection_reason"], "note": r["rejection_note"],
                "err": r["error_msg"],
                "created": _parse_dt(r["created_at"]),
                "reviewed": _parse_dt(r["reviewed_at"]),
                "applied": _parse_dt(r["applied_at"]),
            })
    return len(rows)


def _migrate_ingest_tasks(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "tasks")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO ingest_tasks (id, user_hash, state, total_files, processed, failed,
                                          started_at, finished_at, error, work_dir,
                                          input_files_json, output_files_json)
                VALUES (:id, :user, :state, :total, :proc, :failed, :started, :finished,
                        :err, :work_dir, :in_json, :out_json)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "user": r["user_hash"], "state": r["state"],
                "total": r["total_files"], "proc": r["processed"], "failed": r["failed"],
                "started": _parse_dt(r["started_at"]),
                "finished": _parse_dt(r["finished_at"]),
                "err": r["error"], "work_dir": r["work_dir"],
                "in_json": r["input_files_json"], "out_json": r["output_files_json"],
            })
    return len(rows)


def _migrate_kg_audit(pg_engine, sqlite_path: Path) -> int:
    rows = _rows(sqlite_path, "audit")
    with pg_engine.begin() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO kg_audit (id, ts, action, actor, target, result, detail)
                VALUES (:id, :ts, :action, :actor, :target, :result, :detail)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": r["id"], "ts": r["ts"], "action": r["action"],
                "actor": r["actor"], "target": r["target"],
                "result": r["result"], "detail": r["detail"],
            })
    return len(rows)


# === SEQUENCE 推进 ===

# 每张表有 autoincrement PK → PG SEQUENCE 名为 <table>_id_seq
SEQUENCE_TABLES = [
    "users", "accounts", "invites", "password_resets",
    "messages", "evaluations", "evaluation_samples", "approvals",
    "kg_audit",
]


def _advance_sequences(pg_engine) -> None:
    """把 PG SEQUENCE 推进到 >= 当前 MAX(id), 避免后续 INSERT 撞 PK."""
    with pg_engine.begin() as conn:
        for table in SEQUENCE_TABLES:
            seq_name = f"{table}_id_seq"
            conn.execute(text(f"""
                SELECT setval(:seq,
                    GREATEST(
                        COALESCE((SELECT MAX(id) FROM {table}), 0),
                        (SELECT last_value FROM {seq_name})
                    ),
                    true
                )
            """), {"seq": seq_name})


# === 备份 ===

def _backup_sqlite(sqlite_dir: Path) -> Path:
    """备份 3 个 SQLite 文件到 <sqlite_dir>/.archive/<utc_ts>/."""
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = sqlite_dir / ".archive" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ["app.db", "ingest_tasks.db", "kg_audit.db"]:
        src = sqlite_dir / name
        if src.exists():
            shutil.copy2(src, backup_dir / name)
    return backup_dir


# === 主流程 ===

def run(*, sqlite_dir: str | Path = DEFAULT_SQLITE_DIR, pg_url: str | None = None,
        delete_sqlite: bool = True, dry_run: bool = False) -> dict[str, int]:
    """搬运主入口.

    Args:
        sqlite_dir: SQLite 文件目录 (默认 packages/service/data/)
        pg_url: PG 连接串 (默认读 RAG_DB_URL env)
        delete_sqlite: 成功后是否删 SQLite 文件
        dry_run: 只打印计划, 不写 PG

    Returns:
        各表行数字典 {"users": 1, "ingest_tasks": 1, ...}
    """
    sqlite_dir = Path(sqlite_dir)
    pg_url = pg_url or _get_pg_url()

    if dry_run:
        print(f"[dry-run] sqlite_dir = {sqlite_dir}")
        print(f"[dry-run] pg_url = {pg_url}")
        for sqlite_file, table, _ in TABLE_ORDER:
            src = sqlite_dir / sqlite_file
            if not src.exists():
                print(f"  [skip] {sqlite_file} ({table}) - file not found")
                continue
            try:
                conn = sqlite3.connect(str(src))
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").scalar()
                conn.close()
                print(f"  {sqlite_file}.{table}: {count} rows")
            except Exception as e:
                print(f"  [error] {sqlite_file}.{table}: {e}")
        return {}

    # 1. 备份
    backup_dir = _backup_sqlite(sqlite_dir)
    print(f"[migrate] backup → {backup_dir}")

    # 2. 连 PG
    pg_engine = create_engine(pg_url)
    stats: dict[str, int] = {}

    try:
        # 3. 顺序搬运 (每张表独立 BEGIN/COMMIT, 失败只影响该表)
        for sqlite_file, table, fn_name in TABLE_ORDER:
            src = sqlite_dir / sqlite_file
            if not src.exists():
                print(f"  [skip] {sqlite_file} ({table}) - file not found")
                stats[table] = 0
                continue
            migrate_fn: Callable = globals()[fn_name]
            n = migrate_fn(pg_engine, src)
            stats[table] = n
            print(f"  [ok] {table}: {n} rows")

        # 4. 推进 SEQUENCE
        _advance_sequences(pg_engine)
        print(f"[migrate] sequences advanced for {len(SEQUENCE_TABLES)} tables")

    except Exception as e:
        print(f"[migrate] FAIL: {e}", file=sys.stderr)
        print(f"[migrate] SQLite files preserved at {backup_dir}", file=sys.stderr)
        raise

    # 5. 删 SQLite 文件 (仅 delete_sqlite=True 且全成功)
    if delete_sqlite:
        for name in ["app.db", "ingest_tasks.db", "kg_audit.db"]:
            src = sqlite_dir / name
            if src.exists():
                src.unlink()
                print(f"[migrate] deleted {src.name}")

    print(f"[migrate] done. stats: {json.dumps(stats, ensure_ascii=False)}")
    return stats


def _get_pg_url() -> str:
    import os
    url = os.environ.get("RAG_DB_URL")
    if not url:
        raise SystemExit("RAG_DB_URL 未设置. 例如: postgresql+psycopg://postgres:postgres@localhost:5432/rag")
    return url


# === CLI ===

def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite → PG 一次性搬运脚本")
    parser.add_argument("--sqlite-dir", default=str(DEFAULT_SQLITE_DIR),
                        help=f"SQLite 文件目录 (默认 {DEFAULT_SQLITE_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="只打印统计, 不写 PG")
    parser.add_argument("--keep-sqlite", action="store_true", help="搬完不删 SQLite 文件")
    args = parser.parse_args()

    run(
        sqlite_dir=args.sqlite_dir,
        delete_sqlite=not args.keep_sqlite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/scripts/test_migrate_sqlite_to_pg.py -v
```

Expected: 5 个 test 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add packages/service/scripts/migrate_sqlite_to_pg.py packages/service/tests/scripts/test_migrate_sqlite_to_pg.py
git commit -m "feat(scripts): one-shot SQLite to PG migration script"
```

---

### Task 13: 真跑搬运脚本 (用本地 SQLite 数据)

**Files:** 无 (操作步骤)

- [ ] **Step 1: dry-run 看统计**

```bash
cd packages/service
uv run python scripts/migrate_sqlite_to_pg.py --dry-run
```

Expected: 打印每张 SQLite 表行数, 不写 PG.

- [ ] **Step 2: 备份数据 (脚本自动) + 真跑**

```bash
cd packages/service
uv run python scripts/migrate_sqlite_to_pg.py --keep-sqlite
```

Expected: 打印每张表搬运行数, backup 路径, sequences advanced. SQLite 文件保留 (`--keep-sqlite`).

- [ ] **Step 3: 抽查 PG 数据**

```bash
echo 'SELECT COUNT(*) FROM users' | docker exec -i pgvector psql -U postgres -d rag -t -A
echo 'SELECT COUNT(*) FROM ingest_tasks' | docker exec -i pgvector psql -U postgres -d rag -t -A
echo 'SELECT COUNT(*) FROM kg_audit' | docker exec -i pgvector psql -U postgres -d rag -t -A
```

Expected: 数字跟 SQLite 源一致 (你本地数据库实际行数).

- [ ] **Step 4: 抽 1 行字段对比**

```bash
# PG 端
echo 'SELECT id, public_token, display_name FROM users LIMIT 1' | docker exec -i pgvector psql -U postgres -d rag

# SQLite 端
sqlite3 data/app.db "SELECT id, public_token, display_name FROM users LIMIT 1"
```

Expected: 两边输出字段值一致.

- [ ] **Step 5: 验证 SEQUENCE 已推进**

```bash
echo "INSERT INTO users (public_token, created_at, last_seen_at) VALUES ('test-after-migrate', NOW(), NOW()) RETURNING id" \
  | docker exec -i pgvector psql -U postgres -d rag
```

Expected: 新 id 不跟已有 id 撞 (e.g. MAX(原 id) + 1).

- [ ] **Step 6: 跑全套测试确认无 regression**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow"
```

Expected: 全 PASS.

- [ ] **Step 7: Commit (无文件改动, 但记录决策到 spec)**

如果上面都没问题, 不用 commit. 阶段 4 才删 SQLite.

---

### 阶段 3 验收

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/scripts/ -v
```

Expected: 5 个 test 全 PASS. 本地 SQLite 文件**保留**(阶段 4 才删).

---

## 阶段 4: 收尾清理 (Batch 4)

### Task 14: 删 SQLite .db 文件

**Files:** 无 (git rm)

- [ ] **Step 1: 确认 PG 端数据齐**

```bash
cd packages/service
echo "SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'conversations', COUNT(*) FROM conversations UNION ALL SELECT 'ingest_tasks', COUNT(*) FROM ingest_tasks UNION ALL SELECT 'kg_audit', COUNT(*) FROM kg_audit" \
  | docker exec -i pgvector psql -U postgres -d rag
```

Expected: 4 行 COUNT 跟本地 SQLite 一致.

- [ ] **Step 2: 删 SQLite 文件**

```bash
cd packages/service
rm -f data/app.db data/ingest_tasks.db data/kg_audit.db
```

- [ ] **Step 3: 验证启动还能跑**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run python -c "from src.ingest.store import save_task_dict; save_task_dict({'id':'t1', 'user_hash':'u', 'state':'pending', 'total_files':1, 'processed':0, 'failed':0, 'started_at':'2026-06-15 10:00:00'}); print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: 跑全套测试**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow"
```

Expected: 全 PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git status  # 应只显示 data/*.db 删除 (如果有 .gitignore 忽略可能不显示)
```

如果 .gitignore 没忽略 .db 文件 (新仓库规则可能忽略):

```bash
cd packages/service
git rm -f data/app.db data/ingest_tasks.db data/kg_audit.db
cd ../..
git commit -m "chore: remove SQLite .db files after migration"
```

---

### Task 15: 更新 README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 找现有 SQLite / PostgreSQL 段落**

```bash
cd /path/to/rag
grep -n "SQLite\|PostgreSQL\|切 PostgreSQL" README.md
```

期望找到 "数据库 (SQLAlchemy 2.0 + Alembic)" 章节和 "切 PostgreSQL 三步" 段落.

- [ ] **Step 2: 改写 "切 PostgreSQL 三步"**

Replace "切 PostgreSQL 三步" 段落, 改成 "PostgreSQL 默认 (跟 pgvector 共用)" 或类似措辞, 强调 PG 是默认 / 唯一选项.

例如:

```markdown
### 启动 PostgreSQL (PG 默认数据库)

PG 跟 pgvector 共用一个 docker 容器. 启动:

\`\`\`bash
docker compose -f docker/docker-compose.yml up -d postgres
\`\`\`

确认 PG 起来后, 项目自动连 `postgresql+psycopg://postgres:postgres@localhost:5432/rag` (跟 `docker/.env` 的 `POSTGRES_PASSWORD` 一致). 改了 `POSTGRES_PASSWORD` 必须同步改 `RAG_DB_URL`.
```

- [ ] **Step 3: 删 "数据搬运脚本不在本 spec 范围, 切的时候再写"**

Search README for this phrase, 删.

- [ ] **Step 4: Commit**

```bash
cd /path/to/rag
git add README.md
git commit -m "docs: update README for PG-only database"
```

---

### Task 16: 更新 .env.example

**Files:**
- Modify: `packages/service/.env.example`

- [ ] **Step 1: 找现有 RAG_DB_URL 行**

```bash
grep -n "RAG_DB_URL" packages/service/.env.example
```

期望找到注释 + SQLite 默认值.

- [ ] **Step 2: 改默认值**

Replace `RAG_DB_URL=sqlite:///data/app.db` 为:

```bash
# PG 默认 (docker-compose 起的 PG, 密码跟 docker/.env POSTGRES_PASSWORD 一致)
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
```

在附近加注释:

```bash
# 改了 docker/.env 的 POSTGRES_PASSWORD 必须同步改这里
# 生产环境务必用强密码, 别用 postgres:postgres
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/.env.example
git commit -m "docs(env): default RAG_DB_URL to PG"
```

---

### Task 17: 更新 docker/.env.example

**Files:**
- Modify: `docker/.env.example`

- [ ] **Step 1: 加 RAG_DB_URL 联动提示**

在 `POSTGRES_PASSWORD=replace-with-strong-password` 下面加:

```bash
# 上面 POSTGRES_PASSWORD 改了, packages/service/.env 的 RAG_DB_URL 也必须同步
# 例: POSTGRES_PASSWORD=deyuan888 → RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag
```

- [ ] **Step 2: Commit**

```bash
git add docker/.env.example
git commit -m "docs(docker): hint RAG_DB_URL sync with POSTGRES_PASSWORD"
```

---

### Task 18: 更新 docs/architecture.md (如果提到 SQLite)

**Files:**
- Modify: `docs/architecture.md`

- [ ] **Step 1: 找 SQLite 引用**

```bash
grep -n -i "sqlite\|业务 db\|存储层" docs/architecture.md
```

- [ ] **Step 2: 改写 SQLite 段落**

如果有 SQLite 描述, 改成 PG. 没找到则跳过此 task.

- [ ] **Step 3: Commit (如果有改动)**

```bash
git add docs/architecture.md
git commit -m "docs(architecture): update storage section to PG-only"
```

---

### Task 19: 启动后端 + curl 健康检查

**Files:** 无 (验收)

- [ ] **Step 1: 启动后端**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run python main.py
```

后端跑起来 (前台进程, dev mode). 等到 "Application startup complete".

- [ ] **Step 2: curl 健康检查**

另开一个 terminal:

```bash
curl http://localhost:8000/api/health | python -m json.tool
```

Expected: `checks.pgvector.status == "ok"`, `latency_ms` 数值.

- [ ] **Step 3: 测试业务路径**

```bash
# 创 anon user
curl -X POST http://localhost:8000/api/auth/anon -c cookies.txt

# 校验 user 表
echo 'SELECT COUNT(*) FROM users' | docker exec -i pgvector psql -U postgres -d rag -t -A
```

Expected: COUNT 增加 1.

- [ ] **Step 4: 停后端 (Ctrl+C)**

回到跑后端的 terminal, Ctrl+C 停掉.

---

### Task 20: 最终验收

- [ ] **Step 1: 跑全套测试**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow" 2>&1 | tail -20
```

Expected: 全 PASS. 0 failed.

- [ ] **Step 2: 确认 SQLite 文件已删**

```bash
ls packages/service/data/*.db 2>&1
```

Expected: `No such file or directory` 或类似 (因为已删).

- [ ] **Step 3: 确认无 shim / 无 SQLite 代码残留**

```bash
cd /path/to/rag
grep -rn "sqlite" packages/service/src/ 2>&1 | grep -v ".pyc"
```

Expected: 0 行 (除 vector_store.py 文件 docstring 第一行 "pgvector" 跟 sqlite 无关).

- [ ] **Step 4: Commit (如有未提交改动)**

```bash
git status
```

如果有未提交改动:

```bash
git add -A
git commit -m "chore: post-migration cleanup"
```

---

## 验收清单

- [ ] docker PG 启动 + alembic upgrade head 在 PG 上跑通
- [ ] 所有 ORM model + store 重写测试通过
- [ ] 数据搬运脚本 5 个测试通过
- [ ] 数据从本地 SQLite 成功迁到 PG (行数一致)
- [ ] 后端启动 + `/api/health` pgvector check = ok
- [ ] 业务路径 (anon user / ingest / kg audit) 在 PG 上跑通
- [ ] SQLite .db 文件全部删除
- [ ] SQLite 适配代码 (PRAGMA / check_same_thread / URL 转换) 全部删除
- [ ] README / .env.example / docker/.env.example 文档更新
- [ ] 跑 `pytest tests/ -m "not slow"` 全 PASS

## 风险 + 回滚

如果中途出问题 (e.g. PG schema 跟 ORM model 不兼容 / 数据搬运某表失败):

1. **别**改代码凑合 — 停下来 debug 根因
2. SQLite 备份在 `data/.archive/<ts>/` (搬运脚本自动备份), 可以恢复
3. `alembic downgrade -1` 删表重来 (但要重装 alembic_version)
4. docker PG 状态坏了: `docker compose down -v` 清 volume 重启

## 后续 follow-up

- 跑生产前把 `RAG_DB_URL` 密码改强, 别用默认 `postgres:postgres`
- 加 `pgvector` 扩展到 PG (vector 库, 已经在 docker 镜像里, 但需要 `CREATE EXTENSION IF NOT EXISTS vector;`)
- 监控 PG 连接数 + 表大小 + 索引使用率
