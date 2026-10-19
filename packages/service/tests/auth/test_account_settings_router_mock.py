"""account_settings_router.py mock 单元测试 (mode 1, mock auth + session_scope)"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.account_settings_router import router
from src.middleware.auth import CurrentUser
from src.permissions.guards import require_account, require_active_account

MOCK_ACCOUNT = MagicMock(
    id=1,
    email="test@x.com",
    display_name="测试",
    role="user",
    avatar_url=None,
    is_pending_deletion=False,
    deletion_requested_at=None,
)

MOCK_USER = CurrentUser(
    id=42,
    public_token="test-token",
    role="user",
    is_account=True,
    account_id=1,
    email="test@x.com",
    display_name="测试",
    is_active=True,
    is_pending_deletion=False,
)


def _make_app(mock_session):
    """创建带依赖覆盖的 FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    # 用 dependency_overrides 覆盖鉴权守卫
    app.dependency_overrides[require_active_account] = lambda: MOCK_USER
    app.dependency_overrides[require_account] = lambda: MOCK_USER
    return app


@patch("src.auth.account_settings_router.session_scope")
def test_patch_profile(mock_scope):
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.update_profile"):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.patch("/api/account/profile", json={"display_name": "新名"})
        assert resp.status_code == 200
        assert "account" in resp.json()


@patch("src.auth.account_settings_router.session_scope")
def test_get_deletion(mock_scope):
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.get_deletion_status", return_value={"pending": False}):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.get("/api/account/deletion")
        assert resp.status_code == 200


@patch("src.auth.account_settings_router.session_scope")
def test_post_avatar_success(mock_scope):
    """上传头像, 正确 mime → 200"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.store_avatar", return_value="local://avatars/1.abc.webp"):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/avatar", files={"file": ("test.png", b"fake-png-data", "image/png")})
        assert resp.status_code == 200
        assert resp.json()["avatar_url"] == "local://avatars/1.abc.webp"


@patch("src.auth.account_settings_router.session_scope")
def test_post_avatar_unsupported_mime(mock_scope):
    """上传头像, 不支持 mime → 422"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.post("/api/account/avatar", files={"file": ("test.bmp", b"fake", "image/bmp")})
    assert resp.status_code == 422


@patch("src.auth.account_settings_router.session_scope")
def test_post_avatar_account_not_found(mock_scope):
    """上传头像, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.post("/api/account/avatar", files={"file": ("test.png", b"fake-png-data", "image/png")})
    assert resp.status_code == 404
    assert "not found" in resp.text


@patch("src.auth.account_settings_router.session_scope")
def test_post_avatar_store_avatar_value_error(mock_scope):
    """上传头像, svc.store_avatar 抛 ValueError → 422"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.store_avatar", side_effect=ValueError("invalid image")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/avatar", files={"file": ("test.png", b"fake-png-data", "image/png")})
        assert resp.status_code == 422


@patch("src.auth.account_settings_router.session_scope")
def test_delete_avatar_success(mock_scope):
    """删除头像 → 200 {ok: true}"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.delete_avatar"):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.delete("/api/account/avatar")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


@patch("src.auth.account_settings_router.session_scope")
def test_delete_avatar_account_not_found(mock_scope):
    """删除头像, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.delete("/api/account/avatar")
    assert resp.status_code == 404


@patch("src.auth.account_settings_router.session_scope")
def test_patch_email_success(mock_scope):
    """申请改邮箱 → 200"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    return_value = {
        "new_email": "new@x.com",
        "expires_at": "2026-07-01T00:00:00Z",
        "verification_url": "/verify-email?token=xxx",
    }
    with patch("src.auth.account_settings_router.svc.request_email_change", return_value=return_value):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.patch("/api/account/email", json={"new_email": "new@x.com", "current_password": "oldpwd"})
        assert resp.status_code == 200
        assert resp.json()["new_email"] == "new@x.com"


@patch("src.auth.account_settings_router.session_scope")
def test_patch_email_value_error(mock_scope):
    """申请改邮箱, svc 抛 ValueError → 400"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.request_email_change", side_effect=ValueError("invalid password")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.patch("/api/account/email", json={"new_email": "new@x.com", "current_password": "wrong"})
        assert resp.status_code == 400


@patch("src.auth.account_settings_router.session_scope")
def test_patch_email_account_not_found(mock_scope):
    """申请改邮箱, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.patch("/api/account/email", json={"new_email": "new@x.com", "current_password": "pwd"})
    assert resp.status_code == 404


@patch("src.auth.account_settings_router.session_scope")
def test_post_email_verify_success(mock_scope):
    """验证邮箱改 token → 200"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.verify_email_change", return_value={"email": "new@x.com"}):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/email/verify", json={"token": "valid-token"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@x.com"


