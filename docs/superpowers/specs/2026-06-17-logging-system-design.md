# RAG 日志系统 Design Spec (2026-06-17)

> **For agentic workers:** 后续 plan / 实施按本 spec 落地, 不偏离. 改 spec 需新 brainstorm + commit.

**Goal**: 把当前 8 个模块的 stdlib `logging` 全量切到 loguru, 加 Postgres 持久化 (3 表 + 月分区), 接 FastAPI 全局异常 handler, 加 PII scrub, 加 25 个危险操作 audit hook, 预留 Grafana / Sentry 升级路径. 0 dev DB 阻塞 (enqueue 后台线程).

**Architecture**: loguru 当 facade + InterceptHandler 桥接 stdlib (SQLAlchemy / uvicorn / boto3 自动接管). 3 个独立 Postgres 表 (app_logs / error_logs / audit_logs), 月分区 + 不可变 trigger. FastAPI 中间件注入 request_id + user_id 到 contextvars. Audit 用 `@audited` decorator 包 endpoint, 自动写 audit_logs (成功 + 失败都记).

**Tech Stack**: loguru 0.7+, FastAPI 中间件, SQLAlchemy 2.0 异步 ORM, Alembic, pytest 9.0+ (CLAUDE.md 4 模式: 1 mock + 2 db_session).

---

## 1. 用户决策记录 (2026-06-17 brainstorming)

| 决策点 | 用户选择 | 备注 |
|---|---|---|
| Scope | 完整方案 (P0+P1+P2+P3 全做) | 不是 MVP |
| Loguru vs stdlib | 全量切 loguru | 8 个模块逐个替换, InterceptHandler 桥接 |
| Sentry | 暂不用, 考虑以后升级 | spec 留 hook + env 切换, 不接 |
| 自建日志 UI | 不做 | 后期接 Grafana (1 天) |
| Supabase Studio | 不用 | 项目不用 Supabase |
| Audit log scope | P0+P1+P2+P3 全覆盖 | ~25 个 hook 点 |
| 4 工具调研写入 spec | 是 | spec §12 详细对比 + Grafana 接入路线图 |
| Grafana hook 预留 | 是 | env `GRAFANA_ENABLED=false`, 文档说明 |

**Why**: 用户 2026-06-17 主动要求接入日志系统. 没有日志经验, 要 2026 行业最佳实践. 重视危险操作审计 + 错误不能静默.

---

## 2. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│ FastAPI Request Lifecycle                                     │
│                                                                │
│  RequestIDMiddleware (生成 UUID4 → contextvars)               │
│       ↓                                                        │
│  Route Handler                                                 │
│       ↓ 业务日志: logger.info("...", user_id=X)               │
│       ↓ 异常: 抛 → FastAPI Global Exception Handler            │
│       ↓ 危险操作: @audited("account.delete") decorator        │
│       ↓                                                        │
│  Response                                                      │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ loguru (facade)                                                │
│  - logger.bind(request_id=, user_id=) 自动注入 contextvars     │
│  - serialize=True → JSON 输出 (12-factor)                      │
│  - enqueue=True → 后台线程, 非阻塞                              │
│  - 3 个 sink:                                                  │
│    1. stdout (JSON 或 ConsoleRenderer 彩色)                     │
│    2. PostgresAppLogSink → app_logs 表 (enqueue)               │
│    3. PostgresErrorLogSink → error_logs 表 (5xx 才写)          │
│    4. AuditSink → audit_logs 表 (@audited decorator 触发)      │
│  - InterceptHandler 桥接 stdlib (SQLAlchemy / uvicorn / boto3) │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ Postgres (3 表 + 月分区 + 不可变 trigger)                      │
│  - app_logs: INFO/WARN/ERROR, 7-30 天, BRIN + B-tree + GIN    │
│  - error_logs: 5xx 异常 + stacktrace, 90 天, 更长保留           │
│  - audit_logs: P0+P1+P2+P3 危险操作, 1-7 年, APPEND-ONLY       │
└──────────────────────────────────────────────────────────────┘
```

**3 大设计原则**:
1. **Facade 模式**: loguru 当统一入口, stdlib 通过 InterceptHandler 转发 (SQLAlchemy / uvicorn / boto3 第三方 log 自动接管)
2. **永不阻塞请求**: 所有 PG 写走 enqueue=True 后台线程; 队列满 → drop newest + 写 stderr 兜底
3. **Audit 独立流**: 跟 app/error log 完全分开 schema + retention + access control; append-only trigger 拒绝 UPDATE/DELETE

---

## 3. 文件结构 (新增 + 改)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/service/src/core/__init__.py` | 5 | 标记 core 子包 |
| `packages/service/src/core/logging.py` | ~150 | loguru 配置 + InterceptHandler + sinks + PII scrub |
| `packages/service/src/core/logging_context.py` | ~40 | contextvars: request_id / user_id |
| `packages/service/src/core/errors.py` | ~80 | FastAPI global exception handlers |
| `packages/service/src/core/middleware.py` | ~60 | RequestIDMiddleware + bind user_id |
| `packages/service/src/core/audit.py` | ~120 | AuditContext + @audited decorator + persist |
| `packages/service/src/db/models/app_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/db/models/error_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/db/models/audit_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py` | ~120 | alembic: 3 表 + 月分区 + 索引 + trigger |
| `packages/service/tests/core/test_logging.py` | ~120 | 5-6 测试: loguru config + JSON + PII scrub + InterceptHandler |
| `packages/service/tests/core/test_middleware.py` | ~80 | 3 测试: RequestID 传播 |
| `packages/service/tests/core/test_audit.py` | ~120 | 5 测试: @audited + 异常时 failure |
| `packages/service/tests/core/test_errors.py` | ~100 | 4-5 测试: 4xx warn + 5xx error + scrub |
| `packages/service/tests/db/test_app_log.py` | ~60 | 3 测试: INSERT 行为 (db_session) |
| `packages/service/tests/db/test_audit_log.py` | ~80 | 3 测试: immutability trigger (db_session) |
| `docs/superpowers/specs/2026-06-17-logging-system-design.md` | 本文件 | spec |
| `docs/superpowers/plans/2026-06-17-logging-system.md` | 待写 | plan |
| `docs/operations/observability.md` | ~150 | 运维查询 SQL (5-10 条) + Grafana 接入路线图 |

