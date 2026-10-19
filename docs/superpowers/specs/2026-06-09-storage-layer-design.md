# Storage Layer Design (SQLite → PostgreSQL-ready)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-06-09
**Status:** Approved (待实施)
**Scope:** 第一阶段 — 评估页重设计 / 客户端 token / 聊天 sqlite 都依赖这层基础设施, 单独可测可合
**Out of scope:** 业务 model (评估表 / 聊天表 / 后续 mem0 适配) — 留给后续 spec

## Goal

给项目一个统一的 SQLAlchemy 2.0 + Alembic 存储层, SQLite 现在跑, PostgreSQL 切 env 即用, 业务代码零改动。

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  src/rag/storage/                        │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐     │
│  │  base  │  │ engine │  │session │  │  migrations │    │
│  │  Base  │  │factory │  │ factory│  │  (Alembic)  │    │
│  └────┬───┘  └────┬───┘  └────┬───┘  └──────┬─────┘    │
│       │           │          │             │           │
│       └───────────┴──────────┴─────────────┘           │
│                          │                               │
│                          ↓                               │
│              RAG_DB_URL env (默认 sqlite:///data/app.db)  │
└─────────────────────────────────────────────────────────┘
            ↓                                    ↓
    ┌──────────────┐                  ┌────────────────────┐
    │  SQLite now  │                  │  PostgreSQL later  │
    │  data/app.db │                  │  +psycopg 切 URL  │
    └──────────────┘                  └────────────────────┘
```

**关键约束**:
1. 业务 model 不在本 spec 范围 (后续 spec 加)
2. 切 PG = 改 1 个 env, 跑 `alembic upgrade head`, 业务代码零改动
3. Windows file lock 安全 (沿用 `kg/audit.py` 的 `journal_mode=DELETE` 修法)

## Tech Stack

| 组件 | 选型 | 理由 |
|---|---|---|
| ORM | SQLAlchemy 2.0 | 2.0+ `Mapped[]` 类型注解, 业界事实标准, 双后端 |
| Migrations | Alembic | SQLAlchemy 官方, autogenerate |
| SQLite driver | stdlib `sqlite3` (Python 3.14 内置) | 零依赖 |
| PG driver (预留) | `psycopg[binary]>=3.2` | 现在装, 切时不用动依赖 |

## Models (4 个, 跨 spec 共用)

> 一次性定 4 个 spec 都要用的表结构. 后面 spec 只写"业务逻辑", 不再改 schema.

**通用约定**:
- PK: `int` 自增 (除 `conversations.id` 用 `str(36)` UUID 兼容前端)
- 时间: naive UTC, 业务代码统一 `datetime.now(UTC)` 写入, 不用 `DateTime(timezone=True)`
- 时间字段名: `created_at` / `updated_at` / `last_seen_at` / `finished_at`
- 删除策略: 硬删, `users` → 其他 用默认 RESTRICT, `conversations` → `messages` / `evaluations` → `evaluation_samples` 用 CASCADE
- JSON 字段: SQLAlchemy 2.0 `JSON` 类型, 切 PG 变 `JSONB`, 业务无感

### `users` — 客户端匿名 token + Mem0 关联

**业务来源**: 第 5 条 (客户端 token) + 第 7 条 (mem0 后续按 user_id 隔离)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | 内部用 |
| `public_token` | `String(64)` | UNIQUE, NOT NULL, INDEX | 32 字节 hex, 客户端存的 |
| `display_name` | `String(50)` | NULL | 后续用户填昵称 (本 spec 不用) |
| `created_at` | `DateTime` | NOT NULL, default=now | 首次访问 |
| `last_seen_at` | `DateTime` | NOT NULL, default=now, INDEX | 最后活跃, 清理冷用户依据 |

**索引**: `public_token` (UNIQUE 自动建), `last_seen_at`

### `conversations` — 聊天会话

**业务来源**: 第 6 条 (聊天记录存 sqlite)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `String(36)` | PK | UUID, 跟前端 `crypto.randomUUID()` 兼容 |
| `user_id` | `Integer` | FK → users.id, NOT NULL, INDEX | 多用户隔离 |
| `title` | `String(200)` | NOT NULL | 会话标题 |
| `message_count` | `Integer` | NOT NULL, default=0 | 冗余, 减少 COUNT |
| `created_at` | `DateTime` | NOT NULL | |
| `updated_at` | `DateTime` | NOT NULL, INDEX | 用于列表"最近对话"排序 |

**索引**: `(user_id, updated_at DESC)` 复合索引, 列表查询

### `messages` — 聊天消息

**业务来源**: 同 6

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `conversation_id` | `String(36)` | FK → conversations.id, NOT NULL, ON DELETE CASCADE, INDEX | |
| `role` | `String(20)` | NOT NULL | `user` / `assistant` / `system` |
| `content` | `Text` | NOT NULL | 长文本 |
| `meta` | `JSON` | NULL | token 用量 / 模型名 / 工具调用 |
| `created_at` | `DateTime` | NOT NULL | |

**索引**: `(conversation_id, created_at)` 复合索引, 单会话按时间正序拉

### `evaluations` — 评估批 (元数据)

**业务来源**: 第 1 条 (评估页重设计)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `user_id` | `Integer` | FK → users.id, NOT NULL, INDEX | 谁发起的 |
| `dataset_name` | `String(200)` | NOT NULL | 原始 CSV 文件名 |
| `dataset_path` | `String(500)` | NULL | 落盘路径 (调试) |
| `status` | `String(20)` | NOT NULL, INDEX | `pending` / `running` / `completed` / `failed` |
| `total_samples` | `Integer` | NOT NULL, default=0 | |
| `successful` | `Integer` | NOT NULL, default=0 | |
| `failed` | `Integer` | NOT NULL, default=0 | |
| `concurrency` | `Integer` | NOT NULL, default=5 | |
| `avg_metrics` | `JSON` | NULL | `{faithfulness, answer_relevancy, context_precision, context_recall}` |
| `duration_seconds` | `Float` | NULL | |
| `error_message` | `Text` | NULL | 整批失败错 |
| `created_at` | `DateTime` | NOT NULL, INDEX | |
| `finished_at` | `DateTime` | NULL | |

**索引**: `(user_id, created_at DESC)` 复合索引, 历史列表

### `evaluation_samples` — 评估条 (一对多)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `Integer` | PK, autoincrement | |
| `evaluation_id` | `Integer` | FK → evaluations.id, NOT NULL, ON DELETE CASCADE, INDEX | |
| `index` | `Integer` | NOT NULL | 批内序号 (1..N) |
| `question` | `Text` | NOT NULL | 问题 |
| `ground_truth` | `Text` | NULL | 标准答案 |
| `answer` | `Text` | NULL | LLM 回答 |
| `contexts` | `JSON` | NULL | 检索上下文 `list[str]` |
| `metrics` | `JSON` | NULL | 4 个分 dict |
| `error` | `Text` | NULL | 单条失败原因 |
| `duration_ms` | `Integer` | NULL | 单条耗时 |

**索引**: `(evaluation_id, index)` 复合索引, 按序展示

### Admin 虚拟 User (跨 spec 约定, 不入 users 表)

**来源**: 评估页 spec 的 admin token 调试需求. **admin 走 Pydantic 虚拟 user, 不动 users 表 schema**, 跟普通用户走同一个 `CurrentUser` 接口, 仅 `is_admin=True` 区别.

- `users` 表不增 `is_admin` 字段 (避免"admin 不入库却字段存在"的语义污染)
- `CurrentUser` Pydantic 模型 (在 `src/rag/middleware/auth.py` 里, 客户端 token spec 加)
- `id=0` 是 admin 哨兵, 自增 PK 从 1 开始不冲突
- 业务 router 用 `current.is_admin` 决定是否过滤 `WHERE user_id=current.id`

详细 admin token 中间件逻辑见评估页 spec 的"调试机制"节.

### 关系图

```
users (1) ──< (N) conversations
   │                  │
   │                  └──< (N) messages
   │
   └──< (N) evaluations
              │
              └──< (N) evaluation_samples
```

### 文件落点

业务 model 放 `src/rag/<feature>/models.py`, 全部 import `Base` from `src.rag.storage`:

```
src/rag/auth/models.py        # User
src/rag/chat/models.py        # Conversation, Message
src/rag/eval/models.py        # Evaluation, EvaluationSample
```

(每个 spec 落地时建对应文件; 本 spec 一次性把 4 个 model 写完)

## File Structure

```
rag-refactor/
├── pyproject.toml                          # 改: 加 sqlalchemy/alembic/psycopg
├── .gitignore                              # 改: 加 data/*.db
├── alembic.ini                             # 新建: alembic 配置
├── data/
│   └── .gitkeep                            # 新建: 占位, app.db 走 .gitignore
│
├── src/rag/storage/
│   ├── __init__.py                         # 新建: 公开 API
│   ├── base.py                             # 新建: DeclarativeBase
│   ├── engine.py                           # 新建: create_engine 工厂
│   ├── session.py                          # 新建: sessionmaker + context manager
│   ├── README.md                           # 新建: 切 PG 的一行配置
│   └── migrations/                         # 新建: alembic init 生成
│       ├── env.py
│       ├── script.py.mako
│       └── versions/                       # 起步空, 留 .gitkeep
│
├── src/rag/auth/
│   └── models.py                           # 新建: User
│
├── src/rag/chat/
│   └── models.py                           # 新建: Conversation, Message
│
└── src/rag/eval/
    └── models.py                           # 新建: Evaluation, EvaluationSample

tests/rag/storage/
    ├── __init__.py                         # 新建
    ├── conftest.py                         # 新建: tmp engine fixture
    ├── test_base.py                        # 新建
    ├── test_engine.py                      # 新建
    ├── test_session.py                     # 新建
    └── test_migrations.py                  # 新建: upgrade/downgrade 双向

tests/rag/auth/test_models.py               # 新建: User
tests/rag/chat/test_models.py               # 新建: Conversation, Message
tests/rag/eval/test_models.py               # 新建: Evaluation, EvaluationSample
```

## Public API

```python
# src/rag/storage/__init__.py
from .base import Base
from .engine import get_engine, init_db
from .session import get_session, session_scope

__all__ = ["Base", "get_engine", "init_db", "get_session", "session_scope"]
```

### `get_engine()`

- 读 `RAG_DB_URL` 环境变量, 默认 `sqlite:///data/app.db`
- 惰性单例 (模块级 `_engine: Engine | None = None`)
- SQLite 特化: `connect_args={"check_same_thread": False}`
- 全局: `pool_pre_ping=True`, `echo=False`
- 启动时 `print` 当前连接的 DB URL (调试用)

### `init_db()`

- 跑 `Base.metadata.create_all(get_engine())`
- **仅 dev/test 用**, 生产必须走 Alembic
- 受 `RAG_AUTO_CREATE_SCHEMA=1` 开关, 默认关
- 调用时 print WARN

### `session_scope()`

- `@contextmanager` 包装 session
- 成功 exit → commit, 异常 → rollback + 重新 raise
- 总是 close

```python
with session_scope() as s:
    s.add(User(name="alice"))
    # 退出时 commit; 中途异常 rollback
```

### `get_session()`

- `Generator[Session, None, None]`
- 配合 FastAPI `Depends`:

```python
@app.get("/items")
def list_items(s: Session = Depends(get_session)):
    return s.query(Item).all()
```

## SQLite 特殊处理

防 Windows file lock 沿用 `kg/audit.py` 修法:

```python
# engine.py
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 开库时设 journal_mode=DELETE, 避免 Windows 文件锁竞争"""
    if "sqlite" in str(dbapi_connection.engine.url):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
```

## Alembic 配置

**`alembic.ini`** (根目录):
- `script_location = src/rag/storage/migrations`
- `sqlalchemy.url = ` (留空, env.py 里读 env)

**`src/rag/storage/migrations/env.py`**:
- `target_metadata = Base.metadata` (import `from src.rag.storage import Base`)
- `from src.rag.storage.engine import _resolve_db_url` 拿 URL (避免循环 import)

**起步**:
- `alembic init src/rag/storage/migrations` 一次性生成
- `alembic revision --autogenerate -m "init"` 出一个空 migration (没 model, 留着占位)
- 后续 spec 加 model 时, 跑 `alembic revision --autogenerate -m "<feature>"` 自动出 diff

## Testing Strategy

### 单元测试 (pytest)

**`conftest.py`** 提供 fixture:
```python
@pytest.fixture
def tmp_engine(tmp_path):
    """每个 test 一个临时 SQLite 文件库, 跑完清理"""
    db_path = tmp_path / "test.db"
    os.environ["RAG_DB_URL"] = f"sqlite:///{db_path}"
    # 重置模块级 _engine 单例
    from src.rag.storage import engine as eng_mod
    eng_mod._engine = None
    yield get_engine()
    eng_mod._engine.dispose()
```

**`test_base.py`**:
- `Base` 是 `DeclarativeBase` 子类
- `Base.metadata` 是空 `MetaData()`

**`test_engine.py`**:
- 默认 URL = `sqlite:///data/app.db`
- 读 `RAG_DB_URL` env 覆盖
- SQLite 走 `check_same_thread=False`
- 重复调用 `get_engine()` 返回同一实例
- `init_db()` 在空 DB 上建表不报错

**`test_session.py`**:
- `session_scope()` commit 后数据可查
- `session_scope()` 抛异常后回滚, 数据不在
- `session_scope()` 总是 close
- `get_session()` (generator) 同样语义

### 集成测试

**`test_migrations.py`**:
- 临时 `tmp_path` 写文件库
- `alembic upgrade head` 成功
- `alembic downgrade -1` 成功 (从空降不下去也没事, 只要不报错)
- 跑完用 `Base.metadata.create_all` 起的库和 alembic 起的库表结构一致

## Dependencies

**`pyproject.toml`** 改 `[project.dependencies]`:
```toml
"sqlalchemy>=2.0",
"alembic>=1.13",
"psycopg[binary]>=3.2",  # PG 驱动, 现在装, 切时不动依赖
```

## .gitignore 追加

```
data/*.db
data/*.db-*
```

**`data/.gitkeep`** 占位 (空文件, 让 data/ 进 git, app.db 不进)。

## Out of Scope (留给后续 spec)

- 业务逻辑 (认证 / 聊天 / 评估接口) — 本 spec 只到 model 层
- Mem0 适配
- 数据搬运脚本 (sqlite → pg)
- `kg/audit.py` 重构 (它已经是 SQLite 直连, 不动, 后续可选择性接入)

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Windows file lock | `journal_mode=DELETE` event listener |
| 多线程竞争 (FastAPI sync endpoints) | `check_same_thread=False` |
| 切 PG 时 SQL 兼容性 | SQLAlchemy 2.0 `Mapped[]` 不写 raw SQL, 业务零改 |
| Alembic autogenerate 漏字段 | 加 model 后先 dry-run `alembic upgrade head --sql` 人工 review |

## Success Criteria

1. `from src.rag.storage import get_session, Base` 在其他模块可 import
2. `from src.rag.auth.models import User` / `from src.rag.chat.models import Conversation, Message` / `from src.rag.eval.models import Evaluation, EvaluationSample` 都可 import
3. `RAG_DB_URL=sqlite:///:memory:` 跑单元测试, 全绿
4. 4 个 model 的测试: 字段 / 约束 / 外键 CASCADE / UNIQUE 索引
5. 改 `RAG_DB_URL=postgresql+psycopg://...` 跑 `alembic upgrade head` 不报错 (虽然 spec 不验证 PG 实际连通)
6. `kg/audit.py` 不受影响, 现有测试全绿
7. 文档 `src/rag/storage/README.md` 写清切 PG 三步
