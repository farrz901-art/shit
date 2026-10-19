"""测试辅助工具: mock CurrentUser 工厂.

用法:
    user = mock_current_user(id=1, role="admin")
    user = mock_current_user(is_anon=True)
"""

from __future__ import annotations

from unittest.mock import MagicMock


def mock_current_user(
    *,
    id: int = 1,
    role: str = "user",
    email: str | None = "admin@x.com",
    is_account: bool = True,
    is_active: bool = True,
    is_pending_deletion: bool = False,
) -> MagicMock:
    """构造 mock CurrentUser (不依赖 Pydantic 构造, 走 MagicMock).

    role 字段控制 is_admin 派生:
    - "admin" / "super_admin" → is_admin=True
    - "user" → is_admin=False
    """
    user = MagicMock()
    user.id = id
    user.public_token = f"tok-{id}"
    user.role = role
    user.email = email
    user.is_account = is_account
    user.is_active = is_active
    user.is_pending_deletion = is_pending_deletion
    user.account_id = id if is_account else None
    user.display_name = email or None
    user.avatar_url = None
    user.deletion_requested_at = None

    # is_admin 派生属性
    user.is_admin = role in ("admin", "super_admin")
    return user
