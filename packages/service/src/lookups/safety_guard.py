"""SafetyGuard: 6 层防御 (2026-06-19 lookup spec §五)

所有写操作 (POST / PATCH / DELETE) 在 router 入口处走 check_all(), 任一层失败立刻 raise LookupSafetyError:
1. 鉴权: super_admin 角色 (其他返 403)
2. 只读: env DICTIONARY_READONLY=true 或 字典级 is_readonly=true (返 403)
3. 二次确认: delete 必走, 校验 16 字符 hex (返 412)
4. 引用检查: delete 必走 (force=True 跳过), 查 _REFERENCE_MAP 反向引用 (返 409)
5. 版本: payload 含 expected_version 才校验, 乐观锁防并发覆盖 (返 412)
6. rate limit: 60/min/user (复用 src.core.rate_limiter dict_admin rule, 返 429)

业务调用示例 (router 层):
    try:
        safety_guard.check_all(
            action="delete", dict_code="reject_reason", key="duplicate",
            user=current_user, confirm_token=token, payload={}, force=False,
        )
    except LookupSafetyError as e:
        raise HTTPException(e.http_status, detail=e.detail)

约束:
- 所有方法 async (内部 await rate_limiter.check_and_increment)
- 失败 raise LookupSafetyError, 不返 bool (业务侧 try/except 模式清晰)
- _REFERENCE_MAP 是 hardcode, 新字典/新引用表必须在这注册 (项目 onboarding 提示)
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import text

from src.core.rate_limiter import check_and_increment
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupSafetyError
from src.middleware.auth import CurrentUser
from src.storage.session import session_scope

# 业务表 → 字典项 的反向引用 map (2026-06-19 lookup spec §5.2 第 4 层)
# 新增字典 / 业务表变动时必须同步更新本表, 否则引用检查失效.
#
# 注: 列名以实际 DB schema 为准, 跟 spec 草稿的命名不一致时已校正:
# - approvals.reject_reason → 实际列名是 rejection_reason (CLAUDE.md 中已确认)
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    "approval_kind": [("approvals", "kind")],
    "approval_review_status": [("approvals", "review_status")],
    "approval_apply_status": [("approvals", "apply_status")],
    "reject_reason": [("approvals", "rejection_reason")],
    "page_key": [("role_permissions", "page_key")],
}


# 16 字符 hex 格式校验 (确认 token 形态)
_HEX16 = set("0123456789abcdefABCDEF")


class SafetyGuard:
    """6 层防御守门人. 单例 (safety_guard) 给 router 层 import."""

    async def check_all(
        self,
        *,
        action: Literal["create", "patch", "delete"],
        dict_code: str,
        key: str | None,
        user: CurrentUser,
        confirm_token: str | None,
        payload: dict[str, Any],
        force: bool = False,
    ) -> None:
        """跑全部 6 层防御. 顺序固定, 任一失败 raise LookupSafetyError.

        Args:
            action: 操作类型 (create/patch/delete).
            dict_code: 字典 code (e.g. "reject_reason").
            key: item key (create 时 None).
            user: 当前登录用户 (resolve_user 返).
            confirm_token: 二次确认 token (delete 必传, 16 字符 hex).
            payload: 请求体 dict (含 expected_version 等).
            force: 是否绕过引用检查 (delete 时 force=True, audit log 标 forced=true).

        Raises:
            LookupSafetyError: 任一层失败, http_status 4xx 映射到 HTTP 响应.
        """
        # 第 1 层: 鉴权 (super_admin only)
        self._check_role(user)
        # 第 2 层: 只读 (env 优先 → 字典级)
        self._check_readonly(dict_code)
        # 第 3 层: 二次确认 (仅 delete)
        if action == "delete":
            self._check_confirm_token(user, confirm_token)
            # 第 4 层: 引用检查 (delete, force=True 跳过)
            if not force:
                await self._check_business_references(dict_code, key or "")
        # 第 5 层: 版本 (payload 显式声明 expected_version 才校验, 乐观锁)
        if payload.get("expected_version") is not None:
            self._check_version(dict_code, payload["expected_version"])
        # 第 6 层: rate limit (60/min/user, 复用 dict_admin rule)
        await self._check_rate_limit(user)

    # ---- 6 层防御实现 ----

    def _check_role(self, user: CurrentUser) -> None:
        """第 1 层: 必须 super_admin 角色."""
        if user.role != "super_admin":
            raise LookupSafetyError(403, "super_admin required")

    def _check_readonly(self, dict_code: str) -> None:
        """第 2 层: env 全局优先 → 字典级 (priority: env > dict > business)."""
        if os.getenv("DICTIONARY_READONLY", "").lower() == "true":
            raise LookupSafetyError(403, "DICTIONARY_READONLY=true (env readonly)")
        if lookup_cache.get_dict_readonly(dict_code):
            raise LookupSafetyError(403, f"dictionary '{dict_code}' is readonly")

    def _check_confirm_token(self, user: CurrentUser, token: str | None) -> None:
        """第 3 层: delete 必走, 校验 16 字符 hex 格式 + 内容有效.

        内容校验:
        - token = sha256("<secret>" + "<YYYYMMDDHH>")[:16]
        - "<secret>" 优先 user.id (后续可换 user.email 等)
        - token 1 小时有效 (小时桶), 每小时自动过期 (防 replay)
        - 注: 本期 secret 用 user.id (后续可调), 业务层 router 必须先签发
        """
        if not token:
            raise LookupSafetyError(412, "confirm token required for delete")
        if len(token) != 16 or not all(c in _HEX16 for c in token):
            raise LookupSafetyError(412, "invalid confirm token format (must be 16 hex chars)")
        # 内容校验: 当前小时 + 前一小时 (边界容错, 防 59'59" race)
        # secret 用 user.id (后续可换 email / dedicated_secret), 1h 自动过期
        now = datetime.now(UTC)
        secret = f"dict-admin-confirm:{user.id}"
        for delta_hours in (0, -1):
            ts = now.timestamp() + delta_hours * 3600
            bucket = datetime.fromtimestamp(ts, tz=UTC).strftime("%Y%m%d%H")
            expected = hashlib.sha256(f"{secret}:{bucket}".encode()).hexdigest()[:16]
            if token.lower() == expected:
                return
        raise LookupSafetyError(412, "invalid confirm token (re-fetch and retry)")

    async def _check_business_references(self, dict_code: str, key: str) -> None:
        """第 4 层: 反向引用计数, >0 阻断删除.

        通过 _REFERENCE_MAP 查 (table, column) 列表, 用 SELECT COUNT(*)
        累加引用行数. force=True 在 check_all() 提前跳过本方法.
        """
        refs = _REFERENCE_MAP.get(dict_code, [])
        if not refs:
            return  # 没注册引用表 = 字典独立, 不检查
        total = 0
        with session_scope() as s:
            for table, column in refs:
                # table / column 是 hardcode 常量 (来自 _REFERENCE_MAP), 安全
                sql = text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :key")
                result = s.execute(sql, {"key": key}).scalar()
                total += int(result or 0)
        if total > 0:
            raise LookupSafetyError(
                409,
                f"item '{dict_code}:{key}' still referenced by {total} rows; "
                f"soft-delete refused. Use ?force=true to bypass (audit logged)",
            )

    def _check_version(self, dict_code: str, expected_version: int) -> None:
        """第 5 层: 乐观锁, 版本不匹配阻断写入."""
        current = lookup_cache.get_dict_version(dict_code)
        if current != expected_version:
            raise LookupSafetyError(
                412,
                f"version mismatch: expected={expected_version}, current={current}",
            )

    async def _check_rate_limit(self, user: CurrentUser) -> None:
        """第 6 层: 60/min/user, 复用 src.core.rate_limiter dict_admin rule."""
        # key 用 str(user.id), rate_limiter 会拼成 rag:rl:dict_admin:<id>
        allowed, _ = await check_and_increment("dict_admin", str(user.id))
        if not allowed:
            raise LookupSafetyError(429, "rate limit exceeded (60/min)")


# 模块级单例 (router 层直接 import safety_guard.check_all)
safety_guard = SafetyGuard()
