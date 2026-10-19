"""buyer_profile/service.py: ProfileService 核心 (2026-06-22)

画像的 CRUD + LLM 提取编排.
update_profile_fields 同时调用 change_notifier 记录变更.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import text

from src.storage.session import session_scope

from .change_notifier import check_and_notify, detect_changes, log_changes
from .field_config import get_active_configs
from .schemas import BuyerProfileUpdate, ProfileFieldValue


class ProfileService:
    """客户画像 CRUD + LLM 提取."""

    @staticmethod
    def create_or_get_profile(
        account_id: int,
        buyer_key: str,
        buyer_name: str | None = None,
    ) -> dict | None:
        """UPSERT: 按 (account_id, buyer_key) 创建或更新 last_contact_at.

        首次创建时写入 first_seen_at + last_contact_at,
        已有记录时仅更新 last_contact_at 和 buyer_name.
        """
        query = """INSERT INTO buyer_profiles (account_id, buyer_key, buyer_name)
            VALUES (:aid, :key, :name)
            ON CONFLICT (account_id, buyer_key)
            DO UPDATE SET last_contact_at = NOW(),
                          buyer_name = COALESCE(:name, buyer_profiles.buyer_name)
            RETURNING *"""
        with session_scope() as sess:
            r = (
                sess.execute(
                    text(query),
                    {"aid": account_id, "key": buyer_key, "name": buyer_name},
                )
                .mappings()
                .one_or_none()
            )
            return dict(r) if r else None

    @staticmethod
    def get_profile(account_id: int, buyer_key: str) -> dict | None:
        """按 (account_id, buyer_key) 查询单个画像."""
        query = "SELECT * FROM buyer_profiles WHERE account_id = :aid AND buyer_key = :key"
        with session_scope() as sess:
            r = sess.execute(text(query), {"aid": account_id, "key": buyer_key}).mappings().one_or_none()
            return dict(r) if r else None

    @staticmethod
    def _validate_profile_data(fields: dict) -> dict:
        """验证 profile_data 字段值符合 ProfileFieldValue schema.

        DATA-008 修复: 写库前确保字段结构一致,
        不同来源 (auto/manual/import) 写出统一的 {value, confidence, source, updated_at} 结构.
        失败时记 warning 并重新抛出, 阻止脏数据入库.
        """
        now = datetime.now(UTC).isoformat()
        validated: dict[str, dict] = {}
        for code, value in fields.items():
            entry = {
                "value": value,
                "confidence": "high" if value else "medium",
                "source": "auto",
                "updated_at": now,
            }
            try:
                pfv = ProfileFieldValue.model_validate(entry)
                validated[code] = pfv.model_dump(mode="json")
            except ValidationError as e:
                logger.warning("profile_data 数据非法 code={} error={}", code, e)
                raise
        return validated

    @staticmethod
    def update_profile_fields(
        account_id: int,
        buyer_key: str,
        fields: dict,
    ) -> bool:
        """更新画像字段 (PG || 原子 merge 到 profile_data JSONB).

        先用 change_notifier 检测变更并记日志, 然后用 PG jsonb || 做原子合并,
        消除 app 层 RMW 丢字段竞态 (CON-004).

        (2026-06-24) 同步 contact_person → buyer_name 列:
        LLM 抽到 contact_person 后, 若 buyer_name 列还为空, 把值同步到列上,
        否则前端列表 / 详情头 buyer_name 永远显示 null (profile_data 里有名字
        但列里没人写). 已有 buyer_name 时不覆盖, 保留人工设置的优先级.
        """
        # 构建待合并的 JSON 对象: {code: {value, confidence, source, updated_at}, ...}
        # 用 ProfileFieldValue schema 验证字段结构 (DATA-008)
        merge_obj = ProfileService._validate_profile_data(fields)

        # 确保 profile 存在 (变更检测需要旧快照, best-effort 读)
        existing = ProfileService.get_profile(account_id, buyer_key)
        if not existing:
            ProfileService.create_or_get_profile(account_id, buyer_key)
            existing = ProfileService.get_profile(account_id, buyer_key)
            if not existing:
                return False

        # 变更检测 (best-effort 读旧值, 仅审计; 不参与写路径)
        changes = detect_changes(
            existing.get("profile_data") or {},
            fields,
        )
        profile_id = existing["id"]
        if isinstance(profile_id, UUID):
            profile_id_str = str(profile_id)
        else:
            profile_id_str = str(profile_id)
        log_changes(account_id, profile_id_str, changes)

        configs = get_active_configs()
        check_and_notify(account_id, changes, configs)

        # (2026-06-24) buyer_name 列同步: contact_person 抽到 + buyer_name 列空 → 写列
        # (避免用户在前端列表看到一片 null/—; 已有人工设置的不覆盖)
        contact_person_value = fields.get("contact_person")
        should_sync_name = (
            contact_person_value and isinstance(contact_person_value, str) and not existing.get("buyer_name")
        )

        # PG jsonb || 原子 merge: 交给 DB 做字段级合并, 避免 app 层 RMW 丢字段.
        # COALESCE(profile_data, '{}'::jsonb) 处理首写时 NULL profile_data 的情况.
        # CAST(:merge AS jsonb) 避免 SA 2.0 + psycopg3 对 ::jsonb 双冒号歧义.
        if should_sync_name:
            query = """UPDATE buyer_profiles SET
                    profile_data = COALESCE(profile_data, '{}'::jsonb) || CAST(:merge AS jsonb),
                    buyer_name = :name,
                    updated_at = NOW()
                WHERE account_id = :aid AND buyer_key = :key"""
            params = {
                "merge": json.dumps(merge_obj),
                "name": contact_person_value,
                "aid": account_id,
                "key": buyer_key,
            }
        else:
            query = """UPDATE buyer_profiles SET
                    profile_data = COALESCE(profile_data, '{}'::jsonb) || CAST(:merge AS jsonb),
                    updated_at = NOW()
                WHERE account_id = :aid AND buyer_key = :key"""
            params = {
                "merge": json.dumps(merge_obj),
                "aid": account_id,
                "key": buyer_key,
            }
        with session_scope() as sess:
            r = sess.execute(text(query), params)
            return r.rowcount > 0  # type: ignore[reportAttributeAccessIssue]  #  SQLAlchemy Result.rowcount

    @staticmethod
    def list_profiles(
        account_id: int,
        limit: int = 20,
        offset: int = 0,
        filters: dict | None = None,
    ) -> tuple[list[dict], int]:
        """分页列出画像, 支持 status 过滤."""
        where = "account_id = :aid"
        params: dict[str, Any] = {"aid": account_id, "lim": limit, "off": offset}
        if filters and filters.get("status"):
            where += " AND status = :status"
            params["status"] = filters["status"]

        count_q = f"SELECT count(*) FROM buyer_profiles WHERE {where}"
        data_q = f"SELECT * FROM buyer_profiles WHERE {where} ORDER BY updated_at DESC LIMIT :lim OFFSET :off"
        with session_scope() as sess:
            total = sess.execute(text(count_q), params).scalar() or 0
            rows = sess.execute(text(data_q), params).mappings().all()
            return [dict(r) for r in rows], total

    @staticmethod
    def soft_delete(account_id: int, profile_id: UUID) -> bool:
        """软删画像 (status = 'archived')."""
        query = "UPDATE buyer_profiles SET status = 'archived', updated_at = NOW() WHERE id = :id AND account_id = :aid"
        with session_scope() as sess:
            r = sess.execute(text(query), {"id": profile_id, "aid": account_id})
            return r.rowcount > 0  # type: ignore[reportAttributeAccessIssue]  # SQLAlchemy Result.rowcount

    @staticmethod
    def get_profile_by_id(account_id: int, profile_id: UUID) -> dict | None:
        """按 UUID id 查询单个画像 (router get 端点用)."""
        query = "SELECT * FROM buyer_profiles WHERE id = :id AND account_id = :aid"
        with session_scope() as sess:
            r = sess.execute(text(query), {"id": profile_id, "aid": account_id}).mappings().one_or_none()
            return dict(r) if r else None

    @staticmethod
    def update_profile_by_id(
        account_id: int,
        profile_id: UUID,
        body: BuyerProfileUpdate,
    ) -> bool:
        """按 UUID id 更新画像字段 (router patch 端点用).

        只更新 body 中非 None 的字段, profile_data 自动 JSON 序列化.
        """
        sets: dict[str, Any] = {}
        for field in ("buyer_name", "status", "tags", "notes", "profile_data"):
            val = getattr(body, field, None)
            if val is not None:
                sets[field] = val
        if not sets:
            return False
        if "profile_data" in sets:
            sets["profile_data"] = json.dumps(sets["profile_data"])
        set_clause = ", ".join(f"{k} = :{k}" for k in sets)
        sets["aid"] = account_id
        sets["id"] = profile_id
        query = f"UPDATE buyer_profiles SET {set_clause}, updated_at = NOW() WHERE id = :id AND account_id = :aid"
        with session_scope() as sess:
            r = sess.execute(text(query), sets)
            return r.rowcount > 0  # type: ignore[reportAttributeAccessIssue]  # SQLAlchemy Result.rowcount

    @staticmethod
    def get_changes(account_id: int, profile_id: UUID) -> list[dict]:
        """获取画像变更日志 (router changes 端点用)."""
        query = """SELECT id, profile_id, field_code, old_value, new_value, source, conv_id, created_at
                   FROM profile_change_logs
                   WHERE account_id = :aid AND profile_id = :pid
                   ORDER BY created_at DESC LIMIT 100"""
        with session_scope() as sess:
            rows = sess.execute(text(query), {"aid": account_id, "pid": profile_id}).mappings().all()
            return [dict(r) for r in rows]

    @staticmethod
    def try_extract(
        account_id: int,
        buyer_key: str,
        messages: list[dict],
    ) -> None:
        """fire-and-forget: LLM 从对话提取画像字段.

        失败时静默记录 warning, 不向上抛异常.
        """
        try:
            configs = get_active_configs()
            if not configs:
                return
            profile = ProfileService.get_profile(account_id, buyer_key)
            existing = (profile or {}).get("profile_data") or {}
            result = extract_fields(configs, existing, messages)
            if result:
                ProfileService.update_profile_fields(
                    account_id,
                    buyer_key,
                    result,
                )
        except Exception as e:
            logger.opt(exception=True).warning(
                "buyer profile extract failed aid={} key={} err={}",
                account_id,
                buyer_key,
                e,
            )


# 避免循环 import: extract_fields 只在 try_extract 中才引用
from .extractor import extract_fields  # noqa: E402
