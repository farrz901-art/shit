"""RequestID + user_id 注入 contextvars (2026-06-17 logging spec §6)"""

from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .logging_context import current_request_id, current_user_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """每请求注入 / 回写 X-Request-ID + reset contextvars."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token_req = current_request_id.set(request_id)
        token_user = current_user_id.set(None)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            current_request_id.reset(token_req)
            current_user_id.reset(token_user)


def bind_user_id(user_id: int | None) -> None:
    """auth 解析后调. 把 user_id 注入 contextvars."""
    current_user_id.set(user_id)
