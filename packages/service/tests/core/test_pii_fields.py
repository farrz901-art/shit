"""测试 PII 字段集中定义 (SEC-004).

模式 1 mock, 0 PG 依赖.
"""

from __future__ import annotations


def test_pii_fields_has_19_fields():
    """验证集中列表包含所有 19 个字段."""
    from src.core.pii_fields import PII_FIELDS

    assert len(PII_FIELDS) == 19, "PII_FIELDS 应有 19 个字段"
    assert "password" in PII_FIELDS
    assert "passwd" in PII_FIELDS
    assert "pwd" in PII_FIELDS
    assert "token" in PII_FIELDS
    assert "access_token" in PII_FIELDS
    assert "refresh_token" in PII_FIELDS
    assert "api_key" in PII_FIELDS
    assert "apikey" in PII_FIELDS
    assert "secret" in PII_FIELDS
    assert "client_secret" in PII_FIELDS
    assert "authorization" in PII_FIELDS
    assert "cookie" in PII_FIELDS
    assert "set-cookie" in PII_FIELDS
    assert "ssn" in PII_FIELDS
    assert "credit_card" in PII_FIELDS
    assert "card_number" in PII_FIELDS
    assert "cvv" in PII_FIELDS
    assert "private_key" in PII_FIELDS
    assert "privatekey" in PII_FIELDS


def test_pii_fields_is_frozenset():
    """验证 PII_FIELDS 是不可变的 frozenset."""
    from src.core.pii_fields import PII_FIELDS

    assert isinstance(PII_FIELDS, frozenset)


def test_pii_fields_all_lowercase():
    """验证所有字段都是小写 (loguru filter 自动不区分大小写)."""
    from src.core.pii_fields import PII_FIELDS

    for field in PII_FIELDS:
        assert field == field.lower(), f"{field} 应全小写"


def test_pii_fields_imported_by_logging():
    """验证 logging.py 确实从 pii_fields 导入."""
    from src.core.logging import _scrub

    assert "password" in _scrub({"password": "xxx"})
    assert _scrub({"password": "xxx"})["password"] == "***REDACTED***"
    assert "token" in _scrub({"token": "yyy"})
    assert _scrub({"token": "yyy"})["token"] == "***REDACTED***"
