"""PII 字段集中列表 (SEC-004 fix).

所有审计/日志模块引用此单一来源, 防散落.
"""

from __future__ import annotations

# 大小写不敏感, loguru filter 自动匹配
# 从 logging.py SENSITIVE_KEYS 迁移而来 (19 字段)
PII_FIELDS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "secret",
        "client_secret",
        "authorization",
        "cookie",
        "set-cookie",
        "ssn",
        "credit_card",
        "card_number",
        "cvv",
        "private_key",
        "privatekey",
    }
)
