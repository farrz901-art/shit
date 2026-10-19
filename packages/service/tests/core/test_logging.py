"""loguru config + PII scrub + InterceptHandler 测试 (模式 1, 0 PG)"""

from __future__ import annotations

import logging

from src.core.logging import InterceptHandler, _scrub


def test_scrub_password():
    assert _scrub({"password": "abc123"}) == {"password": "***REDACTED***"}


def test_scrub_token_variants():
    """token / access_token / refresh_token / api_key / apikey / authorization 全 redacted"""
    data = {
        "token": "t1",
        "access_token": "t2",
        "refresh_token": "t3",
        "api_key": "k1",
        "apikey": "k2",
        "authorization": "Bearer xyz",
        "secret": "s1",
        "private_key": "pk",
    }
    out = _scrub(data)
    for key in data:
        assert out[key] == "***REDACTED***", f"{key} 没被 scrub"


def test_scrub_case_insensitive():
    """Password / TOKEN / Authorization 大小写不敏感"""
    data = {"Password": "x", "TOKEN": "y", "Authorization": "z", "API_KEY": "w"}
    out = _scrub(data)
    assert all(v == "***REDACTED***" for v in out.values())


def test_scrub_keeps_safe_fields():
    """user_id / email / ip / request_id 不算 PII, 不动"""
    data = {"user_id": 42, "email": "a@b.com", "ip": "1.2.3.4", "request_id": "req-1"}
    assert _scrub(data) == data


def test_scrub_nested_dict():
    """嵌套 dict 递归 scrub"""
    data = {
        "user": {"id": 1, "password": "abc"},
        "credentials": {"api_key": "k1", "ssn": "111-22-3333"},
    }
    out = _scrub(data)
    assert out["user"]["id"] == 1
    assert out["user"]["password"] == "***REDACTED***"
    assert out["credentials"]["api_key"] == "***REDACTED***"
    assert out["credentials"]["ssn"] == "***REDACTED***"


def test_scrub_list_of_dicts():
    data = [{"password": "a"}, {"token": "b"}, {"safe": "c"}]
    out = _scrub(data)
    assert out == [
        {"password": "***REDACTED***"},
        {"token": "***REDACTED***"},
        {"safe": "c"},
    ]


def test_scrub_non_dict_passthrough():
    assert _scrub("hello") == "hello"
    assert _scrub(42) == 42
    assert _scrub(None) is None


def test_intercept_handler_subclass():
    assert issubclass(InterceptHandler, logging.Handler)


def test_intercept_handler_emit_does_not_raise():
    """emit() 拿到 stdlib LogRecord 不抛"""
    handler = InterceptHandler()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    handler.emit(record)


# ---------------- configure_logging ----------------


def test_configure_logging_dev_mode_no_db(monkeypatch, capsys):
    """dev 模式: 彩色控制台 + 不写 DB"""
    from loguru import logger as _loguru

    from src.core.logging import configure_logging

    configure_logging(json_console=False, write_to_db=False, level="INFO")
    _loguru.info("test message")
    _loguru.complete()
    captured = capsys.readouterr()
    assert "test message" in captured.err


def test_configure_logging_json_mode(monkeypatch, capsys):
    """JSON 模式: serialize=True 输出 JSON"""
    import json as json_mod

    from loguru import logger as _loguru

    from src.core.logging import configure_logging

    configure_logging(json_console=True, write_to_db=False, level="INFO")
    _loguru.info("json test")
    _loguru.complete()

    captured = capsys.readouterr()
    line = captured.out.strip().split("\n")[-1]
    parsed = json_mod.loads(line)
    assert parsed["record"]["message"] == "json test"
    assert parsed["record"]["level"]["name"] == "INFO"


def test_configure_logging_intercepts_stdlib(monkeypatch, capsys):
    """stdlib logging.getLogger('uvicorn') 经 InterceptHandler 进 loguru"""
    import logging as stdlib_logging

    from loguru import logger as _loguru

    from src.core.logging import configure_logging

    configure_logging(json_console=False, write_to_db=False, level="INFO")
    stdlib_logger = stdlib_logging.getLogger("uvicorn")
    stdlib_logger.info("stdlib intercepted")
    _loguru.complete()

    captured = capsys.readouterr()
    assert "stdlib intercepted" in captured.err


def test_configure_logging_db_sink_registered(monkeypatch):
    """write_to_db=True 时, _pg_sink_app 被 add 到 loguru

    DB sink level 配 WARNING+ (避免 INFO 噪声撑爆 app_logs), 所以用 WARNING 触发
    """
    from src.core import logging as core_logging

    sink_calls = []
    monkeypatch.setattr(core_logging, "_pg_sink_app", lambda message: sink_calls.append(message))

    core_logging.configure_logging(json_console=False, write_to_db=True, level="INFO")
    from loguru import logger as _loguru

    _loguru.warning("to db")
    _loguru.complete()

    assert len(sink_calls) >= 1
