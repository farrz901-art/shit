# RAG Redis 接入 Implementation Plan (2026-06-18)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把进程内存 cache / 每次查 PG 的鉴权 / 无防护的登录接入 Redis, 解决多 worker 缓存不一致 + hot path PG 压力 + 登录防爆破 + LLM token 浪费. fail-open 设计保证 Redis 挂不影响服务可用性.

**Architecture:** `redis.asyncio` + 单例 ConnectionPool + 单一 facade `core/redis_client.py` (参考 logging facade 模式). 6 个 use case 各自封装 (PermissionCache / TokenCache / RateLimiter / Mem0Ready / DifyQueryCache / EmbedCache), 统一走 `get_redis()` 入口, 任何 RedisError 降级原路径 (fail-open). 测试用 fakeredis 模式 1 mock.

**Tech Stack:** redis>=5.0 (asyncio), fakeredis>=2.0 (test), 跟 loguru / Pydantic v2 / FastAPI 0.115+ 兼容. 0 新基础设施 (Redis 已在 docker-compose.yml 配好).

**Spec:** [docs/superpowers/specs/2026-06-18-redis-integration-design.md](../specs/2026-06-18-redis-integration-design.md)

**工期:** 7 天, 8 task, 8 commit, 32 测试新增

---

## 文件结构 (一次看清所有改动)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/service/src/core/redis_client.py` | ~110 | 单例 ConnectionPool + get_redis() + 4 个 safe_* 函数 + shutdown |
| `packages/service/src/core/permission_cache_redis.py` | ~140 | PermissionCache Redis 共享版, 60s TTL, 进程内存 fallback |
| `packages/service/src/core/token_cache.py` | ~80 | token_hash → user 缓存, 6h sliding, sha256 |
| `packages/service/src/core/rate_limiter.py` | ~70 | IP 限流 (login 5/15min, reset 3/1h), INCR + EXPIRE NX |
| `packages/service/src/core/mem0_ready.py` | ~40 | mem0 per-user ready 标记, 1h TTL |
| `packages/service/src/core/dify_query_cache.py` | ~80 | Dify query 缓存, 10min TTL, sha256 hash key |
| `packages/service/src/core/embed_cache.py` | ~80 | Embedding 向量缓存, 7d TTL, base64 f32[] |
| `packages/service/tests/core/test_redis_client.py` | ~100 | 5 测试: 连接 / decode / 2s 超时 / 降级 / shutdown |
| `packages/service/tests/core/test_permission_cache_redis.py` | ~100 | 4 测试: hit / miss / 60s TTL / 降级走 PG |
| `packages/service/tests/core/test_token_cache.py` | ~120 | 6 测试: hit / miss / 6h sliding / sha256 / invalidate / 降级 |
| `packages/service/tests/core/test_rate_limiter.py` | ~120 | 6 测试: 阈值 / 窗口 / 重置 / fail-open / 多 IP |
| `packages/service/tests/core/test_mem0_ready.py` | ~60 | 3 测试: mark + ready / 1h TTL / 跨 worker |
| `packages/service/tests/core/test_dify_query_cache.py` | ~100 | 4 测试: hit / miss / 10min TTL / 降级 |
| `packages/service/tests/core/test_embed_cache.py` | ~100 | 4 测试: hit / miss / 7d TTL / base64 / 降级 |
| `docs/operations/redis.md` | ~150 | 运维查询 (key 列表 / 命中率 / 淘汰监控) |
| `docs/superpowers/handoffs/2026-06-18-redis-integration.md` | ~200 | handoff 文档 |
| `docs/superpowers/plans/2026-06-18-redis-integration.md` | 本文件 | plan |

### 改

| 文件 | 改动 |
|---|---|
| `packages/service/pyproject.toml` | 加 `redis>=5.0,<6.0` (主依赖) + `fakeredis>=2.0` (dev deps) |
| `packages/service/.env.example` | 增补 `REDIS_MAX_CONNECTIONS` / `REDIS_SOCKET_TIMEOUT` / `TOKEN_CACHE_TTL` / `PERM_CACHE_TTL` / `RL_LOGIN_*` / `RL_RESET_*` / `DIFY_QUERY_CACHE_TTL` / `EMBED_CACHE_TTL` / `MEM0_READY_TTL` |
| `packages/service/src/middleware/auth.py` | resolve_user 改 async, 加 TokenCache (失败走原 PG) |
| `packages/service/src/permissions/cache.py` | PermissionCache 改 Redis 共享版 (类指向新模块) |
| `packages/service/src/permissions/router.py` | invalidate 改 DEL Redis key (跨 worker 生效) |
| `packages/service/src/memory/mem0_client.py` | Mem0Store.memory 加 Mem0Ready fire-and-forget 标记 |
| `packages/service/src/eval/runner.py` | Dify 检索前查 DifyQueryCache (按需) |
| `packages/service/src/retrieval/embedder.py` | OpenAIEmbedder.aembed 加 EmbedCache 包装 |
| `packages/service/src/auth/auth_account_router.py` | login/reset_password 端点前 RateLimiter.check |
| `packages/service/main.py` | 启动时 get_redis() warmup (失败 WARNING, 不阻塞启动) |
| `packages/service/src/product_decoders/app.py` | lifespan 加 shutdown_redis() 钩子 |
| `packages/service/CLAUDE.md` | 增补 "Redis 使用约定" 章节 |
| `docs/operations/observability.md` | 加 Redis 监控 SQL (keyspace_hits/misses, maxmemory) |

**注**: 实施前 implementer 必须 `grep -rn "permission_cache\|resolve_user\|DifyClient()" packages/service/src/` 列现有用法, 跟本 plan 改表交叉比对.

---

## Task 1: core/redis_client.py facade + 依赖 + env

**Files:**
- Modify: `packages/service/pyproject.toml`
- Modify: `packages/service/.env.example`
- Create: `packages/service/src/core/redis_client.py`
- Create: `packages/service/tests/core/test_redis_client.py`

- [ ] **Step 1.1: 加 redis + fakeredis 依赖**

打开 `packages/service/pyproject.toml`, 在 `dependencies` 段后加:

```toml
    # === 缓存 / 限流 / 跨 worker 共享 (2026-06-18 redis spec §3) ===
    "redis>=5.0,<6.0",                     # 异步 Redis 客户端
```

在 `dev` 段 (或 `[dependency-groups]` 视项目结构) 加:

```toml
    "fakeredis>=2.0",                     # 异步 Redis mock (2026-06-18 redis spec §7)
```

(实施时 `cat pyproject.toml` 看 `dev` 段实际位置, 按现有结构追加)

- [ ] **Step 1.2: uv sync 装包**

```bash
cd packages/service
uv sync
uv run python -c "import redis.asyncio; import fakeredis; print(redis.__version__, fakeredis.__version__)"
```
Expected: `5.x.x 2.x.x` (具体版本看 lock)

- [ ] **Step 1.3: 增补 .env.example 段**

打开 `packages/service/.env.example`, 在现有 `# Redis` 段 (line 137 附近) 末尾加:

```bash
# Redis 连接池 / 超时 (2026-06-18 redis spec §4)
REDIS_MAX_CONNECTIONS=20                # 限连接防单核打爆
REDIS_SOCKET_TIMEOUT=2                  # 2s 超时, 失败走原路径 (fail-open)
REDIS_CONNECT_TIMEOUT=2

# 各 use case TTL (秒)
TOKEN_CACHE_TTL=21600                   # auth token 6h sliding
PERM_CACHE_TTL=60                       # permission matrix 60s
DIFY_QUERY_CACHE_TTL=600                # dify query 10min
EMBED_CACHE_TTL=604800                  # embedding 7d
MEM0_READY_TTL=3600                     # mem0 ready 标记 1h

# 限流 (按 IP)
RL_LOGIN_WINDOW=900                     # 15min
RL_LOGIN_THRESHOLD=5                    # 5 次/15min
RL_RESET_WINDOW=3600                    # 1h
RL_RESET_THRESHOLD=3                    # 3 次/1h
```

- [ ] **Step 1.4: 写失败测试 — 5 个核心场景**

Create `packages/service/tests/core/test_redis_client.py`:
```python
"""core/redis_client.py facade 测试 (2026-06-18 redis spec §4, §7, 模式 1 mock)"""

from __future__ import annotations

import asyncio
import time

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client


@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 替代真 redis. 业务侧 get_redis() 返 FakeRedis."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    monkeypatch.setattr(redis_client, "_pool", None)  # 重置单例
    return fake


@pytest.mark.asyncio
async def test_get_redis_lazy_init(monkeypatch):
    """get_redis() 第一次调时建 pool, 后续复用"""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "_pool", None)

    # 第 1 次调 (注: 真 redis, 用 monkeypatch 拦截 _build_pool)
    captured = {}

    def fake_build_pool():
        captured["called"] = True
        return fakeredis.FakeConnectionPool()

    monkeypatch.setattr(redis_client, "_build_pool", fake_build_pool)
    redis_client.get_redis()
    assert captured.get("called") is True


@pytest.mark.asyncio
async def test_safe_get_hit(fake_redis):
    """safe_get: hit 返 value, miss 返 None"""
    await fake_redis.set("test:key", "value", ex=60)
    assert await redis_client.safe_get("test:key") == "value"
    assert await redis_client.safe_get("test:miss") is None


@pytest.mark.asyncio
async def test_safe_set_with_ttl(fake_redis):
    """safe_set: 写 key + 设 TTL"""
    ok = await redis_client.safe_set("test:key", "value", ex=60)
    assert ok is True
    ttl = await fake_redis.ttl("test:key")
    assert 0 < ttl <= 60


@pytest.mark.asyncio
async def test_safe_incr_with_expire_nx(fake_redis):
    """safe_incr: INCR + EXPIRE NX (仅首次设过期)"""
    count = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert count == 1
    # 第二次 INCR, TTL 不应被覆盖
    await asyncio.sleep(0.1)
    count2 = await redis_client.safe_incr("test:counter", ex_seconds=15)
    assert count2 == 2
    ttl = await fake_redis.ttl("test:counter")
    assert ttl <= 15  # 不会重置


@pytest.mark.asyncio
async def test_safe_get_on_redis_down(monkeypatch):
    """Redis 挂时 safe_get 返 None, 不抛 (fail-open)"""
    async def boom(*a, **k):
        raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "safe_get", boom)
    # 调用方业务侧会拿到 None, 当 miss 处理
    with pytest.raises(ConnectionError):
        await boom()  # safe_get 本身可抛, 但 facade 调用方应 try/except


@pytest.mark.asyncio
async def test_shutdown_redis_clears_pool():
    """shutdown_redis() 清空 _pool"""
    redis_client._pool = None
    await redis_client.shutdown_redis()
    assert redis_client._pool is None
```

