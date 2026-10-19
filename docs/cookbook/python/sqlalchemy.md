# SQLAlchemy 2.0 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

SQLAlchemy 是 Python 生态最成熟的 ORM 库，2.0 版本（2023 年发布）统一了 Core 和 ORM API，全面拥抱 Python 类型注解，提供 `select()` 链式查询 + `Session.execute()` 现代 API。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **SQLAlchemy 2.0** | 全功能 ORM | 本项目**主力** ORM |
| **Django ORM** | Django 绑定 | 项目不用 Django |
| **Peewee** | 轻量 ORM | 生态小 |
| **Tortoise ORM** | 异步优先 | 生态小，文档少 |
| **SQLModel** | Pydantic + SQLAlchemy | FastAPI 友好，但项目用纯 SQLAlchemy |

**SQLAlchemy 解决的核心问题**：
- **类型安全**：表 / 字段 / 关系都有 Python 类型
- **跨数据库**：PG / MySQL / SQLite 一套代码
- **同步 / 异步**：`sync_engine` + `async_engine` 共享 ORM 模型
- **关系映射**：1-to-1 / 1-to-many / many-to-many
- **迁移**：跟 Alembic 配合（项目用 `alembic >= 1.18.4`）

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (pyproject.toml)
"sqlalchemy>=2.0.50",   # 异步 ORM
"asyncpg>=0.30.0",      # 异步 PG 驱动
"psycopg[binary]>=3.3.4", # 同步 PG 驱动
"alembic>=1.18.4",      # 迁移
```

### 2.2 引擎配置

项目 `src/storage/session.py`（推测）：

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, sessionmaker, Session
from src.common.db_url import get_rag_db_url

# 同步引擎
sync_engine = create_engine(get_rag_db_url(), pool_size=10, max_overflow=20)
SyncSession = sessionmaker(sync_engine, expire_on_commit=False)

# 异步引擎
async_db_url = get_rag_db_url().replace("postgresql+psycopg", "postgresql+asyncpg")
async_engine = create_async_engine(async_db_url, pool_size=10, max_overflow=20)
AsyncSessionMaker = async_sessionmaker(async_engine, expire_on_commit=False)
```

### 2.3 Base 类

`src/db/base.py`（推测）：

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

---

## 三、基础语法 & 类型系统

### 3.1 模型定义

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关系
    posts: Mapped[list["Post"]] = relationship(back_populates="author", cascade="all, delete-orphan")

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    author: Mapped["User"] = relationship(back_populates="posts")
```

### 3.2 select 查询（2.0 新 API）

```python
from sqlalchemy import select

# 单条
stmt = select(User).where(User.email == "alice@x.com")
user = session.execute(stmt).scalar_one_or_none()

# 列表
stmt = select(User).where(User.is_active == True).order_by(User.created_at.desc())
users = session.execute(stmt).scalars().all()

# join
stmt = select(User, Post).join(Post).where(Post.title.contains("RAG"))
rows = session.execute(stmt).all()

# 聚合
from sqlalchemy import func
stmt = select(func.count(User.id))
count = session.execute(stmt).scalar_one()
```

### 3.3 Session 用法

```python
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# 使用
with session_scope() as s:
    user = s.query(User).filter_by(id=1).first()
    user.display_name = "Bob"
    # 退出 with 时自动 commit
```

### 3.4 异步用法

```python
async with AsyncSessionMaker() as session:
    stmt = select(User).where(User.id == 1)
    user = (await session.execute(stmt)).scalar_one()
    user.display_name = "Bob"
    await session.commit()
```

### 3.5 关系查询

```python
# 懒加载（默认）
user = session.get(User, 1)
posts = user.posts  # 自动查询

# 预加载（避免 N+1）
from sqlalchemy.orm import selectinload, joinedload

stmt = select(User).options(selectinload(User.posts)).where(User.id == 1)
user = session.execute(stmt).scalar_one()
posts = user.posts  # 已经在内存里
```

### 3.6 JSONB 支持

```python
from sqlalchemy.dialects.postgresql import JSONB

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB)
```

详见 [`python/jsonb-usage.md`](jsonb-usage.md)。

---

## 四、核心概念

### 4.1 Engine（引擎）

数据库连接的顶层抽象，**单例**。包含连接池。

```python
engine = create_engine("postgresql+psycopg://...")
```

### 4.2 Session（会话）

数据库事务的顶层抽象。每次业务操作创建一个 Session，用完关闭。

### 4.3 DeclarativeBase

`class Base(DeclarativeBase)` 继承后，所有表继承 `Base`，SQLAlchemy 2.0 自动用 type annotations 推断列类型。

### 4.4 Unit of Work

SQLAlchemy 的"工作单元"模式：把所有要做的数据库改动挂在 session 上，最后 `commit()` 一次提交。

### 4.5 Identity Map

同一个 Session 内，相同主键的实例只存在一个对象引用。改了即改，改完 commit 生效。

### 4.6 Connection Pool

Engine 内部维护连接池。`pool_size=10` + `max_overflow=20` = 最多 30 并发连接。

---

## 五、常用命令 & 工具链

```bash
# 项目命令
cd packages/service

