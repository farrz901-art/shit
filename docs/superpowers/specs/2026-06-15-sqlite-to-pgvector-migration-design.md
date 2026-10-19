# SQLite → pgvector 迁移

**日期**: 2026-06-15
**状态**: 设计已批准, 待实施
**作者**: Claude (brainstorming with user)

## Context

RAG 项目当前**业务数据 + task 元数据 + 审计日志**用 3 个 SQLite 文件存 (`packages/service/data/*.db`), 但 docker 起的 PG 实例已经装了 pgvector 扩展, **向量库代码 (src/retrieval/vector_store.py) 早在设计时就只走 PGVectorStore, 没有 SQLite 后备**.

现状的矛盾:

- 业务 DB (`app.db`) / task 元数据 (`ingest_tasks.db`) / 审计日志 (`kg_audit.db`) 都用 SQLite, 跨进程并发有限, 不适合生产
- 向量库已经硬绑 PG (psycopg2 + pgvector)
- 同一项目里两套存储, 备份 / 监控 / 迁移都要做两遍
- README 写了"切 PostgreSQL 三步", 但那只是 env 切换, 没说代码改造——本 spec 是把 SQLite 这条链路彻底清零

**Why 现在做**:

- docker-compose 里的 PG 已经常驻, 投入已经在
- 业务量上 SQLite 行锁 / WAL 局限开始显现 (尤其 ingest_tasks 多 worker 写)
- pgvector 跟业务表共用同一个 PG 实例, 单一数据源, 备份 / 监控 / 迁移成本最低

## 目标

- **业务表 + ingest_tasks + kg_audit 全部用 SQLAlchemy ORM 迁到 PG** (跟 pgvector 同 DB)
- 删掉 `packages/service/data/*.db` 3 个 SQLite 文件
- 删掉 SQLite 特化代码 (`_set_sqlite_pragma`, `connect_args["check_same_thread"]`, sqlite URL 转换)
- 写一次性数据搬运脚本 (本地 SQLite 数据 → PG)
- 现有对外 API (`session_scope()`, `save_task_dict()`, `AuditStore` 等) 签名 0 改动
- Alembic 重新做一次 consolidated init migration (删 4 个旧 migration)
- 测试全部重写为 PG 测试

## 非目标

- 不保留 SQLite fallback / 兼容代码 (符合 `feedback-no-shim-no-minimal-changes`)
- 不重写 ORM model 字段 (现有 model 用 SQLAlchemy 2.0 跨方言写法, 字段定义不动)
- 不动向量库代码 (已经在 pgvector)
- 不优化 SQL 索引 / 查询 (迁完跟现状 1:1)
- 不改数据搬运脚本为通用工具 (一次性脚本, 跑完删)
- 不做 PII 脱敏 / 数据清洗
- 不写回滚脚本 (downgrade 留空, 跑前先备份)

## 架构

### 单一数据源

```
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI (uvicorn :8000)                 │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │ src/storage/   │  │ src/ingest/    │  │ src/kg/        │  │
│  │ engine.py      │  │ models.py +    │  │ audit_models + │  │
│  │ session.py     │  │ store.py       │  │ store.py       │  │
│  └───────┬────────┘  └────────┬───────┘  └────────┬───────┘  │
│          │ SQLAlchemy ORM     │                   │          │
│          └────────────────────┴───────────────────┘          │
└─────────────────────────────────┬────────────────────────────┘
                                  │ psycopg3
                          ┌───────▼────────┐
                          │  PostgreSQL    │
                          │  (docker 5432) │
                          │                │
                          │  rag DB:       │
                          │   ├ users      │
                          │   ├ accounts   │
                          │   ├ invites    │
                          │   ├ password_  │
                          │   │  resets    │
                          │   ├ convos     │
                          │   ├ messages   │
                          │   ├ evaluations│
                          │   ├ eval_      │
                          │   │  samples   │
                          │   ├ approvals  │
                          │   ├ ingest_    │  ← 新 (原 sqlite3 raw)
                          │   │  tasks     │
                          │   ├ kg_audit   │  ← 新 (原 sqlite3 raw)
                          │   └ llamaindex │  ← pgvector 扩展
                          │      _embedd.  │
                          │     + hnsw idx │
                          └────────────────┘
```

