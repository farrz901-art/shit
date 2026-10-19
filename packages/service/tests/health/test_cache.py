"""cache.py 单元测试 (2026-06-11) — 进程内 cache + 5s 后台任务"""

from __future__ import annotations

import asyncio

import pytest

from src.health import cache as cache_mod


@pytest.fixture(autouse=True)
def _reset_cache():  # pyright: ignore[reportUnusedFunction]  # pytest autouse fixture 通过装饰器自动调用
    """每个测试前后清 cache 状态, 防止跨测试污染."""
    cache_mod._health_cache = None
    yield
    cache_mod._health_cache = None


def test_get_cached_health_returns_warming_up_when_empty():
    """首次启动, cache 为 None → 返 warming_up 占位"""
    result = cache_mod.get_cached_health()
    assert result["checked_at"] is None
    assert result["status"] == "warming_up"
    assert "python" in result


def test_cache_set_and_get():
    """手动 set 后 get 读出来"""
    payload = {
        "checked_at": "2026-06-11T10:00:00Z",
        "python": {"status": "ok"},
    }
    cache_mod.set_cached_health(payload)
    assert cache_mod.get_cached_health() == payload


def test_loop_runs_all_checks(monkeypatch):
    """后台 loop 调 _run_all_checks, 把结果写 cache."""
    calls = []

    async def fake_run_all_checks():
        calls.append("called")
        return {
            "checked_at": "2026-06-11T10:00:00Z",
            "python": {"status": "ok", "latency_ms": 1.0},
            "dify": {"status": "ok", "latency_ms": 1.0, "error": None, "extra": {}},
            "neo4j": {"status": "ok", "latency_ms": 1.0, "error": None, "extra": {}},
            "pgvector": {"status": "ok", "latency_ms": 1.0, "error": None, "extra": {}},
            "system": {"status": "ok", "latency_ms": 1.0, "error": None, "extra": {}},
        }

    monkeypatch.setattr(cache_mod, "_run_all_checks", fake_run_all_checks)

    # 用短间隔跑一下, 验证被调用 + cache 被写
    async def main():
        task = asyncio.create_task(cache_mod.start_health_loop(interval_s=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(main())
    assert len(calls) >= 1
    assert cache_mod.get_cached_health()["checked_at"] == "2026-06-11T10:00:00Z"


def test_run_all_checks(monkeypatch):
    """_run_all_checks 并发跑 7 check 返完整 dict"""
    from src.health.checks import CheckResult

    async def fake_check_good(**kw):
        return CheckResult(status="ok", latency_ms=1.0)

    # mock 所有 6 个 async check + 1 sync check
    monkeypatch.setattr(cache_mod._checks, "check_python", lambda: CheckResult(status="ok", latency_ms=0.0))
    for name in ("check_dify", "check_neo4j", "check_pgvector", "check_system", "check_minio", "check_redis"):
        monkeypatch.setattr(cache_mod._checks, name, fake_check_good)

    result = asyncio.run(cache_mod._run_all_checks())

    assert "checked_at" in result
    for key in ("python", "dify", "neo4j", "pgvector", "system", "minio", "redis"):
        assert key in result
        assert result[key]["status"] == "ok"


def test_stop_health_loop():
    """stop_health_loop 取消 task 不抛"""

    async def fake_loop():
        try:
            await asyncio.sleep(9999)
        except asyncio.CancelledError:
            raise

    async def main():
        task = asyncio.create_task(fake_loop())
        await asyncio.sleep(0.01)
        await cache_mod.stop_health_loop(task)
        assert task.cancelled()

    asyncio.run(main())


def test_start_health_loop_catches_exception(monkeypatch):
    """start_health_loop 内部异常不退出循环, 恢复后仍能写 cache"""
    calls = []

    async def fake_run_all_checks_with_boom():
        if not calls:
            calls.append("boom")
            raise RuntimeError("transient failure")
        calls.append("ok")
        return {
            "checked_at": "2026-06-11T10:00:00Z",
            "python": {"status": "ok"},
            "dify": {"status": "ok"},
            "neo4j": {"status": "ok"},
            "pgvector": {"status": "ok"},
            "system": {"status": "ok"},
            "minio": {"status": "ok"},
            "redis": {"status": "ok"},
        }

    monkeypatch.setattr(cache_mod, "_run_all_checks", fake_run_all_checks_with_boom)
    cache_mod._health_cache = None

    async def main():
        task = asyncio.create_task(cache_mod.start_health_loop(interval_s=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(main())
    # 第一个抛异常, 后续恢复 — cache 被写入了
    assert len(calls) >= 2
    assert calls[0] == "boom"
    assert cache_mod.get_cached_health()["checked_at"] == "2026-06-11T10:00:00Z"


def test_start_health_loop_cancelled_error_inside_try(monkeypatch):
    """CancelledError 在 try 块内抛出 → 走 except CancelledError: raise 路径 (line 76)"""

    async def fake_checks():
        raise asyncio.CancelledError("模拟内部取消")

    monkeypatch.setattr(cache_mod, "_run_all_checks", fake_checks)

    async def main():
        task = asyncio.create_task(cache_mod.start_health_loop(interval_s=0.01))
        await asyncio.sleep(0.03)
        # task 应该已经结束了 (CancelledError 传播)
        assert task.done()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
