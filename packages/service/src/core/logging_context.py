"""contextvars 持有请求级元数据 (2026-06-17 logging spec §6)

middleware 在请求进入时 set, 离开时 reset.
loguru sink 跟 audit decorator 通过这两个 contextvar 拿值.
"""

from __future__ import annotations

from contextvars import ContextVar

# 请求级 UUID4 (RequestIDMiddleware 生成或读 X-Request-ID header)
current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

# auth 解析后注入 (bind_user_id 调用), 用于日志 + audit_logs.actor_id
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