### 边界

| 模块 | 职责 | 状态 |
|---|---|---|
| `src/storage/` | 通用 Base / engine / session | 已存在, 重写 |
| `src/ingest/models.py` | IngestTask ORM | 新增 |
| `src/ingest/store.py` | task CRUD (走 ORM) | 重写 |
| `src/kg/audit_models.py` | KgAudit ORM | 新增 |
| `src/kg/audit.py` | AuditStore (走 ORM) | 重写 |
| `src/retrieval/` | 向量库 (pgvector) | 不动 |
| `src/storage/migrations/` | Alembic | 删 4 个旧, 加 1 个新 |

### 对外 API 不变

- `src.storage.{Base, get_engine, init_db, session_scope, get_session}` 签名保留
- `src.ingest.store.{save_task_dict, load_task_dict, list_user_task_dicts, reset_for_test}` 签名保留
- `src.kg.audit.AuditStore.{record, list_recent}` 签名保留

## 组件

### 1. 新建 ORM model

**`src/ingest/models.py`** (新文件):

```python
class IngestTask(Base):
    """ingest task 元数据. 替原 sqlite3 raw table (data/ingest_tasks.db)."""
    __tablename__ = "ingest_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False)
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
    __table_args__ = (
        Index("ix_ingest_tasks_user_started", "user_hash", "started_at"),
    )
```

**`src/kg/audit_models.py`** (新文件):

```python
class KgAudit(Base):
    """知识图谱审计日志. 替原 sqlite3 raw table (data/kg_audit.db)."""
    __tablename__ = "kg_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    __table_args__ = (Index("ix_kg_audit_ts", "ts"),)
```

### 2. 重写 `src/storage/engine.py`

```python
def _make_engine(url: str) -> Engine:
    """PG-only: 不再有 SQLite 特化."""
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )

# 删 _set_sqlite_pragma event listener 整段
# 删 if url.startswith("sqlite"): connect_args["check_same_thread"] 分支
```

**默认 URL 改 PG**:

```python
DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/rag"
```

注意: 密码默认 `postgres` 只是**开发占位**——docker-compose 的 `POSTGRES_PASSWORD` 由 `docker/.env` 注入, 没硬编码默认值. 真实使用必须把 `RAG_DB_URL` 配成跟 `POSTGRES_PASSWORD` 一致 (例如: `docker/.env` 写 `POSTGRES_PASSWORD=deyuan888` → `.env.local` 写 `RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag`).

### 3. 重写 `src/ingest/store.py`

保留旧函数签名, 内部走 `session_scope()`:

```python
def save_task_dict(d: dict) -> None:
    with session_scope() as s:
        s.merge(IngestTask(
            id=d["id"], user_hash=d["user_hash"], state=d["state"],
            total_files=d["total_files"], processed=d.get("processed", 0),
            failed=d.get("failed", 0),
            started_at=_to_dt(d["started_at"]),
            finished_at=_to_dt(d.get("finished_at")),
            error=d.get("error"), work_dir=d.get("work_dir"),
            input_files_json=json.dumps(d.get("input_files", []), ensure_ascii=False),
            output_files_json=json.dumps(d.get("output_files", []), ensure_ascii=False),
        ))

# load_task_dict / list_user_task_dicts / reset_for_test 同样改走 ORM
# 删 _conn / _lock 全局单例, 删 _connect(), 删 _row_to_dict (ORM 直接返对象)
```

`reset_for_test()` 改成:

```python
def reset_for_test() -> None:
    with session_scope() as s:
        s.execute(text("DELETE FROM ingest_tasks"))
```

