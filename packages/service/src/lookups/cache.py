"""LookupCache: Redis L2 + 进程内 L1 (2026-06-19 lookup spec §2 + §5)

设计:
- L2 = Redis: 全字典 hash 存 1 个 key, 5 分钟 TTL
- L1 = 进程内 dict (microsecond 级)
- 写操作触发 DEL Redis + PUBLISH dict.invalidate 广播
- 启动订阅广播: 收到消息清 L1 (跨进程失效)

所有方法 async (业务侧 await); 内部用 src.core.redis_client.safe_* facade,
Redis 挂时 fail-open (返 None / False / 0, 业务侧当 cache miss 走 DB).

读路径 (L1 → L2 → DB):
- get_all(): L1 有返 L1; 否则 await safe_get Redis; Redis miss/挂 → 返 None, 业务侧走 DB
- set_all(): L1 + await safe_set Redis (失败仅 L1, 仍能本地命中)
- invalidate(): 清 L1 + await safe_delete Redis + publish 广播
"""

from __future__ import annotations

import asyncio
import json
import time

from loguru import logger

from src.core.redis_client import build_pubsub_client, get_redis, safe_delete, safe_get, safe_set

# 全字典 hash 唯一 key
_REDIS_KEY = "rag:dict:all"
# 5 分钟 TTL (跟 spec §2 一致, 广播丢消息时也兜底)
_REDIS_TTL = 300
# 失效广播 channel
_INVALIDATE_CHANNEL = "rag:dict:invalidate"


class LookupCache:
    """全局单例 (类属性 _instance), L1 (进程内 dict) + L2 (Redis) 双层缓存.

    公共方法均 async (内部 await safe_* facade). 业务侧不直接 new,
    用 `from src.lookups.cache import lookup_cache`.
    """

    _instance: LookupCache | None = None

    def __new__(cls) -> LookupCache:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._l1_data = None
        return cls._instance

    # ---- L2 (Redis) 异步读 / 写 ----

    async def get_all(self) -> dict[str, dict] | None:
        """读 L1 → L2. 返 {dict_code: {label_zh, label_en, version, items: [...]}}.

        None 表示 cache miss (业务侧应走 DB 重建 + set_all).
        """
        if self._l1_data is not None:
            return self._l1_data
        raw = await safe_get(_REDIS_KEY)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            self._l1_data = data
            return data
        except json.JSONDecodeError as e:
            logger.warning("lookup cache JSON 损坏, 走 DB 重建: {}", e)
            return None

    async def set_all(self, data: dict[str, dict]) -> None:
        """写 L1 (同步) + L2 (await safe_set). Redis 失败仅 L1 命中, 不抛."""
        self._l1_data = data
        ok = await safe_set(_REDIS_KEY, json.dumps(data, default=str), ex=_REDIS_TTL)
        if not ok:
            logger.warning("lookup cache Redis SET 失败, 退化到 L1 only")

    async def invalidate(self, dict_code: str | None = None) -> None:
        """清 L1 + DEL Redis + publish 广播. Redis 失败仅本进程 L1 失效, 跨进程靠 TTL 兜底."""
        self._l1_data = None
        await safe_delete(_REDIS_KEY)
        try:
            r = get_redis()
            await r.publish(_INVALIDATE_CHANNEL, dict_code or "*")
        except Exception as e:
            # broadcast 失败可容忍 (单进程部署 / Redis 挂都 OK), 仅 log
            logger.opt(exception=True).warning("lookup cache publish 广播失败: {}", e)

    # ---- 字典级便捷查询 (给 SafetyGuard 用) ----

    def get_dict_readonly(self, dict_code: str) -> bool:
        """查字典级 is_readonly. 同步, 走 L1 (L1 命中避免 round trip)."""
        data = self._l1_data or {}
        d = data.get(dict_code, {})
        return bool(d.get("is_readonly", False))

    def get_dict_version(self, dict_code: str) -> int:
        """查字典 schema 版本号. 同步, 走 L1 (L1 命中避免 round trip)."""
        data = self._l1_data or {}
        d = data.get(dict_code, {})
        return int(d.get("version", 0))

    # ---- 测试 / 调试用: 重置 L1 ----

    def reset_l1(self) -> None:
        """仅清 L1, 不动 Redis. 测试 setup / teardown 用."""
        self._l1_data = None


