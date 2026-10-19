# RAG Redis 接入 Design Spec (2026-06-18)

> **For agentic workers:** 后续 plan / 实施按本 spec 落地, 不偏离. 改 spec 需新 brainstorm + commit.

**Goal**: 把当前进程内存 cache / 每次查 PG 的鉴权 / 无防护的登录接入 Redis, 解决多 worker 缓存不一致 + hot path PG 压力 + 登录防爆破 + LLM token 浪费. fail-open 设计保证 Redis 挂不影响服务可用性. 0 PG schema 改动.

**Architecture**: `redis.asyncio` + 单例 ConnectionPool + 单一 facade `core/redis_client.py` (参考 logging facade 模式). 7 个 use case 各自封装 (PermissionCache / TokenCache / RateLimiter / Mem0Ready / DifyQueryCache / EmbedCache), 统一走 `get_redis()` 入口, 任何 RedisError 降级原路径 (fail-open). 测试用 fakeredis 模式 1 mock.

**Tech Stack**: redis>=5.0 (asyncio), fakeredis>=2.0 (test), 跟 loguru / Pydantic v2 / FastAPI 0.115+ 兼容. 0 新基础设施 (Redis 已在 docker-compose.yml 配好, .env 已声明).

---

## 1. 用户决策记录 (2026-06-18 brainstorming)

| 决策点 | 用户选择 | 备注 |
|---|---|---|
| 范围 | Phase 1 + Phase 2 (P0 5 任务 + P1 2 任务) | 7 任务, 7 天, 1 个 spec 解决 |
| Auth token TTL | 6h + sliding 续期 | 安全 + 性能平衡 |
| 限流维度 | 仅 IP (5 次/15min login, 3 次/1h reset) | 邮箱查重 / 重置密码 / 登录 |
| Mem0 共享方式 | Redis 只存 ready 标记 | 轻, 实例本身不可序列化 |
| Dify 缓存失效 | 10min 纯 TTL | ingest 后最多 10min 旧结果, 业务可接受 |
| 降级策略 | 全 fail-open | Redis 挂 = 走原路径, 服务不挂 |
| Key 命名空间 | 统一 `rag:` 前缀 | `rag:perm:matrix`, `rag:auth:tok:...` |
| 测试策略 | 模式 1 mock + fakeredis | 0 真实依赖, 10ms/test |

