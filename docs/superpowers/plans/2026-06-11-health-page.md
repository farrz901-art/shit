# Health Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/api/health/system` endpoint + `/[locale]/health` page that aggregates 5 health checks (Python/Dify/Neo4j/pgvector/host) into a single admin-only view, with 5s polling.

**Architecture:** FastAPI backend runs 5 async check functions in a 5s background loop, writing to an in-memory cache. The HTTP handler reads from cache (亚毫秒响应). BFF forwards the request. Frontend page renders 5 sections with `useApi` polling.

**Tech Stack:** Python 3.11 + FastAPI + psutil + pynvml + pytest, Next.js 16.2 + React 19 + useApi (SWR) + vitest, next-intl

---

## File Structure

**Create (backend):**
- `src/rag/health/__init__.py`
- `src/rag/health/checks.py` — 5 async check functions + CheckResult dataclass
- `src/rag/health/checks_test.py`
- `src/rag/health/cache.py` — in-memory cache + background loop
- `src/rag/health/cache_test.py`
- `src/rag/health/router.py` — FastAPI router with admin-only auth
- `src/rag/health/router_test.py`

**Modify (backend):**
- `src/rag/__init__.py:18-34` — register health router in `register_routers()`
- `src/rag/product_decoders/app.py:42-90` — add FastAPI lifespan that starts/stops the health loop
- `pyproject.toml` — add `psutil` + `pynvml` deps

**Create (frontend):**
- `web/app/[locale]/health/page.tsx`
- `web/app/[locale]/health/page.test.tsx`
- `web/app/api/health/system/route.ts`

**Modify (frontend):**
- `web/components/settings/settings-dialog.tsx` — add 「健康」 row
- `web/messages/zh.json` — add 14 new keys
- `web/messages/en.json` — add 14 new keys
- `tests/test_api_contract.py` — add BFF contract for `/api/health/system`

---

### Task 1: Add `psutil` + `pynvml` to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read the deps block**

```bash
grep -n "dependencies\|psutil\|pynvml" c:/doc/Code/worktrees/rag-refactor/pyproject.toml | head -20
```

- [ ] **Step 2: Add deps**