# 模块级单例 (供 service / safety_guard import)
lookup_cache = LookupCache()


# ---- 启动时 Redis pub/sub 订阅 (跨进程失效广播) ----


def start_invalidation_subscriber() -> asyncio.Task[None] | None:
    """启动后台 task 订阅 dict.invalidate channel, 收到消息清 L1.

    返回 task handle 供 lifespan shutdown 时显式 cancel + await, 防止
    fire-and-forget task 异常 propagate 到 uvicorn 主循环 (2026-06-23 实测:
    CancelledError → redis-py TimeoutError → uvicorn shutdown propagate →
    main() 返非 0 → SystemExit 1).

    没 event loop (CLI / 测试 import 期) → 直接返回 None, 不起订阅.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is None or not loop.is_running():
        # 没 event loop (CLI / 测试 import 期) → 直接返回, 不起订阅
        return None

    async def _subscriber() -> None:
        """订阅循环: 收到 dict.invalidate 消息 → 清 L1.

        关键设计 (2026-06-23 redis subscriber 修复):
        1. 用 build_pubsub_client() 拿**独立 connection** (socket_timeout=None),
           不复用 get_redis() 的共享 pool (socket_timeout=2s 跟 pubsub long-polling 必撞超时).
        2. while True + try/except + sleep 重连: 网络抖动 / Redis 重启 / timeout 都自动恢复,
           不会因一次异常导致跨进程失效永久失效.
        3. CancelledError 显式 break 退出循环 (lifespan shutdown 会 task.cancel()),
           其他异常 sleep 5s 重试.

        (2026-06-23) 降噪: 退避 5s → 30s, 首次失败 WARNING, 后续静默 INFO 直到恢复.
        解决 dev 环境不启 Redis 时日志被刷爆的问题.
        """
        backoff_s = 30
        silence_until = 0.0  # 首次失败立即 WARNING, 后续每 5min 重复
        while True:
            client = None
            try:
                client = build_pubsub_client()
                pubsub = client.pubsub()
                await pubsub.subscribe(_INVALIDATE_CHANNEL)
                if silence_until != 0:
                    logger.info("lookup cache subscriber 重连成功, 恢复订阅 channel={}", _INVALIDATE_CHANNEL)
                    silence_until = 0
                else:
                    logger.info("lookup cache invalidate subscriber 已启动 channel={}", _INVALIDATE_CHANNEL)
                async for msg in pubsub.listen():
                    # 格式: {'type': 'message', 'pattern': None, 'channel': 'rag:dict:invalidate', 'data': '*'}
                    if msg.get("type") == "message":
                        data = msg.get("data", "*")
                        if isinstance(data, bytes):
                            data = data.decode("utf-8", errors="ignore")
                        logger.info("lookup cache invalidate 广播收到 dict_code={}", data)
                        lookup_cache.reset_l1()
            except asyncio.CancelledError:
                # lifespan shutdown 调 task.cancel() → 优雅退出
                logger.info("lookup cache subscriber 收到 cancel, 退出")
                break
            except Exception as e:
                # Redis 挂 / pubsub 失败 / 网络抖动 → 退避后重试, 每 5min 重复 WARNING
                if time.time() > silence_until:
                    logger.warning(
                        "lookup cache subscriber 异常({}), 退避 {}s 重连: {}",
                        type(e).__name__,
                        backoff_s,
                        e,
                    )
                    silence_until = time.time() + 300  # 5min 静默
                try:
                    await asyncio.sleep(backoff_s)
                except asyncio.CancelledError:
                    break
            finally:
                # 关闭本轮独立 client (重连下一轮新建)
                if client is not None:
                    try:
                        await client.aclose()
                    except Exception:
                        pass

    try:
        return loop.create_task(_subscriber())
    except Exception as e:
        logger.opt(exception=True).warning("lookup cache subscriber 调度失败: {}", e)
        return None
