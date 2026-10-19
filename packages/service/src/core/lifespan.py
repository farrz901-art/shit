"""FastAPI 启动/关闭生命周期 (lifespan)

提取自 product_decoders/app.py 的 _lifespan 和 main.py 的 3 个 _setup_* 函数.
按以下顺序执行:

启动:
  1. _setup_logging  — 配置 loguru + 接管 stdlib
  2. _setup_redis    — socket 探测 Redis 连通性 (fail-open)
  3. _setup_dictionaries — seed + check_consistency + subscriber + warmup
  4. start_health_loop    — 后台 5s 轮询 7 个 check
  5. register_schedulers  — APScheduler 定时任务 (每天 03:00 清理)

关闭:
  1. scheduler.shutdown(wait=False)
  2. stop_health_loop
  3. shutdown_logging (排空 loguru enqueue 队列)
  4. shutdown_redis   (关闭连接池)
"""

from __future__ import annotations

import asyncio
import os
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

# ============================================================
# _setup_logging — 配置 loguru + 接管 stdlib
# ============================================================


def _setup_logging() -> None:
    """配置 loguru + 接管 stdlib (2026-06-17 logging spec §5)"""
    # 启动期 lazy: logging 配置在 lifespan 触发时执行, 避免 import 时副作用 (写 sink / DB conn)
    from src.core.logging import configure_logging  # noqa: E402

    configure_logging(
        json_console=os.getenv("LOG_JSON", "false").lower() == "true",
        write_to_db=os.getenv("LOG_TO_DB", "true").lower() == "true",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


# ============================================================
# _setup_redis — 启动时验证 Redis 连通性 (fail-open)
# ============================================================


def _setup_redis() -> None:
    """启动时验证 Redis 连通性. 失败 WARNING, 不阻塞启动 (fail-open 设计).

    用 socket 探测, 不调 get_redis(). 因为此时无 running loop,
    get_redis() 创建的 pool 无 loop binding, 后续请求复用报
    'Future attached to a different loop'.
    """
    try:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        with socket.create_connection((host, port), timeout=2):
            pass
    except Exception as e:
        logger.warning("Redis warmup 失败: {}, 以降级模式启动 (走原路径)", e)


# ============================================================
# _setup_dictionaries — seed + check_consistency + subscriber + warmup
# ============================================================


def _setup_dictionaries() -> asyncio.Task[None] | None:
    """启动时字典 + 画像字段初始化.

    返回 subscriber task handle 供 lifespan shutdown 显式 cancel.

    顺序:
    1. seed 系统字典: 缺啥补啥, 不覆盖 admin 在 DB 改的 label
    2. seed 画像字段: profile_field_configs 为空时插 7 个默认字段
    3. start_invalidation_subscriber: 订阅 Redis dict.invalidate 广播

    失败行为:
    - seed 失败 → WARNING, 不阻塞 (DB 表可能不存在, R1 兼容期)
    - check_consistency async 失败 → RuntimeError 传播 (fail-fast)
    - subscriber 启动失败 → WARNING (跨进程失效靠 Redis TTL 兜底)
    - warmup_page_keys 失败 → WARNING (用 fallback 8 项)
    """
    # 1. seed 字典 (缺啥补啥, 不覆盖已存在)
    try:
        # 启动期 lazy: seed 脚本依赖 DB env + scripts 路径, lifespan 触发时才跑
        from scripts.seed_dictionaries import run_seed  # noqa: E402

        d, i = run_seed(force_sync=False)
        logger.info("字典 seed: {} 个新字典 + {} 个新 item", d, i)
    except Exception as e:
        logger.warning("字典 seed 失败: {}, 跳过 (降级模式)", e)

    # 2. seed 客户画像默认字段 (表空才插)
    try:
        # 启动期 lazy: 同上, scripts.seed_profile_fields 仅 lifespan 触发时需要
        from scripts.seed_profile_fields import run_seed as seed_fields  # noqa: E402

        cnt = seed_fields()
        if cnt:
            logger.info("画像字段 seed: {} 个默认字段", cnt)
    except Exception as e:
        logger.warning("画像字段 seed 失败: {}, 跳过 (降级模式)", e)

    # 3. 启动 Redis 订阅广播 (跨进程失效)
    task: asyncio.Task[None] | None = None
    try:
        # 启动期 lazy: Redis subscriber 推迟连接, 失败不阻塞 lifespan
        from src.lookups.cache import start_invalidation_subscriber  # noqa: E402

        task = start_invalidation_subscriber()
    except Exception as e:
        logger.warning("lookup cache 订阅启动失败: {}", e)
    return task


async def _async_setup_dictionaries() -> None:
    """(2026-06-23) 异步版 _setup_dictionaries: 跑 check_consistency_async + warmup_page_keys.

    设计原因: FastAPI lifespan 是 async context manager, 本身在 running event loop 里.
    同步版 _setup_dictionaries 调 scripts.check_dictionary_refs.check_consistency() 内部用
    asyncio.run 调 async LookupService, 会抛 'asyncio.run() cannot be called from a running event loop'.
    异步版直接 await 异步函数, 规避这个问题.

    调用顺序: 同步版 (seed + subscriber) 先跑, 然后 await 异步版 (check + warmup).
    """
    # 2. 字典一致性校验 (项缺失 / 被禁用时不阻塞启动)
    try:
        # 启动期 lazy: 一致性检查延后到 lifespan, scripts.check_dictionary_refs 在此才装载
        from scripts.check_dictionary_refs import check_consistency_async  # noqa: E402

        await check_consistency_async()
    except RuntimeError as e:
        logger.warning("字典一致性校验不一致, 跳过 (不影响启动): {}", e)
    except Exception as e:
        logger.warning("字典一致性校验跳过 (表未建?): {}: {}", type(e).__name__, e)
        logger.warning("修复: cd packages/service && uv run alembic upgrade head")

    # 4. warmup page_keys cache (permissions/router 用)
    try:
        # 启动期 lazy: permissions.cache 触发 redis 连接, 失败走 fallback 8 项不阻塞
        from src.permissions.cache import warmup_page_keys  # noqa: E402

        keys = await warmup_page_keys()
        logger.info("page_keys warmup: {} 个 page 已缓存", len(keys))
    except Exception as e:
        logger.warning("page_keys warmup 失败: {}, 用 fallback 8 项", e)


# ============================================================
# _lifespan — FastAPI 启动/关闭异步上下文管理器
# ============================================================


@asynccontextmanager
async def _lifespan(app: FastAPI):  # FastAPI lifespan 需要 yield
    """FastAPI 启动/关闭钩子."""
    # 启动期 lazy: health / scheduler 后台任务延后启动, lifespan 模块导入期不需要
    from src.health import start_health_loop, stop_health_loop  # noqa: E402
    from src.scheduler import register_schedulers  # noqa: E402

    # ----- 启动 -----
    _setup_logging()
    _setup_redis()
    subscriber_task = _setup_dictionaries()
    await _async_setup_dictionaries()

    # (2026-07-03) 启动时清理 orphan pre-analysis tasks (后端重启导致 BackgroundTasks 死的卡 running)
    try:
        # 启动期 lazy: pre_analysis.router 是大模块, orphan cleanup 只在 lifespan 启动触发一次
        from src.ingest.pre_analysis.router import _orphan_cleanup_pre_analysis_tasks  # noqa: E402, PLC0415

        cleaned = _orphan_cleanup_pre_analysis_tasks()
        if cleaned > 0:
            logger.warning("orphan pre-analysis tasks cleaned count={}", cleaned)
    except Exception:
        logger.exception("pre-analysis orphan cleanup failed (not fatal)")

    health_task = asyncio.create_task(start_health_loop(interval_s=5.0))
    scheduler = register_schedulers()

    try:
        yield
    finally:
        # ----- 关闭 -----
        # 1. 关 subscriber 后台 task: cancel + await 防 CancelledError propagate
        if subscriber_task is not None and not subscriber_task.done():
            subscriber_task.cancel()
            try:
                await subscriber_task
            except asyncio.CancelledError, Exception:
                pass  # task 已优雅取消

        # 2. 关 scheduler 时不等待正在跑的 job (避免挂起; 下次启动再跑)
        scheduler.shutdown(wait=False)
        await stop_health_loop(health_task)

        # shutdown: 排空 loguru enqueue 队列 (2026-06-17 logging spec §5)
        # 启动期 lazy: shutdown 推迟到 lifespan 关闭阶段, 模块加载期不引入
        from src.core.logging import shutdown_logging  # noqa: E402

        shutdown_logging()

        # shutdown: 关闭 Redis 连接池 (2026-06-18 redis spec §4)
        # 捕 Exception 防止 Windows proactor 残留 I/O 事件抛 InvalidStateError
        try:
            # 启动期 lazy: redis shutdown 同样推迟, 跟 startup 路径解耦
            from src.core.redis_client import shutdown_redis  # noqa: E402

            await shutdown_redis()
        except Exception as exc:
            logger.warning("shutdown_redis 异常(非致命) err={}", exc)
