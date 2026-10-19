"""bcrypt hash + verify + rounds 配置测试"""

from __future__ import annotations

import pytest


@pytest.fixture
def low_rounds(monkeypatch):
    """测试提速: bcrypt rounds 降到 4"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    yield


@pytest.mark.usefixtures("low_rounds")
def test_hash_password_returns_string():
    """hash_password(plain) -> str (60 字符 bcrypt 格式 $2b$12$...)"""
    from src.auth.account_service import hash_password

    h = hash_password("hunter2hunter")
    assert isinstance(h, str)
    assert h.startswith("$2b$") or h.startswith("$2a$")
    assert len(h) >= 60


@pytest.mark.usefixtures("low_rounds")
def test_hash_password_salt_random():
    """同密码两次 hash 不同 (salt 随机)"""
    from src.auth.account_service import hash_password

    a = hash_password("samepass")
    b = hash_password("samepass")
    assert a != b


@pytest.mark.usefixtures("low_rounds")
def test_verify_password_correct():
    """verify_password(plain, hash) == True when 密码对"""
    from src.auth.account_service import hash_password, verify_password

    h = hash_password("correctpass")
    assert verify_password("correctpass", h) is True


@pytest.mark.usefixtures("low_rounds")
def test_verify_password_wrong():
    """错密码 → False"""
    from src.auth.account_service import hash_password, verify_password

    h = hash_password("rightpass")
    assert verify_password("wrongpass", h) is False


@pytest.mark.usefixtures("low_rounds")
def test_min_length_enforced():
    """< 8 字符密码 → ValueError"""
    from src.auth.account_service import hash_password

    with pytest.raises(ValueError, match="(?i)password.*8"):
        hash_password("short")