### 4. 重写 `src/kg/audit.py`

`AuditStore` 改造成无状态薄壳, 保持旧 `record/list_recent` 接口:

```python
class AuditStore:
    """薄壳: 保持旧 record/list_recent 接口, 内部走 session_scope."""
    def __init__(self, db_path: Path | str | None = None):
        # db_path 参数保留但忽略 (向后兼容已有调用方: src/kg/router.py:25)
        pass

    def record(self, *, action, actor, target, result, detail):
        with session_scope() as s:
            s.add(KgAudit(
                ts=time.time(), action=action, actor=actor, target=target,
                result=result, detail=json.dumps(detail, ensure_ascii=False),
            ))

    def list_recent(self, limit=50):
        with session_scope() as s:
            rows = s.execute(
                select(KgAudit).order_by(KgAudit.ts.desc()).limit(limit)
            ).scalars().all()
            return [{**{"id": r.id, "ts": r.ts, "action": r.action,
                        "actor": r.actor, "target": r.target, "result": r.result},
                     "detail": json.loads(r.detail)} for r in rows]
```

### 5. Alembic consolidated migration

**删**:
- `1f49cc6444e1_init.py`
- `a3b8c1d2e4f5_add_sources_to_evaluation_samples.py`
- `2a3b4c5d6e7f_add_accounts_and_invites.py`
- `b7c4e2f1a9d3_add_approvals.py`

**新建**: `YYYYMMDD_HHMMSS_consolidated_pg_init.py` — single revision, `down_revision = None`

包含内容:

| 表 | 来源 |
|---|---|
| `users` | 原 1f49 + 2a3b (加 `account_id`) |
| `accounts` | 原 2a3b |
| `invites` | 原 2a3b |
| `password_resets` | 原 2a3b |
| `conversations` | 原 1f49 |
| `messages` | 原 1f49 |
| `evaluations` | 原 1f49 |
| `evaluation_samples` | 原 1f49 + a3b8 (加 `sources`) |
| `approvals` | 原 b7c4 |
| `ingest_tasks` | **新** |
| `kg_audit` | **新** |
| `alembic_version` | alembic 自带 |

PG 方言要点:

- `JSON` → `JSONB` (PG 原生, query 性能更好)
- ENUM 字段 (approvals.kind / review_status / apply_status / rejection_reason) 保留 `String` + check constraint (现有 model 已经这么写, 不动)
- `String(36)` PK (conversations.id) PG 原生 UUID 兼容, 不强转 `UUID` (跟现有 1f49 migration 风格一致)
- `DateTime` → `TIMESTAMP WITHOUT TIME ZONE` (SQLAlchemy 默认; 项目代码已经全部 `HKT` 时区化, 不存 tz)

**`src/storage/migrations/env.py`** 加 2 行强制注册新 model:

```python
from src.ingest.models import IngestTask  # noqa: F401
from src.kg.audit_models import KgAudit  # noqa: F401
```

### 6. 数据搬运脚本

**`scripts/migrate_sqlite_to_pg.py`** (一次性, 跑完删):

```python
"""一次性 SQLite → PG 搬运脚本 (2026-06-15).
从 3 个本地 SQLite 文件搬数据到 docker PG, 成功提交后删 SQLite 文件.
跑前自动备份到 data/.archive/<timestamp>/, 失败可手动恢复.
"""
# 用法: uv run python scripts/migrate_sqlite_to_pg.py [--dry-run]

# 步骤:
#   1. 备份 data/*.db 到 data/.archive/<utc_ts>/
#   2. 连 PG, 校验 alembic_version == head
#   3. BEGIN TRANSACTION
#   4. 顺序搬运 (FK 依赖序):
#      - users → accounts → invites → password_resets
#      - conversations → messages
#      - evaluations → evaluation_samples
#      - approvals
#      - ingest_tasks
#      - kg_audit
#   5. 推进 PG SEQUENCE (用 SELECT setval(pg_get_serial_sequence(...)))
#      保证后续 INSERT 不会撞 PK
#   6. COMMIT
#   7. 删 SQLite .db 文件
#   8. 打印统计 (各表行数 + 耗时)
```

