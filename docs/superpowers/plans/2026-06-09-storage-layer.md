# Storage Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给项目一个统一的 SQLAlchemy 2.0 + Alembic 存储层 + 4 业务 model (User/Conversation/Message/Evaluation/EvaluationSample), SQLite 现在跑, PostgreSQL 切 env 即用.

**Architecture:** `src/rag/storage/` 提供 `Base` / `get_engine` / `get_session` / `session_scope` / `init_db` 5 个公开 API; 4 业务 model 各放各的 `models.py` (auth/chat/eval), 全部 import 同一 `Base`; Alembic 起步空, 加 model 跑 autogenerate 自动出 migration.

**Tech Stack:** Python 3.14 / SQLAlchemy 2.0 / Alembic 1.13 / pytest 9 / uv (项目已有).

**Spec:** [2026-06-09-storage-layer-design.md](../specs/2026-06-09-storage-layer-design.md)

**实施约束:**
- 中文注释 (`web/CLAUDE.md` + 项目 `CLAUDE.md` 强制)
- 函数/类 < 100 行 (`CLAUDE.md` 强制)
- TDD: 红 → 绿 → commit
- 测试文件放 `tests/<mirror path>/test_*.py`
- 跑测试用 `uv run --no-sync python -m pytest` (Windows `uv run pytest` 报 "uv trampoline failed to canonicalize script path", 必须用 --no-sync + python -m; Task 0 经验)

---

## File Structure (创建的文件)

```
rag-refactor/
├── pyproject.toml                          # 改: +sqlalchemy +alembic +psycopg
├── .gitignore                              # 改: +data/*.db +data/*.db-*
├── alembic.ini                             # 新建
├── data/
│   └── .gitkeep                            # 新建 (空)
│
├── src/rag/storage/
│   ├── __init__.py                         # Task 5: 公开 API
│   ├── base.py                             # Task 1: DeclarativeBase
│   ├── engine.py                           # Task 2-3: create_engine 工厂
│   ├── session.py                          # Task 4: sessionmaker + context manager
│   ├── README.md                           # Task 14: 切 PG 文档
│   └── migrations/
│       ├── env.py                          # Task 10: Alembic 启动钩子
│       ├── script.py.mako                  # Task 9: alembic init 生成
│       ├── versions/
│       │   └── .gitkeep                    # Task 9: 占位
│
├── src/rag/auth/
│   ├── __init__.py                         # Task 6: 空
│   └── models.py                           # Task 6: User
│
├── src/rag/chat/
│   ├── __init__.py                         # Task 7: 空
│   └── models.py                           # Task 7: Conversation, Message
│
├── src/rag/eval/
│   ├── __init__.py                         # Task 8: 空
│   └── models.py                           # Task 8: Evaluation, EvaluationSample
│
├── tests/rag/
│   ├── __init__.py                         # 各 task: 空
│   ├── storage/
│   │   ├── __init__.py                     # Task 1: 空
│   │   ├── conftest.py                     # Task 0: 共享 fixture
│   │   ├── test_base.py                    # Task 1
│   │   ├── test_engine.py                  # Task 2-3
│   │   ├── test_session.py                 # Task 4
│   │   └── test_migrations.py              # Task 12
│   ├── auth/
│   │   ├── __init__.py                     # Task 6: 空
│   │   └── test_models.py                  # Task 6
│   ├── chat/
│   │   ├── __init__.py                     # Task 7: 空
│   │   └── test_models.py                  # Task 7
│   └── eval/
│       ├── __init__.py                     # Task 8: 空
│       └── test_models.py                  # Task 8
```

---

## Task 0: 项目级依赖 + .gitignore