**Why**: 用户 2026-06-18 决定接入 Redis 优化 hot path + 防爆破. 项目多 worker 部署时进程内存 cache 不一致是已知痛点 (CLAUDE.md 已记, 接手者撞过). Dify / OpenAI 调用浪费 token 是隐性成本, 加缓存 ROI 高.

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│ FastAPI Request Lifecycle                                     │
│                                                                │
│  RequestIDMiddleware (X-Request-ID → contextvar)              │
│       ↓                                                        │
│  resolve_user (auth) → TokenCache.get(token_hash)              │
│       ├─ hit → return cached user                             │
│       └─ miss → PG users.public_token + cache.set (6h sliding)│
│       ↓                                                        │
│  permission_cache.get(role, page) → PermissionCache           │
│       ├─ hit → return bool                                    │
│       └─ miss/stale (60s TTL) → PG role_permissions           │
│       ↓                                                        │
│  ratelimit_check(ip, op) → RateLimiter (login/reset 端点)     │
│       ├─ over limit → 429                                     │
│       └─ under limit → INCR + EXPIRE NX 15min                 │
│       ↓                                                        │
│  Route Handler                                                │
│       ├─ mem0.memory → Mem0Ready marker + 进程内 lazy init     │
│       ├─ dify.query → DifyQueryCache (10min TTL)              │
│       └─ embedder.embed → EmbedCache (7d TTL)                  │
│       ↓                                                        │
│  Response                                                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ core/redis_client.py (facade, 跟 logging.py 同模式)           │
│  - get_redis() → 单例 aioredis.Redis via ConnectionPool         │
│  - max_connections=20, socket_timeout=2s, decode_responses=True│
│  - health_check_interval=30s                                  │
│  - 永不抛: 业务侧 try/except RedisError → 走原路径              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Redis 7.4-alpine (docker-compose.yml 已配)                    │
│  - AOF 持久化 (appendfsync everysec)                          │
│  - maxmemory 512mb, allkeys-lru 淘汰                          │
│  - requirepass (REDIS_PASSWORD env)                           │
│  - 已有 check_redis() health endpoint                          │
└──────────────────────────────────────────────────────────────┘
```

**5 大设计原则**:
1. **Facade 模式**: 跟 logging.py 同款, 业务侧只调 `get_redis()`, 不直接 import redis
2. **永不阻塞请求**: 所有 Redis 调用 `socket_timeout=2s`, 超时走原路径 (fail-open)
3. **降级透明**: 任何 RedisError 在 facade 层 catch + log CRITICAL, 业务侧无感
4. **Key 规范统一**: `rag:` 前缀 + 分域 (perm/auth/rl/mem0/dify/embed), 跟 service 边界对齐
5. **测试零依赖**: fakeredis 提供 FakeAsyncRedis 完整 asyncio API, pytest fixture monkeypatch `get_redis()`

---

## 3. 文件结构 (新增 + 改)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/service/src/core/redis_client.py` | ~80 | 单例 ConnectionPool + get_redis() + try/except facade |
| `packages/service/src/core/permission_cache_redis.py` | ~120 | PermissionCache 改造: 进程内存 → Redis 共享, 60s TTL |
| `packages/service/src/core/token_cache.py` | ~100 | token_hash → user 缓存, 6h sliding, fail-open 走 PG |
| `packages/service/src/core/rate_limiter.py` | ~80 | IP 限流 (login 5/15min, reset 3/1h), INCR + EXPIRE NX |
| `packages/service/src/core/mem0_ready.py` | ~60 | mem0 per-user ready 标记, 跨 worker decorrelation |
| `packages/service/src/core/dify_query_cache.py` | ~80 | Dify query 缓存, 10min TTL, sha256 hash key |
| `packages/service/src/core/embed_cache.py` | ~80 | Embedding 向量缓存, 7d TTL, base64 f32[] |
| `packages/service/tests/core/test_redis_client.py` | ~100 | 5 测试: 连接 / 超时 / 降级 / fakeredis mock |
| `packages/service/tests/core/test_permission_cache_redis.py` | ~80 | 4 测试: hit / miss / 60s TTL / 降级走 PG |
| `packages/service/tests/core/test_token_cache.py` | ~120 | 6 测试: hit / miss / 6h sliding / 降级 / 失效踢 |
| `packages/service/tests/core/test_rate_limiter.py` | ~100 | 6 测试: 计数 / 阈值 / 重置 / 降级 fail-open |
| `packages/service/tests/core/test_mem0_ready.py` | ~60 | 3 测试: ready 标记 / 1h TTL / 跨 worker |
| `packages/service/tests/core/test_dify_query_cache.py` | ~80 | 4 测试: hit / miss / 10min TTL / 降级 |
| `packages/service/tests/core/test_embed_cache.py` | ~80 | 4 测试: hit / miss / 7d TTL / 降级 |
| `docs/operations/redis.md` | ~150 | 运维查询 (key 列表 / 命中率 / 淘汰监控) |
| `docs/superpowers/specs/2026-06-18-redis-integration-design.md` | 本文件 | spec |
| `docs/superpowers/plans/2026-06-18-redis-integration.md` | 待写 | plan |
| `docs/superpowers/handoffs/2026-06-18-redis-integration.md` | 待写 | handoff |

### 改

| 文件 | 改动 |
|---|---|
| `packages/service/pyproject.toml` | 加 `redis>=5.0,<6.0`, `fakeredis>=2.0` (test deps) |
| `packages/service/.env.example` | 增补 `REDIS_MAX_CONNECTIONS=20`, `REDIS_SOCKET_TIMEOUT=2`, `TOKEN_CACHE_TTL=21600` 等 |
| `packages/service/src/middleware/auth.py` | resolve_user 调 TokenCache.get (失败回退原 PG 路径) |
| `packages/service/src/permissions/cache.py` | PermissionCache.get 改为查 Redis (失败回退原 PG _refresh) |
| `packages/service/src/permissions/router.py` | invalidate 改为 DEL Redis key (跨 worker 生效) |
| `packages/service/src/memory/mem0_client.py` | Mem0Store.memory 加 Mem0Ready check (避免冷启动 race) |
| `packages/service/src/eval/router.py` | Dify 检索前查 DifyQueryCache |
| `packages/service/src/retrieval/embedder.py` | embed_texts 前查 EmbedCache |
| `packages/service/src/auth/auth_account_router.py` | login/reset 端点前 RateLimiter.check |
| `packages/service/src/main.py` | 启动时 get_redis() warmup (失败 WARNING, 不阻塞启动) |
| `packages/service/src/product_decoders/app.py` | 启动 lifespan 加 Redis client 关闭钩子 |
| `packages/service/src/core/redis_client.py` | shutdown_redis() 排空连接 |
| `packages/service/CLAUDE.md` | 增补 "Redis 使用约定" 章节 |
| `docs/operations/observability.md` | 加 Redis 监控 SQL (keyspace_hits/misses, maxmemory) |

