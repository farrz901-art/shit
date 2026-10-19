"""PermissionCache: 进程内存 + Redis 共享双层 (2026-06-18 redis spec §5.1)

实现迁移到 src.core.permission_cache_redis (新模块),
本文件保留 re-export, 兼容现有 permission_cache.invalidate() / .get() 调用.

(2026-06-19 lookup spec §3.5 迁移兼容期):
- ALL_PAGE_KEYS 保留 fallback tuple 8 个 (R1 兼容期, R2 删)
- 新增 get_all_page_keys() / get_all_page_keys_sync() 从 LookupService 拉 (启动时 warmup)
- 新增 get_all_page_metadata_sync() 同理, 返 list[dict] (含 path 在 metadata_json)
- 新增 warmup_page_keys() 在 main.py lifespan 启动时跑一次, 后续读走进程内缓存
"""

from __future__ import annotations

import asyncio

# 2026-06-18: 改用 Redis 共享版, 进程内 fallback 保留 (Redis 挂时降级)
from src.core.permission_cache_redis import PermissionCacheRedis

# ---- 旧硬编 fallback (R1 兼容期保留, R2 删) ----
ALL_PAGE_KEYS_FALLBACK: tuple[str, ...] = (
    "admin",
    "buyers",
    "chat",
    "output",
    "knowledge",
    "evaluate",
    "submissions",
    "decode",
    "health",
)

# 兼容旧引用: ALL_PAGE_KEYS = fallback tuple (业务代码无 DB 时仍可用)
# patch_permissions / create_role 校验 page_key 合法性的依据, fallback 8 个保证 R1 兼容期
# 业务稳定: 即使 LookupService 挂 / DB 未 seed, PATCH /me 也只接受这 8 个 page_key
ALL_PAGE_KEYS: tuple[str, ...] = ALL_PAGE_KEYS_FALLBACK

# ---- 进程内缓存 (DB miss / LookupService 挂时降级到 fallback) ----

_page_keys_cache: tuple[str, ...] | None = None  # warmup_page_keys() 后填充
_page_metadata_cache: list[dict] | None = None  # warmup_page_keys() 后填充

# fallback 元数据 (跟 ALL_PAGE_KEYS_FALLBACK 对应, DB 挂时返回)
# (2026-07-02 nav spec) 含 metadata 字段, 离线时仍渲染顶级平铺导航 (Phase-1 兼容)
_PAGE_METADATA_FALLBACK: list[dict] = [
    {"key": k, "label_zh": zh, "label_en": en, "path": f"/{k}", "is_active": True, "metadata": {"path": f"/{k}"}}
    for k, zh, en in [
        ("admin", "管理中心", "Admin"),
        ("buyers", "客户画像", "Buyers"),
        ("chat", "对话", "Chat"),
        ("output", "文档结构化", "Output"),
        ("knowledge", "知识库", "Knowledge"),
        ("evaluate", "评估", "Evaluate"),
        ("submissions", "审核中心", "Submissions"),
        ("decode", "型号解析", "Decode"),
        ("health", "监控", "Health"),
    ]
]


async def get_all_page_keys() -> tuple[str, ...]:
    """从 LookupService.get("page_key") 拉所有 active page_key, 返 tuple.

    LookupService.get 是 async, 内部走 Redis L2 → DB.
    异常 (DB 挂 / LookupService 没注册 / dict 不存在) → fallback 8 个, 保证 R1 兼容.
    """
    try:
        # 防循环: LookupService 顶层 import 会触发 lookups 全装载 (含 cache 子模块)
        from src.lookups.service import LookupService  # noqa: E402

        d = await LookupService.get("page_key", only_active=True)
        keys = tuple(item["key"] for item in d.get("items", []))
        if keys:
            return keys
    except Exception:
        # LookupService 不可用 / dict 未 seed → fallback (R1 兼容)
        pass
    return ALL_PAGE_KEYS_FALLBACK


async def get_all_page_metadata() -> list[dict]:
    """从 LookupService.get("page_key") 拉 items, 转成 [{key, label_zh, label_en, path}, ...].

    path 从 item.metadata_json.path 取 (yaml 种子定义), 没 path 用 /<key> 兜底.
    异常 → fallback 元数据 (8 项).
    """
    try:
        # 防循环: 同 warmup_page_keys, LookupService 顶层 import 触发 lookups 全装载
        from src.lookups.service import LookupService  # noqa: E402

        d = await LookupService.get("page_key", only_active=False)
        result: list[dict] = []
        for item in d.get("items", []):
            raw_meta = item.get("metadata_json")
            # (2026-07-02 nav spec §2.2) 透传整块 metadata_json, 缺失兜底空 dict
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            path = meta.get("path")
            result.append(
                {
                    "key": item["key"],
                    "label_zh": item.get("label_zh", item["key"]),
                    "label_en": item.get("label_en", item["key"]),
                    "path": path or f"/{item['key']}",
                    "is_active": item.get("is_active", True),
                    "metadata": meta,  # 整块 metadata_json 透传给前端 (parent_id / is_group / icon 等)
                }
            )
        if result:
            return result
    except Exception:
        pass
    return list(_PAGE_METADATA_FALLBACK)