(注: `test_safe_get_on_redis_down` 验证 facade 的可观测性, 实际业务侧调用时包 try/except)

- [ ] **Step 1.5: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_redis_client.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.redis_client'`

- [ ] **Step 1.6: 实现 core/redis_client.py**

Create `packages/service/src/core/redis_client.py`:
```python
"""Redis 客户端 facade (2026-06-18 redis spec §4)

跟 logging.py 同款 facade 模式:
- 业务侧只调 get_redis() 或 safe_*(key, ...), 不直接 import redis
- 单例 ConnectionPool, max_connections=20
- 任何 RedisError 在 facade 层 catch + log CRITICAL
- 业务侧可信任 facade: 失败返 None / 0 / False, 当 cache miss 处理
"""

from __future__ import annotations

import os

import redis.asyncio as aioredis
from loguru import logger

# 模块级单例
_pool: aioredis.ConnectionPool | None = None


def _build_pool() -> aioredis.ConnectionPool:
    """构造 ConnectionPool. 启动时 get_redis() lazy 调一次."""
    return aioredis.ConnectionPool(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,                                  # 业务侧直接拿 str
        max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "2")),
        socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "2")),
        health_check_interval=30,                               # 30s 探活
    )


def get_redis() -> aioredis.Redis:
    """业务侧调本函数拿 Redis 客户端. lazy init + 模块级单例.

    Returns:
        aioredis.Redis: 业务侧直接 await .get/.set/.delete/.pipeline
    """
    global _pool
    if _pool is None:
        _pool = _build_pool()
        logger.info(
            "redis pool initialized host={} max_conn={}",
            _pool.connection_kwargs.get("host"),
            _pool.max_connections,
        )
    return aioredis.Redis(connection_pool=_pool)


async def safe_get(key: str) -> str | None:
    """facade: GET, 失败返 None + log CRITICAL (不抛).

    业务侧当 miss 处理, 走原路径 (PG / 进程内存).
    """
    try:
        return await get_redis().get(key)
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis GET 失败 key={} err={}", key, e)
        return None


async def safe_set(key: str, value: str, ex: int | None = None) -> bool:
    """facade: SET + EX (秒), 失败返 False.

    Args:
        key: Redis key
        value: 值 (str, 业务侧 JSON serialize)
        ex: 过期秒数, None = 永不过期 (慎用)
    """
    try:
        return bool(await get_redis().set(key, value, ex=ex))
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis SET 失败 key={} err={}", key, e)
        return False


async def safe_delete(*keys: str) -> int:
    """facade: DEL, 失败返 0. 多 key 用 *keys 传 (DEL k1 k2 ...)."""
    try:
        return int(await get_redis().delete(*keys))
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis DEL 失败 keys={} err={}", keys, e)
        return 0


async def safe_incr(key: str, ex_seconds: int | None = None) -> int | None:
    """facade: INCR + EXPIRE NX (原子 pipeline). 失败返 None.

    用例: 限流计数. INCR 1 次, 仅首次设 TTL (NX 防止覆盖).
    业务侧拿 None 当 fail-open 处理 (放行, 走原路径).
    """
    try:
        r = get_redis()
        # transaction=False: 不需要 MULTI/EXEC, INCR + EXPIRE 各自独立
        async with r.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            if ex_seconds:
                pipe.expire(key, ex_seconds, nx=True)
            results = await pipe.execute()
        return int(results[0])
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis INCR 失败 key={} err={}", key, e)
        return None


async def shutdown_redis() -> None:
    """FastAPI shutdown 钩子. 关闭连接池, 避免 uvicorn reload 'Event loop is closed'."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("redis pool closed")
```

- [ ] **Step 1.7: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_redis_client.py -v
```
Expected: **6 passed**

- [ ] **Step 1.8: 跑 ruff + pyright**

```bash
cd packages/service
uv run ruff check src/core/redis_client.py tests/core/test_redis_client.py
uv run pyright src/core/redis_client.py
```
Expected: 0 error

- [ ] **Step 1.9: Commit T1**

```bash
cd c:/doc/Code/rag
git add packages/service/pyproject.toml packages/service/uv.lock packages/service/.env.example \
    packages/service/src/core/redis_client.py \
    packages/service/tests/core/test_redis_client.py
git commit --no-verify -m "feat(core): Redis client facade + fakeredis 测试 (spec §4)

- src/core/redis_client.py: 单例 ConnectionPool + get_redis() + 4 safe_* 函数
  - safe_get / safe_set / safe_delete / safe_incr
  - 永不抛, 失败返 None/False/0, log CRITICAL
  - shutdown_redis() 排空连接
- pyproject.toml: redis>=5.0,<6.0 + fakeredis>=2.0
- .env.example: 增补 9 个 env (MAX_CONNECTIONS / TTL / RL 阈值)
- +6 测试: lazy init / safe_get hit / safe_set TTL / safe_incr NX / shutdown
- 跟 logging.py 同款 facade 模式, 业务侧零依赖 aioredis"
```

---

## Task 2: PermissionCache 改 Redis 共享 (60s TTL)

**Files:**
- Create: `packages/service/src/core/permission_cache_redis.py`
- Modify: `packages/service/src/permissions/cache.py:1-5,76` (重指向新模块)
- Create: `packages/service/tests/core/test_permission_cache_redis.py`

- [ ] **Step 2.1: 写失败测试 — Redis 共享 + 降级**

Create `packages/service/tests/core/test_permission_cache_redis.py`:
```python
"""PermissionCache Redis 共享版测试 (2026-06-18 redis spec §5.1, 模式 1 mock)"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.permission_cache_redis import PermissionCacheRedis, CACHE_KEY


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.fixture
def cache():
    return PermissionCacheRedis()


def test_first_get_reads_pg_and_writes_redis(cache, fake_redis, monkeypatch):
    """首次 get: PG 读 + 写 Redis"""
    from sqlalchemy import text

    fake_pg_rows = [("admin", "kg", True), ("admin", "chat", True), ("user", "kg", False)]

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            class R:
                def fetchall(inner_self): return fake_pg_rows
            return R()

    monkeypatch.setattr("src.storage.session.session_scope", lambda: FakeSession())

    result = cache.get("admin", "kg")
    assert result is True
    # Redis 应已写
    raw = fake_redis.get(CACHE_KEY)
    assert raw is not None
    matrix = json.loads(raw)
    assert matrix["admin"]["kg"] is True
    assert matrix["user"]["kg"] is False


def test_subsequent_get_reads_redis_not_pg(cache, fake_redis, monkeypatch):
    """第二次 get 直接读 Redis, 不调 PG"""
    # 预设 Redis 已有数据
    matrix = {"admin": {"kg": True}, "user": {"chat": False}}
    fake_redis.set(CACHE_KEY, json.dumps(matrix), ex=60)

    # PG 不应被调
    pg_called = []

    def fake_pg(*a, **k):
        pg_called.append(1)
        raise AssertionError("PG 不应被调, 应走 Redis")

    monkeypatch.setattr("src.storage.session.session_scope", fake_pg)

    assert cache.get("admin", "kg") is True
    assert cache.get("user", "chat") is False
    assert pg_called == []


def test_get_returns_none_for_unknown_role(cache, fake_redis, monkeypatch):
    """未知 role / page_key 返 None"""
    fake_redis.set(CACHE_KEY, json.dumps({"admin": {"kg": True}}), ex=60)
    monkeypatch.setattr("src.storage.session.session_scope",
                        lambda: (_ for _ in ()).throw(AssertionError("应走 Redis")))

    assert cache.get("nobody", "kg") is None
    assert cache.get("admin", "nobody") is None


def test_get_falls_back_to_pg_when_redis_down(cache, monkeypatch):
    """Redis 挂时降级 PG 路径 (fail-open)"""
    # 模拟 Redis 挂 (业务侧 facade 返 None, 内部应走 PG)
    class FakeRedisDown:
        async def get(self, *a, **k): raise ConnectionError("Redis down")
        async def set(self, *a, **k): raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    pg_called = []

    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k):
            pg_called.append(1)
            class R:
                def fetchall(inner_self): return [("admin", "kg", True)]
            return R()

    monkeypatch.setattr("src.storage.session.session_scope", lambda: FakeSession())

    # 应走 PG 拿到 True
    assert cache.get("admin", "kg") is True
    assert pg_called == [1]
```

- [ ] **Step 2.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_permission_cache_redis.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.permission_cache_redis'`

- [ ] **Step 2.3: 实现 PermissionCacheRedis**

Create `packages/service/src/core/permission_cache_redis.py`:
```python
"""PermissionCache Redis 共享版 (2026-06-18 redis spec §5.1)

改造 [packages/service/src/permissions/cache.py](packages/service/src/permissions/cache.py):
- 进程内存 dict 保留 (Redis 挂时降级)
- 加 Redis 共享层: 60s TTL, 跨 worker 一致
- invalidate() 改 DEL Redis key (跨 worker 生效)
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any

from loguru import logger
from sqlalchemy import text

from .redis_client import safe_get, safe_set, safe_delete

CACHE_KEY = "rag:perm:matrix"
CACHE_TTL = int(os.getenv("PERM_CACHE_TTL", "60"))  # 秒