**ID 重映射细节**:

SQLite 自增 PK 是 `rowid`, INSERT 时不指定就自动生成。本地数据 PK 可能是 1, 2, 3, ... 也可能是 sqlite3 临时表的随机 ID。

策略:
- **保留原 PK 值**: INSERT 时显式指定 `id=src_row["id"]`
- **推进 PG SEQUENCE**: 用 `SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1)) FROM users`
- 每个表搬运完后立即跑

**字段映射 (跨方言差异)**:

| SQLite 列 | PG 列 | 处理 |
|---|---|---|
| `JSON` (TEXT in SQLite) | `JSONB` | SQLAlchemy 自动 coerce |
| `DateTime` (TEXT in SQLite) | `TIMESTAMP` | `_to_dt()` parse `YYYY-MM-DD HH:MM:SS` |
| `Boolean` (INTEGER 0/1) | `BOOLEAN` | `bool(value)` |
| `Enum.String` | VARCHAR + check | 直接传字符串值 |

**Dry-run** (`--dry-run` flag): 不写 PG, 不删 SQLite, 只打印 `表名 → 行数 / 抽样 3 行`.

### 7. 清理 SQLite 代码

**`src/approvals/router.py`** 删:

```python
if url.startswith("sqlite://") and not url.startswith("sqlite+"):
    return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
```

(为啥要删: 不再有 SQLite URL, 这条转换是给 SQLite 异步驱动用的, 残留就是 shim)

**`src/storage/engine.py`** 删整段 `_set_sqlite_pragma` event listener.

### 8. `.env.example` 更新

```diff
- # 默认 (省略 env 时)
- RAG_DB_URL=sqlite:///data/app.db
+ # 默认 (省略 env 时): docker-compose 起的 PG, 密码跟 POSTGRES_PASSWORD 一致
+ RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
```

docker `.env.example` 加注释提示 `POSTGRES_PASSWORD` 改了之后 `RAG_DB_URL` 必须同步改.

### 9. README 更新

- 删 "数据库 (SQLAlchemy 2.0 + Alembic)" 章节里 "SQLite 默认跑" 的措辞
- 改 "切 PostgreSQL 三步" → "启动 PostgreSQL (PG 在 docker-compose 里)"
- 删 "数据搬运脚本不在本 spec 范围, 切的时候再写" 这句 (现在已经在本 spec 范围)

## 数据流

### 启动时

```
uv run python main.py
  → alembic upgrade head (读 RAG_DB_URL, 默认 PG)
  → 启动 uvicorn
  → _get_pg_engine() (src/health/checks.py) 校验 PG 联通
```

### 业务请求 (不变)

```
HTTP /api/auth/anon
  → src/auth/auth_account_router.create_anon_user()
    → session_scope()
      → INSERT INTO users (...) RETURNING id
```

### Ingest task

```
HTTP /api/ingest/upload
  → src/ingest/api.py: enqueue_task()
    → save_task_dict({id, state, ...})
      → session_scope().merge(IngestTask(...))
      → commit
  → background worker
  → save_task_dict({id, state: "completed", output_files: [...]})
```

### KG audit

```
HTTP /api/kg/triples
  → src/kg/router.py: create_triple()
    → _audit_store.record(action="create_triple", ...)
      → session_scope().add(KgAudit(...))
      → commit
```

### 向量库 (不变)

```
HTTP /api/chat
  → src/retrieval/query_engine.py
    → PGVectorStore.query(query_embedding, top_k)
      → SELECT ... FROM llamaindex_embeddings ORDER BY embedding <=> $1 LIMIT k
```

## 错误处理

