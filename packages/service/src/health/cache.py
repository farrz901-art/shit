"""Health check 后台 cache (2026-06-11)

进程内单例 cache + 5s asyncio task 持续刷新.
HTTP handler 直接读 cache (亚毫秒响应).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from . import checks as _checks

# 模块级 cache + lock
_health_cache: dict[str, Any] | None = None
_cache_lock = asyncio.Lock()


def get_cached_health() -> dict[str, Any]:
    """读 cache. 启动后 <1s 若无数据 → 返 warming_up 占位."""
    if _health_cache is None:
        return {
            "checked_at": None,
            "status": "warming_up",
            "python": {"status": "ok", "latency_ms": 0.0, "error": None, "extra": {}},
            "dify": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
            "neo4j": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
            "pgvector": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
            "system": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
            "minio": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
            "redis": {"status": "ok", "latency_ms": None, "error": None, "extra": {}},
        }
    return _health_cache


def set_cached_health(payload: dict[str, Any]) -> None:
    """写 cache (测试 + 内部用)."""
    global _health_cache
    _health_cache = payload


async def _run_all_checks() -> dict[str, Any]:
    """(2026-06-18) 7 check 并发跑, 加 check_redis."""
    python_r = _checks.check_python()
    dify_r, neo4j_r, pgvector_r, system_r, minio_r, redis_r = await asyncio.gather(
        _checks.check_dify(),
        _checks.check_neo4j(),
        _checks.check_pgvector(),
        _checks.check_system(),
        _checks.check_minio(),
        _checks.check_redis(),
        return_exceptions=False,
    )
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "python": python_r.__dict__,
        "dify": dify_r.__dict__,
        "neo4j": neo4j_r.__dict__,
        "pgvector": pgvector_r.__dict__,
        "system": system_r.__dict__,
        "minio": minio_r.__dict__,
        "redis": redis_r.__dict__,
    }


async def start_health_loop(interval_s: float = 5.0) -> None:
    """后台 task: 每 interval_s 秒跑 7 个 check, 写 cache.
    失败不退出, 下个周期重试."""
    while True:
        try:
            async with _cache_lock:
                payload = await _run_all_checks()
                set_cached_health(payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(interval_s)


async def stop_health_loop(task: asyncio.Task) -> None:
    """测试 + lifespan 用: 取消后台 task."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