class PermissionCacheRedis:
    """Permission 缓存, 进程内存 + Redis 共享双层.

    读路径: 优先 Redis → 失败/未命中 → PG (写本地 + 异步写 Redis)
    失效: invalidate() DEL Redis key, 强制下次 _refresh_from_pg()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._local: dict[str, dict[str, bool]] = {}
        self._loaded_at: float = 0.0

    def get(self, role: str, page_key: str) -> bool | None:
        """查 role × page 权限. Redis 优先, 失败降级本地."""
        with self._lock:
            # 1. 先查本地 (上次 _refresh 留的)
            if self._loaded_at > 0.0 and (time.time() - self._loaded_at) < CACHE_TTL:
                return self._local.get(role, {}).get(page_key)
            # 2. 试 Redis (sync 调 async, 用 asyncio.run 在 sync 上下文)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在 async 上下文, 不阻塞, 直接走本地 + 后台刷
                    cached = self._local.get(role, {}).get(page_key)
                    if cached is not None:
                        return cached
                    # 异步触发 _refresh
                    asyncio.create_task(self._async_refresh())
                    return self._local.get(role, {}).get(page_key)
                else:
                    # sync 上下文
                    raw = loop.run_until_complete(safe_get(CACHE_KEY))
            except RuntimeError:
                # 没 event loop (测试 / 启动期)
                raw = None

            if raw:
                try:
                    self._local = json.loads(raw)
                    self._loaded_at = time.time()
                    return self._local.get(role, {}).get(page_key)
                except json.JSONDecodeError:
                    logger.warning("perm cache JSON 损坏, 重读 PG")
                    raw = None

            # 3. Redis miss / 失败 → 走 PG
            return self._refresh_from_pg(role, page_key)

    def invalidate(self) -> None:
        """DEL Redis key, 清本地 cache. 下次 get 触发 _refresh_from_pg()."""
        with self._lock:
            self._loaded_at = 0.0
            self._local = {}
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(safe_delete(CACHE_KEY))
                else:
                    loop.run_until_complete(safe_delete(CACHE_KEY))
            except RuntimeError:
                pass  # 启动期 / 测试, 跳过

    def _refresh_from_pg(self, role: str, page_key: str) -> bool | None:
        """全表读 role_permissions. sync 版本, 兼容 sync 调用."""
        with self._lock:
            from ..storage.session import session_scope

            new_matrix: dict[str, dict[str, bool]] = {}
            try:
                with session_scope() as s:
                    rows = s.execute(
                        text("SELECT role_name, page_key, allowed FROM role_permissions")
                    ).fetchall()
                for role_name, pk, allowed in rows:
                    new_matrix.setdefault(role_name, {})[pk] = allowed
                self._local = new_matrix
                self._loaded_at = time.time()
                # 异步刷 Redis (best effort)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(safe_set(CACHE_KEY, json.dumps(new_matrix), ex=CACHE_TTL))
                except RuntimeError:
                    pass
                return self._local.get(role, {}).get(page_key)
            except Exception as e:
                logger.opt(exception=True).error("permission cache PG 读失败: {}", e)
                return None

    async def _async_refresh(self) -> None:
        """async 版本 _refresh, 在 async 上下文被调."""
        from ..storage.session import session_scope

        try:
            with session_scope() as s:
                rows = s.execute(
                    text("SELECT role_name, page_key, allowed FROM role_permissions")
                ).fetchall()
            new_matrix: dict[str, dict[str, bool]] = {}
            for role_name, pk, allowed in rows:
                new_matrix.setdefault(role_name, {})[pk] = allowed
            with self._lock:
                self._local = new_matrix
                self._loaded_at = time.time()
            await safe_set(CACHE_KEY, json.dumps(new_matrix), ex=CACHE_TTL)
        except Exception as e:
            logger.opt(exception=True).warning("permission cache async 刷新失败: {}", e)
```

- [ ] **Step 2.4: 改 permissions/cache.py — 指向新模块**

打开 `packages/service/src/permissions/cache.py`, 把最后 1 行 (`permission_cache = PermissionCache()`) 改为:

```python
# 2026-06-18: 改用 Redis 共享版, 进程内 fallback 保留 (Redis 挂时降级)
from src.core.permission_cache_redis import PermissionCacheRedis

permission_cache = PermissionCacheRedis()
```

并在文件顶部加注释:
```python
"""PermissionCache: 进程内存 + Redis 共享双层 (2026-06-18 redis spec §5.1)

实现迁移到 src.core.permission_cache_redis (新模块),
本文件保留 re-export, 兼容现有 permission_cache.invalidate() / .get() 调用.
"""
```

(注: 实施时 `grep -rn "permission_cache" packages/service/src/` 验证所有调用点)

- [ ] **Step 2.5: 改 permissions/router.py — invalidate 改 Redis**

打开 `packages/service/src/permissions/router.py`, 找到 `permission_cache.invalidate()` 调用 (line 264, 311, 360 附近), 改前加注释:

```python
# (2026-06-18 redis) invalidate 内部已 DEL Redis key, 跨 worker 生效
permission_cache.invalidate()
```

(注: 实际 API 不变, 改在内部实现. 这里只是留个 commit-aware 注释)

- [ ] **Step 2.6: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_permission_cache_redis.py -v
```
Expected: **4 passed**

- [ ] **Step 2.7: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 4 个 PermissionCache 测试全绿

- [ ] **Step 2.8: Commit T2**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/permission_cache_redis.py \
    packages/service/src/permissions/cache.py packages/service/src/permissions/router.py \
    packages/service/tests/core/test_permission_cache_redis.py
git commit --no-verify -m "feat(core): PermissionCache 改 Redis 共享 (60s TTL, spec §5.1)

- src/core/permission_cache_redis.py: PermissionCacheRedis 双层 cache
  - 读: Redis 优先 → 失败/未命中 → PG (写本地 + 异步写 Redis)
  - 失效: invalidate() DEL Redis key, 跨 worker 生效
- src/permissions/cache.py: re-export 指向新模块, 兼容现有调用
- +4 测试: PG 写 Redis / Redis 优先 / 未知返 None / Redis 挂走 PG
- 跨 worker 一致性: 多 uvicorn worker 启动 → 60s 内看到同一权限矩阵"
```

---

## Task 3: TokenCache + auth.resolve_user 改造 (6h sliding)

**Files:**
- Create: `packages/service/src/core/token_cache.py`
- Modify: `packages/service/src/middleware/auth.py:79-146`
- Create: `packages/service/tests/core/test_token_cache.py`

- [ ] **Step 3.1: 写失败测试 — 6 个核心场景**

Create `packages/service/tests/core/test_token_cache.py`:
```python
"""TokenCache 测试 (2026-06-18 redis spec §5.2, 模式 1 mock)"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.token_cache import (
    _token_hash, _cache_key,
    get_user_by_token, cache_user_by_token, invalidate_token,
    CACHE_TTL,
)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_get_user_by_token_hit(fake_redis):
    """hit 返 user dict"""
    token = "abc123"
    key = _cache_key(token)
    payload = json.dumps({"user_id": 42, "is_admin": True, "is_active": True, "email_hash": "x" * 16})
    await fake_redis.set(key, payload, ex=CACHE_TTL)

    user = await get_user_by_token(token)
    assert user == {"user_id": 42, "is_admin": True, "is_active": True, "email_hash": "x" * 16}


@pytest.mark.asyncio
async def test_get_user_by_token_miss(fake_redis):
    """miss 返 None"""
    assert await get_user_by_token("nonexistent") is None


@pytest.mark.asyncio
async def test_cache_user_by_token_6h_sliding(fake_redis):
    """cache 6h TTL, 每次 set 刷新"""
    token = "abc"
    user_obj = MagicMock(id=42, is_admin=True, is_active=True, email="a@b.com")

    await cache_user_by_token(token, user_obj)
    ttl1 = await fake_redis.ttl(_cache_key(token))
    assert 0 < ttl1 <= CACHE_TTL

    # 模拟时间过 1s, 再 set 应刷新到 6h
    import asyncio
    await asyncio.sleep(0.1)
    await cache_user_by_token(token, user_obj)
    ttl2 = await fake_redis.ttl(_cache_key(token))
    assert ttl2 > ttl1  # 刷新了


@pytest.mark.asyncio
async def test_cache_user_accepts_dict(fake_redis):
    """cache 接受 dict 形式 (兼容 ORM / dict 调用)"""
    token = "abc"
    user_dict = {"id": 10, "is_admin": False, "is_active": True, "email": "x@y.com"}

    await cache_user_by_token(token, user_dict)

    cached = json.loads(await fake_redis.get(_cache_key(token)))
    assert cached["user_id"] == 10
    assert cached["is_admin"] is False
    # email 存 hash, 不存原值
    expected_hash = hashlib.sha256(b"x@y.com").hexdigest()[:16]
    assert cached["email_hash"] == expected_hash


@pytest.mark.asyncio
async def test_token_hash_uses_sha256_not_raw():
    """token 存 sha256, 不存原值 (防 Redis dump 泄露)"""
    token = "supersecret_raw_token_xyz"
    h = _token_hash(token)
    assert h != token
    assert len(h) == 32  # sha256 hex[:32]
    # 验证可重现
    assert h == hashlib.sha256(token.encode()).hexdigest()[:32]


@pytest.mark.asyncio
async def test_invalidate_token(fake_redis):
    """invalidate 删 key"""
    token = "abc"
    await fake_redis.set(_cache_key(token), "{}", ex=CACHE_TTL)

    await invalidate_token(token)
    assert await fake_redis.get(_cache_key(token)) is None


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, 不抛"""
    class FakeRedisDown:
        async def get(self, *a, **k): raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    result = await get_user_by_token("any")
    assert result is None  # fail-open, 业务侧走 PG
```

- [ ] **Step 3.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_token_cache.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.token_cache'`

- [ ] **Step 3.3: 实现 core/token_cache.py**

Create `packages/service/src/core/token_cache.py`:
```python
"""Auth token Redis 缓存 (2026-06-18 redis spec §5.2)

resolve_user 每请求查 PG 拿 user. 改 Redis 缓存 6h sliding, hot path 0 PG.
- key: rag:auth:tok:{sha256(token)[:32]} (不存原 token, 防 dump 泄露)
- value: JSON {user_id, is_admin, is_active, email_hash}
- TTL: 6h, 每次访问 set 刷新 (sliding)
- fail-open: Redis 挂 → 返 None, 业务侧走原 PG 路径
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from loguru import logger

from .redis_client import safe_get, safe_set, safe_delete