| 失败点 | 行为 |
|---|---|
| `alembic upgrade head` 失败 | uvicorn 启动崩溃 (已有行为, 不动) |
| 业务请求 PG 连接失败 | FastAPI 返 500 (SQLAlchemy OperationalError 上浮, 现有 try/except 捕获) |
| 健康检查 `check_pgvector` PG 不可达 | 返 `status="error"` + error msg (现有逻辑不变) |
| 搬运脚本某张表失败 | 整个事务 rollback; 不删 SQLite; exit 1; 用户从 `data/.archive/` 恢复 |
| 搬运脚本备份目录已存在 | `data/.archive/<ts>` 用 UTC 时间戳到秒, 重复概率极低, 不处理 |
| 搬运后启动 uvicorn 报 500 | PG 缺表 → 跑 `alembic upgrade head` (PG 表是 migration 建的, 不是搬运脚本建的, 缺表说明 migration 没跑) |

## 测试

按 `feedback-tdd-test-real-behavior-not-just-no-crash` 和 `feedback-must-test-both-ends`:

### 单元测试

| 文件 | 改动 |
|---|---|
| `tests/ingest/test_models.py` | 新增. IngestTask 字段 + 索引断言 |
| `tests/ingest/test_store.py` | 重写. save/load/list 行为, 用真 PG |
| `tests/kg/test_audit_models.py` | 新增. KgAudit 字段断言 |
| `tests/kg/test_audit.py` | 重写. record/list_recent 行为 |
| `tests/storage/test_engine.py` | 重写. 默认 URL = PG + 连接串透传 |
| `tests/storage/test_session.py` | 保留. session_scope 行为 |
| `tests/storage/test_migrations.py` | 重写. alembic upgrade head 在 PG 跑通 + `alembic_version` 在 head |
| `tests/approvals/test_*.py` | 删 sqlite URL 转换相关断言 (如果有) |

### 集成测试

| 文件 | 改动 |
|---|---|
| `tests/integration/test_smoke_pg.py` | 新增. 启动后端 + curl `/api/health` + `check_pgvector.status == "ok"` |
| `tests/scripts/test_migrate_sqlite_to_pg.py` | 新增. 用临时 SQLite fixture + 真 PG 验证: 行数 + 抽 3 行字段一致 |

### Test fixture

`tests/conftest.py` 加 `pg_engine` fixture:

```python
@pytest.fixture(scope="session")
def pg_engine():
    """每个测试 session 开头跑 alembic upgrade head 一次."""
    engine = create_engine(os.environ["RAG_DB_URL"])
    # 不主动 dispose, 让 pytest session 结束时回收
    yield engine
    # 测试结束后: 可选 TRUNCATE 所有表 (除非 fixture 加 autouse=clean)
```

`tests/storage/conftest.py` 删 SQLite fixture.

### Test 命令

```bash
# 跑全套 (假设 docker PG 在跑)
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow"

# 跑集成测试
RAG_DB_URL=... uv run pytest tests/integration/
```

**pre-commit 不跑 alembic upgrade**: migration 测试只在 CI + 本地手动跑, 不阻塞 commit.

## 实施批次

按 `feedback-commit-in-batches-for-large-changes` (4 批, 每批可独立 review/回滚/bisect):

### Batch 1: ORM model + consolidated migration

- 新增 `src/ingest/models.py`, `src/kg/audit_models.py`
- 新增 `YYYYMMDD_HHMMSS_consolidated_pg_init.py` migration
- 删 4 个旧 migration
- 更新 `src/storage/migrations/env.py` 注册新 model
- 新增 `tests/ingest/test_models.py`, `tests/kg/test_audit_models.py`
- 跑 `RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag uv run alembic upgrade head` 在 docker PG 验证 (空库 fresh init)
- **不**改 `ingest/store.py`、`kg/audit.py`、`engine.py` (旧 SQLite 代码仍工作)
- **不**删 SQLite .db 文件

### Batch 2: 重写 store 层

