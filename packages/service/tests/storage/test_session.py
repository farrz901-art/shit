"""session.py 测试 (2026-06-16 重写 100% mock, 3 tests)

cover src/storage/session.py:
- session_scope(): commit on success / rollback on exception / always close
- get_session(): generator yields Session, always closes

100% mock: patch get_engine + _make_session, 0 真 DB 连接.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_session_scope_commit_on_success():
    """正常退出 -> session.commit() 被调, session.close() 被调"""
    from src.storage.session import session_scope

    mock_session = MagicMock()

    with patch("src.storage.session._make_session", return_value=mock_session):
        with session_scope() as s:
            assert s is mock_session
            s.add(MagicMock())

    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_session_scope_rollback_on_exception():
    """抛异常 -> session.rollback() 被调, 异常向上传播, session.close() 被调"""
    from src.storage.session import session_scope

    mock_session = MagicMock()

    class _Boom(Exception):
        pass

    with patch("src.storage.session._make_session", return_value=mock_session):
        with pytest.raises(_Boom):
            with session_scope() as s:
                s.add(MagicMock())
                raise _Boom("boom")

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
    mock_session.close.assert_called_once()


def test_get_session_yields_and_closes():
    """get_session() 是 generator: yield 一个 Session, close 后结束"""
    from sqlalchemy.orm import Session

    from src.storage.session import get_session

    mock_session = MagicMock(spec=Session)

    with patch("src.storage.session._make_session", return_value=mock_session):
        gen = get_session()
        s = next(gen)
        assert s is mock_session
        with pytest.raises(StopIteration):
            next(gen)

    mock_session.close.assert_called_once()
