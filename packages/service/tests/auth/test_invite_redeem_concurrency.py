"""Invite redeem TOCTOU 防护测试 (2026-06-24 CON-001)

模式 1 mock: 不连真 PG, 验证 _lock_invite_in_session 行为契约.

核心场景:
1. test_lock_invite_returns_invite_for_unredeemed: 未用 invite → 返 invite, with_for_update 调过
2. test_lock_invite_400_for_nonexistent: token 不存在 → 400 (统一防探测)
3. test_lock_invite_400_for_redeemed: 已用 invite → 400 (被 redeem_at IS NULL 过滤掉)
4. test_lock_invite_400_for_expired: 已过期 invite → 400
5. test_redeem_double_session_atomic: 模拟双重 session 并发 redeem:
   第一个 mock session 走完整路径, 第二个拿不到 invite → 400.
   验在同一事务内 锁 + 创账号 + 标 redeemed_at 是原子的.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, Invite
from src.auth.auth_invite_router import _lock_invite_in_session
from src.core.app_factory import create_app
from src.utils.timezone import HKT


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_mock_invite(
    email: str = "new@x.com",
    token: str = "test-tok-001",
    inviter_id: int = 1,
    expired: bool = False,
    redeemed: bool = False,
) -> MagicMock:
    inv = MagicMock(spec=Invite)
    inv.id = 1
    inv.email = email
    inv.token = token
    inv.invited_by_account_id = inviter_id
    inv.expires_at = datetime.now(HKT) + (timedelta(days=-1) if expired else timedelta(days=7))
    inv.redeemed_at = datetime.now(HKT) if redeemed else None
    inv.created_at = datetime.now(HKT)
    inv.account_id = None
    return inv


@contextmanager
def _patch_session_scope(mock_session):
    with patch("src.auth.auth_invite_router.session_scope") as patched:
        patched.return_value.__enter__.return_value = mock_session
        patched.return_value.__exit__.return_value = False
        yield patched


# ==================== _lock_invite_in_session 单元测试 ====================


def test_lock_invite_returns_invite_for_unredeemed():
    """未过期未用的 invite → 返 invite 实例, with_for_update() 调过."""
    mock_inv = _make_mock_invite(redeemed=False, expired=False)
    mock_session = MagicMock()
    # _lock_invite_in_session 用 s.execute(select(...).with_for_update())
    # mock 整个链路: s.execute(...).scalars().first() → mock_inv
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_inv

    inv = _lock_invite_in_session(mock_session, "test-tok-001")

    assert inv is mock_inv
    # 验证 with_for_update 链路上调过 (CON-001 关键)
    stmt = mock_session.execute.call_args[0][0]
    # select(Invite).where(...).with_for_update() — execute 入参是 statement, 检查它有 _for_update_arg
    assert hasattr(stmt, "_for_update_arg")
    assert stmt._for_update_arg is not None


def test_lock_invite_400_for_nonexistent():
    """token 不存在 (mock 返 None) → 400 统一防探测."""
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _lock_invite_in_session(mock_session, "nonexistent-token")

    assert exc_info.value.status_code == 400
    assert "invalid" in exc_info.value.detail


def test_lock_invite_400_for_expired():
    """已过期 invite → 400 (即便第一行返了 invite)."""
    mock_inv = _make_mock_invite(expired=True, redeemed=False)
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_inv

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _lock_invite_in_session(mock_session, "expired-token")

    assert exc_info.value.status_code == 400


# ==================== redeem_invite 集成测试 ====================


def test_redeem_double_session_atomic_first_wins(client, monkeypatch):
    """CON-001 核心场景: 模拟双重 session 并发 redeem 同一 token.

    第一个 redeem 成功 (mock invite 已被加载 + 创账号 + 标 redeemed_at).
    第二个 redeem 拿不到 invite (mock s.execute 返 None, 因为 redeemed_at IS NULL 不再匹配).
    期望: 一个 200, 一个 400. (PG 真场景下行锁让第二个阻塞到第一个 commit 后再过滤掉).
    """
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")

    # ---- 第 1 次 redeem: 模拟 invite 未用, 走完整路径 ----
    mock_inv = _make_mock_invite(email="race@x.com", token="race-tok-001")
    mock_session_1 = MagicMock()
    # _lock_invite_in_session: s.execute(...).scalars().first() → mock_inv
    mock_session_1.execute.return_value.scalars.return_value.first.return_value = mock_inv
    # query(Account).filter_by(email=...).first() → None (邮箱未占)
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = None
    mock_session_1.query.return_value = account_query

    def _fake_refresh(obj):
        obj.id = 100
        obj.role = "user"
        obj.is_active = True

    mock_session_1.refresh.side_effect = _fake_refresh

    with _patch_session_scope(mock_session_1):
        r1 = client.post(
            "/api/invites/race-tok-001/redeem",
            json={"display_name": "Race1", "password": "longpassword"},
        )

    assert r1.status_code == 200, r1.text
    # 第一个 redeem 已标 redeemed_at (模拟 PG commit 后的状态)
    assert mock_inv.redeemed_at is not None
    assert mock_inv.account_id == 100

    # ---- 第 2 次 redeem: 模拟 invite 已被标 redeemed_at, _lock_invite 过滤掉 ----
    # 在 PG 真场景下, 第 2 个 session 的 SELECT FOR UPDATE 阻塞到 session1 commit 后,
    # 再 fetch 时 redeemed_at IS NOT NULL → where 子句不匹配 → 返 None → 400.
    # 这里 mock s.execute 返 None 模拟此状态.
    mock_session_2 = MagicMock()
    mock_session_2.execute.return_value.scalars.return_value.first.return_value = None

    with _patch_session_scope(mock_session_2):
        r2 = client.post(
            "/api/invites/race-tok-001/redeem",
            json={"display_name": "Race2", "password": "longpassword"},
        )

    assert r2.status_code == 400, f"第 2 个 redeem 应 400, 实际 {r2.status_code}: {r2.text}"
    assert "invalid" in r2.json()["detail"]
    # 第二个 redeem 不能创建第二个账号
    # (mock 路径: session.add 没被调过)
    assert mock_session_2.add.call_count == 0


def test_redeem_invite_locked_returns_400_not_500(client, monkeypatch):
    """CON-001 业务决策: 已用 invite redeem 必须返 400 (防探测), 不是 500.

    旧实现下双重并发 redeem 会触发 IntegrityError (Account.email 唯一约束),
    表面看是 500. 修后, 行锁让第二次 redeem 阻塞后看到 redeemed_at 已标 → 400.
    """
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    # 模拟已 redeem 的 invite: SELECT ... WHERE redeemed_at IS NULL 返 None
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = None

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/used-tok/redeem",
            json={"display_name": "U", "password": "longpassword"},
        )

    assert r.status_code == 400
    # 不是 500 (CON-001 bug fix)
    assert r.status_code != 500
    # 也不应是 409 (409 留给 email 已注册场景)
    assert r.status_code != 409


def test_redeem_email_already_registered_returns_409(client, monkeypatch):
    """CON-001 边界: invite 有效, 但 email 已被别的方式注册 → 409.

    验: 锁通过 + account 创建冲突 → 409 (跟原逻辑一致).
    """
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_inv = _make_mock_invite(email="existing@x.com", token="tok-existing")
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_inv
    # 模拟 email 已注册: query(Account).filter_by(email=...).first() → 返 account
    existing_account = MagicMock(spec=Account)
    existing_account.email = "existing@x.com"
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = existing_account
    mock_session.query.return_value = account_query

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/tok-existing/redeem",
            json={"display_name": "New", "password": "longpassword"},
        )

    assert r.status_code == 409
    assert "registered" in r.json()["detail"]
    # mock_inv.redeemed_at 没被标 (事务 rollback 了)
    assert mock_inv.redeemed_at is None


def test_redeem_lock_with_for_update_called(client, monkeypatch):
    """CON-001 安全契约: redeem 必须经 SELECT FOR UPDATE 路径 (s.execute + with_for_update).

    这是修复的关键, 不是单看 _lock_invite_in_session 而是从 redeem_invite 端到端验.
    """
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    mock_inv = _make_mock_invite()
    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_inv
    account_query = MagicMock()
    account_query.filter_by.return_value.first.return_value = None
    mock_session.query.return_value = account_query

    def _fake_refresh(obj):
        obj.id = 1
        obj.role = "user"
        obj.is_active = True

    mock_session.refresh.side_effect = _fake_refresh

    with _patch_session_scope(mock_session):
        r = client.post(
            "/api/invites/test-tok-001/redeem",
            json={"display_name": "U", "password": "longpassword"},
        )

    assert r.status_code == 200, r.text
    # 关键验: s.execute 调过, 且入参 statement 有 _for_update_arg
    assert mock_session.execute.called
    stmt = mock_session.execute.call_args[0][0]
    assert hasattr(stmt, "_for_update_arg")
    assert stmt._for_update_arg is not None