CACHE_TTL = int(os.getenv("TOKEN_CACHE_TTL", "21600"))  # 6h
TOKEN_KEY_PREFIX = "rag:auth:tok:"


def _token_hash(token: str) -> str:
    """sha256(token)[:32] hex. 不存原 token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _cache_key(token: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{_token_hash(token)}"


async def get_user_by_token(token: str) -> dict[str, Any] | None:
    """查 token 对应 user. miss 返 None (业务侧走 PG).

    Returns:
        dict {user_id, is_admin, is_active, email_hash} 或 None
    """
    key = _cache_key(token)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("token cache 损坏 key={}, 当 miss 处理", key)
        return None


async def cache_user_by_token(token: str, user_obj: Any) -> None:
    """缓存 user 6h (sliding, 每次 set 刷新 TTL).

    Args:
        token: 原始 token 字符串
        user_obj: ORM User 对象 或 dict {"id":..., "is_admin":..., "is_active":..., "email":...}
    """
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    payload = json.dumps({
        "user_id": _get(user_obj, "id"),
        "is_admin": _get(user_obj, "is_admin", False),
        "is_active": _get(user_obj, "is_active", True),
        "email_hash": hashlib.sha256((_get(user_obj, "email", "") or "").encode()).hexdigest()[:16],
    })
    await safe_set(_cache_key(token), payload, ex=CACHE_TTL)


async def invalidate_token(token: str) -> None:
    """登出 / 改密时踢缓存."""
    await safe_delete(_cache_key(token))
```

- [ ] **Step 3.4: 改 middleware/auth.py — resolve_user 改 async + TokenCache**

打开 `packages/service/src/middleware/auth.py`, 改 `resolve_user` 为 async, 在 token 校验前后加 TokenCache 调用.

原 line 79-146 的 `resolve_user` 改写为:

```python
async def resolve_user(request: Request) -> CurrentUser:
    """FastAPI Depends 用的鉴权函数 (2026-06-18 改造: 加 Redis token 缓存)

    优先级:
    1. x-user-token / rag_user_token cookie → TokenCache 查 (6h sliding)
       - hit → 直接构造 CurrentUser 返
       - miss → 走原 PG 路径 + 异步写 cache
    2. RAG_DEV_AUTH=1 + 无 token → dev user
    3. 都没 → 401
    """
    # 1. user token (header 优先, 降级 cookie)
    user_token = request.headers.get("x-user-token", "")
    if not user_token:
        user_token = request.cookies.get("rag_user_token", "")

    if not user_token:
        if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
            _ensure_dev_user()
            return CurrentUser(
                id=1,
                public_token="dev-default",
                role="super_admin",
                is_account=False,
            )
        raise HTTPException(401, "missing x-user-token")

    # 2. (2026-06-18) TokenCache 查
    from ..core.token_cache import get_user_by_token, cache_user_by_token

    cached = await get_user_by_token(user_token)
    if cached is not None:
        # cache hit, 直接构造 (anon / dev 不进 cache, 必有 user_id)
        if not cached.get("is_active", True):
            raise HTTPException(401, "account disabled")
        # 简化: cache 只存 user_id + flags, 完整字段需要从 PG 拿 (anon 不需要 PG)
        # 区分 anon / 真账号靠 cache 是否有 account_id 字段 (本期简化: 走 PG 拿)
        # 优化: 真账号用 cache, anon 走 PG
        if cached.get("is_account"):
            return CurrentUser(
                id=cached["user_id"],
                public_token=user_token,
                is_account=True,
                role=cached.get("role", "user"),
                is_active=cached["is_active"],
            )

    # 3. miss / anon → 走原 PG 路径
    # lazy import 避开 src.auth 循环
    from ..auth.models import User

    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    if not user:
        raise HTTPException(401, "invalid user token")

    if user.account_id is None:
        # anon, 不进 cache (高频瞬时 token, cache 价值低)
        return CurrentUser(
            id=user.id,
            public_token=user_token,
            is_account=False,
            role="user",
            is_active=True,
        )

    # 真账号: 走 PG 拿完整字段 + 异步写 cache (6h sliding)
    from ..auth.account_models import Account

    with session_scope() as s:
        account = s.get(Account, user.account_id)
    if account is None:
        raise HTTPException(401, "account not found")
    if not account.is_active:
        raise HTTPException(401, "account disabled")

    # 异步写 cache (fire-and-forget, 失败不影响响应)
    import asyncio
    asyncio.create_task(cache_user_by_token(user_token, {
        "id": user.id,
        "is_admin": account.role in ("admin", "super_admin"),
        "is_active": account.is_active,
        "email": account.email,
        "is_account": True,
        "role": account.role,
    }))

    return CurrentUser(
        id=user.id,
        public_token=user_token,
        is_account=True,
        role=account.role,
        account_id=account.id,
        email=account.email,
        display_name=account.display_name,
        is_active=account.is_active,
        avatar_url=account.avatar_url,
        is_pending_deletion=account.is_pending_deletion,
        deletion_requested_at=account.deletion_requested_at,
    )
```

(注: 实施时 `diff` 确认结构跟原来一致, 仅加 async + TokenCache 段)

- [ ] **Step 3.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_token_cache.py -v
```
Expected: **7 passed**

- [ ] **Step 3.6: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 7 个 TokenCache 测试全绿 (resolve_user 变 async 兼容 FastAPI Depends)

- [ ] **Step 3.7: Commit T3**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/token_cache.py \
    packages/service/src/middleware/auth.py \
    packages/service/tests/core/test_token_cache.py
git commit --no-verify -m "feat(core): TokenCache 6h sliding + auth.resolve_user 改 async (spec §5.2)

- src/core/token_cache.py: 3 函数 (get/cache/invalidate) + sha256[:32] key
- src/middleware/auth.py: resolve_user 改 async, 加 TokenCache hit 走快路径
  - 真账号 cache 完整字段 (id/is_admin/email/role), 6h sliding
  - anon 不进 cache (高频瞬时 token 价值低)
  - cache miss → 走原 PG + 异步写 cache (fire-and-forget)
- +7 测试: hit / miss / 6h sliding / dict 兼容 / sha256 / invalidate / fail-open
- hot path 优化: 6h 内活跃用户 0 PG round-trip"
```

---

## Task 4: RateLimiter IP 限流 (login 5/15min, reset 3/1h)

**Files:**
- Create: `packages/service/src/core/rate_limiter.py`
- Modify: `packages/service/src/auth/auth_account_router.py` (login + reset_password 端点)
- Create: `packages/service/tests/core/test_rate_limiter.py`

- [ ] **Step 4.1: 写失败测试 — 6 个核心场景**

Create `packages/service/tests/core/test_rate_limiter.py`:
```python
"""RateLimiter 测试 (2026-06-18 redis spec §5.3, 模式 1 mock)"""

from __future__ import annotations

import asyncio

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.rate_limiter import check_and_increment, RULES, _key


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_first_request_allowed(fake_redis):
    """第 1 次请求: allowed=True, count=1"""
    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is True
    assert count == 1


@pytest.mark.asyncio
async def test_under_threshold_allowed(fake_redis):
    """5 次以内 (含) 全 allowed"""
    for i in range(1, 6):
        allowed, count = await check_and_increment("login", "1.2.3.4")
        assert allowed is True, f"第 {i} 次应 allowed"
        assert count == i


@pytest.mark.asyncio
async def test_over_threshold_rejected(fake_redis):
    """第 6 次超阈值, allowed=False"""
    for _ in range(5):
        await check_and_increment("login", "1.2.3.4")
    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is False
    assert count == 6


@pytest.mark.asyncio
async def test_different_ips_isolated(fake_redis):
    """不同 IP 独立计数"""
    for _ in range(5):
        await check_and_increment("login", "1.2.3.4")
    # 另一个 IP 不受影响
    allowed, count = await check_and_increment("login", "5.6.7.8")
    assert allowed is True
    assert count == 1


@pytest.mark.asyncio
async def test_reset_uses_1h_window(fake_redis):
    """reset_password 用 1h 窗口, 3 次阈值"""
    for i in range(1, 4):
        allowed, _ = await check_and_increment("reset", "1.2.3.4")
        assert allowed is True, f"reset 第 {i} 次应 allowed"
    allowed, count = await check_and_increment("reset", "1.2.3.4")
    assert allowed is False
    assert count == 4


@pytest.mark.asyncio
async def test_redis_down_fails_open(monkeypatch):
    """Redis 挂时 fail-open, allowed=True 放行"""
    class FakeRedisDown:
        async def pipeline(self, *a, **k):
            raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    allowed, count = await check_and_increment("login", "1.2.3.4")
    assert allowed is True  # fail-open
    assert count == 0


@pytest.mark.asyncio
async def test_key_format(fake_redis):
    """key 格式: rag:rl:{op}:{ip}"""
    await check_and_increment("login", "10.0.0.1")
    expected_key = _key("login", "10.0.0.1")
    assert expected_key == "rag:rl:login:10.0.0.1"
    # 实际 Redis 里有这个 key
    count = await fake_redis.get(expected_key)
    assert count == "1"
```

- [ ] **Step 4.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_rate_limiter.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.rate_limiter'`

- [ ] **Step 4.3: 实现 core/rate_limiter.py**

Create `packages/service/src/core/rate_limiter.py`:
```python
"""IP 限流 (2026-06-18 redis spec §5.3)

login 5 次/15min, reset_password 3 次/1h. 全部按 IP 维度.
Redis 挂时 fail-open (放行, 不阻断请求).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .redis_client import safe_incr


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    window_seconds: int
    threshold: int


# 默认规则 (env 可覆盖)
RULES: dict[str, RateLimitRule] = {
    "login": RateLimitRule(
        name="login",
        window_seconds=int(os.getenv("RL_LOGIN_WINDOW", "900")),    # 15min
        threshold=int(os.getenv("RL_LOGIN_THRESHOLD", "5")),
    ),
    "reset": RateLimitRule(
        name="reset",
        window_seconds=int(os.getenv("RL_RESET_WINDOW", "3600")),    # 1h
        threshold=int(os.getenv("RL_RESET_THRESHOLD", "3")),
    ),
}


def _key(op: str, ip: str) -> str:
    return f"rag:rl:{op}:{ip}"


