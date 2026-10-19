"""PermissionCache Redis 共享版 (2026-06-18 redis spec §5.1)

改造 [packages/service/src/permissions/cache.py](packages/service/src/permissions/cache.py):
- 进程内存 dict 保留 (Redis 挂时降级)
- 加 Redis 共享层: 60s TTL, 跨 worker 一致
- invalidate() 改 DEL Redis key (跨 worker 生效)

读路径: 优先 Redis → 失败/未命中 → PG (写本地 + 异步写 Redis)
失效: invalidate() DEL Redis key, 强制下次 _refresh_from_pg()

sync/async 双上下文兼容:
- 现有调用点 (guards.py / service.py) 是 sync, 走 `loop.run_until_complete` 调 facade
- 未来 async 端点可直接 await 调 facade (本期暂无)
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time

from loguru import logger
from sqlalchemy import text

from .redis_client import safe_delete, safe_get, safe_set

CACHE_KEY = "rag:perm:matrix"
CACHE_TTL = int(os.getenv("PERM_CACHE_TTL", "60"))  # 秒


class PermissionCacheRedis:
    """Permission 缓存, 进程内存 + Redis 共享双层.

    Attributes:
        _lock: RLock 保护本地 cache (并发安全).
        _local: 本地 fallback dict (Redis 挂时降级).
        _loaded_at: 本地 cache 加载时间戳 (epoch 秒).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._local: dict[str, dict[str, bool]] = {}
        self._loaded_at: float = 0.0

    def get(self, role: str, page_key: str) -> bool | None:
        """查 role × page 权限. Redis 优先, 失败降级本地.

        Args:
            role: 角色名 (e.g. 'admin', 'user', 自定义角色).
            page_key: 页面 key (e.g. 'chat', 'knowledge').

        Returns:
            bool: True=允许, False=拒绝.
            None: role 或 page_key 不存在 (跟原 PermissionCache 行为一致).
        """
        with self._lock:
            # 1. 本地 cache TTL 内, 直接返 (避免每请求 RTT Redis)
            if self._loaded_at > 0.0 and (time.time() - self._loaded_at) < CACHE_TTL:
                return self._local.get(role, {}).get(page_key)

            # 2. 试 Redis (sync 上下文, 用 run_until_complete)
            raw = self._sync_redis_get()
            if raw:
                try:
                    self._local = json.loads(raw)
                    self._loaded_at = time.time()
                    return self._local.get(role, {}).get(page_key)
                except json.JSONDecodeError:
                    logger.warning("perm cache JSON 损坏, 重读 PG")

            # 3. Redis miss / 失败 / 损坏 → 走 PG
            return self._refresh_from_pg(role, page_key)

    def invalidate(self) -> None:
        """DEL Redis key, 清本地 cache. 下次 get 触发 _refresh_from_pg().

        跨 worker 生效: DEL 让所有 worker 下次 get 走 PG 重建.
        """
        with self._lock:
            self._loaded_at = 0.0
            self._local = {}
            self._sync_redis_delete(CACHE_KEY)

    def _sync_redis_get(self) -> str | None:
        """sync 上下文安全调 async safe_get. 用一次性 event loop 跑. 失败返 None (走 PG)."""
        # 用 get_running_loop 检测是否在 async 上下文 (Py 3.14 兼容: get_event_loop 已 deprecated)
        try:
            asyncio.get_running_loop()
            # 在 async 上下文, 业务侧应该直接 await facade. 这里 fallback 到本地.
            return None
        except RuntimeError:
            # sync 上下文 (无 running loop), 起新 loop 跑 coroutine
            pass
        try:
            return asyncio.run(safe_get(CACHE_KEY))
        except Exception as e:
            logger.opt(exception=True).warning("perm cache Redis GET 失败, 走 PG fallback: {}", e)
            return None

    def _sync_redis_delete(self, key: str) -> None:
        """sync 上下文安全调 async safe_delete. 失败仅 log, 不抛."""
        try:
            asyncio.get_running_loop()
            return  # 在 async 上下文 fallback
        except RuntimeError:
            pass
        try:
            asyncio.run(safe_delete(key))
        except Exception as e:
            logger.opt(exception=True).warning("perm cache Redis DEL 失败 (best-effort): {}", e)

    def _refresh_from_pg(self, role: str, page_key: str) -> bool | None:
        """全表读 role_permissions. sync 版本, 兼容 sync 调用.

        写本地 + 异步刷 Redis (best effort, 失败不阻塞).
        """
        with self._lock:
            # 防循环: 顶层 from ..storage.session 会触发 src.storage 完整装载
            # (PG engine / session_scope / 基座 ORM 元数据), permission_cache 是冷启动必经
            from ..storage.session import session_scope  # noqa: E402

            new_matrix: dict[str, dict[str, bool]] = {}
            try:
                with session_scope() as s:
                    rows = s.execute(text("SELECT role_name, page_key, allowed FROM role_permissions")).fetchall()
                for role_name, pk, allowed in rows:
                    new_matrix.setdefault(role_name, {})[pk] = bool(allowed)
                self._local = new_matrix
                self._loaded_at = time.time()
                # 异步刷 Redis (best effort, 不阻塞当前请求)
                self._schedule_async_redis_set(new_matrix)
                return self._local.get(role, {}).get(page_key)
            except Exception as e:
                logger.opt(exception=True).error("permission cache PG 读失败: {}", e)
                return None

    def _schedule_async_redis_set(self, matrix: dict[str, dict[str, bool]]) -> None:
        """异步刷 Redis. sync 上下文: 起 thread 跑; async 上下文: create_task."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            # async 上下文, 用 create_task
            try:
                asyncio.create_task(safe_set(CACHE_KEY, json.dumps(matrix), ex=CACHE_TTL))
            except Exception as e:
                logger.opt(exception=True).warning("perm cache async SET 调度失败: {}", e)
        else:
            # sync 上下文 (测试 / 启动期 / 无 event loop), 起 daemon thread 跑 event loop
            def _runner() -> None:
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(safe_set(CACHE_KEY, json.dumps(matrix), ex=CACHE_TTL))
                    new_loop.close()
                except Exception as e:
                    logger.opt(exception=True).warning("perm cache sync SET 失败: {}", e)

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