### 改 (实际项目结构对齐)

| 文件 | 改动 |
|---|---|
| `packages/service/src/main.py` | `configure_logging()` + `install_error_handlers(app)` + 中间件挂载 |
| `packages/service/src/auth/account_settings_router.py` | 加 `@audited("email.change")`, `@audited("password.change")`, `@audited("account.delete")`, `@audited("avatar.delete")`, `@audited("deletion.cancel")` 等 5 hook — auth 重构后 email/password/deletion 操作从 auth_account_router.py 迁移至此 |
| `packages/service/src/auth/auth_account_router.py` | 加 `@audited("password.reset")` (POST /api/account/reset-password, 忘记密码重置 — 跟 account_settings_router 的 PATCH /password 不同) |
| `packages/service/src/auth/auth_admin_router.py` | 加 `@audited("role.change")`, `@audited("account.disable")`, `@audited("account.enable")` 等 3 hook |
| `packages/service/src/auth/auth_invite_router.py` | 加 `@audited("user.invite")` |
| `packages/service/src/kg/router.py` | 加 `@audited("kg_node.delete")`, `@audited("kg_relation.delete")` 等 2 hook |
| `packages/service/src/eval/router.py` | 加 `@audited("evaluation.run")`, `@audited("evaluation.cancel")` (无 DELETE 端点, 原 spec evaluation.delete 改为 cancel) |
| `packages/service/src/memory/router.py` | 加 `@audited("memory.purge_all")`, `@audited("memory.delete")` 等 2 hook |
| `packages/service/src/chat_share/router.py` | stdlib logger → loguru |
| `packages/service/src/ingest/api.py` | 加 `@audited("files.bulk_download")` (GET /tasks/{id}/download) — 无 DELETE 端点, 原 spec knowledge.delete/dataset.delete/task.cancel/data.export 端点不存在, 跳过 |
| `packages/service/src/ingest/pipeline.py` | stdlib logger → loguru |
| `packages/service/src/chat_share/router.py` | stdlib logger → loguru |
| `packages/service/src/chat_share/service.py` | stdlib logger → loguru |
| `packages/service/src/eval/llama_eval.py` | stdlib logger → loguru |
| `packages/service/src/memory/mem0_client.py` | stdlib logger → loguru |
| `packages/service/src/memory/router.py` | stdlib logger → loguru |
| `packages/service/src/memory/service.py` | stdlib logger → loguru |
| `packages/service/src/storage/object_store.py` | stdlib logger → loguru |
| `packages/service/src/health/checks.py` | stdlib logger → loguru (实际代码无 logger, 跳过) |
| `packages/service/src/auth/account_settings_service.py` | stdlib logger → loguru (新增: auth 重构后分离出的 service) |
| `packages/service/src/scheduler/deletion.py` | stdlib logger → loguru (新增: 定时清理任务) |
| `packages/service/src/product_decoders/app.py` | stdlib `_log` → loguru (工厂文件, 含 `_sa_exception_handler`) |
| `packages/service/src/api/routes.py` | 加 `@audited("admin.access")` 中间件 + `@audited("audit.read_self")` 端点 |
| `packages/service/src/auth/router.py` | 加 `@audited("api_key.create")`, `@audited("api_key.revoke")` 等 2 hook |
| `packages/service/.env.example` | 加 `LOG_LEVEL` / `LOG_JSON` / `LOG_TO_DB` / `GRAFANA_ENABLED` / `SENTRY_ENABLED` / `LOKI_ENABLED` |
| `packages/service/pyproject.toml` | 加 `loguru>=0.7,<1.0` |
| `packages/service/CLAUDE.md` | 增补 "日志使用约定" 章节 |

**注**: 实施时 implementer subagent 必须先 `ls src/` 验证实际文件结构, 缺文件就 grep 找对应路由 (例如 `grep -rn "@router.delete|@router.post|@router.patch" src/`), 调整 hook 落点. spec 列的是估计路径, 真实路径以代码为准. **(2026-06-18 sync: hook 表已按实际代码重对齐 — account_settings_router.py 承接 email/password/deletion, ingest/api.py 只有 GET/POST 无 DELETE, eval/router.py 无 DELETE 端点, memory/router.py 多 DELETE /memory/{id})**

---

## 4. DB Schema (3 表 + 月分区)

### 4.1 app_logs (应用生命周期, 7-30 天)