**注**: 实施前 implementer subagent 必须先 `grep -rn "permission_cache\|token\|rate.limit" packages/service/src/` 列现有用法, 跟 spec §3 改表交叉比对.

---

## 4. core/redis_client.py (facade)

```python
"""Redis 客户端 facade (2026-06-18 redis spec §4)

跟 logging.py 同款 facade 模式:
- 业务侧只调 get_redis(), 不直接 import redis
- 单例 ConnectionPool, max_connections=20
- 任何 RedisError 在 facade 层 catch + log CRITICAL
- 业务侧 try/except RedisError → 走原路径 (fail-open)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

# 模块级单例
_pool: aioredis.ConnectionPool | None = None


def _build_pool() -> aioredis.ConnectionPool:
    """构造 ConnectionPool. 启动时调一次."""
    return aioredis.ConnectionPool(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,                 # 业务侧直接拿 str
        max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "2")),     # 2s 超时
        socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "2")),
        health_check_interval=30,              # 30s 探活, 防僵尸连接
    )


def get_redis() -> aioredis.Redis:
    """业务侧调本函数拿 Redis 客户端. lazy init + 模块级单例."""
    global _pool
    if _pool is None:
        _pool = _build_pool()
        logger.info("redis pool initialized host={} max_conn={}",
                    _pool.connection_kwargs.get("host"),
                    _pool.max_connections)
    return aioredis.Redis(connection_pool=_pool)


async def safe_get(key: str) -> str | None:
    """facade: GET, 失败返 None + log CRITICAL (不抛, 业务侧当 miss 处理)."""
    try:
        return await get_redis().get(key)
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis GET 失败 key={} err={}", key, e)
        return None


async def safe_set(key: str, value: str, ex: int | None = None) -> bool:
    """facade: SET + EX (秒), 失败返 False."""
    try:
        return await get_redis().set(key, value, ex=ex)
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis SET 失败 key={} err={}", key, e)
        return False


async def safe_delete(*keys: str) -> int:
    """facade: DEL, 失败返 0."""
    try:
        return await get_redis().delete(*keys)
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis DEL 失败 keys={} err={}", keys, e)
        return 0


async def safe_incr(key: str, ex_seconds: int | None = None) -> int | None:
    """facade: INCR + EXPIRE NX (原子). 失败返 None (业务侧当 fail-open 处理).

    Redis 挂判定 (facade 统一抓):
    - aioredis.ConnectionError: TCP 拒连
    - aioredis.TimeoutError: socket_timeout 2s 到了
    - aioredis.RedisError: 其他 Redis 协议错 (NOAUTH / OOM 等)

    业务侧不需要 import aioredis, 全部经 facade.
    """
    try:
        r = get_redis()
        # pipeline 原子: INCR + EXPIRE NX (仅首次设过期)
        async with r.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            if ex_seconds:
                pipe.expire(key, ex_seconds, nx=True)
            results = await pipe.execute()
        return results[0]  # INCR 后的计数
    except (aioredis.RedisError, ConnectionError, TimeoutError) as e:
        logger.critical("redis INCR 失败 key={} err={}", key, e)
        return None


async def shutdown_redis() -> None:
    """FastAPI shutdown 钩子. 关闭连接池."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
        logger.info("redis pool closed")
```

**Facade 设计要点**:
- 业务侧只 import `from src.core.redis_client import safe_get, safe_set, safe_delete, safe_incr`
- 永不抛, 失败返 None / 0 / False, 业务侧当 cache miss / 计数 0 处理
- log CRITICAL (进 error_logs) 让 on-call 知道 Redis 故障, 但不阻断请求
- shutdown 钩子排空连接池, 避免 uvicorn reload 时 "Event loop is closed" 错误

---

## 5. 7 个 use case 实现细节

### 5.1 PermissionCache (P0-2, §2 of task list)