**Files:**
- Modify: `pyproject.toml:21` (dependencies 段追加)
- Modify: `.gitignore` (追加 data/*.db 规则)
- Create: `data/.gitkeep` (空文件)
- Create: `tests/rag/storage/conftest.py` (共享 fixture, 后续 task 复用)

- [ ] **Step 1: 装依赖**

```bash
cd C:/doc/Code/worktrees/rag-refactor
uv add sqlalchemy alembic "psycopg[binary]"
```

- [ ] **Step 2: 验证版本**

```bash
uv run python -c "import sqlalchemy, alembic, psycopg; print(sqlalchemy.__version__, alembic.__version__, psycopg.__version__)"
```

Expected: `2.0.x 1.x.x 3.x` (具体版本号, 至少 SQLAlchemy 是 2.0+)

- [ ] **Step 3: 改 .gitignore**

在文件末尾追加:
```
# SQLite 数据库文件 (storage layer, 2026-06-09)
data/*.db
data/*.db-*
```

- [ ] **Step 4: 建 data/ 占位**

```bash
mkdir -p data
touch data/.gitkeep
```

- [ ] **Step 5: 写 conftest.py** (后续 task 都要用)

文件 `tests/rag/storage/conftest.py`:

```python
"""storage 层测试共享 fixture

每个 test 一个临时 SQLite 文件库 + 重置模块级 _engine 单例, 避免测试间污染。

⚠️ 不在 fixture 里 Base.metadata.clear(): 业务 model (User/Conversation/...) 在 import 时注册,
    清空会破坏 Task 6-8 后续 model 测试。临时 model 用不同 __tablename__ 规避冲突 (Task 4 经验)。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_url(tmp_path: Path) -> str:
    """返回临时 SQLite 文件 URL, 写 conftest 帮你 cleanup"""
    db_path = tmp_path / "test.db"
    return f"sqlite:///{db_path}"


@pytest.fixture
def reset_storage_engine(monkeypatch: pytest.MonkeyPatch, tmp_db_url: str):
    """设置 RAG_DB_URL env + 重置 storage.engine 模块级 _engine 单例"""
    monkeypatch.setenv("RAG_DB_URL", tmp_db_url)
    # 重置单例 (后续 task 才会用到, 提前 import-safe)
    from src.rag.storage import engine as engine_mod

    engine_mod._engine = None
    yield
    # teardown: 释放 engine 句柄, Windows 才能删文件
    if engine_mod._engine is not None:
        engine_mod._engine.dispose()
        engine_mod._engine = None
```

- [ ] **Step 6: 跑现有测试确保没破坏**

```bash
uv run --no-sync python -m pytest tests/test_kg_neo4j.py -q
```

Expected: 全部通过 (没动到 neo4j 代码, 应该 PASS)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore data/.gitkeep tests/rag/storage/conftest.py
git commit -m "chore(deps): 加 sqlalchemy + alembic + psycopg; storage 测试 fixture"
```

---

## Task 1: Base (DeclarativeBase)

**Files:**
- Create: `src/rag/storage/__init__.py` (空, 后续 task 填)
- Create: `src/rag/storage/base.py`
- Create: `tests/rag/storage/__init__.py` (空)
- Create: `tests/rag/storage/test_base.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/storage/test_base.py`:

```python
"""base.py 测试: Base 是 DeclarativeBase 子类, metadata 可用"""
from src.rag.storage.base import Base


def test_base_is_declarative_base():
    """Base 必须是 SQLAlchemy DeclarativeBase 子类, 2.0+ 写法"""
    from sqlalchemy.orm import DeclarativeBase

    assert issubclass(Base, DeclarativeBase)


def test_base_metadata_is_empty():
    """起步没任何 model 时 metadata 应为空"""
    assert len(Base.metadata.tables) == 0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_base.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.storage.base'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/storage/base.py`:

```python
"""SQLAlchemy 2.0 DeclarativeBase

所有业务 model (User / Conversation / Message / Evaluation / EvaluationSample) 都继承这个 Base。
metadata 在这里维护, Alembic autogenerate 拿这个生成 migration。
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """项目所有 SQLAlchemy model 的基类"""
    pass
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_base.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/storage/base.py tests/rag/storage/test_base.py
git commit -m "feat(storage): DeclarativeBase"
```

---

## Task 2: Engine — URL 解析 + 单例 + SQLite PRAGMA

**Files:**
- Create: `src/rag/storage/engine.py`
- Create: `tests/rag/storage/test_engine.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/storage/test_engine.py`:

```python
"""engine.py 测试: URL 解析 + 单例 + SQLite PRAGMA"""
from __future__ import annotations


def test_resolve_db_url_default(monkeypatch):
    """不配 RAG_DB_URL 时默认 sqlite:///data/app.db"""
    monkeypatch.delenv("RAG_DB_URL", raising=False)
    from src.rag.storage.engine import _resolve_db_url

    assert _resolve_db_url() == "sqlite:///data/app.db"


def test_resolve_db_url_from_env(monkeypatch, tmp_db_url):
    """配 RAG_DB_URL 时读 env"""
    monkeypatch.setenv("RAG_DB_URL", tmp_db_url)
    from src.rag.storage.engine import _resolve_db_url

    assert _resolve_db_url() == tmp_db_url


def test_get_engine_returns_singleton(reset_storage_engine, tmp_db_url):
    """get_engine() 重复调用返回同一 Engine 实例 (单例)"""
    from src.rag.storage.engine import get_engine

    e1 = get_engine()
    e2 = get_engine()
    assert e1 is e2
    # URL 是测试库
    assert str(e1.url) == tmp_db_url


def test_sqlite_check_same_thread_false(reset_storage_engine, tmp_db_url):
    """SQLite 必须 check_same_thread=False (FastAPI 多线程)"""
    from src.rag.storage.engine import get_engine

    eng = get_engine()
    # 通过 dialect 拿 connect_args
    assert eng.dialect.name == "sqlite"
    # 实际连接验证
    with eng.connect() as conn:
        # 多次连接不报错 = check_same_thread=False 生效
        pass
    with eng.connect() as conn:
        pass


def test_sqlite_journal_mode_delete(reset_storage_engine, tmp_db_url):
    """SQLite 开库时设 PRAGMA journal_mode=DELETE (防 Windows 文件锁)"""
    from sqlalchemy import text
    from src.rag.storage.engine import get_engine

    eng = get_engine()
    with eng.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result.lower() == "delete"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_engine.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.storage.engine'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/storage/engine.py`:

```python
"""SQLAlchemy Engine 工厂

- _resolve_db_url(): 读 RAG_DB_URL env, 默认 sqlite:///data/app.db
- get_engine(): 惰性单例, SQLite 加 check_same_thread=False, 全局 pool_pre_ping=True
- _set_sqlite_pragma: event listener, SQLite 开库时设 journal_mode=DELETE
- init_db(): dev/test 跑 create_all, 受 RAG_AUTO_CREATE_SCHEMA 开关
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from .base import Base

DEFAULT_DB_URL = "sqlite:///data/app.db"
_engine: Engine | None = None


def _resolve_db_url() -> str:
    """读 RAG_DB_URL, 默认 SQLite 本地文件"""
    return os.getenv("RAG_DB_URL", DEFAULT_DB_URL)


def _make_engine(url: str) -> Engine:
    """根据 URL 创建 Engine

    SQLite 特化: check_same_thread=False (FastAPI 多线程)
    全局: pool_pre_ping=True (防连接过期, 切 PG 后必需)
    """
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 开库时设 PRAGMA, 避免 Windows 文件锁竞争

    journal_mode=DELETE: 不用 WAL, 避免 -wal/-shm 残留文件
    synchronous=NORMAL: 性能/安全平衡, 单进程 OK
    """
    # dbapi_connection 是 raw DBAPI 连接 (如 sqlite3.Connection), 没有 .engine 属性
    # 用模块名判断 (Task 2 经验: dbapi_connection.engine.url 不存在)
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # SQLite 默认关闭 FK 强制, 开了才能 enforce ForeignKey + ON DELETE CASCADE
        # (Task 7 经验: 不开这一行, CASCADE 测试全失败)
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine() -> Engine:
    """惰性单例 Engine"""
    global _engine
    if _engine is None:
        url = _resolve_db_url()
        _engine = _make_engine(url)
        print(f"[storage] engine init: {url}")
    return _engine


def init_db() -> None:
    """建表 (仅 dev/test 用, 生产走 Alembic)

    受 RAG_AUTO_CREATE_SCHEMA=1 开关, 默认关闭 (保护生产)。
    """
    if os.getenv("RAG_AUTO_CREATE_SCHEMA") != "1":
        print("[storage] init_db skipped (set RAG_AUTO_CREATE_SCHEMA=1 to enable)")
        return
    print("[storage] WARN: 自动建表, 仅限 dev/test")
    Base.metadata.create_all(get_engine())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_engine.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/storage/engine.py tests/rag/storage/test_engine.py
git commit -m "feat(storage): engine 工厂 + SQLite PRAGMA + 单例"
```

---

## Task 3: Init DB (create_all) 开关

**Files:**
- Modify: `tests/rag/storage/test_engine.py` (追加 test)

- [ ] **Step 1: 追加失败测试**

先在 `tests/rag/storage/test_engine.py` 顶部 import 后面加一行模块级 import (Task 3 经验: `from __future__ import annotations` 不解决 Mapped lookup, SQLAlchemy 解析 `Mapped` 时查模块级 globals):

```python
from sqlalchemy.orm import Mapped, mapped_column  # noqa: F401
```

然后在 `tests/rag/storage/test_engine.py` 末尾追加:

```python
def test_init_db_disabled_by_default(reset_storage_engine, monkeypatch, capsys):
    """不配 RAG_AUTO_CREATE_SCHEMA=1 时 init_db 跳过"""
    monkeypatch.delenv("RAG_AUTO_CREATE_SCHEMA", raising=False)
    from src.rag.storage.engine import init_db, get_engine
    from src.rag.storage.base import Base

    init_db()
    # 没建表: Base 触不到任何表
    assert len(Base.metadata.tables) == 0
    captured = capsys.readouterr()
    assert "skipped" in captured.out


def test_init_db_enabled_creates_tables(reset_storage_engine, monkeypatch, capsys):
    """配 RAG_AUTO_CREATE_SCHEMA=1 时 init_db 跑 create_all"""
    monkeypatch.setenv("RAG_AUTO_CREATE_SCHEMA", "1")
    from src.rag.storage.engine import init_db
    from src.rag.storage.base import Base

    # 先定义一个临时 model 让 create_all 有活干
    class _TempModel(Base):
        __tablename__ = "_temp_test"
        id: Mapped[int] = mapped_column(primary_key=True)

    init_db()
    # 验证表真的建了
    eng = __import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine()
    with eng.connect() as conn:
        from sqlalchemy import text
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='_temp_test'")).all()
        assert len(rows) == 1
    captured = capsys.readouterr()
    assert "WARN" in captured.out
```

**测试顺序**: 追加到文件末尾, `test_init_db_disabled_by_default` 必须先于 `test_init_db_enabled_creates_tables` 跑 (后者定义 `_TempModel` 注册到 `Base.metadata`, 一旦跑了污染全局). pytest 默认文件内 source order, 追加末尾天然 OK.

- [ ] **Step 2: 跑测试**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_engine.py::test_init_db_disabled_by_default tests/rag/storage/test_engine.py::test_init_db_enabled_creates_tables -v
```

Expected: 2 passed (init_db 实现已在 Task 2 写过, 这两个测试应该直接通过)

- [ ] **Step 3: Commit**

```bash
git add tests/rag/storage/test_engine.py
git commit -m "test(storage): init_db 开关测试"
```

---

## Task 4: Session (sessionmaker + context manager + FastAPI Depends)

**Files:**
- Create: `src/rag/storage/session.py`
- Create: `tests/rag/storage/test_session.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/storage/test_session.py`:

```python
"""session.py 测试: session_scope commit/rollback + get_session generator"""
from __future__ import annotations

# 模块级 import, 让 SQLAlchemy 在 storage.test_session 命名空间能解析 Mapped
# (Task 3/4 经验: Mapped lookup 走模块 globals, 函数级 import 不行)
from sqlalchemy.orm import Mapped, mapped_column  # noqa: F401


def test_session_scope_commit_persists(reset_storage_engine, tmp_db_url):
    """session_scope 正常 exit 后 commit, 数据可查"""
    from src.rag.storage.base import Base
    from src.rag.storage.session import session_scope

    class _WidgetCommit(Base):
        __tablename__ = "widgets_commit"  # 每个 test 用不同表名, 避免 Base.metadata 冲突
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(_WidgetCommit(name="alice"))
    # exit 后能查到
    with session_scope() as s:
        assert s.query(_WidgetCommit).filter_by(name="alice").count() == 1


def test_session_scope_rollback_on_exception(reset_storage_engine, tmp_db_url):
    """session_scope 抛异常时 rollback, 数据不入库"""
    import pytest
    from src.rag.storage.base import Base
    from src.rag.storage.session import session_scope

    class _WidgetRollback(Base):
        __tablename__ = "widgets_rollback"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    class _Marker(Exception):
        pass

    with pytest.raises(_Marker):
        with session_scope() as s:
            s.add(_WidgetRollback(name="bob"))
            raise _Marker("boom")

    # rollback 后查不到
    with session_scope() as s:
        assert s.query(_WidgetRollback).filter_by(name="bob").count() == 0


def test_get_session_yields_and_closes(reset_storage_engine, tmp_db_url):
    """get_session() 是 generator, 用完自动 close"""
    from sqlalchemy.orm import Session
    from src.rag.storage.base import Base
    from src.rag.storage.session import get_session

    class _WidgetGen(Base):
        __tablename__ = "widgets_gen"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column()

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    gen = get_session()
    s = next(gen)
    assert isinstance(s, Session)
    s.add(_WidgetGen(name="carol"))
    s.commit()
    # close
    import pytest
    with pytest.raises(StopIteration):
        next(gen)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_session.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.storage.session'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/storage/session.py`:

```python
"""Session 工厂

- session_scope(): context manager, commit on success / rollback on exception
- get_session(): generator 给 FastAPI Depends 用

⚠️ 不在模块级 bind engine: 测试场景 dispose + 重建 engine 后, 模块级 SessionLocal
    还在旧 engine 上, session 会找不到新表 (Task 4 经验)。每次调用重新拿 engine 重建。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from .engine import get_engine


def _make_session() -> Session:
    """懒构造 session, 每次重新拿 engine 重建 sessionmaker"""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """事务作用域: 成功 commit, 异常 rollback, 总是 close

    用法:
        with session_scope() as s:
            s.add(user)
    """
    session = _make_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Generator[Session, None, None]:
    """FastAPI Depends 用的 generator

    用法:
        @app.get("/items")
        def list_items(s: Session = Depends(get_session)):
            ...
    """
    session = _make_session()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_session.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/storage/session.py tests/rag/storage/test_session.py
git commit -m "feat(storage): session_scope + get_session"
```

---

## Task 5: 公开 API (storage 包 __init__)

**Files:**
- Modify: `src/rag/storage/__init__.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/storage/test_init_exports.py`:

```python
"""storage 包公开 API 测试: 5 个导出都从顶层 import 可用"""
def test_storage_top_level_imports():
    from src.rag.storage import Base, get_engine, init_db, get_session, session_scope

    # 都是 callable / 类, 不是 None
    assert Base is not None
    assert callable(get_engine)
    assert callable(init_db)
    assert callable(get_session)
    assert callable(session_scope)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_init_exports.py -v
```

Expected: FAIL `ImportError: cannot import name 'init_db' from 'src.rag.storage'`

- [ ] **Step 3: 写实现**

文件 `src/rag/storage/__init__.py`:

```python
"""SQLAlchemy 2.0 存储层

公开 API:
- Base: DeclarativeBase, 业务 model 都继承
- get_engine: 惰性单例 Engine
- init_db: create_all (dev/test 用, 受 env 开关)
- session_scope: 事务 context manager
- get_session: FastAPI Depends 用的 generator

切 PostgreSQL: 改 RAG_DB_URL 环境变量, 跑 alembic upgrade head
"""
from .base import Base
from .engine import get_engine, init_db
from .session import get_session, session_scope

__all__ = ["Base", "get_engine", "init_db", "get_session", "session_scope"]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_init_exports.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/storage/__init__.py tests/rag/storage/test_init_exports.py
git commit -m "feat(storage): 公开 API 汇总"
```

---

## Task 6: User Model

**Files:**
- Create: `src/rag/auth/__init__.py` (空)
- Create: `src/rag/auth/models.py`
- Create: `tests/rag/auth/__init__.py` (空)
- Create: `tests/rag/auth/test_models.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/auth/test_models.py`:

```python
"""User model 测试: 字段 + 约束 + UNIQUE public_token + 索引"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


def test_user_create_and_query(reset_storage_engine):
    """User 基础创建+查询"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        u = User(public_token="abc123", display_name="alice")
        s.add(u)
    with session_scope() as s:
        found = s.query(User).filter_by(public_token="abc123").one()
        assert found.display_name == "alice"
        assert found.id is not None
        assert found.created_at is not None
        assert found.last_seen_at is not None


def test_user_public_token_unique(reset_storage_engine):
    """public_token 必须 UNIQUE, 重复插入报错"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(User(public_token="dup"))
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(User(public_token="dup"))


def test_user_public_token_not_null(reset_storage_engine):
    """public_token NOT NULL, 空字符串也允许 (业务校验长度)"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(User(public_token=None))  # type: ignore[arg-type]


def test_user_display_name_optional(reset_storage_engine):
    """display_name 可空"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(User(public_token="noname"))
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="noname").one()
        assert u.display_name is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/auth/test_models.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.auth.models'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/auth/models.py`:

```python
"""User model: 客户端匿名 token + Mem0 关联"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class User(Base):
    """客户端匿名用户

    - public_token: 32 字节 hex, 客户端存的; 首次访问 /api/auth/anon 后端生成 + 落库
    - last_seen_at: 清理冷用户的依据 (后续脚本扫描)
    - display_name: 后续用户填昵称 (本 spec 不用)
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} token={self.public_token[:8]}…>"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/auth/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/auth/ tests/rag/auth/
git commit -m "feat(auth): User model + 测试"
```

---

## Task 7: Conversation + Message Models

**Files:**
- Create: `src/rag/chat/__init__.py` (空)
- Create: `src/rag/chat/models.py`
- Create: `tests/rag/chat/__init__.py` (空)
- Create: `tests/rag/chat/test_models.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/chat/test_models.py`:

```python
"""Conversation + Message model 测试"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


def test_conversation_create(reset_storage_engine):
    """Conversation 基础创建"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.chat.models import Conversation
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(User(public_token="tok-conv"))
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-conv").one()
        s.add(Conversation(id="uuid-conv-1", user_id=u.id, title="测试会话"))
    with session_scope() as s:
        c = s.query(Conversation).filter_by(id="uuid-conv-1").one()
        assert c.title == "测试会话"
        assert c.message_count == 0
        assert c.user_id is not None


def test_conversation_user_id_fk_required(reset_storage_engine):
    """Conversation.user_id 必须有 (FK)"""
    from src.rag.storage import Base
    from src.rag.chat.models import Conversation
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(Conversation(id="orphan", user_id=999, title="x"))


def test_message_create_and_cascade_delete(reset_storage_engine):
    """Message 基础创建 + Conversation 删时 CASCADE"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.chat.models import Conversation, Message
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        u = User(public_token="tok-msg")
        s.add(u)
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-msg").one()
        c = Conversation(id="uuid-msg", user_id=u.id, title="t")
        s.add(c)
    with session_scope() as s:
        c = s.query(Conversation).filter_by(id="uuid-msg").one()
        s.add(Message(conversation_id=c.id, role="user", content="hi"))
    with session_scope() as s:
        s.delete(s.query(Conversation).filter_by(id="uuid-msg").one())
    with session_scope() as s:
        assert s.query(Message).count() == 0  # CASCADE


def test_message_role_required(reset_storage_engine):
    """Message.role NOT NULL"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.chat.models import Conversation, Message
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        u = User(public_token="tok-role")
        s.add(u)
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-role").one()
        s.add(Conversation(id="uuid-role", user_id=u.id, title="t"))
    with session_scope() as s:
        c = s.query(Conversation).filter_by(id="uuid-role").one()
        c_id = c.id
    # pytest.raises 在外: session_scope 提交时 (退出时) 才会触发 IntegrityError
    # (Task 7 经验: 嵌套反了 pytest 收不到异常)
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(Message(conversation_id=c_id, role=None, content="x"))  # type: ignore[arg-type]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/chat/test_models.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.chat.models'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/chat/models.py`:

```python
"""Conversation + Message models: 聊天会话/消息"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..storage import Base


class Conversation(Base):
    """聊天会话

    - id 用 UUID 字符串, 跟前端 crypto.randomUUID() 兼容
    - message_count 冗余, 减少 COUNT(*)
    - (user_id, updated_at DESC) 复合索引, 列表查询"最近对话"
    """
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r}>"


class Message(Base):
    """单条聊天消息

    - role: user / assistant / system
    - meta: token 用量 / 模型名 / 工具调用 (JSON, 后续可加)
    - (conversation_id, created_at) 复合索引, 按时间正序拉
    """
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conv={self.conversation_id} role={self.role}>"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/chat/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/chat/ tests/rag/chat/
git commit -m "feat(chat): Conversation + Message models + CASCADE 测试"
```

---

## Task 8: Evaluation + EvaluationSample Models

**Files:**
- Create: `src/rag/eval/__init__.py` (空)
- Create: `src/rag/eval/models.py`
- Create: `tests/rag/eval/__init__.py` (空)
- Create: `tests/rag/eval/test_models.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/eval/test_models.py`:

```python
"""Evaluation + EvaluationSample model 测试"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


def test_evaluation_create(reset_storage_engine):
    """Evaluation 基础创建 + avg_metrics JSON 存取"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.eval.models import Evaluation
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(User(public_token="tok-eval"))
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-eval").one()
        avg = {"faithfulness": 0.8, "answer_relevancy": 0.7}
        s.add(Evaluation(
            user_id=u.id, dataset_name="test.csv", status="completed",
            total_samples=10, successful=10, failed=0, concurrency=5,
            avg_metrics=avg, duration_seconds=12.5,
        ))
    with session_scope() as s:
        e = s.query(Evaluation).filter_by(dataset_name="test.csv").one()
        assert e.status == "completed"
        assert e.avg_metrics == avg
        assert e.finished_at is None  # 测试没设


def test_evaluation_status_not_null(reset_storage_engine):
    """status NOT NULL"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.eval.models import Evaluation
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        s.add(User(public_token="tok-status"))
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-status").one()
        u_id = u.id
    # pytest.raises 在外: session_scope 提交时才触发 IntegrityError (Task 7/8 经验)
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(Evaluation(user_id=u_id, status=None, dataset_name="x"))  # type: ignore[arg-type]


def test_evaluation_sample_create_and_cascade(reset_storage_engine):
    """EvaluationSample 创建 + Evaluation 删时 CASCADE"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.eval.models import Evaluation, EvaluationSample
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        u = User(public_token="tok-samp")
        s.add(u)
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-samp").one()
        e = Evaluation(user_id=u.id, dataset_name="x", status="running")
        s.add(e)
    with session_scope() as s:
        e = s.query(Evaluation).filter_by(dataset_name="x").one()
        s.add(EvaluationSample(
            evaluation_id=e.id, index=1, question="q1",
            answer="a1", metrics={"faithfulness": 0.9}, duration_ms=1200,
        ))
    # 删 evaluation
    with session_scope() as s:
        s.delete(s.query(Evaluation).filter_by(dataset_name="x").one())
    with session_scope() as s:
        assert s.query(EvaluationSample).count() == 0  # CASCADE


def test_evaluation_sample_contexts_json(reset_storage_engine):
    """contexts 存 JSON list[str]"""
    from src.rag.storage import Base
    from src.rag.auth.models import User
    from src.rag.eval.models import Evaluation, EvaluationSample
    from src.rag.storage.session import session_scope

    Base.metadata.create_all(__import__("src.rag.storage.engine", fromlist=["get_engine"]).get_engine())

    with session_scope() as s:
        u = User(public_token="tok-ctx")
        s.add(u)
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="tok-ctx").one()
        e = Evaluation(user_id=u.id, dataset_name="x", status="running")
        s.add(e)
    with session_scope() as s:
        e = s.query(Evaluation).filter_by(dataset_name="x").one()
        s.add(EvaluationSample(
            evaluation_id=e.id, index=1, question="q",
            contexts=["ctx1", "ctx2"],
        ))
    with session_scope() as s:
        samp = s.query(EvaluationSample).filter_by(index=1).one()
        assert samp.contexts == ["ctx1", "ctx2"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_models.py -v
```

Expected: FAIL `ModuleNotFoundError: No module named 'src.rag.eval.models'`

- [ ] **Step 3: 写最小实现**

文件 `src/rag/eval/models.py`:

```python
"""Evaluation + EvaluationSample models: 评估批/评估条"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..storage import Base


class Evaluation(Base):
    """一次评估任务 (元数据)

    - status: pending / running / completed / failed / cancelled
    - avg_metrics: {faithfulness, answer_relevancy, context_precision, context_recall}
    - (user_id, created_at DESC) 复合索引, 历史列表
    """
    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_evaluations_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    avg_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    samples: Mapped[list["EvaluationSample"]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Evaluation id={self.id} status={self.status}>"


class EvaluationSample(Base):
    """评估批里的一条样本

    - question/answer/ground_truth/contexts 全文存, 详情页能复原
    - metrics 存 JSON dict (4 指标)
    - (evaluation_id, index) 复合索引, 按序展示
    """
    __tablename__ = "evaluation_samples"
    __table_args__ = (
        Index("ix_samples_eval_index", "evaluation_id", "index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    contexts: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="samples")

    def __repr__(self) -> str:
        return f"<EvaluationSample id={self.id} eval={self.evaluation_id} idx={self.index}>"
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_models.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/rag/eval/ tests/rag/eval/
git commit -m "feat(eval): Evaluation + EvaluationSample models + CASCADE 测试"
```

---

## Task 9: Alembic 初始化

**Files:**
- Create: `alembic.ini`
- Create: `src/rag/storage/migrations/` (alembic init 生成)

- [ ] **Step 1: 跑 alembic init**

```bash
cd C:/doc/Code/worktrees/rag-refactor
uv run alembic init src/rag/storage/migrations
```

Expected: 创建 `src/rag/storage/migrations/env.py` + `script.py.mako` + `versions/`, 在仓库根创建 `alembic.ini`

- [ ] **Step 2: 改 alembic.ini**

修改 `alembic.ini`:
- 找 `script_location = ` 行, 改成 `script_location = src/rag/storage/migrations`
- 找 `sqlalchemy.url = ` 行, 改成 `sqlalchemy.url = ` (留空, env.py 读 env)

- [ ] **Step 3: 改 env.py target_metadata**

修改 `src/rag/storage/migrations/env.py`, 找到这段:

```python
# target_metadata = None
```

替换成:

```python
from src.rag.storage import Base
target_metadata = Base.metadata
# ⚠️ 必须显式 import 4 个 model, 不然 autogenerate 出空 migration
# (Task 10 经验: SQLAlchemy registry 不会自动收集, import 时才注册)
from src.rag.auth.models import User  # noqa: F401
from src.rag.chat.models import Conversation, Message  # noqa: F401
from src.rag.eval.models import Evaluation, EvaluationSample  # noqa: F401
```

并在文件顶部 import 后面加:

```python
import os
from src.rag.storage.engine import _resolve_db_url
```

然后把 `run_migrations_offline` 和 `run_migrations_online` 里的 `config.get_main_option("sqlalchemy.url")` 换成读 env:

- `run_migrations_offline` 函数体里:
```python
    url = _resolve_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
```

- `run_migrations_online` 函数体里:
```python
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_db_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
```

- [ ] **Step 4: 验证 alembic 能跑**

```bash
uv run alembic current
```

Expected: 打印当前版本 (空库时是 nothing)

- [ ] **Step 5: Commit**

```bash
git add alembic.ini src/rag/storage/migrations/
git commit -m "feat(storage): alembic init + 读 RAG_DB_URL env"
```

---

## Task 10: 第一个空 migration

**Files:**
- Create: `src/rag/storage/migrations/versions/<rev>_init.py` (alembic 生成)

- [ ] **Step 1: 出空 migration**

```bash
cd C:/doc/Code/worktrees/rag-refactor
mkdir -p data
uv run alembic revision --autogenerate -m "init"
```

Expected: 在 `src/rag/storage/migrations/versions/` 生成 `<hash>_init.py` (内容可能为空, 因为没 model register)

- [ ] **Step 2: 跑 upgrade head**

```bash
uv run alembic upgrade head
```

Expected: 不报错, 数据库里记录当前版本

- [ ] **Step 3: 跑 downgrade -1**

```bash
uv run alembic downgrade -1
```

Expected: 不报错 (空 migration 啥也不做)

- [ ] **Step 4: 验证版本表**

```bash
uv run alembic current
```

Expected: 打印 nothing (downgrade 完)

- [ ] **Step 5: Commit**

```bash
git add src/rag/storage/migrations/versions/
git commit -m "feat(storage): 第一个空 migration (alembic upgrade/downgrade 跑通)"
```

---

## Task 11: 集成测试 — upgrade/downgrade 双向

**Files:**
- Create: `tests/rag/storage/test_migrations.py`

- [ ] **Step 1: 写失败测试**

文件 `tests/rag/storage/test_migrations.py`:

```python
"""Alembic 集成测试: 升级/降级 双向, 临时 SQLite 文件库"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_alembic_upgrade_and_downgrade(tmp_path: Path, monkeypatch):
    """在临时库跑 alembic upgrade head + downgrade base, 不报错"""
    db_path = tmp_path / "alembic_test.db"
    monkeypatch.setenv("RAG_DB_URL", f"sqlite:///{db_path}")

    # 跑 upgrade head
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=Path.cwd(),
    )
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"

    # 验证库存在
    assert db_path.exists()

    # 跑 downgrade base
    result = subprocess.run(
        ["uv", "run", "alembic", "downgrade", "base"],
        capture_output=True, text=True, cwd=Path.cwd(),
    )
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"


def test_alembic_current_version(tmp_path: Path, monkeypatch):
    """upgrade head 后 alembic current 输出有版本号"""
    db_path = tmp_path / "alembic_test2.db"
    monkeypatch.setenv("RAG_DB_URL", f"sqlite:///{db_path}")

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=Path.cwd(), check=True,
    )

    result = subprocess.run(
        ["uv", "run", "alembic", "current"],
        capture_output=True, text=True, cwd=Path.cwd(), check=True,
    )
    # current 输出应该不只 "nothing"
    assert "nothing" not in result.stdout.lower() or result.stdout.strip() == ""
```

- [ ] **Step 2: 跑测试**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_migrations.py -v
```

Expected: 2 passed (Task 9-10 已实现)

- [ ] **Step 3: Commit**

```bash
git add tests/rag/storage/test_migrations.py
git commit -m "test(storage): alembic upgrade/downgrade 集成测试"
```

---

## Task 12: 端到端 — create_all 跟 alembic 起的库结构一致

**Files:**
- Create: `tests/rag/storage/test_e2e_consistency.py`

- [ ] **Step 1: 写测试**

文件 `tests/rag/storage/test_e2e_consistency.py`:

```python
"""create_all 跟 alembic 起的库表结构应该一致 (业务代码不感知迁移路径)

只要 model 都 import 进 Base, 两种方式起库产生的表一样, 业务代码无感。
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _list_tables(db_path: Path) -> set[str]:
    """从 SQLite 库读所有表名 (排除 alembic_version)"""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_create_all_vs_alembic_same_tables(tmp_path: Path, monkeypatch):
    """import 全部 model 后 create_all 跟 alembic upgrade head 表名一致"""
    # 1. 用 create_all 起的库
    db_create = tmp_path / "create_all.db"
    monkeypatch.setenv("RAG_DB_URL", f"sqlite:///{db_create}")
    # 重置单例
    from src.rag.storage import engine as engine_mod
    engine_mod._engine = None
    # 触发 import 全部 model
    from src.rag.auth.models import User  # noqa: F401
    from src.rag.chat.models import Conversation, Message  # noqa: F401
    from src.rag.eval.models import Evaluation, EvaluationSample  # noqa: F401
    from src.rag.storage import Base, get_engine, init_db
    import os
    os.environ["RAG_AUTO_CREATE_SCHEMA"] = "1"
    init_db()
    if engine_mod._engine is not None:
        engine_mod._engine.dispose()
        engine_mod._engine = None
    create_tables = _list_tables(db_create)

    # 2. 用 alembic 起的库
    db_alembic = tmp_path / "alembic.db"
    monkeypatch.setenv("RAG_DB_URL", f"sqlite:///{db_alembic}")
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=Path.cwd(), check=True,
    )
    alembic_tables = _list_tables(db_alembic)

    # 3. 表名一致 (alembic 表有 alembic_version, 已排除)
    assert create_tables == alembic_tables
    # 至少有 4 个业务表
    assert {"users", "conversations", "messages", "evaluations", "evaluation_samples"} <= create_tables
```

- [ ] **Step 2: 跑测试**

```bash
uv run --no-sync python -m pytest tests/rag/storage/test_e2e_consistency.py -v
```

Expected: 1 passed (前提: Task 6-10 都已实施)

- [ ] **Step 3: Commit**

```bash
git add tests/rag/storage/test_e2e_consistency.py
git commit -m "test(storage): create_all 跟 alembic 起库结构一致"
```

---

## Task 13: README 文档 (切 PG)

**Files:**
- Create: `src/rag/storage/README.md`

- [ ] **Step 1: 写 README**

文件 `src/rag/storage/README.md`:

````markdown
# Storage Layer

SQLAlchemy 2.0 + Alembic 存储层. SQLite 现在跑, PostgreSQL 切 env 即用.

## 公开 API

```python
from src.rag.storage import Base, get_engine, init_db, get_session, session_scope
```

- `Base`: DeclarativeBase, 业务 model 继承
- `get_engine()`: 惰性单例 Engine
- `init_db()`: 跑 create_all, **仅 dev/test**, 受 `RAG_AUTO_CREATE_SCHEMA=1` 开关
- `session_scope()`: 事务 context manager (commit on success / rollback on exception)
- `get_session()`: generator 给 FastAPI Depends 用

## 数据库配置

**环境变量** `RAG_DB_URL`:

```bash
# 默认 (省略 env 时)
RAG_DB_URL=sqlite:///data/app.db

# 切 PostgreSQL
RAG_DB_URL=postgresql+psycopg://user:pwd@host:5432/rag
```

业务代码零改动, 只改 env + 跑 migration。

## Migration (Alembic)

```bash
# 加 model 后自动生成 migration
uv run alembic revision --autogenerate -m "<feature>"

# 跑 migration
uv run alembic upgrade head

# 回滚一步
uv run alembic downgrade -1

# 看当前版本
uv run alembic current
```

**生产部署必须走 Alembic**, 别用 init_db() 自动建表.

## 切 PostgreSQL 三步

```bash
# 1. 启动 PG (举例 docker)
docker run -d --name rag-pg -e POSTGRES_PASSWORD=rag -p 5432:5432 postgres:16

# 2. 改 env
echo 'RAG_DB_URL=postgresql+psycopg://postgres:rag@localhost:5432/rag' >> .env

# 3. 跑 migration
uv run alembic upgrade head
```

(数据搬运脚本不在本 spec 范围, 切的时候再写)

## 加新 model 流程

1. 在 `src/rag/<feature>/models.py` 写新 model, `from ..storage import Base` 继承
2. 跑 `uv run alembic revision --autogenerate -m "add xxx"` 查 diff
3. 人工 review migration 文件
4. 跑 `uv run alembic upgrade head` 验证
5. 写测试 (`tests/rag/<feature>/test_models.py`)

## Windows 文件锁

SQLite 开库时自动设 `PRAGMA journal_mode=DELETE` + `synchronous=NORMAL` (event listener), 跟 `kg/audit.py` 修法一致. 不用 WAL, 避免 `-wal` / `-shm` 残留文件.

## Admin 虚拟 User

调试用 admin token 走 `CurrentUser` Pydantic 模型 (在 `src/rag/middleware/auth.py` 里), 不入 users 表. 业务代码用 `current.is_admin` 决定是否过滤 `WHERE user_id=current.id`. 详见 [评估页 spec § 调试机制](../specs/2026-06-09-evaluate-page-redesign-design.md#调试机制-admin-token).
````

- [ ] **Step 2: Commit**

```bash
git add src/rag/storage/README.md
git commit -m "docs(storage): 切 PG 路径 + 加 model 流程"
```

---

## Task 14: 全套测试 + 现有测试回归

**Files:** (无新建, 跑全套验证)

- [ ] **Step 1: 跑 storage 全部测试**

```bash
uv run --no-sync python -m pytest tests/rag/storage/ tests/rag/auth/ tests/rag/chat/ tests/rag/eval/ -v
```

Expected: 全部通过

- [ ] **Step 2: 跑现有测试确认没破坏**

```bash
uv run --no-sync python -m pytest tests/ -q --ignore=tests/rag/storage --ignore=tests/rag/auth --ignore=tests/rag/chat --ignore=tests/rag/eval
```

Expected: 全部通过 (特别留意 `tests/test_kg_neo4j.py`)

- [ ] **Step 3: 跑 ruff 检查**

```bash
uv run ruff check src/rag/storage/ src/rag/auth/ src/rag/chat/ src/rag/eval/ tests/rag/
```

Expected: 全过 (项目 ruff 只启用 F 规则)

- [ ] **Step 4: 最终 commit (空, 验证已绿)**

```bash
git status
# 应该 clean
```

---

## Success Criteria (复述)

1. ✅ `from src.rag.storage import get_session, Base` 在任何模块可 import
2. ✅ 4 业务 model (User / Conversation / Message / Evaluation / EvaluationSample) 可 import
3. ✅ `RAG_DB_URL=sqlite:///:memory:` 跑全部 storage/auth/chat/eval 测试, 全绿
4. ✅ 字段 / 约束 / 外键 CASCADE / UNIQUE 索引 全部覆盖测试
5. ✅ `RAG_DB_URL=postgresql+psycopg://...` 跑 `alembic upgrade head` 不报错 (本 spec 不验证 PG 实际连通)
6. ✅ `kg/audit.py` 不受影响
7. ✅ `src/rag/storage/README.md` 写清切 PG 三步 + 加 model 流程