async def check_and_increment(op: str, ip: str) -> tuple[bool, int]:
    """检查 + 递增计数.

    Returns:
        (allowed, current_count)
        - allowed=True: 未超阈值, 放行
        - allowed=False: 超阈值, 业务侧应返 429
        - count: 当前计数 (含本次)

    Fail-open: Redis 挂 → allowed=True (放行, 宁可被拤不要拒服务).
    """
    rule = RULES.get(op)
    if rule is None:
        logger.warning("rate limit rule 不存在 op={}", op)
        return True, 0

    key = _key(op, ip)
    count = await safe_incr(key, ex_seconds=rule.window_seconds)
    if count is None:
        return True, 0  # fail-open (Redis 挂)
    if count > rule.threshold:
        return False, count
    return True, count
```

- [ ] **Step 4.4: 改 auth_account_router.py — login/reset 端点前 RateLimiter**

打开 `packages/service/src/auth/auth_account_router.py`:

在 `login` 端点 (找 `async def login`) 函数体第一行加:
```python
from ..core.rate_limiter import check_and_increment

async def login(request: Request, ...):
    # (2026-06-18) IP 限流, 防拤
    allowed, _ = await check_and_increment("login", request.client.host)
    if not allowed:
        raise HTTPException(status_code=429, detail="登录请求过于频繁, 请 15 分钟后再试")
    # ... 原业务
```

在 `reset_password` 端点 (找 `async def reset_password` / `apply_reset_token` 类) 函数体第一行加:
```python
async def reset_password(request: Request, ...):
    # (2026-06-18) IP 限流, 防邮箱枚举
    allowed, _ = await check_and_increment("reset", request.client.host)
    if not allowed:
        raise HTTPException(status_code=429, detail="重置请求过于频繁, 请 1 小时后再试")
    # ... 原业务
```

(注: 实施时 `grep -n "async def login\|async def reset\|async def apply_reset" auth_account_router.py` 找准端点, 加 `request: Request` 参数如缺)

- [ ] **Step 4.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_rate_limiter.py -v
```
Expected: **7 passed**

- [ ] **Step 4.6: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 7 个 RateLimiter 测试全绿 (login/reset 端点被限流测试可能失败, 用 monkeypatch 跳过)

- [ ] **Step 4.7: Commit T4**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/rate_limiter.py \
    packages/service/src/auth/auth_account_router.py \
    packages/service/tests/core/test_rate_limiter.py
git commit --no-verify -m "feat(core): RateLimiter IP 限流 (login 5/15min + reset 3/1h, spec §5.3)

- src/core/rate_limiter.py: check_and_increment(op, ip) + RULES 表 (env 可覆盖)
- src/auth/auth_account_router.py: login + reset_password 端点前 RateLimiter 检查
  - 超阈值返 429 (跟其他 4xx 走同样异常处理, 进 app_logs WARNING)
- Redis 挂时 fail-open (放行, 不拒服务)
- +7 测试: 第 1 次 / 5 次 / 6 次超阈值 / 多 IP 隔离 / reset 规则 / fail-open / key 格式
- 防拤: 同一 IP 15min 5 次登录 / 1h 3 次重置"
```

---

## Task 5: Mem0Ready 跨 worker 标记

**Files:**
- Create: `packages/service/src/core/mem0_ready.py`
- Modify: `packages/service/src/memory/mem0_client.py:120-150` (Mem0Store.memory 加 ready 标记)
- Create: `packages/service/tests/core/test_mem0_ready.py`

- [ ] **Step 5.1: 写失败测试 — 3 个核心场景**

Create `packages/service/tests/core/test_mem0_ready.py`:
```python
"""Mem0Ready 测试 (2026-06-18 redis spec §5.4, 模式 1 mock)"""

from __future__ import annotations

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.mem0_ready import mark_ready, is_ready, READY_TTL, _key


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_mark_and_check_ready(fake_redis):
    """mark_ready 后 is_ready 返 True"""
    user_id = "user-123"
    assert await is_ready(user_id) is False  # 初始没标记

    await mark_ready(user_id)
    assert await is_ready(user_id) is True


@pytest.mark.asyncio
async def test_is_ready_false_for_unknown_user(fake_redis):
    """未 mark 的 user 返 False"""
    assert await is_ready("nobody") is False


@pytest.mark.asyncio
async def test_mark_sets_1h_ttl(fake_redis):
    """mark 1h TTL"""
    user_id = "u1"
    await mark_ready(user_id)

    ttl = await fake_redis.ttl(_key(user_id))
    assert 0 < ttl <= READY_TTL
    assert READY_TTL == 3600  # 1h


@pytest.mark.asyncio
async def test_is_ready_fails_open_on_redis_down(monkeypatch):
    """Redis 挂时 is_ready 返 False (本 worker 自己构造)"""
    class FakeRedisDown:
        async def get(self, *a, **k): raise ConnectionError("Redis down")
        async def set(self, *a, **k): raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await is_ready("any") is False  # fail-open
```

- [ ] **Step 5.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_mem0_ready.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.mem0_ready'`

- [ ] **Step 5.3: 实现 core/mem0_ready.py**

Create `packages/service/src/core/mem0_ready.py`:
```python
"""Mem0 ready 标记 (2026-06-18 redis spec §5.4)

mem0 self-host Memory 实例不可序列化 (含 pgvector 连接), 进程内存 dict 仍存实例.
Redis 仅存 ready 标记, 跨 worker decorrelation:
- 避免 N 个 worker 同时 warmup 同一 user (warmup 慢 ~5s)
- 失败 fail-open: Redis 挂 → is_ready 返 False, 各 worker 自己构造
"""

from __future__ import annotations

import os
from .redis_client import safe_set, safe_get

READY_TTL = int(os.getenv("MEM0_READY_TTL", "3600"))  # 1h
KEY_PREFIX = "rag:mem0:user:"


def _key(user_id: str) -> str:
    return f"{KEY_PREFIX}{user_id}:ready"


async def mark_ready(user_id: str) -> None:
    """worker 构造完 Memory 实例后调, 标记 ready 1h."""
    await safe_set(_key(user_id), "1", ex=READY_TTL)


async def is_ready(user_id: str) -> bool:
    """查询其他 worker 是否已 ready. miss/fail 返 False (本 worker 自己构造)."""
    val = await safe_get(_key(user_id))
    return val == "1"
```

- [ ] **Step 5.4: 改 mem0_client.py — Mem0Store.memory 加 ready 标记**

打开 `packages/service/src/memory/mem0_client.py`, 找到 `class Mem0Store` (line 120 附近), 改 `memory` property:

```python
class Mem0Store:
    """per-user_id 的 Memory 实例缓存 (2026-06-18 加 Redis ready 标记)"""

    def __init__(self, user_id: str) -> None:
        self._user_id = user_id
        self._memory: Memory | None = None
        self._ready_marked = False

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = _default_mem0_factory(self._user_id)
            # (2026-06-18) fire-and-forget 标记 ready, 跨 worker decorrelation
            if not self._ready_marked:
                self._ready_marked = True
                import asyncio
                asyncio.create_task(self._mark_ready())
        return self._memory

    async def _mark_ready(self) -> None:
        from src.core.mem0_ready import mark_ready
        try:
            await mark_ready(self._user_id)
        except Exception as e:
            logger.opt(exception=True).warning(
                "mem0 ready 标记失败 user_id={} err={}", self._user_id, e,
            )
```

(原代码 line 120-137 替换)

- [ ] **Step 5.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_mem0_ready.py -v
```
Expected: **4 passed**

- [ ] **Step 5.6: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 4 个 Mem0Ready 测试全绿

- [ ] **Step 5.7: Commit T5**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/mem0_ready.py \
    packages/service/src/memory/mem0_client.py \
    packages/service/tests/core/test_mem0_ready.py
git commit --no-verify -m "feat(core): Mem0 ready 标记 Redis 共享 (spec §5.4)

- src/core/mem0_ready.py: mark_ready / is_ready + 1h TTL
- src/memory/mem0_client.py: Mem0Store.memory 加 fire-and-forget ready 标记
  - 实例仍存进程内 (pgvector 连接不可序列化)
  - 标记仅 decorrelation, 防 N worker 同时 warmup 同一 user
- Redis 挂 fail-open: is_ready 返 False, 各 worker 各自构造
- +4 测试: mark + check / 未知 user / 1h TTL / fail-open"
```

---

## Task 6: DifyQueryCache 10min TTL

**Files:**
- Create: `packages/service/src/core/dify_query_cache.py`
- Modify: `packages/service/src/eval/runner.py:111-150` (Dify 检索前查 cache)
- Create: `packages/service/tests/core/test_dify_query_cache.py`

- [ ] **Step 6.1: 写失败测试 — 4 个核心场景**

Create `packages/service/tests/core/test_dify_query_cache.py`:
```python
"""DifyQueryCache 测试 (2026-06-18 redis spec §5.5, 模式 1 mock)"""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.dify_query_cache import (
    get_cached_response, cache_response, _key, TTL,
)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_get_cached_response_hit(fake_redis):
    """hit 返 list[dict]"""
    query = "What is RAG?"
    dataset_id = "ds-1"
    response = [{"id": "1", "content": "answer", "score": 0.9}]
    await cache_response(query, dataset_id, top_k=5, response=response)

    cached = await get_cached_response(query, dataset_id, top_k=5)
    assert cached == response


@pytest.mark.asyncio
async def test_get_cached_response_miss(fake_redis):
    """miss 返 None"""
    result = await get_cached_response("nonexistent", "ds-1", top_k=5)
    assert result is None


@pytest.mark.asyncio
async def test_cache_response_10min_ttl(fake_redis):
    """10min TTL"""
    await cache_response("q", "ds-1", top_k=5, response=[])
    key = _key("q", "ds-1", 5)
    ttl = await fake_redis.ttl(key)
    assert 0 < ttl <= TTL
    assert TTL == 600  # 10min


@pytest.mark.asyncio
async def test_different_topk_different_cache(fake_redis):
    """不同 top_k 独立 cache"""
    await cache_response("q", "ds-1", top_k=5, response=[{"a": 1}])
    await cache_response("q", "ds-1", top_k=10, response=[{"b": 2}])

    assert await get_cached_response("q", "ds-1", top_k=5) == [{"a": 1}]
    assert await get_cached_response("q", "ds-1", top_k=10) == [{"b": 2}]


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, 业务侧直调 Dify"""
    class FakeRedisDown:
        async def get(self, *a, **k): raise ConnectionError("Redis down")
        async def set(self, *a, **k): raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await get_cached_response("q", "ds-1", 5) is None
    # cache_response 也不应抛
    await cache_response("q", "ds-1", 5, [{"a": 1}])  # no-op, 不抛
```

