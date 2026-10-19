"""@audited decorator + AuditContext + _persist_audit (2026-06-17 logging spec §8)

用法:
    from src.core.audit import audited, AuditContext

    @router.delete("/account")
    @audited("account.delete", target_type="user")
    async def delete_account(request: Request, current_user = Depends(...)):
        request.state.audit_ctx.set(
            target_id=str(current_user.id),
            before={"email": current_user.email},
        )
        ...
"""

from __future__ import annotations

import inspect
from functools import wraps
from typing import Any

from fastapi import Request
from loguru import logger
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from .logging import _scrub
from .logging_context import current_request_id


class AuditContext:
    """请求级 audit 上下文. decorator 在 endpoint 前后填充, 业务函数中 set."""

    def __init__(self, action: str, target_type: str):
        self.action = action
        self.target_type = target_type
        self.target_id: str | None = None
        self.before: dict | None = None
        self.after: dict | None = None
        self.metadata: dict[str, Any] = {}

    def set(
        self,
        *,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
        **metadata: Any,
    ) -> None:
        self.target_id = target_id
        self.before = before
        self.after = after
        self.metadata.update(metadata)


def audited(action: str, target_type: str):
    """Decorator: 包装 endpoint, 成功 / 失败都写 audit_logs."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            request: Request | None = kwargs.get("request") or next((a for a in args if isinstance(a, Request)), None)
            user = kwargs.get("current_user") or next(
                (a for a in args if hasattr(a, "id") and hasattr(a, "email")), None
            )

            ctx = AuditContext(action=action, target_type=target_type)
            if request is not None:
                request.state.audit_ctx = ctx

            result = "success"
            try:
                # 兼容 sync / async 两种 handler:
                # sync def → func(...) 直接返值, 不能 await (会 TypeError: dict can't be awaited)
                # async def → func(...) 返 coroutine, 必须 await
                # 根因: 2026-07-03 kg/router.py:715 start_extract 等 4 个端点是同步 def,
                # 原 wrapper 一律 await func(...) → /api/kg/extract/start 500.
                value = func(*args, **kwargs)
                if inspect.isawaitable(value):
                    value = await value
                return value
            except Exception as exc:
                result = "failure"
                ctx.metadata["error"] = repr(exc)[:500]
                raise
            finally:
                _persist_audit(request=request, user=user, ctx=ctx, result=result)

        return wrapper

    return decorator


def _persist_audit(
    request: Request | None,
    user: Any,
    ctx: AuditContext,
    result: str,
) -> None:
    """写 audit_logs 表. 永不抛, 失败用 logger.critical 记 + stderr 兜底.

    before / after / metadata 三列是 JSONB, 显式 bindparam(type_=JSONB) 让 psycopg 自动
    adapt Python dict → JSONB 字符串. 不绑的话 psycopg 抛 ProgrammingError
    "cannot adapt type 'dict' using placeholder '%s' (format: AUTO)"
    (2026-06-22 anon /api/auth/anon 真实报错).
    """
    try:
        # 推迟副作用: session_scope 触发 src.storage 完整装载 (engine + ORM Base 元数据),
        # audit 模块导入期不需要付出
        from src.storage import session_scope  # noqa: E402

        with session_scope() as s:
            stmt = text(
                "INSERT INTO audit_logs (actor_id, actor_type, action, target_type, "
                "target_id, ip, user_agent, request_id, result, before, after, metadata) "
                "VALUES (:actor_id, 'user', :action, :target_type, :target_id, "
                ":ip, :ua, :request_id, :result, :before, :after, :metadata)"
            ).bindparams(
                bindparam("before", type_=JSONB),
                bindparam("after", type_=JSONB),
                bindparam("metadata", type_=JSONB),
            )
            s.execute(
                stmt,
                {
                    "actor_id": getattr(user, "id", 0) or 0,
                    "action": ctx.action,
                    "target_type": ctx.target_type,
                    "target_id": ctx.target_id or "",
                    "ip": (request.client.host if request and request.client else None),
                    "ua": (request.headers.get("user-agent", "")[:500] if request else ""),
                    "request_id": current_request_id.get(),
                    "result": result,
                    "before": _scrub(ctx.before) if ctx.before else None,
                    "after": _scrub(ctx.after) if ctx.after else None,
                    "metadata": _scrub(ctx.metadata),
                },
            )
    except Exception as e:
        logger.critical(
            "audit_logs 写入失败 action={} target={}: {}",
            ctx.action,
            ctx.target_id,
            e,
        )