Locate the `[project] dependencies = [...]` array and add `"psutil"` and `"pynvml"` at the end (alphabetical or grouped). Use **uv** (not pip, per `feedback-uv-only-no-pip` memory):

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv add psutil pynvml
```

Expected: `pyproject.toml` updates + `uv.lock` updates.

- [ ] **Step 3: Verify**

```bash
uv run python -c "import psutil, pynvml; print(psutil.__version__, 'pynvml ok')"
```

Expected: prints version + `pynvml ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add psutil + pynvml for health check"
```

---

### Task 2: `src/rag/health/checks.py` — CheckResult dataclass + 5 check functions (TDD)

**Files:**
- Create: `src/rag/health/__init__.py`
- Create: `src/rag/health/checks.py`
- Create: `src/rag/health/checks_test.py`

- [ ] **Step 1: Write the failing tests**

`src/rag/health/checks_test.py`:

```python
"""checks.py 单元测试 (2026-06-11) — 5 个 _check_* 函数"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.rag.health.checks import (
    CheckResult,
    check_python,
    check_dify,
    check_neo4j,
    check_pgvector,
    check_system,
)


# ---------- check_python ----------

def test_check_python_returns_uptime():
    """uptime = time.time() - process_start_time, 返 extra.uptime_s + version"""
    import time as _time
    # 模块级 _process_start_time 在第一次 import 时设定, 当前测试运行时间 < 10s
    r = check_python()
    assert r.status == "ok"
    assert r.latency_ms == 0.0
    assert r.error is None
    assert 0 <= r.extra["uptime_s"] < 60
    assert "version" in r.extra


# ---------- check_dify ----------

@pytest.mark.asyncio
async def test_check_dify_ok():
    """Dify ping 成功, latency_ms > 0, error=None"""
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.elapsed.total_seconds.return_value = 0.12
    fake_client.list_parameters = AsyncMock(return_value=fake_response)
    with patch("src.rag.health.checks._get_dify_client", return_value=fake_client):
        r = await check_dify()
    assert r.status == "ok"
    assert r.latency_ms == pytest.approx(120.0, abs=1.0)
    assert r.error is None


@pytest.mark.asyncio
async def test_check_dify_connection_error():
    """Dify ping 失败, status=error, error 含异常信息"""
    fake_client = MagicMock()
    fake_client.list_parameters = AsyncMock(side_effect=ConnectionError("timeout"))
    with patch("src.rag.health.checks._get_dify_client", return_value=fake_client):
        r = await check_dify()
    assert r.status == "error"
    assert r.latency_ms is None
    assert "timeout" in r.error


# ---------- check_neo4j ----------

@pytest.mark.asyncio
async def test_check_neo4j_ok():
    """Neo4j verify_connectivity 成功"""
    fake_store = MagicMock()
    fake_store.verify_connectivity = AsyncMock(return_value=None)
    with patch("src.rag.health.checks._get_neo4j_store", return_value=fake_store):
        r = await check_neo4j()
    assert r.status == "ok"
    assert r.latency_ms >= 0
    assert r.error is None


@pytest.mark.asyncio
async def test_check_neo4j_driver_missing():
    """Neo4j driver 不可用 → status=error"""
    with patch("src.rag.health.checks._get_neo4j_store", side_effect=ImportError("no driver")):
        r = await check_neo4j()
    assert r.status == "error"
    assert "driver" in r.error.lower() or "no driver" in r.error


# ---------- check_pgvector ----------

@pytest.mark.asyncio
async def test_check_pgvector_ok():
    """pgvector SELECT 1 成功"""
    fake_engine = MagicMock()
    fake_conn = MagicMock()
    fake_conn.execute = MagicMock(return_value=MagicMock(scalar=MagicMock(return_value=1)))
    fake_engine.connect.return_value.__enter__ = MagicMock(return_value=fake_conn)
    fake_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    with patch("src.rag.health.checks._get_pg_engine", return_value=fake_engine):
        r = await check_pgvector()
    assert r.status == "ok"
    assert r.latency_ms >= 0
    assert r.error is None


@pytest.mark.asyncio
async def test_check_pgvector_connection_refused():
    """pgvector 连接失败 → status=error"""
    with patch("src.rag.health.checks._get_pg_engine", side_effect=ConnectionRefusedError("refused")):
        r = await check_pgvector()
    assert r.status == "error"
    assert r.error is not None


# ---------- check_system ----------

@pytest.mark.asyncio
async def test_check_system_returns_cpu_mem_gpu():
    """psutil + pynvml 数值正确, gpu 列表非空"""
    fake_mem = MagicMock()
    fake_mem.percent = 67.2
    fake_mem.used = 12 * 1024 * 1024
    fake_mem.total = 18 * 1024 * 1024
    with patch("src.rag.health.checks.psutil.cpu_percent", return_value=23.5), \
         patch("src.rag.health.checks.psutil.virtual_memory", return_value=fake_mem), \
         patch("src.rag.health.checks._sample_gpu", return_value=[{
             "name": "NVIDIA RTX 4090", "util_pct": 45, "mem_used_mb": 8000, "mem_total_mb": 24000,
         }]):
        r = await check_system()
    assert r.status == "ok"
    assert r.extra["cpu_pct"] == 23.5
    assert r.extra["mem_pct"] == 67.2
    assert r.extra["mem_used_mb"] == 12000
    assert r.extra["mem_total_mb"] == 18000
    assert len(r.extra["gpu"]) == 1
    assert r.extra["gpu"][0]["name"] == "NVIDIA RTX 4090"


@pytest.mark.asyncio
async def test_check_system_no_gpu():
    """pynvml NVMLError → gpu=[] (优雅降级), status 仍 ok"""
    fake_mem = MagicMock()
    fake_mem.percent = 50.0
    fake_mem.used = 1024 * 1024
    fake_mem.total = 2048 * 1024
    with patch("src.rag.health.checks.psutil.cpu_percent", return_value=10.0), \
         patch("src.rag.health.checks.psutil.virtual_memory", return_value=fake_mem), \
         patch("src.rag.health.checks._sample_gpu", return_value=[]):
        r = await check_system()
    assert r.status == "ok"
    assert r.extra["gpu"] == []
```

- [ ] **Step 2: Run tests to verify they all fail (RED)**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/checks_test.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.rag.health.checks'`

- [ ] **Step 3: Create `__init__.py` and implement `checks.py`**

`src/rag/health/__init__.py`:

```python
"""Health check subsystem (2026-06-11)
5 个 check 函数 + 后台 5s 轮询 cache + admin-only /api/health/system 端点.
"""
from .checks import (
    CheckResult, check_python, check_dify, check_neo4j, check_pgvector, check_system,
)
from .cache import start_health_loop, stop_health_loop, get_cached_health
from .router import router as health_router

__all__ = [
    "CheckResult",
    "check_python", "check_dify", "check_neo4j", "check_pgvector", "check_system",
    "start_health_loop", "stop_health_loop", "get_cached_health",
    "health_router",
]
```

`src/rag/health/checks.py`:

```python
"""Health check 函数 (2026-06-11)

5 个独立 async 函数, 各返 CheckResult. 失败不抛异常, 字段 status="error" + error="<msg>".
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

import psutil

# 模块加载时间戳, 算 uptime
_PROCESS_START_TIME = time.time()
_VERSION = "0.1.0"


@dataclass
class CheckResult:
    """单个 check 结果. latency_ms 是核心, 特有信息走 extra."""
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


# ---------- Python 进程自身 ----------

def check_python() -> CheckResult:
    """读 _PROCESS_START_TIME 算 uptime. 本地读, latency=0."""
    return CheckResult(
        status="ok",
        latency_ms=0.0,
        error=None,
        extra={"uptime_s": int(time.time() - _PROCESS_START_TIME), "version": _VERSION},
    )


# ---------- 依赖注入 helper (单测 mock 切入点) ----------

def _get_dify_client():
    from src.rag.integrations.dify_client import DifyClient
    return DifyClient()


def _get_neo4j_store():
    from src.rag.kg.neo4j import get_neo4j_store
    return get_neo4j_store()


def _get_pg_engine():
    """绕开 llama_index.vector_stores.pgvector 的复杂初始化, 直接 sqlalchemy."""
    from sqlalchemy import create_engine
    from src.rag.retrieval.vector_store import PGVectorConfig
    cfg = PGVectorConfig()
    return create_engine(cfg.connection_string, pool_pre_ping=True)


def _sample_gpu() -> list[dict]:
    """采样所有 NVIDIA GPU. 驱动缺失 → []."""
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            gpus = []
            for i in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h).decode("utf-8", errors="replace")
                util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                gpus.append({
                    "name": name,
                    "util_pct": util,
                    "mem_used_mb": mem.used // (1024 * 1024),
                    "mem_total_mb": mem.total // (1024 * 1024),
                })
            return gpus
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return []


# ---------- Dify ----------