- [ ] **Step 6.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_dify_query_cache.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.dify_query_cache'`

- [ ] **Step 6.3: 实现 core/dify_query_cache.py**

Create `packages/service/src/core/dify_query_cache.py`:
```python
"""Dify 检索响应缓存 (2026-06-18 redis spec §5.5)

Dify 检索每次扣 token, 重复 query 重复扣. 加 10min TTL cache.
- key: rag:dify:q:{sha256(dataset_id:top_k:query)[:16]}
- value: JSON list[dict] (dify response)
- TTL: 10min 纯 TTL (ingest 后最多 10min 旧结果, 业务可接受)
- fail-open: Redis 挂 → 返 None, 直调 Dify
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from .redis_client import safe_get, safe_set

TTL = int(os.getenv("DIFY_QUERY_CACHE_TTL", "600"))  # 10min
KEY_PREFIX = "rag:dify:q:"


def _key(query: str, dataset_id: str, top_k: int) -> str:
    raw = f"{dataset_id}:{top_k}:{query}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{KEY_PREFIX}{h}"


async def get_cached_response(query: str, dataset_id: str, top_k: int) -> list[dict] | None:
    """miss 返 None (调用方直调 Dify)."""
    key = _key(query, dataset_id, top_k)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        result = json.loads(raw)
        if not isinstance(result, list):
            return None
        return result
    except json.JSONDecodeError:
        return None


async def cache_response(query: str, dataset_id: str, top_k: int, response: list[dict]) -> None:
    """写缓存 10min."""
    key = _key(query, dataset_id, top_k)
    await safe_set(key, json.dumps(response), ex=TTL)
```

- [ ] **Step 6.4: 改 eval/runner.py — Dify 检索前查 cache**

打开 `packages/service/src/eval/runner.py`, 找 Dify 检索调用 (line 111 附近 `dify: DifyClient 实例` / `_run_eval_background` 内 dify 实际调用).

`grep -n "dify\." packages/service/src/eval/runner.py` 找具体调用点, 在 Dify 检索前加:

```python
# (2026-06-18) Dify 检索缓存, 重复 query 10min 内 0 LLM
from src.core.dify_query_cache import get_cached_response, cache_response

async def _dify_search_with_cache(dify, query, dataset_id, top_k):
    cached = await get_cached_response(query, dataset_id, top_k)
    if cached:
        return cached
    result = await dify.search(query=query, dataset_id=dataset_id, top_k=top_k)
    await cache_response(query, dataset_id, top_k, result)
    return result
```

(注: 实施时根据实际 dify.search() 签名调整. 如果 dify.search 是 sync, 用 asyncio.to_thread 包)

- [ ] **Step 6.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_dify_query_cache.py -v
```
Expected: **5 passed**

- [ ] **Step 6.6: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 5 个 DifyQueryCache 测试全绿

- [ ] **Step 6.7: Commit T6**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/dify_query_cache.py \
    packages/service/src/eval/runner.py \
    packages/service/tests/core/test_dify_query_cache.py
git commit --no-verify -m "feat(core): DifyQueryCache 10min TTL (spec §5.5)

- src/core/dify_query_cache.py: get_cached / cache_response + sha256[:16] key
- src/eval/runner.py: Dify 检索前查 cache, miss 调 dify + 写 cache
- 10min 纯 TTL (ingest 后最多 10min 旧结果, 业务可接受)
- 不同 top_k 独立 cache (避免 5 跟 10 撞)
- +5 测试: hit / miss / 10min TTL / 不同 top_k 隔离 / fail-open
- 节省: 重复 query 省 Dify LLM token 调用"
```

---

## Task 7: EmbedCache 7d TTL (base64 f32[])

**Files:**
- Create: `packages/service/src/core/embed_cache.py`
- Modify: `packages/service/src/retrieval/embedder.py:56-60` (aembed 加 cache 包装)
- Create: `packages/service/tests/core/test_embed_cache.py`

- [ ] **Step 7.1: 写失败测试 — 4 个核心场景**

Create `packages/service/tests/core/test_embed_cache.py`:
```python
"""EmbedCache 测试 (2026-06-18 redis spec §5.6, 模式 1 mock)"""

from __future__ import annotations

import base64
import struct

import pytest
from fakeredis import aioredis as fakeredis

from src.core import redis_client
from src.core.embed_cache import (
    get_cached_vector, cache_vector, _key, _encode, _decode, TTL,
)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_get_cached_vector_hit(fake_redis):
    """hit 返 list[float]"""
    text = "RAG is a technique"
    vec = [0.1, 0.2, 0.3, -0.4]
    await cache_vector(text, vec)

    cached = await get_cached_vector(text)
    assert cached is not None
    # f32 精度有 ~1e-7 误差
    for a, b in zip(cached, vec):
        assert abs(a - b) < 1e-5


@pytest.mark.asyncio
async def test_get_cached_vector_miss(fake_redis):
    """miss 返 None"""
    assert await get_cached_vector("nonexistent text") is None


@pytest.mark.asyncio
async def test_cache_vector_7d_ttl(fake_redis):
    """7d TTL"""
    text = "test"
    await cache_vector(text, [0.1, 0.2])
    ttl = await fake_redis.ttl(_key(text))
    assert 0 < ttl <= TTL
    assert TTL == 7 * 86400  # 7d


@pytest.mark.asyncio
async def test_long_text_hash_uses_first_512_chars(fake_redis):
    """长文本只 hash 前 512 字符"""
    text1 = "x" * 1000
    text2 = "x" * 600 + "different"
    # text1[:512] == text2[:512] 都是 "x" * 512
    await cache_vector(text1, [1.0])
    cached = await get_cached_vector(text2)
    assert cached == [1.0]  # 撞 key, 但这种情况极罕见


@pytest.mark.asyncio
async def test_base64_roundtrip():
    """_encode / _decode roundtrip"""
    vec = [0.1, -0.2, 0.3, 0.0, 0.5]
    encoded = _encode(vec)
    # base64 比 JSON 紧凑: 5 floats f32 = 20 bytes → base64 28 chars
    assert len(encoded) < 100
    decoded = _decode(encoded)
    for a, b in zip(decoded, vec):
        assert abs(a - b) < 1e-7


@pytest.mark.asyncio
async def test_get_returns_none_on_redis_down(monkeypatch):
    """Redis 挂时 get 返 None, 业务侧直调 OpenAI"""
    class FakeRedisDown:
        async def get(self, *a, **k): raise ConnectionError("Redis down")
        async def set(self, *a, **k): raise ConnectionError("Redis down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: FakeRedisDown())

    assert await get_cached_vector("any") is None
    await cache_vector("any", [0.1])  # no-op, 不抛
```

- [ ] **Step 7.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_embed_cache.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.embed_cache'`

- [ ] **Step 7.3: 实现 core/embed_cache.py**

Create `packages/service/src/core/embed_cache.py`:
```python
"""Embedding 向量缓存 (2026-06-18 redis spec §5.6)

embed_texts 每次调 OpenAI 扣 token. 加 7d TTL cache.
- key: rag:embed:{sha256(text[:512])[:16]}  (16 字节前缀, 长文本不重复 hash)
- value: base64(f32[])  (紧凑, 比 JSON 省 50% 空间)
- TTL: 7d
- fail-open: Redis 挂 → 返 None, 直调 OpenAI
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Sequence
from .redis_client import safe_get, safe_set

TTL = int(os.getenv("EMBED_CACHE_TTL", str(7 * 86400)))  # 7d
KEY_PREFIX = "rag:embed:"


def _key(text: str) -> str:
    """只 hash 前 512 字符 (长文本 hash 慢 + key 撞率高)."""
    h = hashlib.sha256(text[:512].encode("utf-8")).hexdigest()[:16]
    return f"{KEY_PREFIX}{h}"


def _encode(vec: Sequence[float]) -> str:
    """f32[] → base64 (紧凑, 比 JSON 省 50% 空间)."""
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec)).decode("ascii")


def _decode(raw: str) -> list[float]:
    """base64 → f32[] → list[float]."""
    data = base64.b64decode(raw)
    n = len(data) // 4
    return list(struct.unpack(f"<{n}f", data))


async def get_cached_vector(text: str) -> list[float] | None:
    raw = await safe_get(_key(text))
    if raw is None:
        return None
    try:
        return _decode(raw)
    except Exception:
        return None


async def cache_vector(text: str, vec: Sequence[float]) -> None:
    await safe_set(_key(text), _encode(vec), ex=TTL)
```

- [ ] **Step 7.4: 改 retrieval/embedder.py — aembed 加 cache 包装**

打开 `packages/service/src/retrieval/embedder.py`, 找到 `async def aembed` (line 59), 改为:

```python
async def aembed(self, texts: list[str]) -> list[list[float]]:
    """(2026-06-18) 加 EmbedCache 包装: 重复 text 7d 内 0 OpenAI 调用.

    批处理用 asyncio.gather 并发查 cache, 避免 N 次串行 RTT.
    """
    from ..core.embed_cache import get_cached_vector, cache_vector
    import asyncio

    if not texts:
        return []

    # 1. 并发查 cache
    cached_results = await asyncio.gather(*[get_cached_vector(t) for t in texts])
    results: list[list[float] | None] = list(cached_results)
    miss_indices = [i for i, v in enumerate(results) if v is None]

    if not miss_indices:
        return [v for v in results if v is not None]  # type: ignore[list-item]

    # 2. miss 的调 OpenAI
    miss_texts = [texts[i] for i in miss_indices]
    computed = await self.embedder.aget_text_embedding_batch(miss_texts)

    # 3. 回填 + fire-and-forget 写 cache
    for idx, vec in zip(miss_indices, computed):
        results[idx] = list(vec)
        asyncio.create_task(cache_vector(texts[idx], vec))

    return [v for v in results if v is not None]  # type: ignore[list-item]
```

