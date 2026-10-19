"""account 模块测试 fixtures (2026-06-16 改)

db_session 从这里删了, 走 tests/integration/conftest.py 的 db_session (事务回滚, 0 commit).
tests/auth/* 测试显式 import db_session, 不用 usefixtures.

make_account 工厂: caller 必须传 session 进来 (事务回滚, 不 commit).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.auth.account_models import Account
from src.utils.timezone import HKT


@pytest.fixture
def make_account():
    """工厂: 创 account 行, 返 Account 实例. caller 传 session 进来 (事务回滚, 0 commit)."""
    counter = {"i": 0}

    def _make(session, email: str | None = None, **kwargs) -> Account:
        counter["i"] += 1
        e = email or f"u{counter['i']}@x.com"
        # (2026-06-17) 兼容旧 is_admin kwarg: 映射到 role (admin/super_admin)
        is_admin = kwargs.pop("is_admin", False)
        role = kwargs.pop("role", "super_admin" if is_admin else "user")
        defaults = dict(
            email=e,
            password_hash=kwargs.pop("password_hash", "stub"),
            role=role,
            is_active=kwargs.pop("is_active", True),
            display_name=kwargs.pop("display_name", None),
            created_at=datetime.now(HKT),
        )
        a = Account(**defaults, **kwargs)
        session.add(a)
        session.flush()
        session.refresh(a)
        session.expunge(a)
        return a

    return _make
