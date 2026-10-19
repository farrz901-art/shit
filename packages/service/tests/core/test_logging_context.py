"""contextvars 测试 (模式 1, 0 PG 依赖)"""

from __future__ import annotations

from src.core.logging_context import current_request_id, current_user_id


def test_current_request_id_default_is_none():
    """没 set 时 default = None"""
    assert current_request_id.get() is None


def test_current_user_id_default_is_none():
    assert current_user_id.get() is None


def test_current_request_id_set_and_get():
    """set 后 get 一致, reset 恢复"""
    token = current_request_id.set("req-abc-123")
    try:
        assert current_request_id.get() == "req-abc-123"
    finally:
        current_request_id.reset(token)
    assert current_request_id.get() is None


def test_current_user_id_set_and_get():
    token = current_user_id.set(42)
    try:
        assert current_user_id.get() == 42
    finally:
        current_user_id.reset(token)
    assert current_user_id.get() is None