```sql
CREATE TABLE app_logs (
    id          BIGSERIAL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level       TEXT NOT NULL CHECK (level IN ('DEBUG','INFO','WARNING','ERROR','CRITICAL')),
    logger      TEXT NOT NULL,
    message     TEXT NOT NULL,
    request_id  UUID,
    user_id     BIGINT,
    trace_id    CHAR(32),
    context     JSONB NOT NULL DEFAULT '{}'::jsonb
) PARTITION BY RANGE (ts);

-- 当月 + 下月分区 (alembic migration 自动创建, cron 续建)
CREATE TABLE app_logs_2026_06 PARTITION OF app_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE app_logs_2026_07 PARTITION OF app_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

-- 索引 (BRIN 时序 + B-tree 用户 + GIN context + partial 错误)
CREATE INDEX idx_app_logs_ts_brin ON app_logs USING BRIN (ts);
CREATE INDEX idx_app_logs_user_ts ON app_logs (user_id, ts DESC);
CREATE INDEX idx_app_logs_context_gin ON app_logs USING GIN (context);
CREATE INDEX idx_app_logs_errors ON app_logs (ts DESC) WHERE level IN ('ERROR', 'CRITICAL');
```

### 4.2 error_logs (5xx 异常 + stacktrace, 90 天)

```sql
CREATE TABLE error_logs (
    id              BIGSERIAL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level           TEXT NOT NULL,
    exception_type  TEXT NOT NULL,
    exception_msg   TEXT NOT NULL,
    stacktrace      TEXT,
    request_id      UUID,
    user_id         BIGINT,
    path            TEXT,
    method          TEXT,
    status_code     INT,
    context         JSONB NOT NULL DEFAULT '{}'::jsonb
) PARTITION BY RANGE (ts);

CREATE TABLE error_logs_2026_06 PARTITION OF error_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_error_logs_ts_brin ON error_logs USING BRIN (ts);
CREATE INDEX idx_error_logs_user_ts ON error_logs (user_id, ts DESC);
CREATE INDEX idx_error_logs_exception_type ON error_logs (exception_type);
```

### 4.3 audit_logs (危险操作, 1-7 年, APPEND-ONLY)

```sql
CREATE TABLE audit_logs (
    id          BIGSERIAL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id    BIGINT NOT NULL,
    actor_type  TEXT NOT NULL DEFAULT 'user',  -- user / service / api_key
    action      TEXT NOT NULL,                 -- 'account.delete' / 'password.reset'
    target_type TEXT NOT NULL,                 -- 'user' / 'dataset' / 'kg_node'
    target_id   TEXT NOT NULL,
    ip          INET,
    user_agent  TEXT,
    request_id  UUID,
    result      TEXT NOT NULL DEFAULT 'success', -- success / failure
    before      JSONB,
    after       JSONB,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
) PARTITION BY RANGE (ts);

CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- 索引
CREATE INDEX idx_audit_logs_ts_brin ON audit_logs USING BRIN (ts);
CREATE INDEX idx_audit_logs_actor_ts ON audit_logs (actor_id, ts DESC);
CREATE INDEX idx_audit_logs_action_ts ON audit_logs (action, ts DESC);
CREATE INDEX idx_audit_logs_target ON audit_logs (target_type, target_id);
CREATE INDEX idx_audit_logs_metadata_gin ON audit_logs USING GIN (metadata);

-- 不可变 trigger (append-only)
CREATE OR REPLACE FUNCTION reject_audit_modify() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only (no UPDATE/DELETE allowed)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();
CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();

REVOKE UPDATE, DELETE ON audit_logs FROM app_user;
```

### 4.4 保留策略

- **app_logs**: 7-30 天热, drop partition (O(1))
- **error_logs**: 90 天热, 导出 Parquet 到 MinIO (`cold-logs/` prefix) 后 drop
- **audit_logs**: 1 年热, 7 年冷 (MinIO WORM bucket, 合规用)

Cron job (后期接, 不在 spec 范围): `packages/service/scripts/log_partition_cron.py` 每天 0:00 续建下月 + drop 过期.

---

## 5. loguru 核心配置 (`src/core/logging.py`)

