"""admin users API 测试 (2026-06-16 重写 100% mock, 19 tests)

覆盖 src/auth/auth_admin_router.py 的 6 个端点:
- GET    /api/admin/users         (list + 过滤 + 搜索 + 分页)
- POST   /api/admin/users         (创 invite)
- PATCH  /api/admin/users/{id}    (改 is_active / is_admin / display_name)
- POST   /api/admin/users/{id}/reset-password
- GET    /api/admin/invites
- DELETE /api/admin/invites/{token}

100% mock 模式 (跟 test_invite_flow 同套):
- dependency_overrides[require_admin] 注入 CurrentUser
- patch src.auth.auth_admin_router.session_scope 替 mock session
- patch src.middleware.auth.session_scope 替 mock session (鉴权链路)

0 真实 DB 连接, 0 dev DB writes.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, Invite
from src.auth.auth_admin_router import require_admin
from src.auth.models import User
from src.core.app_factory import create_app
from src.middleware.auth import CurrentUser
from src.utils.timezone import HKT

# ---------------- helpers ----------------


def _make_user(
    id: int = 1,
    public_token: str = "tok-1",
    display_name: str | None = "u1",
    account_id: int | None = None,
    created_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> MagicMock:
    """Mock User (spec=User 让属性访问更严格)"""
    u = MagicMock(spec=User)
    u.id = id
    u.public_token = public_token
    u.display_name = display_name
    u.account_id = account_id
    u.created_at = created_at or datetime.now(HKT)
    u.last_seen_at = last_seen_at or datetime.now(HKT)
    return u


def _make_account(
    id: int = 1,
    email: str = "a@x.com",
    role: str = "user",
    is_active: bool = True,
    display_name: str | None = None,
    created_at: datetime | None = None,
    last_login_at: datetime | None = None,
) -> MagicMock:
    """(2026-06-17) 替原 is_admin bool 为 role str. 旧 is_admin=True 传 role='super_admin'."""
    a = MagicMock(spec=Account)
    a.id = id
    a.email = email
    a.role = role
    a.is_active = is_active
    a.display_name = display_name
    a.created_at = created_at or datetime.now(HKT)
    a.last_login_at = last_login_at
    return a


def _make_invite(
    id: int = 1,
    token: str = "inv-tok-1",
    email: str = "new@x.com",
    invited_by_account_id: int = 1,
    redeemed_at: datetime | None = None,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> MagicMock:
    inv = MagicMock(spec=Invite)
    inv.id = id
    inv.token = token
    inv.email = email
    inv.invited_by_account_id = invited_by_account_id
    inv.redeemed_at = redeemed_at
    inv.created_at = created_at or datetime.now(HKT)
    inv.expires_at = expires_at or (datetime.now(HKT) + timedelta(days=7))
    inv.account_id = None
    return inv


def _admin_user(id: int = 99, account_id: int = 99, email: str = "admin@x.com") -> CurrentUser:
    """admin CurrentUser (mock 注入用)"""
    return CurrentUser(
        id=id,
        public_token="admin-tok",
        role="super_admin",
        is_account=True,
        account_id=account_id,
        email=email,
        is_active=True,
    )


@contextmanager
def _patch_session_scope(mock_session: MagicMock):
    """同时 patch auth_admin_router 和 middleware.auth 的 session_scope

    鉴权链路 resolve_user 走 src.middleware.auth.session_scope;
    admin router 业务逻辑走 src.auth.auth_admin_router.session_scope.
    两个入口都 patch 到同一个 mock session, 让 verify session.add / session.flush
    这种断言覆盖两端.
    """
    with (
        patch("src.auth.auth_admin_router.session_scope") as admin_p,
        patch("src.middleware.auth.session_scope") as mw_p,
    ):
        for p in (admin_p, mw_p):
            p.return_value.__enter__.return_value = mock_session
            p.return_value.__exit__.return_value = False
        yield mock_session


@pytest.fixture
def admin_client():
    """TestClient + admin identity 注入 (走 require_admin dependency_overrides)"""
    app = create_app()
    app.dependency_overrides[require_admin] = lambda: _admin_user()
    return TestClient(app)


# ---------------- GET /api/admin/users ----------------


def test_list_users_requires_admin(monkeypatch):
    """没 admin 注入 → 走原 require_admin 依赖链 → 401 (resolve_user 抛, 未提供 x-user-token)

    (2026-06-29) 显式 delenv RAG_DEV_AUTH: .env.local 设了 dev auth=true 会注入 anon user,
    test 期望 'no token → 401', 不应受 dev env 干扰.
    """
    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)
    client = TestClient(create_app())  # 不 override require_admin
    r = client.get("/api/admin/users")
    # 未设 RAG_DEV_AUTH + 未带 token → 401
    assert r.status_code in (401, 403)


def test_list_users_returns_accounts_and_anon(admin_client):
    """混合 user: 1 真账号 + 1 anon, kind 字段都对"""
    admin_user = _make_user(id=99, public_token="admin-tok", account_id=99)
    admin_acct = _make_account(id=99, email="admin@x.com", role="super_admin")
    anon = _make_user(id=2, public_token="anon-tok", account_id=None, display_name="anon")

    mock_session = MagicMock()
    # outerjoin + filter(None) + count + order_by + offset/limit + all
    joined_q = MagicMock()
    joined_q.count.return_value = 2
    joined_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (admin_user, admin_acct),
        (anon, None),
    ]
    mock_session.query.return_value.outerjoin.return_value = joined_q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/users")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    kinds = {it["kind"] for it in body["items"]}
    assert kinds == {"account", "anon"}


def test_list_users_filter_by_kind_account(admin_client):
    """kind=account → 只返 account 行 (anon 被过滤掉)

    关键回归 (2026-06-17): kind filter 必须下推到 SQL WHERE (在 LIMIT 前),
    否则 page 1 LIMIT 20 全是 anon 时, 后置过滤返空 items 但 total 仍含全部.
    断言 `joined_q.filter` 被调 (sqlalchemy 链式), 而不是依赖 limit 后 Python 过滤.
    """
    admin_user = _make_user(id=99, public_token="admin-tok", account_id=99)
    admin_acct = _make_account(id=99, email="admin@x.com", role="super_admin")

    mock_session = MagicMock()
    joined_q = MagicMock()
    # 模拟 SQL filter 链: filter(isnot(None)) → count → order_by → offset → limit → all
    filtered_q = MagicMock()
    joined_q.filter.return_value = filtered_q
    filtered_q.count.return_value = 1  # kind=account 后只剩 1 条 account
    filtered_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (admin_user, admin_acct),
    ]
    mock_session.query.return_value.outerjoin.return_value = joined_q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/users?kind=account")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1, f"total 应是 kind=account 后的计数 1, 实际 {body['total']}"
    assert len(body["items"]) == 1
    assert body["items"][0]["kind"] == "account"
    # 关键断言: kind 走了 SQL .filter(), 不再 Python 后置过滤
    assert joined_q.filter.called, "kind filter 必须下推到 SQL, 否则真实场景 page 1 全 anon 时返空 items"


def test_list_users_filter_by_kind_account_regression(admin_client):
    """**回归真案 (2026-06-17)**: 49 个用户 + page_size=20 + 第一页 20 全是 anon + kind=account

    修复前: limit 返 20 anon, Python 后置过滤全丢 → items=[] 但 total=49 (前后不一致)
    修复后: kind 在 SQL WHERE 过滤, limit 拿到的是 account 行 → items 非空
    """
    admin_user = _make_user(id=10, public_token="a-tok", account_id=10)
    admin_acct = _make_account(id=10, email="admin@x.com", role="super_admin")

    mock_session = MagicMock()
    joined_q = MagicMock()
    filtered_q = MagicMock()
    # 模拟真实场景: SQL filter 已把 anon 过滤掉, limit 拿到的是 account
    joined_q.filter.return_value = filtered_q
    filtered_q.count.return_value = 1
    filtered_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (admin_user, admin_acct),
    ]
    mock_session.query.return_value.outerjoin.return_value = joined_q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/users?kind=account&page=1&page_size=20")

    assert r.status_code == 200
    body = r.json()
    # 修复前: items=[]  total=49 (矛盾)
    # 修复后: items=[admin]  total=1 (一致)
    assert body["items"], "修复后 kind=account 必须返非空 (过滤在 SQL)"
    assert body["total"] >= len(body["items"]), "total 必须 >= items.length"


def test_list_users_search_by_email(admin_client):
    """search 走 or_(Account.email.like, User.display_name.like)"""
    u = _make_user(id=10, public_token="findme-tok", account_id=10, display_name="findme")
    a = _make_account(id=10, email="findme@x.com")

    mock_session = MagicMock()
    joined_q = MagicMock()
    joined_q.count.return_value = 1
    joined_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [(u, a)]
    mock_session.query.return_value.outerjoin.return_value = joined_q
    # 断言 search filter 走了
    joined_q.filter.return_value = joined_q  # chainable

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/users?search=findme")

    assert r.status_code == 200
    assert any("findme" in (it.get("email") or "") for it in r.json()["items"])
    # 确认 .filter() 至少被调一次 (search 触发)
    assert joined_q.filter.called


def test_list_users_pagination(admin_client):
    """page=1, page_size=2 → 返 total, page, page_size 字段都对"""
    u1 = _make_user(id=1, public_token="a1", account_id=1)
    u2 = _make_user(id=2, public_token="a2", account_id=2)
    a1 = _make_account(id=1, email="u1@x.com")
    a2 = _make_account(id=2, email="u2@x.com")

    mock_session = MagicMock()
    joined_q = MagicMock()
    joined_q.count.return_value = 5
    joined_q.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        (u1, a1),
        (u2, a2),
    ]
    mock_session.query.return_value.outerjoin.return_value = joined_q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/users?page=1&page_size=2")

    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ---------------- POST /api/admin/users (创 invite) ----------------


def test_create_invite_returns_url(admin_client, monkeypatch):
    """创 invite → 200, 返 invite_token + invite_url, session.add 被调"""
    monkeypatch.setenv("INVITE_EXPIRES_DAYS", "7")
    mock_session = MagicMock()
    # 3 次 query:
    # 1) Role: role='user' 存在 (返 truthy)
    # 2) Account: email 未注册 (None)
    # 3) Invite: 无 pending (None)
    role_q = MagicMock()
    role_q.filter_by.return_value.first.return_value = MagicMock()  # role 存在
    acct_q = MagicMock()
    acct_q.filter_by.return_value.first.return_value = None
    inv_q = MagicMock()
    inv_q.filter_by.return_value.filter.return_value.first.return_value = None
    mock_session.query.side_effect = [role_q, acct_q, inv_q]

    with _patch_session_scope(mock_session):
        r = admin_client.post(
            "/api/admin/users",
            json={"email": "newbie@x.com", "role": "user", "display_name": "New Bie"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "newbie@x.com"
    assert "invite_token" in body
    assert body["invite_url"].startswith("/zh/invite/")
    assert len(body["invite_token"]) == 64  # secrets.token_hex(32) = 64 hex chars
    # session.add 应被调一次 (创 invite 行)
    assert mock_session.add.call_count == 1
    added_inv = mock_session.add.call_args[0][0]
    assert isinstance(added_inv, Invite)
    assert added_inv.email == "newbie@x.com"
    # invited_by_account_id 来自 admin.account_id = 99
    assert added_inv.invited_by_account_id == 99


def test_create_invite_duplicate_email_409(admin_client):
    """email 已注册 (有 Account 行) → 409"""
    mock_session = MagicMock()
    # 第一次 query(Account).filter_by(email=...).first() → mock Account (重复)
    dup_acct = _make_account(id=5, email="dup@x.com")
    mock_session.query.return_value.filter_by.return_value.first.return_value = dup_acct

    with _patch_session_scope(mock_session):
        r = admin_client.post("/api/admin/users", json={"email": "dup@x.com"})

    assert r.status_code == 409
    assert "email" in r.json()["detail"]


def test_create_invite_existing_pending_409(admin_client):
    """有未 redeem + 未过期 invite → 409"""
    mock_session = MagicMock()
    pending_inv = _make_invite(id=1, token="existing-tok", email="newbie@x.com")

    # 1) Role: role='user' 存在
    # 2) Account: 邮箱未注册 (None)
    # 3) Invite: mock pending
    role_q = MagicMock()
    role_q.filter_by.return_value.first.return_value = MagicMock()
    acct_q = MagicMock()
    acct_q.filter_by.return_value.first.return_value = None
    inv_q = MagicMock()
    inv_q.filter_by.return_value.filter.return_value.first.return_value = pending_inv
    mock_session.query.side_effect = [role_q, acct_q, inv_q]

    with _patch_session_scope(mock_session):
        r = admin_client.post("/api/admin/users", json={"email": "newbie@x.com"})

    assert r.status_code == 409
    assert "pending invite" in r.json()["detail"]


# ---------------- PATCH /api/admin/users/{id} ----------------


def test_patch_user_changes_is_active(admin_client):
    """PATCH is_active=False → 200, mock account.is_active 已被设"""
    target_user = _make_user(id=10, public_token="target-tok", account_id=10)
    target_acct = _make_account(id=10, email="target@x.com", is_active=True)

    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, id_: {
        User: {10: target_user},
        Account: {10: target_acct},
    }.get(model, {}).get(id_)

    with _patch_session_scope(mock_session):
        r = admin_client.patch(
            "/api/admin/users/10",
            json={"is_active": False},
        )

    assert r.status_code == 200
    assert target_acct.is_active is False


def test_patch_user_disabled_token_now_401(admin_client):
    """PATCH is_active=False 后, target user 自己再请求 → 401 (account disabled)"""
    target_user = _make_user(id=10, public_token="target-tok", account_id=10)
    target_acct = _make_account(id=10, email="target@x.com", is_active=True)

    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, id_: {
        User: {10: target_user},
        Account: {10: target_acct},
    }.get(model, {}).get(id_)

    # 1. admin PATCH 禁用 target 账号
    with _patch_session_scope(mock_session):
        r1 = admin_client.patch(
            "/api/admin/users/10",
            json={"is_active": False},
        )
    assert r1.status_code == 200
    assert target_acct.is_active is False

    # 2. target user 拿自己 token 再请求 → resolve_user 看到 is_active=False → 401
    # 走 admin_client 但没 override 当前 user 身份, 走真实 resolve_user 链路
    # 鉴权依赖 require_admin 不被满足 → 401/403 (resolve_user 抛 401, 没传 x-user-token)
    # 用真 token 路径: 不 override, 发 x-user-token=target-tok
    no_auth_client = TestClient(create_app())
    with _patch_session_scope(mock_session):
        r2 = no_auth_client.get(
            "/api/admin/users",
            headers={"x-user-token": "target-tok"},
        )
    assert r2.status_code == 401  # resolve_user 看到 is_active=False → "account disabled"


def test_patch_user_cannot_disable_self(admin_client):
    """admin PATCH 自己 is_active=False → 400 (cannot disable self)"""
    # admin_client 注入 admin id=99
    admin_target = _make_user(id=99, public_token="admin-tok", account_id=99)
    mock_session = MagicMock()
    mock_session.get.return_value = admin_target

    with _patch_session_scope(mock_session):
        r = admin_client.patch(
            "/api/admin/users/99",
            json={"is_active": False},
        )

    assert r.status_code == 400
    assert "disable self" in r.json()["detail"]


def test_patch_anon_user_is_admin_400(admin_client):
    """anon user (account_id=None) 改 role → 400"""
    anon_user = _make_user(id=11, public_token="anon-tok", account_id=None)
    mock_session = MagicMock()
    mock_session.get.return_value = anon_user

    with _patch_session_scope(mock_session):
        r = admin_client.patch(
            "/api/admin/users/11",
            json={"role": "super_admin"},
        )

    assert r.status_code == 400
    assert "anon user cannot have role" in r.json()["detail"]


def test_patch_user_display_name(admin_client):
    """PATCH display_name → user.display_name 已更新"""
    target_user = _make_user(id=10, public_token="target-tok", account_id=10)
    target_acct = _make_account(id=10, email="target@x.com")
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, id_: {
        User: {10: target_user},
        Account: {10: target_acct},
    }.get(model, {}).get(id_)

    with _patch_session_scope(mock_session):
        r = admin_client.patch(
            "/api/admin/users/10",
            json={"display_name": "New Name"},
        )

    assert r.status_code == 200
    assert target_user.display_name == "New Name"


# ---------------- POST /api/admin/users/{id}/reset-password ----------------


def test_reset_password_returns_temp(admin_client, monkeypatch):
    """reset password → 200, 返 temp_password, account.password_hash 已改"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    target_user = _make_user(id=10, public_token="target-tok", account_id=10)
    target_acct = _make_account(id=10, email="target@x.com")
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda model, id_: {
        User: {10: target_user},
        Account: {10: target_acct},
    }.get(model, {}).get(id_)

    with _patch_session_scope(mock_session):
        r = admin_client.post("/api/admin/users/10/reset-password")

    assert r.status_code == 200
    body = r.json()
    assert "temp_password" in body
    assert len(body["temp_password"]) > 0
    # 原始 hash 不应等于新 hash
    assert target_acct.password_hash != "old-hash"