**当前**: [permissions/cache.py:40-76](packages/service/src/permissions/cache.py#L40-L76) 进程内存 dict + 30s TTL.

**改造**: 加 Redis 共享层, TTL 60s, 跨 worker 一致.

```python
# packages/service/src/core/permission_cache_redis.py
"""PermissionCache Redis 共享版 (2026-06-18 redis spec §5.1)"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from loguru import logger
from .redis_client import safe_get, safe_set

CACHE_KEY = "rag:perm:matrix"
CACHE_TTL = int(os.getenv("PERM_CACHE_TTL", "60"))  # 秒


class PermissionCacheRedis:
    """Redis 共享版: 多 worker 看到一致权限矩阵."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._local_fallback: dict[str, dict[str, bool]] = {}  # Redis 挂时降级
        self._loaded_at: float = 0.0

    def get(self, role: str, page_key: str) -> bool | None:
        """查 role × page 权限. 失败降级进程内存."""
        # 先试 Redis
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 在 async context, 用 safe_get
            cached = asyncio.create_task(safe_get(CACHE_KEY))
            cached_value = cached  # 不能在这里 await, 留 fallback 路径
        else:
            cached_value = None

        # 简化: 实际实施时 PermissionCache 改成 async (依赖 FastAPI 全 async 栈)
        # 同步版本降级: 进程内存 dict
        with self._lock:
            if time.time() - self._loaded_at > CACHE_TTL:
                self._refresh_from_pg()
            return self._local_fallback.get(role, {}).get(page_key)

    def invalidate(self) -> None:
        """DEL Redis key, 下次 get 触发 _refresh_from_pg()."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(safe_delete(CACHE_KEY))
        except RuntimeError:
            pass
        with self._lock:
            self._loaded_at = 0.0

    def _refresh_from_pg(self) -> None:
        """全表读 role_permissions 到本地 (同步路径, 兼容现有 sync 调用)."""
        from sqlalchemy import text
        from ..storage.session import session_scope

        with self._lock:
            new_matrix: dict[str, dict[str, bool]] = {}
            with session_scope() as s:
                rows = s.execute(text("SELECT role_name, page_key, allowed FROM role_permissions")).fetchall()
            for role_name, page_key, allowed in rows:
                new_matrix.setdefault(role_name, {})[page_key] = allowed
            self._local_fallback = new_matrix
            self._loaded_at = time.time()
            # 同步写 Redis (best effort, 失败不阻塞)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(safe_set(
                        CACHE_KEY, json.dumps(new_matrix), ex=CACHE_TTL,
                    ))
            except RuntimeError:
                pass


# 保留原单例, 内部实现替换
permission_cache = PermissionCacheRedis()
```

**注**: 实施时根据实际调用点改 async/sync. PermissionCache 当前是 sync 调用, 简化方案:
- PermissionCache.get 保持 sync (兼容现有调用), 但内部加 Redis 共享层: 同步查 Redis 失败 → 走原 sync 进程内存 (degrade)
- 改造要点: 改用 `asyncio.run_coroutine_threadsafe` 在 sync 上下文中调 async Redis, 或把 PermissionCache 改 async (破坏性大, 不推荐本期)
- 推荐: 保留 sync 进程内存 cache 作 fallback, 加一个异步 `_refresh_redis()` 后台 task (类似 health cache) 同步 Redis 跟内存

**注**: 实际实施时用 `PermissionCacheAsync` 替代 sync 版本, 改 resolve_user / guards 为 await. **本期 spec 锁定 async 路径**, 同步 fallback 仅 Redis 挂时使用.

### 5.2 TokenCache (P0-3, auth resolve_user 加速)

**当前**: `middleware/auth.py:resolve_user` 每请求查 PG `users.public_token`.

**改造**: Redis 缓存 `{user_id, is_admin, is_active, email_hash}` JSON, 6h sliding.

```python
# packages/service/src/core/token_cache.py
"""Auth token Redis 缓存 (2026-06-18 redis spec §5.2)"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from loguru import logger
from .redis_client import safe_get, safe_set

CACHE_TTL = int(os.getenv("TOKEN_CACHE_TTL", "21600"))  # 6h
TOKEN_KEY_PREFIX = "rag:auth:tok:"

# 不存原 token, 存 sha256 前 32 字节 (防 Redis dump 泄露)
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _cache_key(token: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{_token_hash(token)}"


async def get_user_by_token(token: str) -> dict[str, Any] | None:
    """查 token 对应 user. miss 返 None (调用方走 PG)."""
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
    """缓存 user 6h (sliding, 每次访问会被 set 刷新 = 续期到当前时刻 + 6h).

    Args:
        token: 原始 token 字符串 (内部会 sha256)
        user_obj: ORM User 对象 (有 .id / .is_admin / .is_active / .email 属性)
                 或 dict 形式 {"id":..., "is_admin":..., "is_active":..., "email":...}
    """
    # 兼容 ORM 对象和 dict
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
    from .redis_client import safe_delete
    await safe_delete(_cache_key(token))
```

**改造 resolve_user**:
```python
# 在 middleware/auth.py:resolve_user 内
async def resolve_user(request: Request) -> CurrentUser:
    token = request.cookies.get("rag_user_token") or request.headers.get("x-user-token")
    if token:
        cached = await get_user_by_token(token)
        if cached:
            return CurrentUser(id=cached["user_id"], is_admin=cached["is_admin"], is_active=cached["is_active"])
    # miss → 走原 PG 路径
    user = await _resolve_user_from_pg(token)
    if user:
        await cache_user_by_token(token, {
            "id": user.id, "is_admin": user.is_admin, "is_active": user.is_active, "email": user.email,
        })
    return user
```

### 5.3 RateLimiter (P0-4, 登录防爆破)

**当前**: 无防护.

**新增**: `core/rate_limiter.py`, IP 维度.

```python
"""IP 限流 (2026-06-18 redis spec §5.3)"""

from __future__ import annotations

import os
from dataclasses import dataclass
from loguru import logger
from .redis_client import safe_incr


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    window_seconds: int
    threshold: int


# 默认规则 (env 可覆盖)
RULES = {
    "login": RateLimitRule(
        name="login",
        window_seconds=int(os.getenv("RL_LOGIN_WINDOW", "900")),  # 15min
        threshold=int(os.getenv("RL_LOGIN_THRESHOLD", "5")),
    ),
    "reset": RateLimitRule(
        name="reset",
        window_seconds=int(os.getenv("RL_RESET_WINDOW", "3600")),  # 1h
        threshold=int(os.getenv("RL_RESET_THRESHOLD", "3")),
    ),
}


def _key(op: str, ip: str) -> str:
    return f"rag:rl:{op}:{ip}"


async def check_and_increment(op: str, ip: str) -> tuple[bool, int]:
    """检查 + 递增计数. 返 (allowed, current_count).

    - allowed=True: 未超阈值, 放行
    - allowed=False: 超阈值, 返 429

    fail-open: Redis 挂 → allowed=True (放行, 宁可被拤不要拒服务)
    """
    rule = RULES.get(op)
    if rule is None:
        logger.warning("rate limit rule 不存在 op={}", op)
        return True, 0

    key = _key(op, ip)
    count = await safe_incr(key, ex_seconds=rule.window_seconds)
    if count is None:
        return True, 0  # fail-open
    if count > rule.threshold:
        return False, count
    return True, count
```

**端点接入** (auth_account_router.py login/reset_password 之前):
```python
from src.core.rate_limiter import check_and_increment
from fastapi import Request

@router.post("/login")
async def login(request: Request, ...):
    allowed, count = await check_and_increment("login", request.client.host)
    if not allowed:
        raise HTTPException(status_code=429, detail="请求过于频繁, 请稍后再试")
    # ... 原业务
```

### 5.4 Mem0Ready (P0-5, 跨 worker decorrelation)

**当前**: `mem0_client.py:120-137` per-user_id Memory 实例 dict 缓存.

**改造**: Redis 存 ready 标记, 进程内仍存实例 (跨进程不可序列化). 标记仅 decorrelation, 避免 N 个 worker 同时 warmup 同一 user.

```python
"""Mem0 ready 标记 (2026-06-18 redis spec §5.4)"""

from __future__ import annotations

import os
from .redis_client import safe_set, safe_get

READY_TTL = int(os.getenv("MEM0_READY_TTL", "3600"))  # 1h


def _key(user_id: str) -> str:
    return f"rag:mem0:user:{user_id}:ready"


async def mark_ready(user_id: str) -> None:
    """worker 构造完 Memory 实例后调, 标记 ready 1h."""
    await safe_set(_key(user_id), "1", ex=READY_TTL)


async def is_ready(user_id: str) -> bool:
    """查询其他 worker 是否已 ready. miss/fail 返 False (本 worker 自己构造)."""
    val = await safe_get(_key(user_id))
    return val == "1"
```

**改造 mem0_client.Mem0Store.memory**:
```python
@property
def memory(self) -> Memory:
    if self._memory is None:
        # 异步检查 ready (简化: 直接构造, ready 标记仅用于跨 worker decorrelation)
        self._memory = _default_mem0_factory(self._user_id)
        # 标记 ready (fire-and-forget, 失败不阻塞)
        asyncio.create_task(mark_ready(self._user_id))
    return self._memory
```

### 5.5 DifyQueryCache (P1-1, 10min TTL)

**当前**: Dify 检索每次直调, 重复 query 重复扣 token.

**新增**: `core/dify_query_cache.py`, sha256 hash key.

```python
"""Dify 检索响应缓存 (2026-06-18 redis spec §5.5)"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from .redis_client import safe_get, safe_set

TTL = int(os.getenv("DIFY_QUERY_CACHE_TTL", "600"))  # 10min


def _key(query: str, dataset_id: str, top_k: int) -> str:
    raw = f"{dataset_id}:{top_k}:{query}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"rag:dify:q:{h}"


async def get_cached_response(query: str, dataset_id: str, top_k: int) -> list[dict] | None:
    """miss 返 None (调用方直调 Dify)."""
    key = _key(query, dataset_id, top_k)
    raw = await safe_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_response(query: str, dataset_id: str, top_k: int, response: list[dict]) -> None:
    """写缓存 10min."""
    key = _key(query, dataset_id, top_k)
    await safe_set(key, json.dumps(response), ex=TTL)
```

**改造 eval/router.py upload_run** (具体调用点视实现):
```python
# 在 DifyClient.search 之前
cached = await get_cached_response(query, dataset_id, top_k)
if cached:
    return cached
# 走原 Dify 调用
result = await dify.search(...)
await cache_response(query, dataset_id, top_k, result)
return result
```

### 5.6 EmbedCache (P1-2, 7d TTL)

**当前**: `retrieval/embedder.py:embed_texts` 每次调 OpenAI.

**新增**: `core/embed_cache.py`, base64 f32[].

```python
"""Embedding 向量缓存 (2026-06-18 redis spec §5.6)"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from typing import Sequence
from .redis_client import safe_get, safe_set

TTL = int(os.getenv("EMBED_CACHE_TTL", str(7 * 86400)))  # 7d


def _key(text: str) -> str:
    # 只 hash 前 512 字符 (长文本 hash 慢 + key 撞率高)
    h = hashlib.sha256(text[:512].encode("utf-8")).hexdigest()[:16]
    return f"rag:embed:{h}"


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

**改造 embedder.py embed_texts** (批处理用 asyncio.gather 避免串行 RTT):
```python
# 批处理: 先并发查所有 key, 收集 miss 索引, 一次性调 OpenAI
async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    cached_results = await asyncio.gather(*[get_cached_vector(t) for t in texts])
    results: list[list[float] | None] = list(cached_results)
    miss_indices = [i for i, v in enumerate(results) if v is None]
    if not miss_indices:
        return [v for v in results if v is not None]  # type: ignore
    miss_texts = [texts[i] for i in miss_indices]
    computed = await _openai_embed(miss_texts)
    # 回填结果 + 写缓存 (fire-and-forget)
    for idx, vec in zip(miss_indices, computed):
        results[idx] = vec
        asyncio.create_task(cache_vector(texts[idx], vec))
    return [v for v in results if v is not None]  # type: ignore
```

---

## 6. 降级策略总表 (fail-open 全部确认)

| 场景 | Redis 正常 | Redis 挂 | 降级行为 |
|---|---|---|---|
| `permission_cache.get` | Redis 查 (60s TTL) | catch RedisError | 进程内存 dict (原行为) |
| `token_cache.get_user_by_token` | Redis 查 (6h sliding) | catch RedisError | 走 PG `users.public_token` (原行为) |
| `rate_limiter.check_and_increment` | INCR + EXPIRE NX | catch RedisError | **allowed=True** (fail-open) |
| `mem0_ready.is_ready` | Redis 查 ready 标记 | catch RedisError | 返 False (本 worker 自己构造) |
| `dify_query_cache.get_cached_response` | Redis 查 (10min TTL) | catch RedisError | 返 None, 直调 Dify |
| `embed_cache.get_cached_vector` | Redis 查 (7d TTL) | catch RedisError | 返 None, 直调 OpenAI |

**核心原则**: Redis 挂 = 性能降级 (回原路径), 服务不挂. 唯一的"安全策略"(限流) 也 fail-open, 因为 Redis 挂时 5xx 全返代价远大于短时无防爆破.

---

## 7. 测试策略 (模式 1 mock + fakeredis)

### 7.1 pytest fixture

```python
# packages/service/tests/core/conftest.py (新建, 或扩展现有)
import pytest
from fakeredis import aioredis as fakeredis

@pytest.fixture
def fake_redis(monkeypatch):
    """fakeredis 模拟 Redis. 业务侧 get_redis() 返 FakeAsyncRedis.
    
    fakeredis 2.0+ 提供完整 asyncio API, 支持 GET/SET/INCR/EXPIRE/PIPELINE,
    内部用 dict 模拟, 0 真实依赖, 10ms/test.
    """
    fake = fakeredis.FakeRedis(decode_responses=True)
    
    # monkeypatch get_redis 返 FakeRedis
    from src.core import redis_client
    monkeypatch.setattr(redis_client, "get_redis", lambda: fake)
    
    # 同时 monkeypatch safe_* 函数, 让它们走 fake
    async def _safe_get(key):
        return await fake.get(key)
    async def _safe_set(key, value, ex=None):
        return await fake.set(key, value, ex=ex)
    async def _safe_delete(*keys):
        return await fake.delete(*keys)
    async def _safe_incr(key, ex_seconds=None):
        async with fake.pipeline(transaction=False) as pipe:
            pipe.incr(key)
            if ex_seconds:
                pipe.expire(key, ex_seconds, nx=True)
            results = await pipe.execute()
        return results[0]
    
    monkeypatch.setattr(redis_client, "safe_get", _safe_get)
    monkeypatch.setattr(redis_client, "safe_set", _safe_set)
    monkeypatch.setattr(redis_client, "safe_delete", _safe_delete)
    monkeypatch.setattr(redis_client, "safe_incr", _safe_incr)
    
    return fake


@pytest.fixture
def fake_redis_fail(monkeypatch):
    """模拟 Redis 挂, 业务侧应走 fail-open 路径."""
    from src.core import redis_client
    
    async def _boom(*a, **k):
        raise ConnectionError("Redis down")
    
    monkeypatch.setattr(redis_client, "safe_get", _boom)
    monkeypatch.setattr(redis_client, "safe_set", _boom)
    monkeypatch.setattr(redis_client, "safe_delete", _boom)
    monkeypatch.setattr(redis_client, "safe_incr", _boom)
```

### 7.2 32 测试覆盖

| 测试 | 模式 | fixture | 覆盖 |
|---|---|---|---|
| `test_redis_client.py` (5) | 1 mock | fake_redis | 连接 / decode_responses / 2s 超时 / 降级 / shutdown |
| `test_permission_cache_redis.py` (4) | 1 mock | fake_redis | hit / miss 60s TTL / 跨 worker 共享 / 降级走 PG |
| `test_token_cache.py` (6) | 1 mock | fake_redis | hit / miss / 6h sliding 续期 / sha256 hash / invalidate / 降级 |
| `test_rate_limiter.py` (6) | 1 mock | fake_redis | 第 5 次返 True / 第 6 次返 False / 15min 后重置 / reset 1h / Redis 挂 fail-open / 多 IP 隔离 |
| `test_mem0_ready.py` (3) | 1 mock | fake_redis | mark + is_ready / 1h TTL / 跨 worker 模拟 |
| `test_dify_query_cache.py` (4) | 1 mock | fake_redis | hit / miss / 10min TTL / sha256 撞 key / 降级 |
| `test_embed_cache.py` (4) | 1 mock | fake_redis | hit / miss / 7d TTL / base64 编解码 / 降级 |

**总测试**: 32 个新增 (CLAUDE.md TDD 流程, 模式 1 mock + fakeredis).

---

## 8. 运维查询 (docs/operations/redis.md 落地)

### 8.1 实时 key 列表 + 内存占用

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning KEYS "rag:*" | head -20
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO memory
```

### 8.2 命中率监控 (keyspace_hits / keyspace_misses)

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO stats | grep keyspace
# keyspace_hits:12345 keyspace_misses:678
# hit_rate = 12345 / (12345 + 678) = 94.8%
```

### 8.3 TTL 倒计时 (大批 key 即将过期)

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:embed:*" | \
  xargs -I {} redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL {}
```

### 8.4 按域分桶 key 数

```bash
for prefix in perm auth rl mem0 dify embed; do
  count=$(redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:${prefix}:*" | wc -l)
  echo "$prefix: $count"
done
```

### 8.5 手动失效某 dataset 缓存 (临时, 不在 spec 范围)

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:dify:q:*" | \
  xargs redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL
```

### 8.6 满内存触发 LRU 监控

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO memory | grep -E "used_memory_human|maxmemory_human"
```

**Redis maxmemory 已配 512mb + allkeys-lru (docker-compose.yml:88-89), 满时自动淘汰, 不需要人工干预.**

---

## 9. 不在本期范围 (YAGNI 明确)

- ❌ **arq 任务队列** (Phase 3, 单独 spec, 涉及 worker 部署 + 监控)
- ❌ **Redis pub/sub 跨 worker 事件广播** (Mem0 用 ready 标记足够, 不需要订阅)
- ❌ **Dify query 主动 cache invalidation on ingest** (10min 纯 TTL, 业务可接受)
- ❌ **Redis Cluster / Sentinel** (单 Redis 足够, 512mb + LRU 撑得住当前量)
- ❌ **Lua 脚本** (本项目没原子操作刚需, INCR + EXPIRE NX pipeline 已够)
- ❌ **限流按 user_id** (按 IP 足够, 不双维度)
- ❌ **embedding 主动失效** (7d TTL + LRU 滚动, 不需要按 dataset 踢)
- ❌ **Redis Sentinel 高可用** (单实例 + health check 已够; 后期 K8s 多 pod 再加)

---

## 10. 风险 + 决策记录

| 风险 | 缓解 |
|---|---|
| Redis 挂 → 服务不可用 | fail-open 全降级原路径, facade 层 log CRITICAL 通知 on-call |
| Redis 满 → 内存撑爆 | maxmemory-policy allkeys-lru 已配 (docker-compose.yml:89) |
| Redis AOF 写盘慢 | appendfsync everysec (docker-compose.yml:86), 最多丢 1s 数据 |
| fakeredis 不真测 Redis 行为 | 关键路径 (TTL 过期 / 限流计数 / LRU) 1-2 个集成测 (CI 跑真 Redis) 兜底, 本期不做 |
| 多 worker 启动 race (Mem0 warmup) | Mem0Ready marker 防重复构造, fire-and-forget 不阻塞 |
| Embedding 缓存 key 撞 | sha256[:16] = 16 字节, 撞概率 ~1/2^64 实际忽略 |
| Token 缓存被窃 → token 泄露 | 存 sha256(token)[:32] 不存原值, Redis dump 也反推不出 |
| TTL 失效期间 token 失效 | 6h sliding, 高频用户无感, 低频用户最多 6h 后再走 1 次 PG |
| 限流误伤 (NAT 出口 IP 多人共享) | 5 次/15min 余量大, 真误伤可通过 env 调阈值 |

**决策记录**:
- ✅ 范围: Phase 1 + Phase 2 (7 任务, 7 天)
- ✅ Auth token: 6h sliding TTL
- ✅ 限流: 仅 IP (login 5/15min, reset 3/1h)
- ✅ Mem0: Redis ready 标记 + 进程内实例
- ✅ Dify query: 10min 纯 TTL
- ✅ 降级: 全 fail-open
- ✅ Key: 统一 `rag:` 前缀
- ✅ 测试: 模式 1 mock + fakeredis

---

## 11. 验收清单

**功能验收**:
- [ ] `core/redis_client.py` facade 实现, 4 个 safe_* 函数
- [ ] PermissionCache 改 Redis, 60s TTL, 跨 worker 一致
- [ ] Auth token 缓存 6h sliding, hot path 0 PG
- [ ] 限流: login 5/15min, reset 3/1h, IP 维度
- [ ] Mem0 ready 标记, 防多 worker race
- [ ] Dify query 缓存 10min TTL
- [ ] Embedding 向量缓存 7d TTL, base64 紧凑

**质量验收**:
- [ ] 32 测试全绿 (模式 1 mock + fakeredis)
- [ ] ruff + pyright 0 error
- [ ] 现有 250+ 测试 0 break
- [ ] 手动: docker compose up + 多 worker 启动 + 验证 PermissionCache 跨 worker 一致

**文档验收**:
- [ ] `docs/operations/redis.md` (运维查询 + 监控)
- [ ] `packages/service/CLAUDE.md` 增补 "Redis 使用约定"
- [ ] `docs/superpowers/handoffs/2026-06-18-redis-integration.md` (handoff)

**集成验收**:
- [ ] Docker compose up + alembic upgrade 0 改动
- [ ] 模拟 Redis 挂 (docker stop redis) → 服务不挂, 只性能降级
- [ ] 多 worker (uvicorn --workers 4) 启动 → PermissionCache 一致

---

**Spec OK 吗? 你 review 完确认 → 写 plan → subagent 实施.**
