"""Permission 业务逻辑: 读 matrix, PATCH 写回, 触发 cache invalidate"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from ..storage.session import session_scope
from .cache import get_all_page_keys_sync, permission_cache
from .models import Role, RolePermission


def get_full_matrix() -> dict[str, dict[str, bool]]:
    """从 cache 读 role × page 完整矩阵 (super_admin 不在)

    实现: 强制 invalidate 后从 DB 读最新矩阵, super_admin 行代码层过滤.
    """
    permission_cache.invalidate()  # 强制刷新 (admin 列表可能变了)
    matrix: dict[str, dict[str, bool]] = {}
    page_keys = get_all_page_keys_sync()  # warmup 后实时值 (含新加 page_key)
    with session_scope() as s:
        roles = list(s.query(Role).all())
        for r in roles:
            role_name = cast(str, r.name)
            if role_name == "super_admin":
                continue  # meta 豁免, super_admin 不入库不入矩阵
            matrix[role_name] = {k: False for k in page_keys}  # 默认 false
        perms = list(s.query(RolePermission).all())
        for p in perms:
            rname = cast(str, p.role_name)
            pkey = cast(str, p.page_key)
            allowed = cast(bool, p.allowed)
            matrix.setdefault(rname, {})[pkey] = allowed
    return matrix


def update_permissions(updates: list[dict]) -> int:
    """批量 UPSERT role_permissions. 返回更新行数.

    跳过 super_admin (代码层 meta 豁免). 写完 commit 后立即 invalidate cache.
    """
    with session_scope() as s:
        for u in updates:
            role_name = u["role_name"]
            page_key = u["page_key"]
            allowed = u["allowed"]
            if role_name == "super_admin":
                continue  # meta 豁免, 跳过
            existing = s.query(RolePermission).filter_by(role_name=role_name, page_key=page_key).first()
            if existing is not None:
                existing.allowed = allowed  # type: ignore[assignment]
                existing.updated_at = datetime.now(UTC)  # type: ignore[assignment]
            else:
                s.add(
                    RolePermission(
                        role_name=role_name,
                        page_key=page_key,
                        allowed=allowed,
                    )
                )
        s.flush()
    permission_cache.invalidate()
    return len(updates)


def get_my_permissions(role: str) -> list[str]:
    """返 role 可访问 page_key 列表. super_admin 返全部 (走 warmup 实时 cache, 含新加 page_key)."""
    page_keys = get_all_page_keys_sync()
    if role == "super_admin":
        return list(page_keys)
    return [k for k in page_keys if permission_cache.get(role, k) is True]
