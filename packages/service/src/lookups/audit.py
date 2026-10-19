"""字典变更审计 (2026-06-19 lookup spec §4.7)

复用项目 src.db.models.audit_log.AuditLog 表.
- actor_id: BigInt not null → 传 user.id (强制要求, 没有 fallback)
- actor: 用 email 或 public_token, 仅作 log 友好显示 (写入 meta.actor_display)
- action: 命名空间 "dictionary.<op>", forced=true 时拼 ".forced" 后缀
- target_id: "<dict_code>:<key>"
- before/after: 变更前后快照 (dict, JSONB 存储)
- ip: request.client.host (None 表示非 HTTP 上下文, e.g. CLI)
"""

from __future__ import annotations

from typing import Any

from src.db.models.audit_log import AuditLog
from src.storage.session import session_scope


def log_dict_change(
    *,
    actor: str,
    actor_id: int,
    action: str,
    target: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    ip: str | None,
    forced: bool = False,
) -> None:
    """写一条字典变更审计 (2026-06-19 lookup spec §4.7).

    字段映射 (跟 AuditLog 表对齐):
    - actor_id: 传 user.id (BigInt, not null) — 必须, 没 id 抛 TypeError
    - actor_type: "user" (字典变更只可能由登录用户发起, anon 没 dict admin 权限)
    - action: "dictionary.{action}{.forced}"
    - target_type: "dictionary_item" (target_id 是 "<dict_code>:<key>" 形式)
    - target_id: 同上
    - before/after: 变更前后快照, None 转空 dict (AuditLog before/after 可空)
    - meta: 装 actor 友好显示名 (actor_display), 跟 actor_id 区分
    - ip: 客户端 IP, 可空 (CLI / 测试不传)
    """
    if actor_id is None:
        raise TypeError("log_dict_change: actor_id is required (AuditLog.actor_id is NOT NULL)")
    action_full = f"dictionary.{action}{'.forced' if forced else ''}"
    with session_scope() as s:
        s.add(
            AuditLog(
                actor_id=actor_id,
                actor_type="user",
                action=action_full,
                target_type="dictionary_item",
                target_id=target,
                before=before or {},
                after=after or {},
                ip=ip,
                meta={"actor_display": actor},
            )
        )