def get_all_page_keys_sync() -> tuple[str, ...]:
    """同步版: 优先读进程内缓存, miss 时返 fallback tuple (R1 兼容).

    用于 router 同步上下文 (FastAPI Depends). 启动后 warmup_page_keys() 调一次,
    后续读走 _page_keys_cache.
    """
    if _page_keys_cache is not None:
        return _page_keys_cache
    return ALL_PAGE_KEYS_FALLBACK


def get_all_page_metadata_sync() -> list[dict]:
    """同步版: 优先读进程内缓存, miss 时返 fallback list (R1 兼容)."""
    if _page_metadata_cache is not None:
        return _page_metadata_cache
    return list(_PAGE_METADATA_FALLBACK)


async def warmup_page_keys() -> tuple[str, ...]:
    """启动时跑一次: 从 LookupService 拉 page_key, 填进程内缓存.

    返回填充后的 tuple (供 main.py 启动钩子打印 INFO).
    Redis / DB 挂时 silently 用 fallback, 启动不阻塞.
    """
    global _page_keys_cache, _page_metadata_cache
    keys = await get_all_page_keys()
    _page_keys_cache = keys
    meta = await get_all_page_metadata()
    _page_metadata_cache = meta
    return keys


# ---- 兼容旧导出名 ----
# ALL_PAGE_KEYS 已定义为 fallback tuple. R1 兼容期, 业务校验 (patch_permissions 等) 仍用此 fallback.
# 启动 warmup 后, 实际生效的是 _page_keys_cache (经 get_all_page_keys_sync 读).
PAGE_METADATA: list[dict] = _PAGE_METADATA_FALLBACK  # module-level fallback list (兼容旧引用)


def invalidate_page_keys_cache() -> None:
    """清进程内 page_keys / metadata 缓存 (写字典后调). 供 admin_router 调用.

    LookupService.invalidate 已广播 Redis L2; L1 进程内缓存由本函数清.
    若没调, 进程内缓存 stale 5min (LookupCache TTL 兜底).

    (2026-07-03) 拆成 2 步: 本函数只清 cache (保留原行为, 不连 DB / 改 contract).
    实际重填交给 `rewarm_page_keys_cache()` 异步入口, 由 admin_router 在
    async 上下文显式 await, 避免 running event loop 调 asyncio.run 炸.
    """
    global _page_keys_cache, _page_metadata_cache
    _page_keys_cache = None
    _page_metadata_cache = None


async def rewarm_page_keys_cache() -> None:
    """(2026-07-03) invalidate 后**异步**重填 cache, 避免下个 sync 读
    miss 走 fallback 9 项, 致前端 buildNavTree 报 orphan.

    admin_router (async 上下文) 写完字典调 invalidate_page_keys_cache() 后
    应 await 本函数, 重建进程内 L1 cache.
    """
    global _page_keys_cache, _page_metadata_cache
    keys = await get_all_page_keys()
    _page_keys_cache = keys
    meta = await get_all_page_metadata()
    _page_metadata_cache = meta


# ---- 同步入口 (CLI / 测试用) ----


def warmup_page_keys_sync() -> tuple[str, ...]:
    """同步版 warmup: 在已有 event loop 中跑会 RuntimeError, 用 asyncio.run 包一层.

    用于 check_dictionary_refs.py (CLI, 无 loop) / main.py _setup_dictionaries.
    """
    return asyncio.run(warmup_page_keys())


class PermissionCache:
    """保留兼容: 旧代码直接 import PermissionCache 时不爆. 实际实现已迁出.

    真正逻辑见 src.core.permission_cache_redis.PermissionCacheRedis.
    """

    def __init__(self, ttl_seconds: float = 30) -> None:  # noqa: ARG002 - 兼容旧签名
        # 委托给 Redis 版, 旧 ttl_seconds 参数不再使用 (Redis 版读 PERM_CACHE_TTL env)
        self._impl = PermissionCacheRedis()

    def get(self, role: str, page_key: str) -> bool | None:
        return self._impl.get(role, page_key)

    def invalidate(self) -> None:
        self._impl.invalidate()

    def _refresh(self) -> None:  # noqa: D401 - 保留旧方法名
        # 旧 _refresh 触发路径已合并到 PermissionCacheRedis._refresh_from_pg
        self._impl._refresh_from_pg("", "")


# (2026-06-18) PermissionCache 实例已指向 Redis 共享版. 单例仍叫 permission_cache.
permission_cache = PermissionCacheRedis()