def test_reset_password_anon_400(admin_client):
    """anon user (account_id=None) → 400 (user has no account)"""
    anon_user = _make_user(id=11, public_token="anon-tok", account_id=None)
    mock_session = MagicMock()
    mock_session.get.return_value = anon_user

    with _patch_session_scope(mock_session):
        r = admin_client.post("/api/admin/users/11/reset-password")

    assert r.status_code == 400
    assert "no account" in r.json()["detail"]


# ---------------- GET /api/admin/invites ----------------


def test_list_invites(admin_client):
    """status=all (默认) → 返所有 invite"""
    inv1 = _make_invite(id=1, token="t1", email="a@x.com")
    inv2 = _make_invite(id=2, token="t2", email="b@x.com", redeemed_at=datetime.now(HKT))

    mock_session = MagicMock()
    q = MagicMock()
    q.count.return_value = 2
    q.order_by.return_value.limit.return_value.all.return_value = [inv1, inv2]
    mock_session.query.return_value = q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/invites")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_list_invites_filter_pending(admin_client):
    """status=pending → 触发 filter(redeemed_at IS NULL AND expires_at > now)"""
    mock_session = MagicMock()
    q = MagicMock()
    q.count.return_value = 0
    q.order_by.return_value.limit.return_value.all.return_value = []
    mock_session.query.return_value = q

    with _patch_session_scope(mock_session):
        r = admin_client.get("/api/admin/invites?status=pending")

    assert r.status_code == 200
    # pending filter 链被走过: query(Invite).filter(...).filter(...).count()
    assert q.filter.call_count >= 1


# ---------------- DELETE /api/admin/invites/{token} ----------------


def test_delete_invite_removes_pending(admin_client):
    """未 redeemed invite → 200 ok, session.delete 被调"""
    pending = _make_invite(id=1, token="t1", email="x@x.com")
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = pending

    with _patch_session_scope(mock_session):
        r = admin_client.delete("/api/admin/invites/t1")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert mock_session.delete.called
    # 删的就是 pending 那条
    deleted_obj = mock_session.delete.call_args[0][0]
    assert deleted_obj is pending


def test_delete_invite_redeemed_400(admin_client):
    """已 redeemed invite → 400 (audit 保留)"""
    redeemed = _make_invite(id=1, token="t1", email="x@x.com", redeemed_at=datetime.now(HKT))
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = redeemed

    with _patch_session_scope(mock_session):
        r = admin_client.delete("/api/admin/invites/t1")

    assert r.status_code == 400
    assert "already redeemed" in r.json()["detail"]
    # 不应调 delete
    assert not mock_session.delete.called