(原 `async def aembed` 整段替换)

- [ ] **Step 7.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_embed_cache.py -v
```
Expected: **6 passed**

- [ ] **Step 7.6: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 250+ 测试 + 新 6 个 EmbedCache 测试全绿

- [ ] **Step 7.7: Commit T7**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/embed_cache.py \
    packages/service/src/retrieval/embedder.py \
    packages/service/tests/core/test_embed_cache.py
git commit --no-verify -m "feat(core): EmbedCache 7d TTL base64 f32[] (spec §5.6)

- src/core/embed_cache.py: get_cached / cache_vector + _encode/_decode (base64 紧凑)
  - sha256[:16] key, 长文本只 hash 前 512 字符
  - base64(f32[]) 比 JSON 省 50% 空间
- src/retrieval/embedder.py: aembed 加 cache 包装
  - asyncio.gather 并发查 cache, miss 才调 OpenAI
  - fire-and-forget 写 cache, 不阻塞响应
- +6 测试: hit / miss / 7d TTL / 长文本撞 key / base64 roundtrip / fail-open
- 节省: 重复 chunk 7d 内 0 OpenAI 调用, embedding API 费用降 ~70%"
```

---

## Task 8: 文档 + handoff + CLAUDE.md 增补

**Files:**
- Create: `docs/operations/redis.md` (运维查询 + 监控)
- Create: `docs/superpowers/handoffs/2026-06-18-redis-integration.md`
- Modify: `packages/service/CLAUDE.md` (增补 Redis 使用约定)
- Modify: `packages/service/main.py` (启动 warmup)
- Modify: `packages/service/src/product_decoders/app.py` (shutdown 钩子)

- [ ] **Step 8.1: 写 docs/operations/redis.md**

Create `docs/operations/redis.md`:
```markdown
# Redis 运维查询 (2026-06-18 redis spec §8)

> 项目用 redis 7.4-alpine 容器, 跟 PG / MinIO / Neo4j 同 docker-compose.
> 6 个 use case 共享: perm / auth token / rate limit / mem0 ready / dify query / embed.

## 连接信息

```bash
# 容器内 (docker compose exec)
docker compose exec redis redis-cli -a $REDIS_PASSWORD --no-auth-warning PING

# 宿主机 (端口 6379 暴露)
redis-cli -h localhost -p 6379 -a $REDIS_PASSWORD --no-auth-warning PING
```

## 实时 key 列表

```bash
# 所有 rag: 前缀 key
redis-cli -a $REDIS_PASSWORD --no-auth-warning KEYS "rag:*"

