"""loguru 全局配置 + PII scrub + InterceptHandler (2026-06-17 logging spec §5/§7/§10)

Task 2: PII Scrubber + InterceptHandler (loguru 桥接 stdlib)
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import UTC
from typing import Any

from loguru import logger as _loguru
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

# ============== PII Scrubber (§10) ==============
# case-insensitive 黑名单 (19 字段, sec-004 集中定义)
from src.core.pii_fields import PII_FIELDS as _PII_FIELDS  # noqa: F401 (集中定义)


def _scrub(data: Any) -> Any:
    """递归 scrub 已知敏感字段. dict / list 嵌套处理."""
    if isinstance(data, dict):
        return {k: ("***REDACTED***" if k.lower() in _PII_FIELDS else _scrub(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [_scrub(item) for item in data]
    return data


# ============== InterceptHandler (stdlib → loguru) ==============


class InterceptHandler(logging.Handler):
    """stdlib logging.Handler → loguru 转发."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


# ============== configure_logging + sinks (§5) ==============

_LOG_QUEUE_MAXSIZE = 10_000


def _pg_sink_app(message) -> None:
    """app_logs sink (后台线程). loguru enqueue=True 调本函数.

    context 列是 JSONB, 显式声明类型让 psycopg 自动 adapt dict → JSONB.
    """
    rec = message.record
    try:
        # 推迟副作用: src.storage 顶层装载会触发 PG engine / ORM Base 元数据, loguru sink
        # 在主线程异步跑, 但写库只在实际日志事件触发, 不在配置阶段需要
        from src.storage import session_scope  # noqa: E402

        with session_scope() as s:
            stmt = text(
                "INSERT INTO app_logs (ts, level, logger, message, request_id, "
                "user_id, trace_id, context) "
                "VALUES (:ts, :level, :logger, :message, :request_id, "
                ":user_id, :trace_id, :context)"
            ).bindparams(bindparam("context", type_=JSONB))
            s.execute(
                stmt,
                {
                    "ts": rec["time"].astimezone(UTC),
                    "level": rec["level"].name,
                    "logger": rec["name"],
                    "message": rec["message"],
                    "request_id": _get_request_id(),
                    "user_id": _get_user_id(),
                    "trace_id": rec["extra"].get("trace_id"),
                    "context": _scrub(dict(rec["extra"])),
                },
            )
    except Exception as e:
        # 兜底: DB 写库失败 → 打印到 stderr, 不阻塞服务
        print(f"[logging] app_logs write failed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)


def _error_sink_sync(level: str, exc: Exception, request) -> None:
    """error_logs sink (同步, 5xx 全局 handler 调).

    context 列是 JSONB, 显式声明类型让 psycopg 自动 adapt dict → JSONB.
    跟 _pg_sink_app 对齐, 不加 bindparam 时非空 dict 会抛
    "cannot adapt type 'dict' using placeholder '%s'" (psycopg3 v3 adapter 协议).
    """
    try:
        # 推迟副作用: 同 _pg_sink_app, 5xx handler 延迟装载 src.storage, 启动期不需要
        from src.storage import session_scope  # noqa: E402

        with session_scope() as s:
            stmt = text(
                "INSERT INTO error_logs (ts, level, exception_type, exception_msg, "
                "stacktrace, request_id, user_id, path, method, status_code, context) "
                "VALUES (NOW(), :level, :type, :msg, :trace, :rid, :uid, "
                ":path, :method, :code, :ctx)"
            ).bindparams(bindparam("ctx", type_=JSONB))
            s.execute(
                stmt,
                {
                    "level": level,
                    "type": type(exc).__name__,
                    "msg": str(exc)[:1000],
                    "trace": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:5000],
                    "rid": _get_request_id(),
                    "uid": _get_user_id(),
                    "path": request.url.path if request else None,
                    "method": request.method if request else None,
                    "code": 500,
                    "ctx": _scrub({}),
                },
            )
    except Exception as e:
        print(f"[logging] error_logs write failed: {e}", file=sys.stderr, flush=True)


def _get_request_id() -> str | None:
    # 防循环: 顶层 import logging_context 会让 logger 模块装载早期触发 ContextVar __set_name__,
    # 可能跟 logging 配置期 side-effect 冲突. 实际取值时再解析
    from src.core.logging_context import current_request_id  # noqa: E402

    return current_request_id.get()


def _get_user_id() -> int | None:
    # 防循环: 同 _get_request_id, 顶层装载时机敏感
    from src.core.logging_context import current_user_id  # noqa: E402

    return current_user_id.get()


_THIRD_PARTY_LOGGERS = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "sqlalchemy.engine",
    "boto3",
    "botocore",
    "httpx",
    "httpcore",
    "neo4j",
    "mem0",
    "kreuzberg",
)


def configure_logging(
    json_console: bool = False,
    write_to_db: bool = True,
    level: str = "INFO",
) -> None:
    """main.py 启动时调一次. 配置 loguru + 接管 stdlib."""
    _loguru.remove()
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in _THIRD_PARTY_LOGGERS:
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = [InterceptHandler()]
        stdlib_logger.propagate = False

    if json_console:
        _loguru.add(
            sys.stdout,
            level=level,
            serialize=True,
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )
    else:
        _loguru.add(
            sys.stderr,
            level=level,
            colorize=True,
            enqueue=True,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            backtrace=True,
            diagnose=False,
        )

    if write_to_db:
        # DB sink 只收 WARNING+: INFO / DEBUG 噪声不写库 (量大撑爆 app_logs).
        # 真错误由 _error_sink_sync (5xx handler) 写 error_logs.
        _loguru.add(
            _pg_sink_app,
            level="WARNING",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )

    # (2026-06-17 spec §13) Grafana hook 预留位置
    grafana_enabled = os.getenv("GRAFANA_ENABLED", "false").lower() == "true"
    if grafana_enabled:
        pass

    _loguru.info(
        "logging configured: level={} json={} db={}",
        level,
        json_console,
        write_to_db,
    )


def shutdown_logging() -> None:
    """FastAPI shutdown 钩子. 排空 enqueue 队列."""
    _loguru.complete()