```python
"""loguru 全局配置 (2026-06-17 logging spec)

loguru 当 facade, InterceptHandler 桥接 stdlib. 后台线程 enqueue=True 写 PG.
"""

from __future__ import annotations

import json
import os
import sys
import time
import logging
from datetime import timezone
from queue import Queue
from typing import Any
from loguru import logger as _loguru
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB as Json
from .logging_context import current_request_id, current_user_id


# ============== PII Scrubber ==============

# case-insensitive 黑名单
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "api_key", "apikey",
    "secret", "client_secret",
    "authorization", "cookie", "set-cookie",
    "ssn", "credit_card", "card_number", "cvv",
    "private_key", "privatekey",
})


def _scrub(data: Any) -> Any:
    """递归 scrub 已知敏感字段. dict / list 嵌套处理."""
    if isinstance(data, dict):
        return {
            k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else _scrub(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_scrub(item) for item in data]
    return data


# ============== InterceptHandler 桥接 stdlib ==============


class InterceptHandler(logging.Handler):
    """stdlib log → loguru. SQLAlchemy / uvicorn / boto3 / httpx 第三方自动接管."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        _loguru.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage(),
        )


# ============== PG Sinks ==============


# 队列满 → drop newest + stderr 兜底 + CRITICAL 告警
LOG_QUEUE_MAXSIZE = 10_000


def _pg_sink_app(message) -> None:
    """app_logs sink (后台线程)."""
    rec = message.record
    try:
        from src.db.session import session_scope
        with session_scope() as s:
            s.execute(text(
                "INSERT INTO app_logs (ts, level, logger, message, request_id, user_id, trace_id, context) "
                "VALUES (:ts, :level, :logger, :message, :request_id, :user_id, :trace_id, :context)"
            ), {
                "ts": rec["time"].astimezone(timezone.utc),
                "level": rec["level"].name,
                "logger": rec["name"],
                "message": rec["message"],
                "request_id": current_request_id.get(),
                "user_id": current_user_id.get(),
                "trace_id": rec["extra"].get("trace_id"),
                "context": Json(_scrub(rec["extra"])),
            })
    except Exception as e:
        print(f"[logging] app_logs write failed: {e}", file=sys.stderr, flush=True)


def _error_sink_sync(level: str, exc: Exception, request) -> None:
    """error_logs sink (同步, 5xx 全局 handler 调)."""
    try:
        from src.db.session import session_scope
        import traceback
        with session_scope() as s:
            s.execute(text(
                "INSERT INTO error_logs (ts, level, exception_type, exception_msg, stacktrace, "
                "request_id, user_id, path, method, status_code, context) "
                "VALUES (:ts, :level, :type, :msg, :trace, :rid, :uid, :path, :method, 500, :ctx)"
            ), {
                "ts": time.time(),
                "level": level,
                "type": type(exc).__name__,
                "msg": str(exc)[:1000],
                "trace": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:5000],
                "rid": current_request_id.get(),
                "uid": current_user_id.get(),
                "path": request.url.path if request else None,
                "method": request.method if request else None,
                "ctx": Json(_scrub({})),
            })
    except Exception as e:
        _loguru.critical(f"error_logs write failed: {e}")


# ============== 主配置 ==============


def configure_logging(
    json_console: bool = False,
    write_to_db: bool = True,
    level: str = "INFO",
) -> None:
    """main.py 启动时调一次. 配置 loguru + 接管 stdlib.

    Args:
        json_console: True → JSON 输出 (生产), False → 彩色 (dev)
        write_to_db: True → 写 app_logs 表
        level: 全局最低 log 级别
    """
    # 清默认 + 接管 stdlib
    _loguru.remove()
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error",
                 "sqlalchemy.engine", "boto3", "botocore", "httpx"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    # 控制台 sink
    if json_console:
        _loguru.add(sys.stdout, level=level, serialize=True, enqueue=True,
                    backtrace=True, diagnose=False)
    else:
        _loguru.add(sys.stderr, level=level, colorize=True, enqueue=True,
                    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
                           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                           "<level>{message}</level>",
                    backtrace=True, diagnose=False)

    # DB sink (enqueue=True 后台线程, 永不阻塞请求)
    if write_to_db:
        _loguru.add(_pg_sink_app, level=level, enqueue=True,
                    backtrace=True, diagnose=False)

    # (2026-06-17 spec §12) Grafana hook 预留位置
    grafana_enabled = os.getenv("GRAFANA_ENABLED", "false").lower() == "true"
    if grafana_enabled:
        # TODO: 后期接入. Grafana 直接连 RAG_DB_URL 即可, 不需要 DSN.
        # 1. 装 Grafana (docker / 自部署)
        # 2. Add datasource → PostgreSQL, 配 RAG_DB_URL
        # 3. Import dashboard JSON (本 spec 后期提供)
        pass

    _loguru.info(f"logging configured: level={level} json={json_console} db={write_to_db}")


def shutdown_logging() -> None:
    """FastAPI shutdown 钩子. 排空 enqueue 队列."""
    _loguru.complete()
```

---

## 6. RequestID Middleware (`src/core/middleware.py`)

```python
"""RequestID + user_id 注入 contextvars (2026-06-17 logging spec)"""

from __future__ import annotations

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from .logging_context import current_request_id, current_user_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """每个请求:
    1. 读 X-Request-ID header, 没则生成 UUID4
    2. 写入 contextvars (current_request_id / current_user_id)
    3. 响应回写 X-Request-ID header
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token_req = current_request_id.set(request_id)
        token_user = current_user_id.set(None)  # auth 后再覆盖
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            current_request_id.reset(token_req)
            current_user_id.reset(token_user)


def bind_user_id(user_id: int | None) -> None:
    """auth 解析后调. 把 user_id 注入 contextvars."""
    current_user_id.set(user_id)
```

```python
# src/core/logging_context.py
"""contextvars 持有请求级元数据 (2026-06-17)"""

from contextvars import ContextVar

current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
```

---

## 7. 全局异常 Handler (`src/core/errors.py`)

```python
"""FastAPI global exception handlers (2026-06-17)

4xx → WARNING (app_logs only)
5xx → ERROR (app_logs + error_logs)
永远不返 stacktrace 给前端 (避免代码泄露)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from .logging import _scrub, _error_sink_sync


def install_error_handlers(app: FastAPI) -> None:
    """main.py create_app() 里调一次."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        # 4xx → WARNING, 不进 error_logs
        logger.warning(
            "http_exception status={} path={} detail={}",
            exc.status_code, request.url.path, exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        logger.warning(
            "validation_error path={} errors={}",
            request.url.path, _scrub(exc.errors()),
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_exc(request: Request, exc: Exception):
        # 5xx → ERROR + error_logs
        logger.opt(exception=True).error(
            "unhandled_exception path={} method={}",
            request.url.path, request.method,
        )
        try:
            _error_sink_sync(level="ERROR", exc=exc, request=request)
        except Exception as write_exc:
            logger.critical(f"error_logs write failed: {write_exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

---

## 8. Audit Decorator (`src/core/audit.py`)

```python
"""@audited decorator + AuditContext (2026-06-17 logging spec)

endpoint 加 @audited("account.delete", target_type="user"), 在函数体里
audit.set(target_id=..., before={...}, after={...}) 即可. decorator 在
finally 块统一写 audit_logs (成功 + 失败都记).
"""

from __future__ import annotations

