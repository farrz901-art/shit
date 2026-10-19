"""CurrentUser + resolve_user 测试

(2026-06-29) 重写 100% mock 跟项目规约一致 (CLAUDE.md §强制测试隔离), 0 真 PG 依赖.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def _patched_session(mock_session):
    """patch resolve_user 的 session_scope + token_cache miss + audit log mock 链.

    resolve_user 内部:
    1. token_cache.get_user_by_token → cache miss 走 PG
    2. session_scope() → s.query(User) → fallback to PG
    3. cache_user_by_token 写 redis
    """
    from contextlib import contextmanager

    @contextmanager
    def _scope():
        yield mock_session

    return patch("src.middleware.auth.session_scope", side_effect=_scope)


def test_resolve_user_token_valid(monkeypatch):
    """有效 x-user-token → resolve_user 返 CurrentUser (mock User row + Account row)"""
    from starlette.requests import Request

    from src.auth.models import User
    from src.middleware.auth import resolve_user

    # mock User row (anon, account_id=None)
    mock_user = MagicMock(spec=User)
    mock_user.id = 42
    mock_user.public_token = "tok-valid"
    mock_user.account_id = None
    mock_user.display_name = "test"

    mock_session = MagicMock()
    # s.query(User).filter_by(public_token=...).first() → mock_user
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
    # s.get(Account, account_id) (account_id=None 直接跳, 但保险也 mock)
    mock_session.get.return_value = None

    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)

    req = Request({"type": "http", "headers": [(b"x-user-token", b"tok-valid")]})

    async def _run():
        # patch token_cache 走 miss 路径
        with (
            patch("src.core.token_cache.get_user_by_token", return_value=None),
            patch("src.core.token_cache.cache_user_by_token", new=MagicMock(return_value=None)),
            _patched_session(mock_session),
        ):
            return await resolve_user(req)

    result = asyncio.run(_run())
    assert result.id == 42
    assert result.public_token == "tok-valid"
    assert result.is_account is False  # account_id=None → anon


def test_resolve_user_token_missing_401(monkeypatch):
    """无 admin + 无 user header → 401

    (2026-06-29) 显式 delenv RAG_DEV_AUTH: .env.local 设了 dev auth=true 会注入 dev super_admin,
    test 期望 'no token → 401', 不应受 dev env 干扰 (跟 test_list_users_requires_admin 同根因).
    """
    from starlette.requests import Request

    from src.middleware.auth import resolve_user

    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "")
    req = Request({"type": "http", "headers": []})
    # (2026-06-18 T3) resolve_user 改 async, 同步测试用 asyncio.run 包装
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_user(req))
    assert exc.value.status_code == 401


def test_resolve_user_token_invalid_401(monkeypatch):
    """DB 不存在的 token → 401 (mock query 返 None)"""
    from starlette.requests import Request

    from src.middleware.auth import resolve_user

    mock_session = MagicMock()
    # query 返 None → 401
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)

    req = Request({"type": "http", "headers": [(b"x-user-token", b"nonexistent")]})

    async def _run():
        with (
            patch("src.core.token_cache.get_user_by_token", return_value=None),
            _patched_session(mock_session),
        ):
            return await resolve_user(req)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_run())
    assert exc.value.status_code == 401
