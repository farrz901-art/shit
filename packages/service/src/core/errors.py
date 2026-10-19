"""FastAPI global exception handlers (2026-06-17 logging spec §7)

4xx → WARNING (app_logs only)
5xx → ERROR (app_logs + error_logs)
永远不返 stacktrace 给前端 (避免代码泄露).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import _error_sink_sync, _scrub


def install_error_handlers(app: FastAPI) -> None:
    """create_app() 里调一次. 注册 3 个 exception handler."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        logger.warning(
            "HTTP 异常 status={} path={} detail={}",
            exc.status_code,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        logger.warning(
            "请求参数校验失败 path={} errors={}",
            request.url.path,
            _scrub(exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exc(request: Request, exc: Exception):
        logger.opt(exception=True).error(
            "unhandled_exception path={} method={}",
            request.url.path,
            request.method,
        )
        try:
            _error_sink_sync(level="ERROR", exc=exc, request=request)
        except Exception as write_exc:
            logger.critical("error_logs write failed: {}", write_exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


# (2026-07-09) LLM helper 异常类, 放 errors.py 不新建文件 (评审调整 #7)
class LLMUnavailableError(RuntimeError):
    """LLM 客户端不可用. caller 接住 → 优雅降级 (跳过 C2 用 C1 结果).

    Attributes:
        message: 错误描述
        backend: 客户端类型 ("ollama" / "openai" / None), 给 caller 区分降级策略
    """

    def __init__(self, message: str, *, backend: str | None = None) -> None:
        super().__init__(message)
        self.backend = backend


class LLMParsingError(ValueError):
    """LLM 返 invalid JSON / 无法解析. caller 接住 → 优雅降级.

    Attributes:
        message: 错误描述
        raw_response: LLM 原始返文本, 给调试用
    """

    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response