from functools import wraps
from fastapi import Request
from loguru import logger
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB as Json
from .logging_context import current_request_id
from .logging import _scrub


class AuditContext:
    """请求级 audit 上下文. decorator 在 endpoint 前后填充."""

    def __init__(self, action: str, target_type: str):
        self.action = action
        self.target_type = target_type
        self.target_id: str | None = None
        self.before: dict | None = None
        self.after: dict | None = None
        self.metadata: dict = {}

    def set(
        self,
        *,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
        **metadata,
    ) -> None:
        self.target_id = target_id
        self.before = before
        self.after = after
        self.metadata.update(metadata)


def audited(action: str, target_type: str):
    """Decorator: 包装 endpoint, 成功 / 失败都写 audit_logs.

    Usage:
        @router.delete("/account")
        @audited("account.delete", target_type="user")
        async def delete_account(request: Request, current_user = Depends(...), audit: AuditContext = Depends(...)):
            audit.set(target_id=str(current_user.id), before={"email": current_user.email})
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None
            )
            user = kwargs.get("current_user") or next(
                (a for a in args if hasattr(a, "id") and hasattr(a, "email")), None
            )
            ctx = AuditContext(action=action, target_type=target_type)
            if request is not None:
                request.state.audit_ctx = ctx

            result = "success"
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                result = "failure"
                ctx.metadata["error"] = repr(exc)[:500]
                raise
            finally:
                _persist_audit(request=request, user=user, ctx=ctx, result=result)
        return wrapper
    return decorator


def _persist_audit(request, user, ctx: AuditContext, result: str) -> None:
    """finally 块统一写 audit_logs (enqueue 后台线程)."""
    try:
        from src.db.session import session_scope
        with session_scope() as s:
            s.execute(text(
                "INSERT INTO audit_logs (actor_id, actor_type, action, target_type, target_id, "
                "ip, user_agent, request_id, result, before, after, metadata) "
                "VALUES (:actor_id, 'user', :action, :target_type, :target_id, "
                ":ip, :ua, :request_id, :result, :before, :after, :metadata)"
            ), {
                "actor_id": getattr(user, "id", 0) or 0,
                "action": ctx.action,
                "target_type": ctx.target_type,
                "target_id": ctx.target_id or "",
                "ip": request.client.host if request and request.client else None,
                "ua": (request.headers.get("user-agent", "")[:500] if request else ""),
                "request_id": current_request_id.get(),
                "result": result,
                "before": Json(_scrub(ctx.before)) if ctx.before else None,
                "after": Json(_scrub(ctx.after)) if ctx.after else None,
                "metadata": Json(_scrub(ctx.metadata)),
            })
    except Exception as e:
        logger.critical(f"audit_logs 写入失败 action={ctx.action} target={ctx.target_id}: {e}")
```

---

## 9. Audit Hook 覆盖 (~25 点, 2026-06-18 sync 按实际代码重对齐)

| 优先级 | 实际端点 | action | target_type | 实际文件 | 函数 | 备注 |
|---|---|---|---|---|---|---|
| **P0 账户安全** | PATCH /api/account/password | `password.change` | user | `src/auth/account_settings_router.py` | `patch_password` | 登录后改密码, auth 重构后落点 |
| | POST /api/account/reset-password | `password.reset` | user | `src/auth/auth_account_router.py` | `reset_password` | 忘记密码重置, 仍在原文件 |
| | PATCH /api/account/email | `email.change` | user | `src/auth/account_settings_router.py` | `patch_email` | auth 重构后落点 |
| | POST /api/account/deletion | `account.delete` | user | `src/auth/account_settings_router.py` | `post_deletion` | 软删(宽限期), 非直接 DELETE |
| | DELETE /api/account/deletion | `deletion.cancel` | user | `src/auth/account_settings_router.py` | `delete_deletion` | **新增**: 取消删除申请 |
| | DELETE /api/account/avatar | `avatar.delete` | avatar | `src/auth/account_settings_router.py` | `delete_avatar` | **新增**: 删除头像 |
| | POST /api/auth/api-keys | `api_key.create` | api_key | `src/auth/router.py` | `create_api_key` | |
| | ~~DELETE /api/auth/api-keys/{id}~~ | `api_key.revoke` | api_key | `src/auth/router.py` | `revoke_api_key` | 需确认实际端点路径 |
| | PATCH /api/admin/users/{id} | `role.change` | user | `src/auth/auth_admin_router.py` | `patch_user` | 实际是 PATCH, 含 role 变更 |
| | ~~POST /admin/users/{id}/disable~~ | `account.disable` | user | `src/auth/auth_admin_router.py` | 待确认 | 需 grep 确认 disable/enable 端点 |
| | ~~POST /admin/users/{id}/enable~~ | `account.enable` | user | `src/auth/auth_admin_router.py` | 待确认 | |
| **P1 数据操作** | ~~DELETE /kg/nodes/{id}~~ | `kg_node.delete` | kg_node | `src/kg/router.py` | 需确认 | kg 目前只有 POST/GET |
| | ~~DELETE /kg/relations/{id}~~ | `kg_relation.delete` | kg_relation | `src/kg/router.py` | 需确认 | |
| | ~~POST /evaluate/runs~~ | `evaluation.run` | evaluation | `src/eval/router.py` | `upload_run` | POST /runs 创建评估 |
| | POST /evaluate/runs/{run_id}/cancel | `evaluation.cancel` | evaluation | `src/eval/router.py` | `cancel_run` | **改为 cancel**, 无 DELETE |
| | DELETE /api/memory | `memory.purge_all` | memory | `src/memory/router.py` | `delete_all_memories` | |
| | DELETE /api/memory/{id} | `memory.delete` | memory | `src/memory/router.py` | `delete_memory` | **新增**: 单条删除 |
| | GET /api/ingest/tasks/{id}/download | `files.bulk_download` | file | `src/ingest/api.py` | `download_zip` | GET, 非 DELETE |
| **P2 资源访问** | GET /admin/* (任一) | `admin.access` | admin_route | `src/api/routes.py` | 中间件 | 需实现中间件 |
| | ~~GET /audit-logs~~ | `audit.read_self` | audit | `src/api/routes.py` | 新端点 | 需实现新端点 |
| **P3 业务** | POST /api/invites | `user.invite` | user | `src/auth/auth_invite_router.py` | `create_invite` | |
| | ~~POST /evaluate/runs~ (run) | `evaluation.run` | evaluation | `src/eval/router.py` | `upload_run` | 同 P1 |
| | POST /models/deploy | `model.deploy` | model | 未来 | | 未来扩展, 本期不接 |
| | PATCH /config | `config.change` | config | `src/api/routes.py` 或新 | | 本期不接 |
| | ~~POST /permissions/adjust~~ | `permission.adjust` | user | `src/auth/auth_admin_router.py` | | 本期不接 |

**本表实施注**:
1. ~~删除线~~: 端点不存在 — implementer 实施时 `grep` 确认, 不存在的端点 skip
2. **新增**: 用户 2026-06-18 确认补的 hook
3. P0 中 disable/enable 端点及其它待确认落点, implementer 实施时 grep 找实际路由, 不在表里的按实际补
4. 表中用 ~~端点路径~~ 表示原 spec 估计路径但在实际代码不存在的端点
5. 每个端点加 1 行 `@audited("...", target_type="...")`, endpoint body 调 `audit.set(target_id=..., before={...}, after={...})`

**实施注**: implementer 实施前必须 `grep -rn "@router.delete\|@router.post\|@router.patch" packages/service/src/` 列所有路由, 跟本表交叉比对, 代码优先, spec 次之.

## 10. PII Scrubber 黑名单

```python
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "api_key", "apikey",
    "secret", "client_secret",
    "authorization", "cookie", "set-cookie",
    "ssn", "credit_card", "card_number", "cvv",
    "private_key", "privatekey",
})
```

**Scrub 范围**:
- `app_logs.context` (JSONB)
- `error_logs.context` (JSONB)
- `audit_logs.before / after / metadata` (JSONB)
- 控制台输出 (DEBUG 模式)

**允许记录 (审计需要)**:
- `user_id` / `email` / `ip` / `request_id`
- `request_body`: 默认不记 (PII 太多), 只在 DEBUG + 开发环境

---

## 11. 测试策略 (CLAUDE.md 4 模式)

| 文件 | 模式 | Fixture | 覆盖 |
|---|---|---|---|
| `tests/core/test_logging.py` | 1 mock | 0 PG | loguru config + JSON shape + PII scrub + InterceptHandler |
| `tests/core/test_middleware.py` | 1 mock | 0 PG | RequestID 生成 + propagation + header 回写 |
| `tests/core/test_audit.py` | 1 mock | mock session_scope | @audited 写入 (success/failure) + exception 时 metadata.error |
| `tests/core/test_errors.py` | 1 mock | 0 PG | 4xx warn + 5xx error + PII scrub + 不返 stacktrace |
| `tests/db/test_app_log.py` | 2 db_session | 集成 | INSERT 行为 + 分区路由 |
| `tests/db/test_audit_log.py` | 2 db_session | 集成 | INSERT + immutability trigger (UPDATE/DELETE 抛) |

**Mock 关键点**:
- 测试不真连 PG, `session_scope()` 用 `MagicMock()` 注入
- 测试不启动 loguru 后台线程 (enqueue=False)
- 测试 PII scrub: 传 `password="secret"` → 验证输出 `"***REDACTED***"`

**总测试数**: ~25 个新增 (CLAUDE.md TDD 流程)

---

## 12. 运维查询 SQL 示例 (`docs/operations/observability.md`)

### 12.1 最近 1 小时 ERROR/WARNING

```sql
SELECT ts, level, logger, message, request_id, user_id
FROM app_logs
WHERE ts > NOW() - INTERVAL '1 hour'
  AND level IN ('WARNING', 'ERROR', 'CRITICAL')
ORDER BY ts DESC
LIMIT 100;
```

### 12.2 某用户最近操作

```sql
SELECT ts, level, message, request_id
FROM app_logs
WHERE user_id = $1
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 200;
```

### 12.3 危险操作审计 (最近 30 天, 按 action 分桶)

```sql
SELECT action, COUNT(*) AS cnt, MAX(ts) AS last_at
FROM audit_logs
WHERE ts > NOW() - INTERVAL '30 days'
GROUP BY action
ORDER BY cnt DESC;
```

### 12.4 某用户的 audit 轨迹

```sql
SELECT ts, action, target_type, target_id, result, ip
FROM audit_logs
WHERE actor_id = $1
ORDER BY ts DESC
LIMIT 100;
```

### 12.5 失败的危险操作 (5xx 异常触发的 audit failure)

```sql
SELECT ts, actor_id, action, target_id, metadata->'error' AS error
FROM audit_logs
WHERE result = 'failure'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC;
```

### 12.6 按小时分桶 ERROR 数 (找异常高峰)

```sql
SELECT date_trunc('hour', ts) AS hour, COUNT(*) AS err_cnt
FROM app_logs
WHERE level = 'ERROR'
  AND ts > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
```

### 12.7 某异常类型最近 7 天

```sql
SELECT ts, exception_type, exception_msg, path, user_id
FROM error_logs
WHERE exception_type = 'ValueError'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 50;
```

### 12.8 GIN 索引查 context JSONB

```sql
SELECT ts, level, message
FROM app_logs
WHERE context @> '{"action": "presign_upload"}'
  AND ts > NOW() - INTERVAL '1 day'
ORDER BY ts DESC;
```

### 12.9 跨用户访问检测 (P2 hook 触发)

```sql
SELECT ts, actor_id, target_id, ip, metadata
FROM audit_logs
WHERE action = 'cross_user.read'
ORDER BY ts DESC
LIMIT 100;
```

### 12.10 删除类操作全表

```sql
SELECT ts, actor_id, action, target_id, target_type
FROM audit_logs
WHERE action LIKE '%delete%' OR action LIKE '%purge%'
ORDER BY ts DESC
LIMIT 200;
```

---

## 13. 日志生态工具对比 (Loki / Grafana / Sentry / Supabase Studio)

### 13.1 4 工具定位

| 工具 | 定位 | 解决什么问题 | 部署方式 |
|---|---|---|---|
| **Loki** | 日志聚合存储 | "我 10 个服务的日志怎么集中查?" | 自部署 (Grafana 配套) |
| **Grafana** | 可视化 / 仪表盘 | "我想看图表 / 设告警 / 拼 SQL/PromQL/LogQL 查询" | 自部署 / SaaS |
| **Sentry** | 异常追踪 + APM | "哪个 bug 影响多少用户? 出现几次? 上下文?" | SaaS / 自部署 (重) |
| **Supabase Studio** | Supabase PG 的 Web UI | "我不想装 pgAdmin, 浏览器直接看表 + 写 SQL + 编辑行" | SaaS / 自部署 |

### 13.2 项目当前 / 后期推荐

**当前** (本期 spec 实施):
- 日志库: loguru + PG 3 表
- 排错: stdout + psql / pgAdmin
- 异常告警: 暂不接, 靠 on-call 人工看 (量小)

**后期** (运维诉求增长时, 按需接入):

| 需求 | 推荐工具 | 接入成本 | 数据源 |
|---|---|---|---|
| 日志查询 UI / 仪表盘 | **Grafana + 直连 PG** | 1 天 | RAG_DB_URL (现成) |
| 日志量大 + K8s 多服务 | **Grafana + Loki** | 2-3 天 | Loki (新增) |
| 异常聚合 + 告警 + breadcrumb | **Sentry SaaS** | 1 小时 (2 行代码) | sentry-sdk[fastapi] |
| 不装 pgAdmin, 浏览器直接看表 | Supabase Studio | 不推荐 (项目不用 Supabase) | - |

### 13.3 Grafana 接入路线图 (本期预留位置)

```bash
# 1. 装 Grafana (docker compose 加一段, 或单独跑)
docker run -d -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana:latest

# 2. Web UI → Configuration → Data sources → Add → PostgreSQL
#    填: host=postgres port=5432 db=rag user=postgres password=...
#    Save & Test

# 3. Create dashboard → Import dashboard JSON
#    (本 spec 后期提供 app_logs / error_logs / audit_logs 仪表盘 JSON)
```

```python
# core/logging.py 已留位置:
def configure_logging(...):
    ...
    grafana_enabled = os.getenv("GRAFANA_ENABLED", "false").lower() == "true"
    if grafana_enabled:
        # TODO: 接入时实装. 当前留位置.
        pass
```

```bash
# .env.example 已留:
GRAFANA_ENABLED=false       # 后期接入
# GRAFANA_URL=http://localhost:3000
```

### 13.4 Sentry 接入路线图 (本期不接)

```bash
# 1. 注册 sentry.io → 创 project → 拿 DSN
# 2. 装包
uv add sentry-sdk[fastapi]

# 3. main.py 加 2 行
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1)

# 4. 全局异常 handler 加 sentry_sdk.capture_exception(exc)
```

```bash
# .env.example 留:
SENTRY_ENABLED=false       # 暂不接, 后期启用
# SENTRY_DSN=https://xxx@sentry.io/123
```

**为什么本 spec 不接**:
- 用户决策 "暂不用, 考虑以后升级" (2026-06-17 brainstorming)
- 日志量小, 异常靠 on-call 人工处理就够
- 接了会增加 1 个外部 SaaS 依赖 + 额外费用

### 13.5 Loki / Supabase Studio 结论

- **Loki**: 本期不接. 单服务 + 量小, 不需要分布式日志聚合. 后期 K8s / 多服务再考虑.
- **Supabase Studio**: 不接. 项目不用 Supabase. 跟 Grafana 功能有重叠 (都能查 PG), 但 Grafana 更通用.

---

## 14. 迁移计划 (5-7 天, 6 commits)

```
Day 1 (loguru 全量切)
├── pyproject.toml: 加 loguru>=0.7,<1.0
├── src/core/__init__.py + logging.py + logging_context.py
├── src/main.py: configure_logging() 启动调
├── 9 个 stdlib logger 模块改 loguru (chat_share × 2, eval, memory × 3, storage, account_settings_service, deletion)
    (2026-06-18 sync: 原定 8 个 + account_settings_service.py + scheduler/deletion.py; health/checks.py & ingest/pipeline.py 无 logger 跳过)
└── commit: feat(core): loguru 全量切换 + InterceptHandler 桥接 stdlib

Day 2 (Middleware + context + 测试)
├── src/core/middleware.py: RequestIDMiddleware + bind_user_id
├── src/main.py: install middleware
├── tests/core/test_logging.py (5 测试: PII scrub + JSON shape + enqueue + InterceptHandler)
└── tests/core/test_middleware.py (3 测试)
    commit: feat(core): RequestID middleware + contextvars 注入

Day 3 (DB schema + alembic + 模型)
├── src/db/models/{app_log,error_log,audit_log}.py
├── src/storage/migrations/versions/20260617_000000_create_log_tables.py
│   - CREATE TABLE × 3 + 当月 + 下月分区
│   - BRIN / B-tree / GIN / partial 索引 × 9
│   - audit_logs 不可变 trigger + REVOKE UPDATE/DELETE
├── .env.example: 加 LOG_LEVEL / LOG_JSON / LOG_TO_DB / GRAFANA_ENABLED / SENTRY_ENABLED / LOKI_ENABLED
├── tests/db/test_app_log.py (3 测试, db_session)
└── tests/db/test_audit_log.py (3 测试, immutability)
    commit: feat(db): 3 表 log schema + 月分区 + audit 不可变

Day 4 (Audit decorator + ~25 hooks, 2026-06-18 按实际代码重对齐)
├── src/core/audit.py: AuditContext + @audited + _persist_audit
├── tests/core/test_audit.py (5 测试, mock session_scope)
└── 25 个 endpoint 加 @audited (P0×8 + P1×7 + P2×5 + P3×5)
    commit: feat(audit): @audited decorator + 25 端点 hook (P0+P1+P2+P3)

Day 5 (Global error handler + PII)
├── src/core/errors.py: 4 个 exception handler
├── src/main.py: install_error_handlers(app) + shutdown_logging()
├── tests/core/test_errors.py (4-5 测试)
└── docs/operations/observability.md (运维 SQL 示例, §12 落地)
    commit: feat(core): global exception handler + PII scrub + ops doc

Day 6 (集成测试 + 文档 + CLAUDE.md 增补)
├── tests/integration/test_logging_e2e.py (端到端: 触发 4xx + 5xx + audit, 验 3 表都写入)
├── CLAUDE.md 增补 "日志使用约定" 章节
└── 跑全测试 0 break
    commit: docs + test: logging handoff + CLAUDE.md 增补
```

**总 commit**: 6 个 (1 个 spec 已 commit)
**总测试**: 25 个新增
**总行数**: 核心 ~450 + 测试 ~480 + migration ~120 + docs ~150 = ~1200 行

---

## 15. 风险 + 决策记录

| 风险 | 缓解 |
|---|---|
| loguru 全量切破坏 8 个 stdlib logger 模块 | InterceptHandler 桥接, Day 1 跑全测试验证 |
| enqueue 队列满 (PG 慢) → 丢日志 | drop newest + stderr 兜底 + CRITICAL 告警 (进 app_logs) |
| loguru 后台线程崩 → 后续日志全丢 | FastAPI shutdown 钩子 `logger.complete()` 排空 |
| audit_logs 写入失败 → 漏审计 | try/except + logger.critical + 监控告警 |
| PII 漏 scrub → 泄漏密码/token | `_scrub` 强制所有 sink 走 + 黑名单 + 测试覆盖 |
| 后期想接 Grafana / Sentry | spec §13 路线图 + env `*_ENABLED=false` flag + core/logging.py 留 hook 位置 |

**决策记录**:
- ✅ loguru 全量切 (用户选, 2026-06-17)
- ✅ 不接 Sentry (用户选, spec §13.4 留路线图)
- ✅ 不接 Grafana / Loki / Supabase (本期不接, §13.5 写明)
- ✅ 不做日志查看 UI (用户选, spec §12 运维 SQL)
- ✅ Audit 25 hook (P0+P1+P2+P3 全做, 用户选)
- ✅ 3 表 schema (app_logs / error_logs / audit_logs)
- ✅ 月分区 + 不可变 trigger
- ✅ PII 黑名单 (16 个常见字段)

---

## 16. 验收清单

**功能验收**:
- [ ] loguru 全量切换, 8 个 stdlib 模块改完
- [ ] 控制台 dev 彩色 / prod JSON (LOG_JSON 切换)
- [ ] app_logs 写入 (enqueue 后台, 0 阻塞)
- [ ] error_logs 5xx 写入 + stacktrace
- [ ] audit_logs 25 hook 全生效, immutability trigger 拒绝 UPDATE/DELETE
- [ ] RequestID 中间件 + contextvars 注入
- [ ] 全局异常 handler: 4xx warn, 5xx error, 不返 stacktrace
- [ ] PII scrub: 16 个黑名单字段测试覆盖

**质量验收**:
- [ ] 25 测试全绿
- [ ] ruff + pyright 0 error
- [ ] 现有 200+ 测试 0 break
- [ ] 手动触发: 删除账户 → 验证 audit_logs 落表 + 不可改

**文档验收**:
- [ ] `docs/operations/observability.md` (运维 SQL + Grafana 路线图)
- [ ] `packages/service/CLAUDE.md` 增补日志约定
- [ ] `docs/superpowers/handoffs/2026-06-17-logging-system.md` (handoff)

**集成验收**:
- [ ] Docker compose 起 PG + MinIO, 跑全栈, 日志 3 表都能查
- [ ] LOG_JSON=true 切换正常 (生产模式)
- [ ] 队列满 → stderr 兜底 + CRITICAL 进 app_logs

---

**Spec OK 吗? 你 review 完确认 → 写 plan → subagent 实施.**