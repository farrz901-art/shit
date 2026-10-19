"""Session 工厂

- session_scope(): context manager, commit on success / rollback on exception
- get_session(): generator 给 FastAPI Depends 用

⚠️ SessionLocal 在每次调用时 bind 当前 engine (不是模块级), 因为测试 + 多 env 场景下
    engine 会被 dispose + 重建, 模块级 bind 会卡在旧 engine 上 (Task 4 经验)。
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from .engine import get_engine


def _make_session() -> Session:
    """懒构造 session, 每次重新拿 engine 重建 sessionmaker"""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


@contextmanager
def session_scope() -> Generator[Session]:
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


def get_session() -> Generator[Session]:
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
