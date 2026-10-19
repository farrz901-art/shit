"""Redis 客户端 facade (2026-06-18 redis spec §4)

跟 logging.py 同款 facade 模式:
- 业务侧只调 get_redis() 或 safe_*(key, ...), 不直接 import redis
- 单例 ConnectionPool, max_connections=20
- 任何 RedisError 在 facade 层 catch + log CRITICAL
- 业务侧可信任 facade: 失败返 None / 0 / False, 当 cache miss 处理

(2026-06-22) Loop-aware pool: aioredis.ConnectionPool 创建时绑定**首个**调用它的事件循环,
跨 loop 复用会抛 "Future attached to a different loop" (permission_cache_redis:_sync_redis_get 实测).
修法: 记 _pool 创建时的 loop 弱引用, get_redis() 检查当前 running loop 不同就 reset pool.

(2026-06-23) 熔断器: Redis 不可达时, safe_* 静默降级 N 秒 (默认 30s) 不再 spam CRITICAL 日志.
解决 dev 环境不启 Redis 时日志被刷爆的问题.
"""

from __future__ import annotations

import asyncio
import time
import weakref

import redis.asyncio as aioredis
from loguru import logger

from src.config.settings import settings

# 模块级单例
_pool: aioredis.ConnectionPool | None = None
# 持有 pool 创建时的 loop 弱引用, 防止 loop 被 GC 后 weakref 返回 None 假阳性 reset
_pool_loop: weakref.ReferenceType[asyncio.AbstractEventLoop] | None = None

# (2026-06-23) 熔断器: Redis 不可达时短路所有 safe_*, 不刷 CRITICAL spam
_CIRCUIT_OPEN_SECONDS = settings.redis_circuit_open_seconds
_circuit_open_until: float = 0.0  # unix timestamp, 0 表示 closed
_circuit_first_failure_logged: bool = False  # 单次失败期内只 log 一次


def _is_circuit_open() -> bool:
    """熔断中 → True, 业务侧直接降级 (不动 Redis, 不 log)."""
    return time.monotonic() < _circuit_open_until


def _trip_circuit(err: BaseException) -> None:
    """记录失败, 打开熔断 _CIRCUIT_OPEN_SECONDS 秒. 首次失败 log WARNING, 后续静默."""
    global _circuit_open_until, _circuit_first_failure_logged
    _circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS
    if not _circuit_first_failure_logged:
        logger.warning(
            "redis 不可达, 打开熔断 {}s (期间 safe_* 静默降级, 不再 spam): {}",
            _CIRCUIT_OPEN_SECONDS,
            err,
        )
        _circuit_first_failure_logged = True


def _reset_circuit_if_due() -> None:
    """熔断到期 → 重置 (下次调用 safe_* 会真试一次, 成功就恢复)."""
    global _circuit_open_until, _circuit_first_failure_logged
    if _circuit_open_until != 0.0 and time.monotonic() >= _circuit_open_until:
        _circuit_open_until = 0.0
        _circuit_first_failure_logged = False
        logger.info("redis 熔断到期, 下次调用尝试恢复连接")


def _build_pool() -> aioredis.ConnectionPool:
    """构造 ConnectionPool. 启动时 get_redis() lazy 调一次."""
    return aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        decode_responses=True,  # 业务侧直接拿 str
        max_connections=settings.redis_max_connections,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_connect_timeout,
        health_check_interval=30,  # 30s 探活
    )


def get_redis() -> aioredis.Redis:
    """业务侧调本函数拿 Redis 客户端. lazy init + 模块级单例 + loop 感知.

    Returns:
        aioredis.Redis: 业务侧直接 await .get/.set/.delete/.pipeline
    """
    global _pool, _pool_loop
    current_loop = _get_current_loop()
    # 跨 loop: reset pool (避免 'attached to a different loop')
    if _pool is not None and current_loop is not None and _pool_changed_loop(current_loop):
        logger.info(
            "redis pool loop 变化 (was={} now={}), 重置 pool",
            _pool_loop,
            current_loop,
        )
        _pool = None
        _pool_loop = None
    if _pool is None:
        _pool = _build_pool()
        if current_loop is not None:
            _pool_loop = weakref.ref(current_loop)
        logger.info(
            "redis 连接池已初始化 host={} max_conn={}",
            _pool.connection_kwargs.get("host"),
            _pool.max_connections,
        )
    return aioredis.Redis(connection_pool=_pool)