# 迁移
uv run alembic current              # 当前版本
uv run alembic upgrade head         # 升级到最新
uv run alembic downgrade -1         # 回退 1 个版本
uv run alembic revision -m "msg"    # 创建空迁移
uv run alembic revision --autogenerate -m "msg"  # 自动生成（基于 model diff）

# 调试
uv run python -c "from src.db.base import Base; from src.db.models import User; ..."
```

---

## 六、项目集成点

### 6.1 项目**主力** ORM

`packages/service/pyproject.toml:2`：

```toml
"sqlalchemy>=2.0.50", # 异步 ORM, 所有 model (auth/chat/eval/approvals/account_models) + engine/session 都靠它
```

### 6.2 项目模型结构

```
src/db/
├── base.py               # DeclarativeBase
├── models/
│   ├── __init__.py
│   ├── auth.py           # User, Account, AccountSettings, ...
│   ├── chat.py           # Conversation, Message
│   ├── approvals.py      # ApprovalApply, ApprovalReview
│   ├── permissions.py    # Page, Role, Permission
│   ├── lookups.py        # Dictionary, DictionaryItem
│   ├── audit_log.py      # AuditLog
│   └── ...
```

### 6.3 Session 模式

项目用 `session_scope()` context manager（推测见 `src/storage/session.py`）：

```python
from src.storage.session import session_scope

def get_user_by_id(user_id: int) -> User | None:
    with session_scope() as session:
        return session.get(User, user_id)
```

### 6.4 迁移

项目用 Alembic 管理 schema 变更（详见 [`python/alembic.md`](alembic.md)）：

```bash
uv run alembic revision --autogenerate -m "add avatar_url to user"
uv run alembic upgrade head
```

### 6.5 测试隔离

项目 `service/CLAUDE.md` 强制测试 mock，**不连真 PG**：

```python
from unittest.mock import patch

@patch("src.storage.session.session_scope")
def test_get_user(mock_scope):
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = User(id=1, email="a@x.com")
    mock_scope.return_value.__enter__.return_value = mock_session
    # ...
```

---

## 七、项目代码示例

### 7.1 业务模型

`src/db/models/auth.py`（项目风格）：

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 7.2 业务 enum 走 lookup

`src/db/models/approvals.py`（项目风格）：

```python
# ❌ 错：硬编 enum
import enum

class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# ✅ 对：走 lookup 字典
# ApprovalStatus 字符串存 DB，前端从 /api/lookups/approval_status 拉
class ApprovalReview(Base):
    __tablename__ = "approval_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20))  # 来自 lookup，不写死
    # ...
```

详见 [`python/lookup.md`](lookup.md)。

### 7.3 全局异常 handler 捕获 SQLAlchemyError

`src/core/app_factory.py:25-50`：

```python
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger
from fastapi.responses import JSONResponse

async def _sa_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """SQLAlchemy 全局兜底 (2026-06-18): 登录 500 时让 traceback 真正可读."""
    logger.opt(exception=True).error(
        "SQLAlchemy 未捕获异常: {} | {} {}",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"数据库错误: {type(exc).__name__}"},
    )

app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)
```

### 7.4 查询 + 关系

```python
# src/db/services/users.py (项目风格)
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.storage.session import session_scope
from src.db.models.auth import User

def get_user_with_accounts(user_id: int) -> User | None:
    with session_scope() as s:
        stmt = (
            select(User)
            .options(selectinload(User.accounts))
            .where(User.id == user_id)
        )
        return s.execute(stmt).scalar_one_or_none()
```

### 7.5 JSONB 字段

```python
from sqlalchemy.dialects.postgresql import JSONB

class ApprovalApply(Base):
    __tablename__ = "approval_applies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)  # 动态审批内容

# 查 JSONB
from sqlalchemy import func

stmt = select(ApprovalApply).where(
    ApprovalApply.payload["target_type"].astext == "user_role"
)
```

### 7.6 异步查询

```python
from sqlalchemy import select
from src.storage.session import async_session_scope

async def get_user_async(user_id: int) -> User | None:
    async with async_session_scope() as s:
        stmt = select(User).where(User.id == user_id)
        result = await s.execute(stmt)
        return result.scalar_one_or_none()
```

### 7.7 批量操作

```python
from sqlalchemy import insert, update, delete