@patch("src.auth.account_settings_router.session_scope")
def test_post_email_verify_value_error(mock_scope):
    """验证邮箱改 token 失败 → 400"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.verify_email_change", side_effect=ValueError("invalid token")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/email/verify", json={"token": "bad-token"})
        assert resp.status_code == 400


@patch("src.auth.account_settings_router.session_scope")
def test_patch_password_success(mock_scope):
    """改密码 → 200 {ok: true}"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.change_password"):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.patch(
            "/api/account/password",
            json={
                "current_password": "old",
                "new_password": "newpass123",
                "confirm": "newpass123",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


@patch("src.auth.account_settings_router.session_scope")
def test_patch_password_value_error(mock_scope):
    """改密码, svc 抛 ValueError → 400"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.change_password", side_effect=ValueError("invalid password")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.patch(
            "/api/account/password",
            json={
                "current_password": "wrong",
                "new_password": "newpass123",
                "confirm": "newpass123",
            },
        )
        assert resp.status_code == 400


@patch("src.auth.account_settings_router.session_scope")
def test_patch_password_account_not_found(mock_scope):
    """改密码, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.patch(
        "/api/account/password",
        json={
            "current_password": "old",
            "new_password": "newpass123",
            "confirm": "newpass123",
        },
    )
    assert resp.status_code == 404


@patch("src.auth.account_settings_router.session_scope")
def test_post_deletion_success(mock_scope):
    """申请注销 → 200"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    return_value = {
        "deletion_requested_at": "2026-06-21T00:00:00Z",
        "expires_at": "2026-06-28T00:00:00Z",
        "restore_url": "/account/restore?token=xxx",
    }
    with patch("src.auth.account_settings_router.svc.request_deletion", return_value=return_value):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/deletion", json={"current_password": "pwd", "confirm_text": "我要注销"})
        assert resp.status_code == 200
        assert "restore_url" in resp.json()


@patch("src.auth.account_settings_router.session_scope")
def test_post_deletion_invalidates_token_cache(mock_scope):
    """(2026-06-26 CONC-003) 申请注销成功后必须失效 Redis token cache,
    防止已注销账号在 cache TTL (6h) 内继续访问. 对齐 verify_email_change / change_password."""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    return_value = {
        "deletion_requested_at": "2026-06-21T00:00:00Z",
        "expires_at": "2026-06-28T00:00:00Z",
        "restore_url": "/account/restore?token=xxx",
    }
    with (
        patch("src.auth.account_settings_router.svc.request_deletion", return_value=return_value),
        patch("src.core.token_cache.invalidate_token", new=AsyncMock()) as mock_invalidate,
    ):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/deletion", json={"current_password": "pwd", "confirm_text": "我要注销"})
        assert resp.status_code == 200
    # 关键: invalidate_token 必须被调用一次, 参数是 user.public_token
    mock_invalidate.assert_awaited_once_with(MOCK_USER.public_token)


@patch("src.auth.account_settings_router.session_scope")
def test_post_deletion_value_error(mock_scope):
    """申请注销, svc 抛 ValueError → 400"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.request_deletion", side_effect=ValueError("wrong password")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.post("/api/account/deletion", json={"current_password": "wrong", "confirm_text": "我要注销"})
        assert resp.status_code == 400


@patch("src.auth.account_settings_router.session_scope")
def test_post_deletion_account_not_found(mock_scope):
    """申请注销, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.post("/api/account/deletion", json={"current_password": "pwd", "confirm_text": "我要注销"})
    assert resp.status_code == 404


@patch("src.auth.account_settings_router.session_scope")
def test_delete_deletion_success(mock_scope):
    """撤销注销 → 200 {ok: true}"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.cancel_deletion"):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.request("DELETE", "/api/account/deletion", json={"current_password": "pwd"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


@patch("src.auth.account_settings_router.session_scope")
def test_delete_deletion_value_error(mock_scope):
    """撤销注销, svc 抛 ValueError → 400"""
    mock_session = MagicMock()
    mock_session.get.return_value = MOCK_ACCOUNT
    mock_scope.return_value.__enter__.return_value = mock_session
    with patch("src.auth.account_settings_router.svc.cancel_deletion", side_effect=ValueError("not pending")):
        app = _make_app(mock_session)
        client = TestClient(app)
        resp = client.request("DELETE", "/api/account/deletion", json={"current_password": "pwd"})
        assert resp.status_code == 400


@patch("src.auth.account_settings_router.session_scope")
def test_delete_deletion_account_not_found(mock_scope):
    """撤销注销, account 不存在 → 404"""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope.return_value.__enter__.return_value = mock_session
    app = _make_app(mock_session)
    client = TestClient(app)
    resp = client.request("DELETE", "/api/account/deletion", json={"current_password": "pwd"})
    assert resp.status_code == 404