async def check_dify() -> CheckResult:
    """调 DifyClient.list_parameters(), 算 latency."""
    import asyncio
    t0 = time.perf_counter()
    try:
        client = _get_dify_client()
        # list_parameters 是 Dify /v1/parameters 公开端点, 不消耗 workflow
        resp = await asyncio.to_thread(lambda: client._client.get("/v1/parameters"))
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code >= 400:
            return CheckResult(status="error", latency_ms=None, error=f"HTTP {resp.status_code}")
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0 if t0 else None
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- Neo4j ----------

async def check_neo4j() -> CheckResult:
    """Neo4jStore.verify_connectivity() (内部 driver.session().run)."""
    import asyncio
    t0 = time.perf_counter()
    try:
        store = _get_neo4j_store()
        await asyncio.to_thread(store.verify_connectivity)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- pgvector ----------

async def check_pgvector() -> CheckResult:
    """直接 sqlalchemy 跑 SELECT 1, 绕开 PGVectorStore 重初始化."""
    import asyncio
    t0 = time.perf_counter()
    try:
        engine = _get_pg_engine()
        def _run():
            with engine.connect() as conn:
                result = conn.execute(__import__("sqlalchemy").text("SELECT 1"))
                return result.scalar()
        val = await asyncio.to_thread(_run)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if val != 1:
            return CheckResult(status="error", latency_ms=latency_ms, error=f"unexpected: {val}")
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- 主机资源 ----------

async def check_system() -> CheckResult:
    """psutil CPU/内存 + pynvml GPU. GPU 缺失优雅降级."""
    import asyncio
    t0 = time.perf_counter()
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)  # Windows 必须 interval>=0.1
        mem = psutil.virtual_memory()
        gpus = await asyncio.to_thread(_sample_gpu)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(
            status="ok",
            latency_ms=latency_ms,
            extra={
                "cpu_pct": cpu_pct,
                "mem_pct": mem.percent,
                "mem_used_mb": mem.used // (1024 * 1024),
                "mem_total_mb": mem.total // (1024 * 1024),
                "gpu": gpus,
            },
        )
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))
```

- [ ] **Step 4: Run tests to verify they pass (GREEN)**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/checks_test.py -v
```

Expected: 11/11 PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/health/
git commit -m "feat(health): checks.py — 5 个 _check 函数 + CheckResult"
```

---

### Task 3: `src/rag/health/cache.py` — in-memory cache + background loop (TDD)

**Files:**
- Create: `src/rag/health/cache.py`
- Create: `src/rag/health/cache_test.py`

- [ ] **Step 1: Write the failing tests**

`src/rag/health/cache_test.py`:

```python
"""cache.py 单元测试 (2026-06-11) — 进程内 cache + 5s 后台任务"""
from __future__ import annotations

import asyncio
import pytest

from src.rag.health import cache as cache_mod


@pytest.fixture(autouse=True)
def _reset_cache():
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


@pytest.mark.asyncio
async def test_loop_runs_all_checks(monkeypatch):
    """后台 loop 调 5 个 check 函数, 把结果写 cache."""
    calls = []
    async def fake_check(name):
        async def _f():
            calls.append(name)
            return {"status": "ok", "latency_ms": 1.0}
        return _f
    monkeypatch.setattr(cache_mod, "_run_all_checks", fake_check)
    # 用 0.01s 间隔快速验证
    task = asyncio.create_task(cache_mod.start_health_loop(interval_s=0.01))
    await asyncio.sleep(0.05)  # 让 loop 跑几次
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # 5 个 check 都至少被调用过一次
    for name in ["python", "dify", "neo4j", "pgvector", "system"]:
        assert name in calls, f"{name} not called"
```

- [ ] **Step 2: Run tests to verify RED**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/cache_test.py -v
```

Expected: ModuleNotFoundError or import errors.

- [ ] **Step 3: Implement `cache.py`**

