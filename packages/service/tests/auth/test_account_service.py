"""auth/account_service.py 单元测试"""

import pytest

from src.auth.account_service import generate_token, hash_password, verify_password


def test_hash_password_returns_hash():
    h = hash_password("password123")
    assert len(h) > 10
    assert isinstance(h, str)


def test_hash_password_too_short():
    with pytest.raises(ValueError, match="at least 8"):
        hash_password("short")


def test_verify_password_correct():
    h = hash_password("password123")
    assert verify_password("password123", h) is True


def test_verify_password_wrong():
    h = hash_password("password123")
    assert verify_password("wrongpass", h) is False


def test_generate_token_length():
    t = generate_token()
    assert len(t) == 64