- 重写 `src/ingest/store.py` 走 ORM
- 重写 `src/kg/audit.py` 走 ORM
- 重写 `src/storage/engine.py` 删 SQLite 特化
- 重写 `src/approvals/router.py` 删 sqlite URL 转换
- 更新 `tests/storage/conftest.py`
- 重写 `tests/storage/test_engine.py`, `tests/kg/test_audit.py`, `tests/ingest/test_store.py`, `tests/approvals/test_*.py`
- 跑 `pytest tests/ -m "not slow"` 全绿
- **不**删 SQLite .db 文件 (搬运脚本还没写, 数据还没迁)

### Batch 3: 数据搬运脚本

- 新增 `scripts/migrate_sqlite_to_pg.py`
- 新增 `tests/scripts/test_migrate_sqlite_to_pg.py`
- 跑脚本本地验证 (`--dry-run` 跑一次, 再正式跑一次)

### Batch 4: 收尾清理

- 删 `data/app.db`, `data/ingest_tasks.db`, `data/kg_audit.db`
- 删 `.gitignore` 里 `data/*.db` 条目 (如果存在)
- 更新 `README.md`: 移除 SQLite 默认相关说明
- 更新 `docs/architecture.md` (如有 SQLite 相关段落)
- 更新 `.env.example`: 默认 `RAG_DB_URL` 改 PG 注释
- 更新 docker `docker/.env.example`: 加 `POSTGRES_PASSWORD` 改后 `RAG_DB_URL` 同步提示
- 跑 `pytest tests/ -m "not slow"` + `curl /api/health` 全绿

## 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| Alembic migration 在 PG 上跑失败 (PG 方言差异) | Batch 1 跑 `alembic upgrade head` 验证, 失败就地修 |
| 搬运脚本数据丢失 | 跑前自动备份到 `data/.archive/<ts>/`, 失败可恢复 |
| 业务代码 SQL 用了 SQLite 特有语法 (e.g. `datetime('now')`) | grep 验证, 没有 (SQLAlchemy 抽象层) |
| PG SEQUENCE 没推进导致后续 INSERT 撞 PK | 搬运脚本每张表后 `SELECT setval(...)` |
| 默认 `postgres:postgres` 在生产用 | `.env.example` 注释强调 "生产必须改 env" |
| 测试 fixture 共享 engine 状态污染 | 用 `TRUNCATE ... CASCADE` 在每个测试 class 头清表 |
| 健康检查 `check_pgvector` 用了 dataclass 默认 (修过 bug 2026-06-15) | 已经走 `PGVectorConfig.from_env()`, 不重蹈覆辙 |

## 验收

```bash
# 1. 起 docker PG (已有)
docker compose -f docker/docker-compose.yml up -d postgres

# 2. 跑 migration
cd packages/service
uv run alembic upgrade head

# 3. 跑搬运脚本 (本地有 SQLite 数据)
uv run python scripts/migrate_sqlite_to_pg.py
# 期望: 各表行数打印, SQLite 文件已删

# 4. 跑全套测试
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag \
  uv run pytest tests/ -m "not slow"

# 5. 启动后端 + 健康检查
uv run python main.py &
curl http://localhost:8000/api/health
# 期望: {"checks": {"pgvector": {"status": "ok", ...}}}

# 6. 数据抽查: 浏览器登录之前的 anon token 还能用 / kg 审计页面能看到历史记录
```

## 相关链接

- [README.md](../../README.md) - 现状说明 (迁完要改)
- [docs/architecture.md](../../architecture.md) - 架构文档 (迁完要改)
- [docs/dev-conventions.md](../../dev-conventions.md) - 编码规范
- memory: `feedback-no-shim-no-minimal-changes` - 无 shim 原则
- memory: `feedback-tdd-test-real-behavior-not-just-no-crash` - TDD 真行为
- memory: `feedback-must-test-both-ends` - 前后端都测
- memory: `feedback-commit-in-batches-for-large-changes` - 大改分批
- memory: `feedback-debug-search-before-loop` - 搜官方文档优先