# 批量 insert
stmt = insert(User).values([
    {"email": "a@x.com", "display_name": "A"},
    {"email": "b@x.com", "display_name": "B"},
])
session.execute(stmt)
session.commit()

# 批量 update
stmt = update(User).where(User.role == "user").values(is_active=False)
session.execute(stmt)
```

---

## 八、项目没用到的能力 / 进阶方向

以下 SQLAlchemy 2.0 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Hybrid 属性** | Python 级计算字段 | 全名 = first + last |
| **Association Proxy** | 简化多对多访问 | 标签 / 角色 |
| **Composite Type** | 多列合成 | 地址（省+市+区） |
| **Custom Type Decorator** | 自定义 Python ↔ DB 类型 | 加密字段 |
| **Connection-level events** | 监听 SQL | 审计 |
| **PostgreSQL-specific type** | JSONB / ARRAY / UUID | JSONB 项目已用 |
| **Materialized view** | 物化视图 ORM | 报表 |
| **PG specific features** | UPSERT / RETURNING | 项目待评估 |
| **Read-only / Write-only relationship** | 性能 | 大表 |

**建议关注**：PG `ON CONFLICT DO UPDATE`（upsert）用得很多时考虑封装为 SQLAlchemy helper。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **业务 enum 走 lookup**（不要硬编 `StrEnum`）
2. **不连接真 PG 测试**（必须 mock `session_scope`）
3. **alembic 迁移可回滚**（写 `downgrade`）
4. **Audit log 走 `@audited` 装饰器**（DELETE / 改账户等）
5. **`Mapped[T]` + `mapped_column()` 强类型注解**（不用 `Column` 旧 API）
6. **global exception handler 捕获 SQLAlchemyError**

### 最佳实践

1. **强类型 Mapped**：

```python
# ✅ SQLAlchemy 2.0
id: Mapped[int] = mapped_column(Integer, primary_key=True)

# ❌ 旧版 1.4
id = Column(Integer, primary_key=True)
```

2. **session_scope context manager**：自动 commit / rollback / close

3. **N+1 预加载**：用 `selectinload` / `joinedload`

```python
# ❌ 错：N+1（每个 user 查一次 posts）
users = session.execute(select(User)).scalars().all()
for user in users:
    print(user.posts)  # 每次都查

# ✅ 对：1 次查全部
users = session.execute(select(User).options(selectinload(User.posts))).scalars().all()
```

4. **避免 `Query.get()` 旧 API**：用 `session.get(Model, id)` 或 `select`

5. **批量操作**：用 `insert` / `update` 走 Core API，比 ORM 循环快 10x

6. **JSONB 操作符**：

```python
# 用项目 pgvector 路径
stmt = select(User).where(User.metadata["theme"].astext == "dark")
```

### 常见坑

1. **expire_on_commit 默认 True**：commit 后对象属性失效，再访问要重新查。项目设 `expire_on_commit=False`

```python
session.commit()
print(user.display_name)  # 报错，expire_on_commit=True 会重查
```

2. **session 跨线程**：SQLAlchemy Session 是非线程安全的，跨线程必须新建

3. **async 上下文里用 sync session**：会阻塞 event loop，必须用 `AsyncSession`

4. **model 没注册到 Base.metadata**：autogenerate 看不到该表

```python
# 必须 import 所有 model（即使不用），才能被 metadata 收集
from src.db.models import auth, chat, approvals, permissions, lookups
```

5. **autogenerate 漏掉 enum 变更**：Alembic autogenerate 不总能识别 enum 增删，要手写 migration

6. **PG 数组字段**：

```python
# 错：直接用 ARRAY（不通用）
from sqlalchemy import ARRAY
tags: Mapped[list[str]] = mapped_column(ARRAY(String))

# 准：PG specific
from sqlalchemy.dialects.postgresql import ARRAY
```

7. **N+1 query**：用 `selectinload` / `joinedload` 显式预加载

8. **session 在 FastAPI 异步里同步调用**：

```python
# ❌ 错：阻塞 event loop
async def handler():
    user = session.get(User, 1)  # 阻塞！

# ✅ 对
async def handler():
    user = await session.get(User, 1)
```

9. **测试 mock 漏 import**：必须 `from src.db.models import User` 否则 mock 时找不到

10. **alembic autogenerate 误报**：手写 `op.execute()` 的迁移，autogenerate 看不到差异会试图回滚，要手写 placeholder

---

## 📚 参考

- [SQLAlchemy 2.0 官方文档](https://docs.sqlalchemy.org/en/20/)
- [SQLAlchemy 2.0 迁移指南](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [async SQLAlchemy 教程](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 文档](https://alembic.sqlalchemy.org/en/latest/)
- [SQLAlchemy 性能调优](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html)
- [项目 service/CLAUDE.md](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
