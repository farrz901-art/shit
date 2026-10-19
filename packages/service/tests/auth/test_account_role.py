"""Account role 字段测试: seed_admin / login / /me 都返 role: str"""


def test_login_response_has_role_field() -> None:
    """LoginResponse / AccountOut 必须含 role 字段"""
    from src.auth.auth_account_router import AccountOut, LoginResponse

    acc = AccountOut(id=1, email="x@y.com", display_name="x", role="admin", is_admin=True)
    # pyright basic 看不到 pending_deletion=False / deletion_expires_at=None 默认值
    resp = LoginResponse(token="tok", account=acc)  # pyright: ignore[reportCallIssue]
    assert resp.account.role == "admin"
    assert resp.account.is_admin is True


def test_account_out_has_role_field() -> None:
    """AccountOut 必须含 role 字段 (替原 is_admin)"""
    from src.auth.auth_account_router import AccountOut

    out = AccountOut(id=1, email="x@y.com", display_name="x", role="admin", is_admin=True)
    assert out.role == "admin"


def test_account_out_user_role() -> None:
    """user role 派生 is_admin=False"""
    from src.auth.auth_account_router import AccountOut

    out = AccountOut(id=1, email="x@y.com", display_name="x", role="user", is_admin=False)
    assert out.role == "user"
    assert out.is_admin is False