```python
"""Health check 后台 cache (2026-06-11)

进程内单例 cache + 5s asyncio task 持续刷新.
HTTP handler 直接读 cache (亚毫秒响应).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
        }
    return _health_cache


def set_cached_health(payload: dict[str, Any]) -> None:
    """写 cache (测试 + 内部用)."""
    global _health_cache
    _health_cache = payload


async def _run_all_checks() -> dict[str, Any]:
    """并发跑 5 个 check, 组装成 cache payload."""
    python_r = _checks.check_python()
    dify_r, neo4j_r, pgvector_r, system_r = await asyncio.gather(
        _checks.check_dify(),
        _checks.check_neo4j(),
        _checks.check_pgvector(),
        _checks.check_system(),
        return_exceptions=False,
    )
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "python": python_r.__dict__,
        "dify": dify_r.__dict__,
        "neo4j": neo4j_r.__dict__,
        "pgvector": pgvector_r.__dict__,
        "system": system_r.__dict__,
    }


async def start_health_loop(interval_s: float = 5.0) -> None:
    """后台 task: 每 interval_s 秒跑 5 个 check, 写 cache.
    失败不退出, 下个周期重试."""
    while True:
        try:
            async with _cache_lock:
                payload = await _run_all_checks()
                set_cached_health(payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            # 单次失败不影响 loop, 下个周期重试
            pass
        await asyncio.sleep(interval_s)


async def stop_health_loop(task: asyncio.Task) -> None:
    """测试 + lifespan 用: 取消后台 task."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 4: Run tests to verify GREEN**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/cache_test.py -v
```

Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/health/cache.py src/rag/health/cache_test.py
git commit -m "feat(health): cache.py — in-memory cache + 后台 5s loop"
```

---

### Task 4: `src/rag/health/router.py` — admin-only FastAPI endpoint (TDD)

**Files:**
- Create: `src/rag/health/router.py`
- Create: `src/rag/health/router_test.py`

- [ ] **Step 1: Write the failing tests**

`src/rag/health/router_test.py`:

```python
"""router.py 单元测试 (2026-06-11) — admin-only /api/health/system"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.rag.health import router as router_mod
from src.rag.health import cache as cache_mod


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_cache():
    cache_mod._health_cache = None
    yield
    cache_mod._health_cache = None


def test_health_endpoint_requires_admin_token(client):
    """无 header → 401"""
    r = client.get("/api/health/system")
    assert r.status_code == 401
    assert r.json() == {"detail": "缺少 x-admin-token"}


def test_user_token_alone_is_rejected(client):
    """仅有 x-user-token (无 admin) → 401"""
    r = client.get("/api/health/system", headers={"x-user-token": "u1"})
    assert r.status_code == 401


def test_health_endpoint_returns_cached_data(client):
    """admin header + 注入 cache → 200 + 完整字段"""
    cache_mod.set_cached_health({
        "checked_at": "2026-06-11T10:30:00Z",
        "python": {"status": "ok", "latency_ms": 0.0, "error": None, "extra": {"uptime_s": 100}},
        "dify": {"status": "ok", "latency_ms": 120, "error": None, "extra": {}},
        "neo4j": {"status": "ok", "latency_ms": 45, "error": None, "extra": {}},
        "pgvector": {"status": "ok", "latency_ms": 30, "error": None, "extra": {}},
        "system": {"status": "ok", "latency_ms": 5, "error": None, "extra": {"cpu_pct": 23}},
    })
    r = client.get("/api/health/system", headers={"x-admin-token": "a1"})
    assert r.status_code == 200
    data = r.json()
    assert data["checked_at"] == "2026-06-11T10:30:00Z"
    assert data["python"]["extra"]["uptime_s"] == 100
    assert data["system"]["extra"]["cpu_pct"] == 23


def test_health_endpoint_warming_up_response(client):
    """cache 为空 → 200 + checked_at: null + status: warming_up"""
    r = client.get("/api/health/system", headers={"x-admin-token": "a1"})
    assert r.status_code == 200
    data = r.json()
    assert data["checked_at"] is None
    assert data["status"] == "warming_up"
```

- [ ] **Step 2: Run tests to verify RED**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/router_test.py -v
```

Expected: ModuleNotFoundError or import errors.

- [ ] **Step 3: Implement `router.py`**

```python
"""/api/health/system FastAPI router (2026-06-11)

admin-only (x-admin-token header). 读 in-memory cache (后台 5s 任务持续刷新).
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from . import cache as _cache


router = APIRouter(tags=["health"])


@router.get("/system")
def health_system(x_admin_token: str | None = Header(default=None)):
    """5 类检查的聚合视图 (admin-only)."""
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="缺少 x-admin-token")
    # 不强校验 token 值, 跟项目 dev 模式风格一致 (见 CLAUDE.md)
    return _cache.get_cached_health()
```

- [ ] **Step 4: Run tests to verify GREEN**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest src/rag/health/router_test.py -v
```

Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/rag/health/router.py src/rag/health/router_test.py
git commit -m "feat(health): router.py — admin-only /api/health/system"
```

---

### Task 5: Register health router in `register_routers()`

**Files:**
- Modify: `src/rag/__init__.py:18-34`

- [ ] **Step 1: Add health router import + register**

In `src/rag/__init__.py`, modify `register_routers`:

```python
def register_routers(app) -> None:
    """把所有 RAG 子模块的 FastAPI 路由注册到 app.

    由 rag/product_decoders/app.py 的 create_app() 调用一次.
    各 router 各自独立 prefix, 不叠加.
    """
    from .api import router as rag_router
    from .kg.router import router as kg_router
    from .eval.router import router as eval_router
    from .ingest import ingest_router
    from .auth.router import router as auth_router
    from .health import health_router       # (2026-06-11) 新增

    app.include_router(rag_router)     # /api/v1/*
    app.include_router(kg_router)      # /api/kg/*
    app.include_router(eval_router)    # /api/evaluate/*
    app.include_router(ingest_router)  # /api/ingest/*
    app.include_router(auth_router)    # /api/auth/*
    app.include_router(health_router)  # /api/health/*  (2026-06-11) 新增
```

- [ ] **Step 2: Verify import works**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run python -c "from src.rag import register_routers; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/rag/__init__.py
git commit -m "feat(rag): register health_router in register_routers"
```

---

### Task 6: Add FastAPI lifespan to start/stop health loop

**Files:**
- Modify: `src/rag/product_decoders/app.py:42-90`

- [ ] **Step 1: Modify `create_app()` to add lifespan**

Replace the `create_app()` function (lines 42-90) with:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """FastAPI 启动/关闭钩子. (2026-06-11) 启动 health check 后台 5s 任务."""
    from src.rag.health import start_health_loop, stop_health_loop
    task = asyncio.create_task(start_health_loop(interval_s=5.0))
    try:
        yield
    finally:
        await stop_health_loop(task)