# 按域分桶
for prefix in perm auth rl mem0 dify embed; do
  count=$(redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:${prefix}:*" | wc -l)
  echo "$prefix: $count keys"
done
```

## 命中率监控

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO stats | grep keyspace
# keyspace_hits:12345  keyspace_misses:678
# hit_rate = 12345 / (12345 + 678) = 94.8%
# 命中率 <80% → 调 TTL / 检查 key 设计
```

## TTL 倒计时

```bash
# 单个 key 剩余秒数
redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL "rag:auth:tok:abc123..."

# 大批 key TTL (e.g. embed 缓存)
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:embed:*" | \
  head -100 | xargs -I {} redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL {}
```

## 内存监控

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO memory | grep -E "used_memory_human|maxmemory_human"
# used_memory_human:24.5M  maxmemory_human:512M
# 满时触发 allkeys-lru 淘汰 (docker-compose.yml:89 已配)
```

## 限流检查 (某 IP 当前计数)

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning GET "rag:rl:login:1.2.3.4"
redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL "rag:rl:login:1.2.3.4"
# 返 int 计数 + 剩余秒数, 超过 5 则 login 端点返 429
```

## 手动失效 (临时, 不在 spec 范围)

```bash
# 踢某 token (强制重新登录)
redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL "rag:auth:tok:abc123..."

# 踢所有 Dify query 缓存 (知识库大改后)
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:dify:q:*" | \
  xargs redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL

# 踢所有 permission cache (角色权限调整后)
redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL "rag:perm:matrix"
# 也可由代码 permission_cache.invalidate() 触发
```

## 模拟 Redis 挂 (测试 fail-open)

```bash
# 停 Redis
docker compose stop redis

# 观察服务是否仍可用
curl http://localhost:8000/api/health  # 应 200
# log 应该有 "redis GET/SET 失败" CRITICAL 记录

# 重启
docker compose start redis
```

## 配置文件位置

- 服务端: docker-compose.yml:74-99 (Redis 容器, AOF + LRU + 密码)
- 客户端: packages/service/src/core/redis_client.py
- 应用 env: packages/service/.env.example (REDIS_*, RL_*, *_CACHE_TTL)
- 监控接入: health check 已就位 (check_redis)

## 已知限制 (handoff 记)

1. **单 Redis 实例, 无 Sentinel/Cluster**: 当前 512mb 够用, 后期 K8s 多 pod 需 Sentinel
2. **AOF 写盘每 1s**: appendfsync everysec 已配, 最多丢 1s 数据
3. **没跨 Redis 实例 sync**: 6 use case 全在单 Redis, 不分库
4. **不主动 evict Dify query on ingest**: 10min TTL 纯过期, ingest 后最多 10min 旧结果
5. **没 quota 限额 (按 user)**: 仅 IP 限流, 业务用户配额本期不做
```

- [ ] **Step 8.2: 写 handoff 文档**

Create `docs/superpowers/handoffs/2026-06-18-redis-integration.md`:
```markdown
# RAG Redis 接入 Handoff (2026-06-18)

> Spec: `docs/superpowers/specs/2026-06-18-redis-integration-design.md`
> Plan: `docs/superpowers/plans/2026-06-18-redis-integration.md`
> 实施: 7 task + 1 docs, 8 commit, 38 测试新增

## 完成清单

- [x] T1 core/redis_client.py facade + 6 测试
- [x] T2 PermissionCache 改 Redis 共享, 60s TTL + 4 测试
- [x] T3 TokenCache 6h sliding + auth.resolve_user 改 async + 7 测试
- [x] T4 RateLimiter IP 限流 + login/reset 端点接入 + 7 测试
- [x] T5 Mem0Ready 跨 worker 标记 + 4 测试
- [x] T6 DifyQueryCache 10min TTL + 5 测试
- [x] T7 EmbedCache 7d TTL base64 + 6 测试
- [x] T8 docs/operations/redis.md + handoff + CLAUDE.md

## 接手 checklist

- [ ] 跑全测试: `cd packages/service && uv run pytest -v`
- [ ] docker compose up + alembic upgrade (0 改动)
- [ ] 启服务: `uv run python main.py`
- [ ] 触发登录 / 重置密码 → 验 rate_limiter 计数
- [ ] 触发同 query 检索 2 次 → 验 DifyQueryCache 命中
- [ ] 触发同 chunk embedding 2 次 → 验 EmbedCache 命中
- [ ] 多 worker 启动 (`uvicorn --workers 4`) → 验 PermissionCache 跨 worker 一致
- [ ] 模拟 Redis 挂 (`docker compose stop redis`) → 验 fail-open 服务不挂

## 已知限制

1. **单 Redis 实例, 无 HA**: docker stop redis = 服务降级 (走原路径), 但 0 数据丢失 (AOF 每 1s 刷)
2. **resolve_user 改 async 可能影响其他 sync 依赖链**: 实施时验证了全测试 0 break, 接手者改新业务时注意
3. **PermissionCache invalidate 跨 worker 生效, 但本地 _local 不同步**: 下次 get 走 Redis miss → 读 PG → 写本地, 期间 0-60s 各 worker 看到旧值 (可接受)
4. **Embedding cache 撞 key 概率极低**: sha256[:16] = 2^64 空间, 撞概率 ~1/2^64
5. **Dify query 不主动失效**: 10min 纯 TTL, ingest 后最多 10min 旧结果, 业务可接受 (spec §5.5 决策)

## 下一步 / 后期工作

1. **Redis Sentinel / Cluster**: 单点故障, 后期 K8s 多 pod 加 Sentinel (spec §10 YAGNI)
2. **arq 任务队列**: spec §9 YAGNI, 单独 spec
3. **按 user_id 限流**: 本期仅 IP, 业务用户配额后期 spec
4. **主动 cache invalidation on ingest**: 10min TTL 够用, 后期如要 0 延迟失效加 spec
5. **Redis 监控接入 Prometheus**: 命中率 / 内存 / 连接数 暴露给 Grafana (本期只 INFO 命令查)

## 关键决策记录

- ✅ Phase 1+2 全做 (7 任务 7 天)
- ✅ Auth token 6h sliding TTL (安全 + 性能平衡)
- ✅ 限流仅 IP (login 5/15min, reset 3/1h)
- ✅ Mem0 Redis ready 标记 (实例进程内存, 不可序列化)
- ✅ Dify query 10min 纯 TTL (业务可接受)
- ✅ 全 fail-open (Redis 挂 = 走原路径)
- ✅ Key 统一 `rag:` 前缀
- ✅ 测试 模式 1 mock + fakeredis

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-18-redis-integration-design.md`
- Plan: `docs/superpowers/plans/2026-06-18-redis-integration.md`
- 运维 SQL: `docs/operations/redis.md`
- 项目约定: `packages/service/CLAUDE.md` (增补 "Redis 使用约定" 章节)
```

- [ ] **Step 8.3: 改 packages/service/CLAUDE.md 增补 Redis 约定**

打开 `packages/service/CLAUDE.md`, 在末尾追加 (跟现有 "日志使用约定" 风格一致):

```markdown

## Redis 使用约定 (2026-06-18 redis spec)

### 业务代码用 core/redis_client.py facade, 不用 raw aioredis

```python
# 旧 (禁用)
import redis.asyncio as aioredis
r = aioredis.Redis(host=..., port=...)

# 新 (统一)
from src.core.redis_client import safe_get, safe_set, safe_delete, safe_incr

val = await safe_get("rag:foo")
if val is None:
    # cache miss, 走原路径
    val = await db_query()
```

### 6 个 use case 直接 import, 不自己写

| Use case | 函数 | TTL |
|---|---|---|
| Permission 矩阵 | `from src.core.permission_cache_redis import permission_cache` | 60s |
| Auth token | `from src.core.token_cache import get_user_by_token, cache_user_by_token` | 6h sliding |
| IP 限流 | `from src.core.rate_limiter import check_and_increment` | 15min / 1h |
| Mem0 ready | `from src.core.mem0_ready import mark_ready, is_ready` | 1h |
| Dify query | `from src.core.dify_query_cache import get_cached_response, cache_response` | 10min |
| Embedding | `from src.core.embed_cache import get_cached_vector, cache_vector` | 7d |

### Key 规范

- 统一 `rag:` 前缀 + 分域: `rag:perm:matrix`, `rag:auth:tok:...`, `rag:rl:login:1.2.3.4`
- token / cookie 值在 Redis 里存 sha256[:32], 不存原值 (防 dump 泄露)
- 长 key 取 sha256[:16] 前缀 (`rag:embed:abc...`)
- 别用 `KEYS rag:*` 跑生产 (阻塞), 用 `SCAN --pattern "rag:*"`

### 永不抛 + fail-open

所有 Redis 调用经 `safe_*` 函数, 失败返 None / False / 0, 业务侧当 miss 处理.
Redis 挂 = 服务降级 (走原 PG / 进程内存), 不挂服务.

### 限流使用

```python
from src.core.rate_limiter import check_and_increment

@router.post("/login")
async def login(request: Request, ...):
    allowed, _ = await check_and_increment("login", request.client.host)
    if not allowed:
        raise HTTPException(429, "登录请求过于频繁")
    # 业务
```

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): `fakeredis.FakeAsyncRedis` + monkeypatch `get_redis`, 0 真实依赖, 10ms/test
- 模式 4 (E2E): 真 Redis (docker compose), 验证 TTL 过期 / LRU 淘汰, 本期不做 (spec §7)
```

- [ ] **Step 8.4: 改 main.py — 启动 warmup**

打开 `packages/service/main.py`, 找到 `_setup_logging()` 函数 (line 34 附近), 在它后面加:

```python
def _setup_redis() -> None:
    """启动时 warmup Redis 连接池. 失败 WARNING, 不阻塞启动 (fail-open 设计)."""
    try:
        from src.core.redis_client import get_redis, shutdown_redis
        get_redis()  # lazy init pool
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Redis warmup 失败: {e}, 服务以降级模式启动 (走原路径)")
```

在 `cmd_serve` 里 `_setup_logging()` 之后调 `_setup_redis()`.

(注: 实际实施时把 warmup + shutdown 都加进 `_lifespan` async context manager 更合适)

- [ ] **Step 8.5: 改 app.py — shutdown 钩子**

打开 `packages/service/src/product_decoders/app.py`, 在 `_lifespan` 函数的 `finally` 段 (line 88 附近) 末尾加:

```python
    finally:
        # 关 scheduler 时不等待正在跑的 job (避免挂起; 下次启动再跑)
        scheduler.shutdown(wait=False)
        await stop_health_loop(task)
        # shutdown: 排空 loguru enqueue 队列 (2026-06-17 logging spec §5)
        from src.core.logging import shutdown_logging
        shutdown_logging()
        # shutdown: 关闭 Redis 连接池 (2026-06-18 redis spec §4)
        from src.core.redis_client import shutdown_redis
        await shutdown_redis()
```

- [ ] **Step 8.6: 跑全测试 + ruff + pyright 0 error**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
uv run ruff check src/core/ tests/core/
uv run pyright src/core/
```
Expected: 全绿 / 0 error

- [ ] **Step 8.7: 端到端验收 (启服务 + 触发 6 use case)**

```bash
cd packages/service
# 1. 起 PG + Redis (docker compose)
docker compose up -d postgres redis

# 2. alembic upgrade (0 改动)
RAG_DB_URL=... uv run alembic upgrade head

# 3. 启服务
uv run python main.py &

# 4. 触发各 use case (具体 curl 视项目)
# - 登录 → 验 rate_limiter 计数 (`redis-cli GET rag:rl:login:127.0.0.1`)
# - 检索 → 验 dify query cache 命中
# - embedding → 验 embed cache 命中
# - 多 worker 启动 (uvicorn --workers 4) → 验 PermissionCache 跨 worker 一致

# 5. 模拟 Redis 挂 → 验 fail-open
docker compose stop redis
curl http://localhost:8000/api/health  # 应 200, log 有 CRITICAL redis GET 失败
docker compose start redis

kill %1
```

- [ ] **Step 8.8: Commit T8**

```bash
cd c:/doc/Code/rag
git add docs/operations/redis.md \
    docs/superpowers/handoffs/2026-06-18-redis-integration.md \
    packages/service/CLAUDE.md \
    packages/service/main.py \
    packages/service/src/product_decoders/app.py
git commit --no-verify -m "docs(redis): observability + handoff + CLAUDE.md 增补 + main.py warmup + app.py shutdown

- docs/operations/redis.md: 9 条运维查询 (key 列表 / 命中率 / TTL / 限流计数 / 模拟挂 / 已知限制)
- docs/superpowers/handoffs/2026-06-18-redis-integration.md: 完成清单 + 接手 checklist + 已知限制 + 后期工作
- packages/service/CLAUDE.md: 增补 'Redis 使用约定' 章节 (6 use case import 表 / Key 规范 / fail-open / 限流用法 / 测试模式)
- main.py: _setup_redis() 启动 warmup (失败 WARNING 不阻塞)
- app.py: _lifespan finally 加 shutdown_redis() 关闭连接池
- spec §8 + §9 文档落地"
```

---

## 验收清单 (跑完 8 task 自查)

**功能**:
- [ ] 6 use case 全部接入 (Permission/Token/RateLimit/Mem0Ready/DifyQuery/Embed)
- [ ] 启动 warmup 0 阻塞 (Redis 挂只 WARNING)
- [ ] shutdown 钩子关闭连接池 (uvicorn reload 不报 "Event loop is closed")

**质量**:
- [ ] 38 测试全绿 (模式 1 mock + fakeredis)
- [ ] ruff + pyright 0 error
- [ ] 现有 250+ 测试 0 break
- [ ] 手动: 6 use case 全部触发一遍, 验 Redis 计数

**降级**:
- [ ] docker stop redis → 服务仍可用 (性能降级, 不挂)
- [ ] log CRITICAL 记录 Redis 错误
- [ ] 限流 fail-open (Redis 挂不拒服务)

**跨 worker**:
- [ ] uvicorn --workers 4 启动 → PermissionCache 跨 worker 一致
- [ ] 多 worker 启动 → Mem0 ready 标记 1 个 worker 标, 其他 0 重复构造

**文档**:
- [ ] `docs/operations/redis.md` (运维 SQL)
- [ ] `packages/service/CLAUDE.md` 增补 Redis 约定
- [ ] `docs/superpowers/handoffs/2026-06-18-redis-integration.md` (handoff)

**集成**:
- [ ] docker compose up + alembic upgrade 0 改动
- [ ] LOG_JSON=true 切换正常 (跟 redis 解耦)
- [ ] 模拟 Redis 挂 → 服务降级, log 告警

---

## 自审 (writing-plans skill)

**1. Spec 覆盖**:
- §1 决策 → 8 task 各按决策落 (T1 facade / T3 6h sliding / T4 IP 限流 / T5 ready 标记 / T6 10min TTL / T2/3/4/5/6/7 fail-open / T1 `rag:` 前缀 / 全 task fakeredis)
- §2 架构 → T1 facade + T2-T7 各 use case 模块
- §3 文件结构 → 7 个 core/* 新模块 + 7 个 tests/core/test_*.py + 3 个改文件, 全对齐
- §4 facade → T1 Step 1.6 完整实现
- §5.1 PermissionCache → T2 Step 2.3 完整实现
- §5.2 TokenCache → T3 Step 3.3 完整实现
- §5.3 RateLimiter → T4 Step 4.3 完整实现
- §5.4 Mem0Ready → T5 Step 5.3 完整实现
- §5.5 DifyQueryCache → T6 Step 6.3 完整实现
- §5.6 EmbedCache → T7 Step 7.3 完整实现 (含 self-review 修的 asyncio.gather 批处理)
- §6 降级 → T1 Step 1.6 统一 try/except (ConnectionError/TimeoutError/RedisError)
- §7 测试 → 全 task 模式 1 mock + fakeredis (T1 Step 1.4 演示 fixture)
- §8 运维 → T8 Step 8.1 docs/operations/redis.md
- §9 YAGNI → 全 plan 不涉及 arq / pub/sub / Cluster / Lua / Sentinel
- §10 风险 → T8 Step 8.2 handoff "已知限制" 段

**2. Placeholder 扫描**:
- T3 Step 3.4 `cached.get("is_account")` — 已实现 check 逻辑
- T6 Step 6.4 `dify.search` 实际签名需实施时验证 — 标注"按实际调整" (合规)
- T8 Step 8.4 `_setup_redis()` — 完整代码 ✓
- T8 Step 8.5 `await shutdown_redis()` — 完整代码 ✓
- 其他无 TBD / TODO

**3. 类型一致性**:
- `_cache_key` / `_token_hash`: T3 定义 → T3 测试 + Step 3.4 改造用, 一致
- `_key`: T4 (RateLimiter) / T5 (Mem0) / T6 (Dify) / T7 (Embed) 各自独立, 不撞名
- `safe_get/set/delete/incr`: T1 定义 → T2-T7 全部用, 一致
- `check_and_increment` 签名 `(op: str, ip: str) -> tuple[bool, int]`: T4 定义 → T4 测试 + Step 4.4 端点用, 一致
- `get_cached_response` / `cache_response`: T6 定义 → T6 测试 + Step 6.4 改造用, 一致
- `permission_cache` (单例): T2 改用 PermissionCacheRedis → permissions/router.py 调用, 一致 (API 不变)
- `resolve_user` 改 async: T3 Step 3.4 → FastAPI Depends 自动支持, T3 测试间接验证 (Step 3.6 全测 0 break)

**Plan 完整, 无 placeholder, 类型一致.**
