"""buyer_profile/field_config.py (2026-06-22)

画像字段定义 (profile_field_configs) CRUD.
所有 insert/update/delete 走 raw SQL + session_scope.

(2026-06-23) 去掉 account_id: 字段配置是全局模板, 不按账号隔离.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from src.storage.session import session_scope


def get_active_configs() -> list[dict]:
    """查询所有启用的字段配置, 按 sort_order 排序 (给 extractor 用)."""
    query = "SELECT * FROM profile_field_configs WHERE is_active = true ORDER BY sort_order"
    with session_scope() as sess:
        rows = sess.execute(text(query)).mappings().all()
        return [dict(r) for r in rows]


def get_all_configs() -> list[dict]:
    """查询所有字段配置 (含停用的), 按 sort_order 排序 (给 admin 管理页用)."""
    query = "SELECT * FROM profile_field_configs ORDER BY sort_order"
    with session_scope() as sess:
        rows = sess.execute(text(query)).mappings().all()
        return [dict(r) for r in rows]


def create_config(data: dict) -> dict:
    """创建新字段配置, 返回含 id 的完整记录."""
    query = """INSERT INTO profile_field_configs
        (code, label, field_type, extraction_prompt,
         options, is_required, sort_order, notify_on_change)
        VALUES (:code, :label, :ft, :ep, :opts, :req, :sort, :notify)
        RETURNING *"""
    with session_scope() as sess:
        r = (
            sess.execute(
                text(query),
                {
                    "code": data["code"],
                    "label": data.get("label", ""),
                    "ft": data.get("field_type", "text"),
                    "ep": data.get("extraction_prompt"),
                    "opts": json.dumps(data.get("options", [])),
                    "req": data.get("is_required", False),
                    "sort": data.get("sort_order", 0),
                    "notify": json.dumps(data.get("notify_on_change", [])),
                },
            )
            .mappings()
            .one()
        )
        return dict(r)


def update_config(code: str, data: dict) -> dict | None:
    """更新字段配置. 只更新 data 中存在的允许字段, 返回更新后记录或 None."""
    allowed = (
        "label",
        "field_type",
        "extraction_prompt",
        "options",
        "is_required",
        "is_active",
        "notify_on_change",
        "sort_order",
    )
    sets = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not sets:
        return None
    set_clause = ", ".join(f"{k} = :{k}" for k in sets)
    sets["code"] = code
    query = f"UPDATE profile_field_configs SET {set_clause} WHERE code = :code RETURNING *"
    with session_scope() as sess:
        r = sess.execute(text(query), sets).mappings().one_or_none()
        return dict(r) if r else None


def soft_delete_config(code: str) -> bool:
    """软删字段配置 (is_active = false). 返回 True 表示真有记录被更新."""
    query = "UPDATE profile_field_configs SET is_active = false WHERE code = :code"
    with session_scope() as sess:
        r = sess.execute(text(query), {"code": code})
        return r.rowcount > 0  # type: ignore[reportAttributeAccessIssue]  # SQLAlchemy Result.rowcount