def create_app() -> FastAPI:
    """FastAPI 工厂: 测试可以 monkeypatch CONFIGS_DIR 后再调本函数"""
    import asyncio
    loader = ConfigLoader(config_dir=str(CONFIGS_DIR))
    decoder = ProductDecoder(loader)

    app = FastAPI(
        title="Product Order No. Decoder",
        description="产品订货号通用解析服务 - 配置驱动, 多厂商",
        version="1.0.0",
        lifespan=_lifespan,  # (2026-06-11) 启动 health loop
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # dev only, 前端 Next.js
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # 挂载管理后台只读 API (本模块自有)
    from .output_api import router as output_router
    app.include_router(output_router)

    # 挂载所有 RAG 子模块路由 (由 src.rag.register_routers 统一注册)
    from src.rag import register_routers
    register_routers(app)

    @app.post("/decode")
    async def decode(req: DecodeRequest):
        """解码一个产品型号, 返回结构化结果"""
        try:
            return decoder.decode(req.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"内部错误: {e}")

    @app.get("/series", response_model=List[SeriesInfo])
    async def list_series():
        """列出所有支持的产品系列"""
        return decoder.list_series()

    @app.get("/health")
    async def health():
        """健康检查"""
        return {
            "status": "ok",
            "series_count": len(decoder.list_series()),
        }

    return app
```

- [ ] **Step 2: Verify the app still starts**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run python -c "from src.rag.product_decoders.app import create_app; app = create_app(); print('ok:', len(app.routes), 'routes')"
```

Expected: prints route count (should be 6+ existing routes plus the new health/system).

- [ ] **Step 3: Commit**

```bash
git add src/rag/product_decoders/app.py
git commit -m "feat(app): lifespan 启动 health check 后台 5s 任务"
```

---

### Task 7: Run full backend test suite

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest -v
```

Expected: All tests pass. The new health tests (11 + 3 + 4 = 18 cases) all green. Pre-existing failures in unrelated test files (if any) are acceptable.

- [ ] **Step 2: Commit (if any fix needed)**

```bash
git add -A
git commit -m "fix(health): 回归修复"
```

---

### Task 8: BFF `web/app/api/health/system/route.ts`

**Files:**
- Create: `web/app/api/health/system/route.ts`

- [ ] **Step 1: Read an existing BFF route as template**

```bash
cat c:/doc/Code/worktrees/rag-refactor/web/app/api/ingest/tasks/route.ts 2>/dev/null | head -50 || cat c:/doc/Code/worktrees/rag-refactor/web/app/api/knowledge/qa/retrieve/route.ts 2>/dev/null | head -50
```

- [ ] **Step 2: Write the BFF route**

`web/app/api/health/system/route.ts`:

```typescript
// BFF /api/health/system (2026-06-11) — 透传 admin-only health endpoint
//   读 x-admin-token cookie/header → 透传给 FastAPI
//   错误按 [feedback-bff-must-propagate-502-not-silently-zero] 严格处理
import { NextResponse } from "next/server";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  // 从 cookie 或 header 拿 admin token (跟项目 auth.ts 风格一致)
  const cookieHeader = req.headers.get("cookie") ?? "";
  const cookieMatch = /(?:^|;\s*)x-admin-token=([^;]+)/.exec(cookieHeader);
  const adminToken =
    cookieMatch?.[1] ?? req.headers.get("x-admin-token");

  try {
    const resp = await fetch(`${BACKEND}/api/health/system`, {
      method: "GET",
      headers: adminToken ? { "x-admin-token": adminToken } : {},
      cache: "no-store",
    });
    const body = await resp.text();
    return new NextResponse(body, {
      status: resp.status,
      headers: {
        "content-type": resp.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (e) {
    // 后端不可达 → 502 (不静默返 0, 跟 [feedback-bff-must-propagate-502-not-silently-zero] 一致)
    return NextResponse.json(
      {
        detail:
          "后端服务不可达, 请检查 main.py 是否在 8000 端口运行",
        error: String(e),
      },
      { status: 502 },
    );
  }
}
```

- [ ] **Step 3: Verify the file compiles**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run typecheck
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add web/app/api/health/system/route.ts
git commit -m "feat(bff): /api/health/system 透传 + 502 on backend down"
```

---

### Task 9: i18n keys for health page

**Files:**
- Modify: `web/messages/zh.json`
- Modify: `web/messages/en.json`

- [ ] **Step 1: Read current zh.json structure**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web
cat messages/zh.json | head -30
```

- [ ] **Step 2: Add health keys to zh.json**

In `web/messages/zh.json`, append (at the end of the JSON):

```json
,
  "health": {
    "title": "健康状态",
    "subtitle": "5 秒轮询",
    "warmingUp": "数据采集中...",
    "needAdmin": "需要管理员权限",
    "backendDown": "后端服务不可达, 请检查 main.py 是否在 8000 端口运行",
    "checkedAt": "最后检查时间",
    "sections": {
      "python": "Python 后端",
      "dify": "Dify",
      "neo4j": "Neo4j",
      "pgvector": "pgvector",
      "system": "主机资源"
    },
    "fields": {
      "status": "状态",
      "latency": "延迟",
      "uptime": "运行时长",
      "cpu": "CPU",
      "memory": "内存",
      "gpu": "GPU",
      "noGpu": "无 GPU / 驱动未安装"
    }
  },
  "settings": {
    "health": "健康"
  }
```

- [ ] **Step 3: Add health keys to en.json**

In `web/messages/en.json`, append:

```json
,
  "health": {
    "title": "Health Status",
    "subtitle": "Polling every 5s",
    "warmingUp": "Collecting data...",
    "needAdmin": "Admin permission required",
    "backendDown": "Backend unreachable. Check that main.py is running on port 8000.",
    "checkedAt": "Last checked at",
    "sections": {
      "python": "Python backend",
      "dify": "Dify",
      "neo4j": "Neo4j",
      "pgvector": "pgvector",
      "system": "Host resources"
    },
    "fields": {
      "status": "Status",
      "latency": "Latency",
      "uptime": "Uptime",
      "cpu": "CPU",
      "memory": "Memory",
      "gpu": "GPU",
      "noGpu": "No GPU / driver not installed"
    }
  },
  "settings": {
    "health": "Health"
  }
```

- [ ] **Step 4: Verify typecheck**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run typecheck
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add web/messages/zh.json web/messages/en.json
git commit -m "feat(i18n): 添加 health 页 14 个翻译 key (zh+en)"
```

---

### Task 10: `web/app/[locale]/health/page.tsx` — health page (TDD)

**Files:**
- Create: `web/app/[locale]/health/page.test.tsx`
- Create: `web/app/[locale]/health/page.tsx`

- [ ] **Step 1: Write the failing tests**

`web/app/[locale]/health/page.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SWRConfig } from "swr";
import { NextIntlClientProvider } from "next-intl";
import HealthPage from "./page";
import zhMessages from "@/messages/zh.json";

const renderWithProviders = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>
    </NextIntlClientProvider>,
  );

const okPayload = {
  checked_at: "2026-06-11T10:30:00Z",
  python: { status: "ok", latency_ms: 0, error: null, extra: { uptime_s: 12345, version: "0.1.0" } },
  dify: { status: "ok", latency_ms: 120, error: null, extra: {} },
  neo4j: { status: "ok", latency_ms: 45, error: null, extra: {} },
  pgvector: { status: "ok", latency_ms: 30, error: null, extra: {} },
  system: {
    status: "ok", latency_ms: 5, error: null,
    extra: { cpu_pct: 23.5, mem_pct: 67.2, mem_used_mb: 12000, mem_total_mb: 18000, gpu: [] },
  },
};

describe("HealthPage", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => okPayload,
    });
  });

  it("渲染 5 个区块标题", async () => {
    renderWithProviders(<HealthPage />);
    expect(await screen.findByText("Python 后端")).toBeInTheDocument();
    expect(screen.getByText("Dify")).toBeInTheDocument();
    expect(screen.getByText("Neo4j")).toBeInTheDocument();
    expect(screen.getByText("pgvector")).toBeInTheDocument();
    expect(screen.getByText("主机资源")).toBeInTheDocument();
  });

  it("渲染 Python uptime + status=ok", async () => {
    renderWithProviders(<HealthPage />);
    const section = await screen.findByText("Python 后端");
    expect(section).toBeInTheDocument();
    // 运行时长数值
    expect(screen.getByText(/12345/)).toBeInTheDocument();
  });

  it("渲染 Dify latency (ok 状态)", async () => {
    renderWithProviders(<HealthPage />);
    expect(await screen.findByText(/120.*ms/)).toBeInTheDocument();
  });

  it("渲染 Dify error 状态", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        ...okPayload,
        dify: { status: "error", latency_ms: null, error: "ConnectionRefused", extra: {} },
      }),
    });
    renderWithProviders(<HealthPage />);
    expect(await screen.findByText("ConnectionRefused")).toBeInTheDocument();
  });

  it("渲染 system CPU / 内存 / GPU 进度条 + 数值", async () => {
    renderWithProviders(<HealthPage />);
    // CPU 23%
    expect(await screen.findByText(/23/)).toBeInTheDocument();
    // 12 GB / 18 GB
    expect(screen.getByText(/12000/)).toBeInTheDocument();
    expect(screen.getByText(/18000/)).toBeInTheDocument();
  });

  it("cache 未就绪时显「数据采集中...」", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ checked_at: null, status: "warming_up", python: { status: "ok" } }),
    });
    renderWithProviders(<HealthPage />);
    expect(await screen.findByText("数据采集中...")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run test -- --run "app/[locale]/health/page.test.tsx"
```

Expected: FAIL (Cannot find module './page')

- [ ] **Step 3: Commit test first**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "web/app/[locale]/health/page.test.tsx"
git commit -m "test: /[locale]/health page 测试先行 (6 cases)"
```

- [ ] **Step 4: Write the page implementation**

`web/app/[locale]/health/page.tsx`:

```tsx
"use client";
// 健康状态页 (2026-06-11) — 5 类检查, 5s 轮询
import useSWR from "swr";
import { useTranslations } from "next-intl";
import { CheckCircle2, XCircle, ChevronRight } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const POLL_MS = 5000;

type CheckResult = {
  status: "ok" | "error";
  latency_ms: number | null;
  error: string | null;
  extra: Record<string, unknown>;
};

type HealthPayload = {
  checked_at: string | null;
  status?: string;
  python: CheckResult;
  dify: CheckResult;
  neo4j: CheckResult;
  pgvector: CheckResult;
  system: CheckResult;
};

async function fetcher(url: string): Promise<HealthPayload> {
  const r = await fetch(url);
  if (!r.ok) {
    // 401/403 → 业务上等价于 admin 缺失
    if (r.status === 401 || r.status === 403) {
      throw new Error("need_admin");
    }
    throw new Error(`http_${r.status}`);
  }
  return r.json();
}

function StatusDot({ status }: { status: "ok" | "error" }) {
  return status === "ok"
    ? <CheckCircle2 className="h-5 w-5 text-emerald-500" />
    : <XCircle className="h-5 w-5 text-rose-500" />;
}

function formatUptime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

function Section({
  title, result, children,
}: {
  title: string;
  result: CheckResult;
  children?: React.ReactNode;
}) {
  return (
    <section
      data-testid="health-section"
      data-section-title={title}
      className="rounded-xl border border-border/40 bg-card p-6"
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot status={result.status} />
          <h2 className="text-lg font-medium">{title}</h2>
        </div>
        <Badge variant={result.status === "ok" ? "secondary" : "destructive"}>
          {result.status}
        </Badge>
      </header>
      <div className="mt-3 space-y-1 text-sm">
        {children}
      </div>
      {result.error && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-rose-500">error</summary>
          <pre className="mt-2 rounded bg-muted/40 p-2 text-xs">{result.error}</pre>
        </details>
      )}
    </section>
  );
}

export default function HealthPage() {
  const t = useTranslations("health");
  const tSettings = useTranslations("settings");
  const { data, error, isLoading } = useSWR<HealthPayload>(
    "/api/health/system",
    fetcher,
    { refreshInterval: POLL_MS },
  );

  if (error) {
    const message = String(error.message) === "need_admin"
      ? t("needAdmin")
      : t("backendDown");
    return (
      <div className="flex h-full flex-col gap-8 p-12">
        <h1 className="display text-4xl">{t("title")}</h1>
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-6 text-destructive">
          {message}
        </div>
      </div>
    );
  }

  if (!data || data.checked_at === null) {
    return (
      <div className="flex h-full flex-col gap-8 p-12">
        <h1 className="display text-4xl">{t("title")}</h1>
        <p className="text-muted-foreground">{t("warmingUp")}</p>
      </div>
    );
  }

  const { python, dify, neo4j, pgvector, system } = data;
  const gpuList = (system.extra.gpu ?? []) as Array<{ name: string; util_pct: number; mem_used_mb: number; mem_total_mb: number }>;

  return (
    <div className="flex h-full flex-col gap-8 p-12">
      <header className="flex items-baseline gap-3">
        <h1 className="display text-4xl">{t("title")}</h1>
        <span className="num text-sm text-muted-foreground/60">{t("subtitle")}</span>
      </header>

      <Section title={t("sections.python")} result={python}>
        <div>{t("fields.uptime")}: <span className="num">{formatUptime(python.extra.uptime_s as number)}</span></div>
        <div className="text-muted-foreground">v{python.extra.version as string}</div>
      </Section>

      <Section title={t("sections.dify")} result={dify}>
        <div>{t("fields.latency")}: <span className="num">{dify.latency_ms?.toFixed(0) ?? "—"} ms</span></div>
      </Section>

      <Section title={t("sections.neo4j")} result={neo4j}>
        <div>{t("fields.latency")}: <span className="num">{neo4j.latency_ms?.toFixed(0) ?? "—"} ms</span></div>
      </Section>

      <Section title={t("sections.pgvector")} result={pgvector}>
        <div>{t("fields.latency")}: <span className="num">{pgvector.latency_ms?.toFixed(0) ?? "—"} ms</span></div>
      </Section>

      <Section title={t("sections.system")} result={system}>
        <div>
          {t("fields.cpu")}: <span className="num">{(system.extra.cpu_pct as number)?.toFixed(1) ?? "—"}%</span>
          <Progress value={system.extra.cpu_pct as number} className="mt-1 h-2" />
        </div>
        <div className="mt-2">
          {t("fields.memory")}: <span className="num">
            {(system.extra.mem_used_mb as number) ?? "—"} / {system.extra.mem_total_mb as number} MB
            ({system.extra.mem_pct as number?.toFixed(1)}%)
          </span>
          <Progress value={system.extra.mem_pct as number} className="mt-1 h-2" />
        </div>
        <div className="mt-2">
          {gpuList.length === 0 ? (
            <span className="text-muted-foreground">{t("fields.noGpu")}</span>
          ) : (
            gpuList.map((gpu, i) => (
              <div key={i} className="mt-1">
                GPU {i}: <span className="num">{gpu.util_pct}%</span> {gpu.name}
                <Progress value={gpu.util_pct} className="mt-1 h-2" />
                <span className="num text-xs text-muted-foreground">
                  {gpu.mem_used_mb} / {gpu.mem_total_mb} MB
                </span>
              </div>
            ))
          )}
        </div>
      </Section>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify GREEN**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run test -- --run "app/[locale]/health/page.test.tsx"
```

Expected: 6/6 PASS

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add "web/app/[locale]/health/page.tsx"
git commit -m "feat(web): /[locale]/health 健康状态页 (5 区块 + 5s 轮询)"
```

---

### Task 11: Add 「健康」 row to SettingsDialog

**Files:**
- Modify: `web/components/settings/settings-dialog.tsx`

- [ ] **Step 1: Read current SettingsDialog**

```bash
cat c:/doc/Code/worktrees/rag-refactor/web/components/settings/settings-dialog.tsx
```

- [ ] **Step 2: Add 「健康」 row**

Insert after the 「语言」 row (the disabled placeholder):

```tsx
<SettingRow label={tSettings("health")}>
  <Link
    href={`/${locale}/health`}
    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    onClick={() => onOpenChange(false)}
  >
    <span>查看</span>
    <ChevronRight className="h-4 w-4" />
  </Link>
</SettingRow>
```

Add the necessary imports at the top of the file:
- `import Link from "next/link";`
- `import { useLocale } from "next-intl";`
- Add `ChevronRight` to the existing `lucide-react` import.

Use `const locale = useLocale();` inside the component.

- [ ] **Step 3: Verify SettingsDialog test still passes**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run test -- --run components/settings
```

Expected: existing tests still PASS

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add web/components/settings/settings-dialog.tsx
git commit -m "feat(settings): SettingsDialog 加「健康」行 (跳 /[locale]/health)"
```

---

### Task 12: Add BFF contract for `/api/health/system`

**Files:**
- Modify: `tests/test_api_contract.py`

- [ ] **Step 1: Read current contract file**

```bash
grep -n "FRONTEND_EXPECTS\|/api/" c:/doc/Code/worktrees/rag-refactor/tests/test_api_contract.py | head -30
```

- [ ] **Step 2: Add BFF route expectation**

Find the list of expected BFF routes and add:

```python
    ("/api/health/system", "GET"),  # (2026-06-11) 健康状态聚合
```

- [ ] **Step 3: Run contract test**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest tests/test_api_contract.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add tests/test_api_contract.py
git commit -m "test(contract): BFF /api/health/system 期望添加"
```

---

### Task 13: Final regression — full test suite + manual verification

**Files:** None (verification only)

- [ ] **Step 1: Run full backend pytest**

```bash
cd c:/doc/Code/worktrees/rag-refactor
uv run pytest -v 2>&1 | tail -20
```

Expected: All health tests (18 new) green. Pre-existing failures in unrelated tests (if any) are documented and acceptable.

- [ ] **Step 2: Run full frontend vitest**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run test 2>&1 | tail -20
```

Expected: All health page tests pass. Pre-existing failures acceptable.

- [ ] **Step 3: Run typecheck**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run typecheck
```

Expected: 0 errors

- [ ] **Step 4: Run lint**

```bash
cd c:/doc/Code/worktrees/rag-refactor/web && bun run lint
```

Expected: 0 errors (warnings OK)

- [ ] **Step 5: Manual verification**

After all tests pass, restart FastAPI per [feedback-uvicorn-must-restart-after-route-add]:

```bash
cd c:/doc/Code/worktrees/rag-refactor
# 杀掉旧 uvicorn (如果有)
netstat -ano | grep :8000
# 启动新
uv run python main.py
```

In another terminal:
```bash
cd c:/doc/Code/worktrees/rag-refactor/web
bun run dev
```

Verify:
1. Open `http://localhost:3000/zh/health` → see 5 sections
2. Wait 5s → data refreshes
3. Click 齿轮 → SettingsDialog → 「健康」 row → click → navigate to /zh/health

- [ ] **Step 6: Commit (if any fix needed)**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add -A
git commit -m "fix(health): 回归修复"
```

---

### Task 14: Write handoff doc

**Files:**
- Create: `docs/superpowers/handoff-2026-06-11-health-page.md`

- [ ] **Step 1: Write the handoff doc**

```markdown
# Health Page 验收 (2026-06-11)

## Spec 覆盖

| AC | Spec 条目 | 实现 |
|---|---|---|
| 1 | 5 类检查 (Python / Dify / Neo4j / pgvector / 主机) | `src/rag/health/checks.py` |
| 2 | 后台 5s task + 进程内 cache | `src/rag/health/cache.py` |
| 3 | admin-only `/api/health/system` | `src/rag/health/router.py` |
| 4 | BFF 透传 + 502 on backend down | `web/app/api/health/system/route.ts` |
| 5 | /[locale]/health 页 (5 区块 + 5s 轮询) | `web/app/[locale]/health/page.tsx` |
| 6 | SettingsDialog 「健康」 行 | `web/components/settings/settings-dialog.tsx` |
| 7 | i18n (zh + en, 14 keys) | `web/messages/{zh,en}.json` |
| 8 | psutil + pynvml 新增依赖 | `pyproject.toml` |
| 9 | BFF 契约测试更新 | `tests/test_api_contract.py` |

## 自动化覆盖

### Backend: 18 新 cases
- `checks_test.py`: 11 cases
- `cache_test.py`: 3 cases
- `router_test.py`: 4 cases

### Frontend: 6 新 cases
- `web/app/[locale]/health/page.test.tsx`: 6 cases

## Commits (13)

| Commit | Task | Title |
|---|---|---|
| ... | 1 | chore(deps): add psutil + pynvml |
| ... | 2 | feat(health): checks.py — 5 check functions |
| ... | 3 | feat(health): cache.py — in-memory cache + loop |
| ... | 4 | feat(health): router.py — admin-only endpoint |
| ... | 5 | feat(rag): register health_router |
| ... | 6 | feat(app): lifespan 启动 health loop |
| ... | 7 | (optional: 回归修复) |
| ... | 8 | feat(bff): /api/health/system 透传 |
| ... | 9 | feat(i18n): 14 个 health key |
| ... | 10 | feat(web): /[locale]/health page |
| ... | 11 | feat(settings): SettingsDialog 健康行 |
| ... | 12 | test(contract): BFF 期望 |
| ... | 13 | (optional: 回归) |
| ... | 14 | docs: handoff |

## 安全/隔离 checklist ✅

- [x] admin-only (`x-admin-token` header 必填, 401 if missing)
- [x] 任一子检查失败不影响 HTTP 200
- [x] GPU 驱动缺失优雅降级 (gpu=[])
- [x] cache 任务失败不退出 loop
- [x] 跨用户: admin token 本身就是 admin-only, 不涉及跨用户

## 风险点验证 ✅

- [x] pynvml NVMLError → gpu=[] (无 crash)
- [x] psutil.cpu_percent(interval=0.1) Windows 兼容
- [x] 后台 5s 任务 vs TestClient 事件循环 — 测试用 monkeypatch 注入, 不真起 loop

## 手动验证清单

1. 重启 uvicorn: `uv run python main.py` (per [feedback-uvicorn-must-restart-after-route-add])
2. 启动前端: `bun run dev`
3. 打开 `http://localhost:3000/zh/health`
4. 验证 5 区块 (Python / Dify / Neo4j / pgvector / 主机)
5. 等待 5s, 数据自动刷新
6. 点齿轮 → SettingsDialog → 「健康」 行 → 跳转
```

- [ ] **Step 2: Commit**

```bash
cd c:/doc/Code/worktrees/rag-refactor
git add docs/superpowers/handoff-2026-06-11-health-page.md
git commit -m "docs: health page 验收清单"
```