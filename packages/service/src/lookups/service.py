"""LookupService: 字典读写业务逻辑 (2026-06-19 lookup spec §2 + §四)

读路径: LookupCache (L1 → L2 → None) → DB load → 回写 cache
写路径: DB 事务 (insert/update/soft-delete) → cache.invalidate → audit_log

约束 (跟 cache 协同):
- 公共方法 async (内部 await lookup_cache.get_all / set_all / invalidate)
- DB 操作仍是 sync session_scope (项目所有 DB 操作都是 sync, 异步 SQLAlchemy 不在范围)
- 写后调用 cache.invalidate(dict_code), 触发跨进程广播 + 本地 L1 清
- 写后调用 audit.log_dict_change(...), actor/actor_id/ip 由 router 层传 (不读 request 避免耦合)

业务方法:
- list_all_dicts() → [{code, label_zh, label_en, version, is_active}]
- get(code, *, only_active, lang) → {code, label_zh, label_en, version, items}
- get_one(code, key) → 单个 item dict (raise LookupNotFoundError)
- create_item(code, payload, *, actor, actor_id, ip) → 新增 (raise 409 on duplicate)
- patch_item(code, key, payload, *, actor, actor_id, ip) → 改 (raise 404 if missing)
- patch_dict(code, payload, *, actor, actor_id, ip) → 改字典 metadata (T6)
- soft_delete_item(code, key, *, actor, actor_id, ip, force) → 软删 (raise 404 if missing)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from src.lookups.audit import log_dict_change
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupNotFoundError, LookupSafetyError
from src.lookups.models import Dictionary, DictionaryItem
from src.storage.session import session_scope


class LookupService:
    """DB 唯一事实源, cache 加速, 写操作触发缓存失效 + 审计.

    全静态方法 (无状态), 业务侧不实例化.
    """

    # ---- 读 (走 cache, DB fallback) ----

    @staticmethod
    async def list_all_dicts() -> list[dict[str, Any]]:
        """列出全部字典概要 (字典级, 不含 items).

        Returns:
            [{code, label_zh, label_en, version, is_active}, ...]
        """
        data = await lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            await lookup_cache.set_all(data)
        return [
            {
                "code": code,
                "label_zh": d["label_zh"],
                "label_en": d["label_en"],
                "version": d["version"],
                "is_active": d.get("is_active", True),
            }
            for code, d in data.items()
        ]

    @staticmethod
    async def get(
        dict_code: str,
        *,
        only_active: bool = True,
        lang: str = "both",
    ) -> dict[str, Any]:
        """查单字典 + items.

        Args:
            dict_code: 字典 code (e.g. "approval_review_status").
            only_active: True=只返 is_active=true (默认); False=含 deprecated.
            lang: "zh" | "en" | "both" (默认 both, 控制 label_* 字段返回).

        Returns:
            {code, label_zh, label_en, version, items: [...]}.

        Raises:
            LookupNotFoundError: 字典不存在.
        """
        data = await lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            await lookup_cache.set_all(data)
        d = data.get(dict_code)
        if d is None:
            raise LookupNotFoundError(f"dictionary '{dict_code}' not found")

        items = list(d.get("items", []))
        if only_active:
            items = [i for i in items if i.get("is_active", True)]
        if lang == "zh":
            items = [{k: v for k, v in i.items() if k != "label_en"} for i in items]
        elif lang == "en":
            items = [{k: v for k, v in i.items() if k != "label_zh"} for i in items]

        return {
            "code": dict_code,
            "label_zh": d["label_zh"],
            "label_en": d["label_en"],
            "version": d["version"],
            "items": items,
        }

    @staticmethod
    async def get_one(dict_code: str, key: str) -> dict[str, Any]:
        """查单个 item.

        Returns:
            单个 item dict.

        Raises:
            LookupNotFoundError: 字典或 item 不存在.
        """
        data = await lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            await lookup_cache.set_all(data)
        d = data.get(dict_code)
        if d is None:
            raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
        for item in d.get("items", []):
            if item["key"] == key:
                return item
        raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")

    # ---- 写 (DB + cache invalidate + audit) ----

    @staticmethod
    async def create_item(
        dict_code: str,
        payload: dict[str, Any],
        *,
        actor: str,
        actor_id: int,
        ip: str | None,
    ) -> dict[str, Any]:
        """新增 item. SafetyGuard 在 router 入口处已跑过 (鉴权/只读/版本/rate).

        Args:
            dict_code: 目标字典 code.
            payload: 必须含 key/label_zh/label_en; 可选 sort/description/metadata_json.
            actor: 显示名 (user.email 或 public_token, 写 audit_log meta).
            actor_id: user.id (AuditLog.actor_id NOT NULL).
            ip: request.client.host.

        Returns:
            新建的 item 字典 (含服务端填的 is_active=True 等).

        Raises:
            LookupNotFoundError: 字典不存在.
            LookupSafetyError: 409 已存在同 key item.
        """
        with session_scope() as s:
            # 验证字典存在
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one_or_none()
            if d is None:
                raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
            # 验证 key 不重复 (UNIQUE(dict_code, key) 约束外加显式查, 返 409 而非 DB 抛 IntegrityError)
            existing = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == payload["key"],
                )
            ).scalar_one_or_none()
            if existing:
                raise LookupSafetyError(409, f"item '{dict_code}:{payload['key']}' already exists")
            new_item = DictionaryItem(
                dict_code=dict_code,
                key=payload["key"],
                label_zh=payload["label_zh"],
                label_en=payload["label_en"],
                sort=payload.get("sort", 0),
                description=payload.get("description"),
                metadata_json=payload.get("metadata_json"),
            )
            s.add(new_item)
            # 字典 version + 1 (触发缓存失效 + 客户端下拉刷新)
            d.version = d.version + 1

        # 失效 cache + 审计 (顺序: 先失效再审计, 失败时 cache 仍 stale 但下次写会刷)
        await lookup_cache.invalidate(dict_code)
        log_dict_change(
            actor=actor,
            actor_id=actor_id,
            action="item.create",
            target=f"{dict_code}:{payload['key']}",
            before=None,
            after={**payload},
            ip=ip,
        )
        return {
            "key": payload["key"],
            "label_zh": payload["label_zh"],
            "label_en": payload["label_en"],
            "sort": payload.get("sort", 0),
            "is_active": True,
            "description": payload.get("description"),
            "metadata_json": payload.get("metadata_json"),
        }

    @staticmethod
    async def patch_dict(
        dict_code: str,
        payload: dict[str, Any],
        *,
        actor: str,
        actor_id: int,
        ip: str | None,
    ) -> dict[str, Any]:
        """改字典 metadata (label_zh/label_en/description/is_active/is_readonly).

        SafetyGuard 在 router 入口处已校验 readonly / 版本 / rate limit.

        Args:
            dict_code: 字典 code (URL path).
            payload: 可含 label_zh / label_en / description / is_active / is_readonly
                (只 apply 显式传的字段, 其他不动).
            actor: 显示名.
            actor_id: user.id.
            ip: 客户端 IP.

        Returns:
            更新后字典 dict (含 version / is_active / is_readonly / description).

        Raises:
            LookupNotFoundError: 字典不存在.
        """
        allowed_fields = ("label_zh", "label_en", "description", "is_active", "is_readonly")
        with session_scope() as s:
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one_or_none()
            if d is None:
                raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
            before = {
                "label_zh": d.label_zh,
                "label_en": d.label_en,
                "description": d.description,
                "is_active": d.is_active,
                "is_readonly": d.is_readonly,
            }
            for field in allowed_fields:
                if field in payload and payload[field] is not None:
                    setattr(d, field, payload[field])
            d.version = d.version + 1
            # 在 session_scope 内捕快照, 避免 close 后访问 detached ORM 属性
            after = {
                "label_zh": d.label_zh,
                "label_en": d.label_en,
                "description": d.description,
                "is_active": d.is_active,
                "is_readonly": d.is_readonly,
            }
            result = {
                "code": dict_code,
                "label_zh": d.label_zh,
                "label_en": d.label_en,
                "description": d.description,
                "version": d.version,
                "is_active": d.is_active,
                "is_readonly": d.is_readonly,
            }

        await lookup_cache.invalidate(dict_code)
        log_dict_change(
            actor=actor,
            actor_id=actor_id,
            action="dict.patch",
            target=dict_code,
            before=before,
            after=after,
            ip=ip,
        )
        return result

    @staticmethod
    async def patch_item(
        dict_code: str,
        key: str,
        payload: dict[str, Any],
        *,
        actor: str,
        actor_id: int,
        ip: str | None,
    ) -> dict[str, Any]:
        """改 item (label_zh/label_en/sort/description/metadata_json/is_active).

        不允许改 key (rename 需 POST 新 + migrate + DELETE 旧, 防 FK 残留).

        Raises:
            LookupNotFoundError: item 不存在.
        """
        with session_scope() as s:
            item = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == key,
                )
            ).scalar_one_or_none()
            if item is None:
                raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")
            # 改前快照 (用于 audit before)
            before = {
                "label_zh": item.label_zh,
                "label_en": item.label_en,
                "sort": item.sort,
                "is_active": item.is_active,
                "description": item.description,
                "metadata_json": item.metadata_json,
            }
            # 应用 patch (key 不允许改)
            allowed_fields = (
                "label_zh",
                "label_en",
                "sort",
                "is_active",
                "description",
                "metadata_json",
            )
            for field in allowed_fields:
                if field in payload and payload[field] is not None:
                    setattr(item, field, payload[field])
            # 字典 version + 1 (触发缓存失效)
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one()
            d.version = d.version + 1
            # after 快照
            after = {
                "label_zh": item.label_zh,
                "label_en": item.label_en,
                "sort": item.sort,
                "is_active": item.is_active,
                "description": item.description,
                "metadata_json": item.metadata_json,
            }

        await lookup_cache.invalidate(dict_code)
        log_dict_change(
            actor=actor,
            actor_id=actor_id,
            action="item.patch",
            target=f"{dict_code}:{key}",
            before=before,
            after=after,
            ip=ip,
        )
        return {"key": key, **after}

    @staticmethod
    async def soft_delete_item(
        dict_code: str,
        key: str,
        *,
        actor: str,
        actor_id: int,
        ip: str | None,
        force: bool = False,
    ) -> dict[str, Any]:
        """软删 item: is_active=False + deprecated_at=NOW().

        SafetyGuard 在 router 入口处已校验 confirm_token + (非 force 时) 引用检查.
        force=True 时绕过引用检查, audit log 标 forced=true.

        Returns:
            {key, is_active: False, deprecated_at: "<ISO8601>"}.

        Raises:
            LookupNotFoundError: item 不存在.
        """
        now = datetime.now(UTC)
        with session_scope() as s:
            item = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == key,
                )
            ).scalar_one_or_none()
            if item is None:
                raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")
            before_state = {"is_active": item.is_active, "deprecated_at": item.deprecated_at}
            item.is_active = False
            item.deprecated_at = now
            # 字典 version + 1
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one()
            d.version = d.version + 1
            after_state = {"is_active": False, "deprecated_at": now.isoformat()}

        await lookup_cache.invalidate(dict_code)
        log_dict_change(
            actor=actor,
            actor_id=actor_id,
            action="item.delete",
            target=f"{dict_code}:{key}",
            before=before_state,
            after=after_state,
            ip=ip,
            forced=force,
        )
        return {
            "key": key,
            "is_active": False,
            "deprecated_at": now.isoformat(),
            "forced": force,
        }

    # ---- DB load helper (cache miss 时重建) ----

    @staticmethod
    def _load_all_from_db() -> dict[str, dict[str, Any]]:
        """从 DB 全量加载字典 → cache 形态 dict[code] = {label_*, version, items: [...]}.

        同步 (DB 操作是 sync), 业务侧一般 await LookupService.list_all_dicts()
        内部调用. items 按 (dict_code, sort) 排序, 给前端稳定展示顺序.
        """
        with session_scope() as s:
            dicts = s.execute(select(Dictionary)).scalars().all()
            items = (
                s.execute(select(DictionaryItem).order_by(DictionaryItem.dict_code, DictionaryItem.sort))
                .scalars()
                .all()
            )
        result: dict[str, dict[str, Any]] = {}
        for d in dicts:
            result[d.code] = {
                "label_zh": d.label_zh,
                "label_en": d.label_en,
                "version": d.version,
                "is_active": d.is_active,
                "is_readonly": d.is_readonly,
                "items": [],
            }
        for item in items:
            if item.dict_code in result:
                result[item.dict_code]["items"].append(
                    {
                        "key": item.key,
                        "label_zh": item.label_zh,
                        "label_en": item.label_en,
                        "sort": item.sort,
                        "is_active": item.is_active,
                        "description": item.description,
                        "metadata_json": item.metadata_json,
                        "effective_at": item.effective_at,
                        "deprecated_at": item.deprecated_at,
                    }
                )
        return result