def _get_current_loop() -> asyncio.AbstractEventLoop | None:
    """拿当前 running loop (safe — 没 loop 时返 None 不抛)."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # 没 running loop (e.g. 同步上下文 import 阶段), 返 None
        return None


def _pool_changed_loop(current_loop: asyncio.AbstractEventLoop) -> bool:
    """检查 _pool 创建时的 loop 跟 current_loop 是否不同.

    weakref 返回 None 表示 loop 已 GC → 视作已变, 重置.
    _pool_loop 为 None 时 (pool 在 warmup 阶段创建, 当时无 running loop),
    也视为已变, 重建绑定正确 loop (2026-06-22 修复: 之前返 False 导致
    无 loop binding 的 pool 被误复用 → 'Future attached to a different loop').
    """
    if _pool_loop is None:
        # warmup/import 阶段创建的 pool 无 loop binding, 现在有 loop 必须重建
        return True
    prev_loop = _pool_loop()
    if prev_loop is None:
        return True  # 老 loop 被 GC
    return prev_loop is not current_loop


async def safe_get(key: str) -> str | None:
    """facade: GET, 失败返 None + log CRITICAL (不抛).

    业务侧当 miss 处理, 走原路径 (PG / 进程内存).

    (2026-06-23) 熔断: Redis 不可达时 _is_circuit_open() → True, 直接返 None,
    不发请求不 log, 避免 dev 环境不启 Redis 时日志刷爆.

    捕 4 类已知异常, 不捕裸 Exception (防掩盖业务 Bug):
    - RedisError / 子类: 超时, 连接拒绝, 响应错误
    - OSError: socket 层错误
    - RuntimeError: event loop 关闭后 'Event loop is closed'
    - AttributeError: (2026-06-22) pipe.execute() → NoneType.send
    """
    if _is_circuit_open():
        return None  # 熔断中, 静默降级
    try:
        # aioredis 返 bytes | str | None (decode_responses 取决于 client 配置), 业务侧统一 str
        val = await get_redis().get(key)
        _reset_circuit_if_due()  # 成功 → 重置熔断标记
        if val is None:
            return None
        return val.decode() if isinstance(val, bytes) else val
    except (aioredis.RedisError, OSError, RuntimeError, AttributeError) as e:
        _trip_circuit(e)
        return None


async def safe_set(key: str, value: str, ex: int | None = None) -> bool:
    """facade: SET + EX (秒), 失败返 False.

    Args:
        key: Redis key
        value: 值 (str, 业务侧 JSON serialize)
        ex: 过期秒数, None = 永不过期 (慎用)
    """
    if _is_circuit_open():
        return False  # 熔断中, 静默降级
    try:
        result = bool(await get_redis().set(key, value, ex=ex))
        _reset_circuit_if_due()
        return result
    except (aioredis.RedisError, OSError, RuntimeError, AttributeError) as e:
        _trip_circuit(e)
        return False


async def safe_delete(*keys: str) -> int:
    """facade: DEL, 失败返 0. 多 key 用 *keys 传 (DEL k1 k2 ...)."""
    if _is_circuit_open():
        return 0  # 熔断中, 静默降级
    try:
        result = int(await get_redis().delete(*keys))
        _reset_circuit_if_due()
        return result
    except (aioredis.RedisError, OSError, RuntimeError, AttributeError) as e:
        _trip_circuit(e)
        return 0


async def safe_incr(key: str, ex_seconds: int | None = None) -> int | None:
    """facade: INCR + EXPIRE NX (原子 pipeline). 失败返 None.

    用例: 限流计数. INCR 1 次, 仅首次设 TTL (NX 防止覆盖).
    业务侧拿 None 当 fail-open 处理 (放行, 走原路径).
    """
    if _is_circuit_open():
        return None  # 熔断中, 静默降级
    try:
        r = get_redis()
        # transaction=False: 不需要 MULTI/EXEC, INCR + EXPIRE 各自独立
        async with r.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            if ex_seconds:
                pipe.expire(key, ex_seconds, nx=True)
            results = await pipe.execute()
        _reset_circuit_if_due()
        return int(results[0])
    except (aioredis.RedisError, OSError, RuntimeError, AttributeError) as e:
        _trip_circuit(e)
        return None


def build_pubsub_client() -> aioredis.Redis:
    """构造**专用** pubsub 客户端 (socket_timeout=None, 独立连接).

    pubsub 模型本质是长 block 等消息, 共享 pool 的 socket_timeout=2s 会立刻撞超时
    (现象: redis.exceptions.TimeoutError 在 pubsub.listen() 反复 spam, 见 2026-06-23 实测).

    本函数返回每次新建的独立 Redis 客户端, 调用方负责生命周期 (用完 close()).
    跟 get_redis() (共享 pool, short-lived 命令) 分离, 互不影响.
    """
    return aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        decode_responses=True,
        # 关键: pubsub 不能设 socket_timeout, 否则 listen() 立刻超时
        socket_timeout=None,
        socket_connect_timeout=settings.redis_connect_timeout_pubsub,
        health_check_interval=30,
    )


async def shutdown_redis() -> None:
    """FastAPI shutdown 钩子. 关闭连接池, 避免 uvicorn reload 'Event loop is closed'.

    Windows + Python 3.14 proactor 下, IOCP 残留的 I/O 完成事件可能跟已取消的
    Future 冲突, 抛 InvalidStateError. 捕已知异常兜底, 不阻塞 shutdown 流程.
    """
    global _pool, _pool_loop
    if _pool is not None:
        try:
            await _pool.disconnect()
        except (aioredis.RedisError, OSError, RuntimeError, asyncio.InvalidStateError) as e:
            logger.warning("redis pool disconnect 异常(非致命) err={}", e)
        _pool = None
        _pool_loop = None
        logger.info("redis 连接池已关闭")
