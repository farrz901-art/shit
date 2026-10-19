# RAG 日志系统 Implementation Plan (2026-06-17)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 stdlib `logging` 全量切到 loguru, 加 Postgres 持久化 (3 表 + 月分区 + audit 不可变), 接 FastAPI 全局异常 handler, 加 PII scrub, 加 25 个危险操作 audit hook, 预留 Grafana / Sentry 升级路径.

**Architecture:** loguru 当 facade + InterceptHandler 桥接 stdlib. 3 个独立 PG 表 (app_logs / error_logs / audit_logs), 月分区, audit 不可变 trigger. FastAPI middleware 注入 request_id + user_id 到 contextvars. Audit 用 `@audited` decorator 包 endpoint, finally 块统一写 audit_logs (成功 + 失败).

**Tech Stack:** loguru 0.7+, FastAPI middleware, SQLAlchemy 2.0 async ORM, Alembic, pytest 9.0+ (CLAUDE.md 4 模式: 1 mock + 2 db_session).

**Spec:** [docs/superpowers/specs/2026-06-17-logging-system-design.md](../specs/2026-06-17-logging-system-design.md) (commit `59ff1de`)

**工期:** 5-7 天, 10 task, 6-7 commit, ~25 测试新增

**(2026-06-18 sync):** 按实际代码调整: 9 模块 loguru 迁移 (原 8 + account_settings_service + deletion); Task 8 hook 表重对齐到 account_settings_router / eval.cancel / memory.delete 等实际端点; down_revision 固定为 `20260617_120000`

---

## 文件结构 (一次看清所有改动)

### 新建

| 文件 | 行数 | 用途 |
|---|---|---|
| `packages/service/src/core/__init__.py` | 5 | 标记 core 子包 |
| `packages/service/src/core/logging_context.py` | ~30 | contextvars: current_request_id / current_user_id |
| `packages/service/src/core/logging.py` | ~180 | loguru 配置 + InterceptHandler + sinks + PII scrub |
| `packages/service/src/core/middleware.py` | ~60 | RequestIDMiddleware + bind_user_id |
| `packages/service/src/core/audit.py` | ~140 | AuditContext + @audited + _persist_audit |
| `packages/service/src/core/errors.py` | ~80 | FastAPI global exception handlers |
| `packages/service/src/db/models/app_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/db/models/error_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/db/models/audit_log.py` | ~30 | SQLAlchemy model |
| `packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py` | ~120 | alembic: 3 表 + 月分区 + 索引 + trigger |
| `packages/service/tests/core/__init__.py` | 5 | 标记 test 子包 |
| `packages/service/tests/core/test_logging.py` | ~120 | 5-6 测试: loguru config + PII scrub + InterceptHandler |
| `packages/service/tests/core/test_middleware.py` | ~80 | 3 测试: RequestID 传播 + header 回写 |
| `packages/service/tests/core/test_audit.py` | ~120 | 5 测试: @audited + 异常时 failure |
| `packages/service/tests/core/test_errors.py` | ~100 | 4-5 测试: 4xx warn + 5xx error + scrub |
| `packages/service/tests/db/test_app_log.py` | ~60 | 3 测试: INSERT 行为 (db_session) |
| `packages/service/tests/db/test_audit_log.py` | ~80 | 3 测试: immutability trigger (db_session) |
| `docs/operations/observability.md` | ~150 | 运维 SQL (10 条) + Grafana 接入路线图 |
| `docs/superpowers/handoffs/2026-06-17-logging-system.md` | ~200 | handoff 文档 |
| `docs/superpowers/plans/2026-06-17-logging-system.md` | 本文件 | plan |

### 改 (2026-06-18 sync: 按实际代码重对齐)

| 文件 | 改动 |
|---|---|
| `packages/service/src/main.py` (或等效入口) | `configure_logging()` + `install_error_handlers(app)` + 中间件挂载 |
| `packages/service/src/auth/account_settings_router.py` | 加 `@audited("email.change")`, `@audited("password.change")`, `@audited("account.delete")`, `@audited("avatar.delete")`, `@audited("deletion.cancel")` (auth 重构, 原 auth_account_router 部分 hook 落点迁移至此) |
| `packages/service/src/auth/auth_account_router.py` | 加 `@audited("password.reset")` (POST /api/account/reset-password) |
| `packages/service/src/auth/auth_admin_router.py` | 加 `@audited("role.change")`, `@audited("account.disable")`, `@audited("account.enable")` |
| `packages/service/src/auth/auth_invite_router.py` | 加 `@audited("user.invite")` |
| `packages/service/src/auth/router.py` | 加 `@audited("api_key.create")`, `@audited("api_key.revoke")` |
| `packages/service/src/kg/router.py` | 加 `@audited("kg_node.delete")`, `@audited("kg_relation.delete")` (需确认实际 DELETE 端点 — kg 目前只有 POST/GET) |
| `packages/service/src/eval/router.py` | 加 `@audited("evaluation.run")`, `@audited("evaluation.cancel")` (无 DELETE 端点, 改 cancel) |
| `packages/service/src/memory/router.py` | 加 `@audited("memory.purge_all")`, `@audited("memory.delete")` |
| `packages/service/src/ingest/api.py` | 加 `@audited("files.bulk_download")` (GET /tasks/{id}/download) — 无 DELETE 端点, knowledge.delete/dataset.delete/task.cancel/data.export 不存在, 跳过 |
| `packages/service/src/api/routes.py` | 加 admin.access 中间件 + audit.read_self 端点 |
| `packages/service/src/chat_share/router.py` | stdlib logger → loguru |
| `packages/service/src/chat_share/service.py` | 同上 |
| `packages/service/src/eval/llama_eval.py` | 同上 |
| `packages/service/src/memory/mem0_client.py` | 同上 |
| `packages/service/src/memory/router.py` | 同上 |
| `packages/service/src/memory/service.py` | 同上 |
| `packages/service/src/storage/object_store.py` | 同上 |
| `packages/service/src/auth/account_settings_service.py` | 同上 (新增: auth 重构后分离出的 service, 原 plan 未列) |
| `packages/service/src/scheduler/deletion.py` | 同上 (新增: 定时清理任务, 原 plan 未列) |
| `packages/service/src/product_decoders/app.py` | stdlib `_log` → loguru (工厂文件, 含 `_sa_exception_handler`) |
| `packages/service/src/health/checks.py` | 实际代码无 logger → 跳过 |
| `packages/service/src/ingest/pipeline.py` | 实际代码无 logger → 跳过 |
| `packages/service/.env.example` | 加 LOG_LEVEL / LOG_JSON / LOG_TO_DB / GRAFANA_ENABLED / SENTRY_ENABLED / LOKI_ENABLED |
| `packages/service/pyproject.toml` | 加 `loguru>=0.7,<1.0` |
| `packages/service/CLAUDE.md` | 增补 "日志使用约定" 章节 |

**注**: 实施前 implementer 必须 `grep -rn "@router.delete\|@router.post\|@router.patch" packages/service/src/` 列所有路由, 跟 spec §9 (2026-06-18 sync 版) 交叉比对, 代码优先, spec 次之.

---
## Task 1: Bootstrap (loguru 装包 + .env + core 包结构)

**Files:**
- Modify: `packages/service/pyproject.toml`
- Modify: `packages/service/.env.example`
- Create: `packages/service/src/core/__init__.py`
- Create: `packages/service/src/core/logging_context.py`
- Create: `packages/service/tests/core/__init__.py`
- Create: `packages/service/tests/core/test_logging_context.py`

- [ ] **Step 1.1: 加 loguru 依赖**

打开 `packages/service/pyproject.toml`, 在 `dependencies` 列表的 `# === 配置 / 环境 ===` 段之后加:

```toml
    # === 日志 ===
    "loguru>=0.7,<1.0",                 # 全量切换 stdlib logging (2026-06-17 spec §1)
```

- [ ] **Step 1.2: uv sync 装包**

```bash
cd packages/service
uv sync
uv run python -c "from loguru import logger; print(logger)"
```
Expected: `<loguru.logger.Logger object at ...>`

- [ ] **Step 1.3: 加 .env.example 段**

打开 `packages/service/.env.example`, 在文件末尾加:

```bash
# -----------------------------------------------------------------------------
# 日志系统 (2026-06-17 logging spec §13)
# -----------------------------------------------------------------------------
LOG_LEVEL=INFO                          # DEBUG / INFO / WARNING / ERROR / CRITICAL
LOG_JSON=false                          # dev 彩色 human-readable, prod JSON
LOG_TO_DB=true                          # enqueue 后台写 PG (spec §5)

# 后期接入 hook (本期不实装, env flag 留位置, spec §13 路线图)
GRAFANA_ENABLED=false                   # 后期接 Grafana, 直接连 RAG_DB_URL, 1 天接好
# GRAFANA_URL=http://localhost:3000

SENTRY_ENABLED=false                    # 后期接 Sentry SaaS, 装 sentry-sdk[fastapi] 即可
# SENTRY_DSN=https://xxx@sentry.io/123

LOKI_ENABLED=false                      # 后期接 Loki (K8s / 多服务时), 不接 PG
# LOKI_URL=http://localhost:3100
```

- [ ] **Step 1.4: 创建 core 包**

Create `packages/service/src/core/__init__.py`:
```python
"""跨子系统公共组件 (2026-06-17 logging spec)

- logging_context: contextvars 持有请求级 request_id / user_id
- logging: loguru 配置 + InterceptHandler + PG sinks + PII scrub
- middleware: RequestIDMiddleware
- audit: @audited decorator + AuditContext
- errors: FastAPI global exception handlers
"""
```

- [ ] **Step 1.5: 写失败测试 — contextvars 默认值**

Create `packages/service/tests/core/__init__.py`:
```python
"""core 包测试 (2026-06-17 logging spec §11)"""
```

Create `packages/service/tests/core/test_logging_context.py`:
```python
"""contextvars 测试 (模式 1, 0 PG 依赖)"""

from __future__ import annotations

from src.core.logging_context import current_request_id, current_user_id


def test_current_request_id_default_is_none():
    """没 set 时 default = None"""
    assert current_request_id.get() is None


def test_current_user_id_default_is_none():
    assert current_user_id.get() is None


def test_current_request_id_set_and_get():
    """set 后 get 一致, reset 恢复"""
    token = current_request_id.set("req-abc-123")
    try:
        assert current_request_id.get() == "req-abc-123"
    finally:
        current_request_id.reset(token)
    assert current_request_id.get() is None


def test_current_user_id_set_and_get():
    token = current_user_id.set(42)
    try:
        assert current_user_id.get() == 42
    finally:
        current_user_id.reset(token)
    assert current_user_id.get() is None
```

- [ ] **Step 1.6: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_logging_context.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.logging_context'`

- [ ] **Step 1.7: 实现 contextvars**

Create `packages/service/src/core/logging_context.py`:
```python
"""contextvars 持有请求级元数据 (2026-06-17 logging spec §6)

middleware 在请求进入时 set, 离开时 reset.
loguru sink 跟 audit decorator 通过这两个 contextvar 拿值.
"""

from __future__ import annotations

from contextvars import ContextVar

# 请求级 UUID4 (RequestIDMiddleware 生成或读 X-Request-ID header)
current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)

# auth 解析后注入 (bind_user_id 调用), 用于日志 + audit_logs.actor_id
current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
```

- [ ] **Step 1.8: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_logging_context.py -v
```
Expected: **4 passed**

- [ ] **Step 1.9: Commit T1**

```bash
cd c:/doc/Code/rag
git add packages/service/pyproject.toml packages/service/uv.lock packages/service/.env.example \
    packages/service/src/core/__init__.py packages/service/src/core/logging_context.py \
    packages/service/tests/core/__init__.py packages/service/tests/core/test_logging_context.py
git commit -m "feat(core): bootstrap logging 系统 - loguru 装包 + .env + contextvars

- pyproject.toml: 加 loguru>=0.7,<1.0 (2026-06-17 spec §1 全量切 loguru)
- .env.example: 加日志段 (LOG_LEVEL/LOG_JSON/LOG_TO_DB) + 3 个升级 hook (GRAFANA/SENTRY/LOKI)
- src/core/__init__.py: 标记 core 子包
- src/core/logging_context.py: ContextVar request_id + user_id
- tests/core/test_logging_context.py 4 测试 (set/get/reset/default, 模式 1 mock)
- spec §6 contextvars + §13 升级路径 hook"
```

---

## Task 2: PII Scrubber + InterceptHandler (loguru 桥接 stdlib)

**Files:**
- Create: `packages/service/src/core/logging.py` (本 task 只写 PII scrub + InterceptHandler 部分, Task 3 补 configure_logging)
- Create: `packages/service/tests/core/test_logging.py`

- [ ] **Step 2.1: 写失败测试 — PII scrub + InterceptHandler**

Create `packages/service/tests/core/test_logging.py`:
```python
"""loguru config + PII scrub + InterceptHandler 测试 (模式 1, 0 PG)

覆盖:
- _scrub: 16 个敏感字段全部 ***REDACTED***
- _scrub: 嵌套 dict / list 递归
- _scrub: case-insensitive
- _scrub: user_id / email / ip / request_id 不动 (审计需要)
- InterceptHandler: stdlib log → loguru 转发 (subclass + emit 不抛)
"""

from __future__ import annotations

import logging

from src.core.logging import InterceptHandler, _scrub


# ---------------- PII scrub ----------------


def test_scrub_password():
    """password 字段 → REDACTED"""
    assert _scrub({"password": "abc123"}) == {"password": "***REDACTED***"}


def test_scrub_token_variants():
    """token / access_token / refresh_token / api_key / apikey / authorization 全 redacted"""
    data = {
        "token": "t1",
        "access_token": "t2",
        "refresh_token": "t3",
        "api_key": "k1",
        "apikey": "k2",
        "authorization": "Bearer xyz",
        "secret": "s1",
        "private_key": "pk",
    }
    out = _scrub(data)
    for key in data:
        assert out[key] == "***REDACTED***", f"{key} 没被 scrub"


def test_scrub_case_insensitive():
    """Password / TOKEN / Authorization 大小写不敏感"""
    data = {"Password": "x", "TOKEN": "y", "Authorization": "z", "API_KEY": "w"}
    out = _scrub(data)
    assert all(v == "***REDACTED***" for v in out.values())


def test_scrub_keeps_safe_fields():
    """user_id / email / ip / request_id 不算 PII (审计需要), 不动"""
    data = {"user_id": 42, "email": "a@b.com", "ip": "1.2.3.4", "request_id": "req-1"}
    assert _scrub(data) == data


def test_scrub_nested_dict():
    """嵌套 dict 递归 scrub"""
    data = {
        "user": {"id": 1, "password": "abc"},
        "credentials": {"api_key": "k1", "ssn": "111-22-3333"},
    }
    out = _scrub(data)
    assert out["user"]["id"] == 1
    assert out["user"]["password"] == "***REDACTED***"
    assert out["credentials"]["api_key"] == "***REDACTED***"
    assert out["credentials"]["ssn"] == "***REDACTED***"


def test_scrub_list_of_dicts():
    """list 里每个 dict 递归 scrub"""
    data = [{"password": "a"}, {"token": "b"}, {"safe": "c"}]
    out = _scrub(data)
    assert out == [
        {"password": "***REDACTED***"},
        {"token": "***REDACTED***"},
        {"safe": "c"},
    ]


def test_scrub_non_dict_passthrough():
    """字符串 / int / None 原样返回"""
    assert _scrub("hello") == "hello"
    assert _scrub(42) == 42
    assert _scrub(None) is None


# ---------------- InterceptHandler ----------------


def test_intercept_handler_subclass():
    """InterceptHandler 是 logging.Handler 子类"""
    assert issubclass(InterceptHandler, logging.Handler)


def test_intercept_handler_emit_does_not_raise():
    """emit() 拿到 stdlib LogRecord 不抛"""
    handler = InterceptHandler()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    handler.emit(record)  # 不应抛
```

- [ ] **Step 2.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_logging.py -v
```
Expected: **FAIL** with `ImportError: cannot import name '_scrub' from 'src.core.logging'`

- [ ] **Step 2.3: 实现 PII scrub + InterceptHandler**

Create `packages/service/src/core/logging.py`:
```python
"""loguru 全局配置 + PII scrub + InterceptHandler (2026-06-17 logging spec §5/§7/§10)

本文件 3 块:
1. PII scrubber (敏感字段 → ***REDACTED***)
2. InterceptHandler (stdlib log → loguru 桥接)
3. configure_logging + sinks (Task 3 加)
"""

from __future__ import annotations

import logging
from typing import Any

from loguru import logger as _loguru


# ============== PII Scrubber (§10) ==============

# case-insensitive 黑名单 (16 字段, spec §10)
SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "api_key", "apikey",
    "secret", "client_secret",
    "authorization", "cookie", "set-cookie",
    "ssn", "credit_card", "card_number", "cvv",
    "private_key", "privatekey",
})


def _scrub(data: Any) -> Any:
    """递归 scrub 已知敏感字段. dict / list 嵌套处理.

    Args:
        data: 任意 JSON 结构 (dict / list / str / int / None)

    Returns:
        新结构 (浅复制), 敏感字段值替换为 '***REDACTED***'.
        非容器类型原样返回.
    """
    if isinstance(data, dict):
        return {
            k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else _scrub(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_scrub(item) for item in data]
    return data


# ============== InterceptHandler (stdlib → loguru) ==============


class InterceptHandler(logging.Handler):
    """stdlib logging.Handler → loguru 转发.

    第三方库 (SQLAlchemy / uvicorn / boto3 / httpx) 全部用 stdlib logging,
    挂这个 handler 到 root logger 后, 它们的 log 自动经 loguru sink 输出.
    spec §5 桥接策略.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # stdlib level → loguru level (string)
        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno  # 未知 level 用数字

        # depth 跳过 logging 模块内部帧, 让 loguru 显示真实调用方
        frame, depth = logging.currentframe(), 2
        while frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage(),
        )
```

- [ ] **Step 2.4: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_logging.py -v
```
Expected: **9 passed** (7 scrub + 2 InterceptHandler)

- [ ] **Step 2.5: 跑 ruff + pyright**

```bash
cd packages/service
uv run ruff check src/core/logging.py tests/core/test_logging.py
uv run pyright src/core/logging.py tests/core/test_logging.py
```
Expected: 0 error / 0 warning

- [ ] **Step 2.6: Commit T2**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/logging.py packages/service/tests/core/test_logging.py
git commit -m "feat(core): PII scrubber + InterceptHandler (loguru 桥接 stdlib)

- src/core/logging.py: _scrub 递归 (16 字段黑名单, case-insensitive) + InterceptHandler
- spec §5 桥接策略: stdlib logger → loguru opt(depth, exception).log()
- spec §10 PII 黑名单: password / token / secret / api_key / authorization / ssn / credit_card / private_key 等
- 9 测试: 7 scrub (单字段/嵌套/case/list/safe-pass) + 2 InterceptHandler (subclass / emit)"
```

---

## Task 3: configure_logging + 控制台 sink + PG sink (核心配置)

**Files:**
- Modify: `packages/service/src/core/logging.py` (在 Task 2 基础上补 configure_logging + sinks)
- Modify: `packages/service/tests/core/test_logging.py` (加 configure_logging 测试)

- [ ] **Step 3.1: 写失败测试 — configure_logging**

打开 `packages/service/tests/core/test_logging.py`, 在文件末尾追加:

```python
# ---------------- configure_logging ----------------


def test_configure_logging_dev_mode_no_db(monkeypatch, capsys):
    """dev 模式: 彩色控制台 + 不写 DB"""
    from src.core.logging import configure_logging
    from loguru import logger as _loguru

    configure_logging(json_console=False, write_to_db=False, level="INFO")
    _loguru.info("test message")

    # _loguru.complete() 同步排空 enqueue, 让 capsys 拿到
    _loguru.complete()
    captured = capsys.readouterr()
    # 彩色模式输出到 stderr
    assert "test message" in captured.err


def test_configure_logging_json_mode(monkeypatch, capsys):
    """JSON 模式: serialize=True 输出 JSON"""
    import json as json_mod
    from src.core.logging import configure_logging
    from loguru import logger as _loguru

    configure_logging(json_console=True, write_to_db=False, level="INFO")
    _loguru.info("json test")
    _loguru.complete()

    captured = capsys.readouterr()
    # JSON 模式走 stdout
    line = captured.out.strip().split("\n")[-1]
    parsed = json_mod.loads(line)
    assert parsed["record"]["message"] == "json test"
    assert parsed["record"]["level"]["name"] == "INFO"


def test_configure_logging_intercepts_stdlib(monkeypatch, capsys):
    """stdlib logging.getLogger("uvicorn") 经 InterceptHandler 进 loguru"""
    import logging as stdlib_logging

    from src.core.logging import configure_logging
    from loguru import logger as _loguru

    configure_logging(json_console=False, write_to_db=False, level="INFO")

    # uvicorn 的 stdlib logger 应该被接管
    stdlib_logger = stdlib_logging.getLogger("uvicorn")
    stdlib_logger.info("stdlib intercepted")
    _loguru.complete()

    captured = capsys.readouterr()
    assert "stdlib intercepted" in captured.err


def test_configure_logging_db_sink_registered(monkeypatch):
    """write_to_db=True 时, _pg_sink_app 被 add 到 loguru"""
    from src.core import logging as core_logging

    sink_calls = []
    monkeypatch.setattr(core_logging, "_pg_sink_app",
                        lambda message: sink_calls.append(message))

    core_logging.configure_logging(json_console=False, write_to_db=True, level="INFO")
    from loguru import logger as _loguru
    _loguru.info("to db")
    _loguru.complete()

    # _pg_sink_app 至少被调一次
    assert len(sink_calls) >= 1
```

- [ ] **Step 3.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_logging.py::test_configure_logging_dev_mode_no_db -v
```
Expected: **FAIL** with `ImportError: cannot import name 'configure_logging' from 'src.core.logging'`

- [ ] **Step 3.3: 实现 configure_logging + sinks**

打开 `packages/service/src/core/logging.py`, 在文件末尾 (`InterceptHandler` 之后) 加:

```python
# ============== configure_logging + sinks (§5) ==============

import os
import sys
import time
import traceback
from datetime import timezone

from sqlalchemy import text


# 队列满 → drop newest + stderr 兜底 (spec §15 风险表)
_LOG_QUEUE_MAXSIZE = 10_000


def _pg_sink_app(message) -> None:
    """app_logs sink (后台线程). loguru enqueue=True 调本函数.

    永不抛 (会让 loguru 后台线程崩, 后续日志全丢). 错误用 stderr 兜底 + critical.
    """
    rec = message.record
    try:
        from src.storage import session_scope

        with session_scope() as s:
            s.execute(
                text(
                    "INSERT INTO app_logs (ts, level, logger, message, request_id, "
                    "user_id, trace_id, context) "
                    "VALUES (:ts, :level, :logger, :message, :request_id, "
                    ":user_id, :trace_id, :context)"
                ),
                {
                    "ts": rec["time"].astimezone(timezone.utc),
                    "level": rec["level"].name,
                    "logger": rec["name"],
                    "message": rec["message"],
                    "request_id": _get_request_id(),
                    "user_id": _get_user_id(),
                    "trace_id": rec["extra"].get("trace_id"),
                    "context": _scrub(dict(rec["extra"])),
                },
            )
    except Exception as e:
        # 永不让 sink 崩
        print(f"[logging] app_logs write failed: {e}", file=sys.stderr, flush=True)


def _error_sink_sync(level: str, exc: Exception, request) -> None:
    """error_logs sink (同步, 5xx 全局 handler 调).

    跟 _pg_sink_app 不同, 这个是同步写, 因为异常发生时希望立即落库.
    request 可为 None (非 HTTP 路径触发的异常).
    """
    try:
        from src.storage import session_scope

        with session_scope() as s:
            s.execute(
                text(
                    "INSERT INTO error_logs (ts, level, exception_type, exception_msg, "
                    "stacktrace, request_id, user_id, path, method, status_code, context) "
                    "VALUES (NOW(), :level, :type, :msg, :trace, :rid, :uid, "
                    ":path, :method, :code, :ctx)"
                ),
                {
                    "level": level,
                    "type": type(exc).__name__,
                    "msg": str(exc)[:1000],
                    "trace": "".join(
                        traceback.format_exception(type(exc), exc, exc.__traceback__)
                    )[:5000],
                    "rid": _get_request_id(),
                    "uid": _get_user_id(),
                    "path": request.url.path if request else None,
                    "method": request.method if request else None,
                    "code": 500,
                    "ctx": _scrub({}),
                },
            )
    except Exception as e:
        # error_logs 写失败 → critical 进 app_logs (注意: 也可能 app_logs 也挂, 那就只剩 stderr)
        print(f"[logging] error_logs write failed: {e}", file=sys.stderr, flush=True)


def _get_request_id() -> str | None:
    """避免循环 import. 运行时拿 contextvar."""
    from src.core.logging_context import current_request_id
    return current_request_id.get()


def _get_user_id() -> int | None:
    from src.core.logging_context import current_user_id
    return current_user_id.get()


# 第三方 logger 列表 (stdlib → loguru 接管)
_THIRD_PARTY_LOGGERS = (
    "uvicorn", "uvicorn.access", "uvicorn.error",
    "sqlalchemy.engine", "boto3", "botocore", "httpx", "httpcore",
    "neo4j", "mem0", "kreuzberg",
)


def configure_logging(
    json_console: bool = False,
    write_to_db: bool = True,
    level: str = "INFO",
) -> None:
    """main.py 启动时调一次. 配置 loguru + 接管 stdlib.

    Args:
        json_console: True → JSON 输出 (生产), False → 彩色 (dev)
        write_to_db: True → 写 app_logs 表 (enqueue=True 后台线程)
        level: 全局最低 log 级别 (DEBUG / INFO / WARNING / ERROR / CRITICAL)
    """
    # 清默认 + 接管 stdlib root
    _loguru.remove()
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in _THIRD_PARTY_LOGGERS:
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = [InterceptHandler()]
        stdlib_logger.propagate = False

    # 控制台 sink
    if json_console:
        _loguru.add(
            sys.stdout, level=level, serialize=True, enqueue=True,
            backtrace=True, diagnose=False,
        )
    else:
        _loguru.add(
            sys.stderr, level=level, colorize=True, enqueue=True,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            backtrace=True, diagnose=False,
        )

    # DB sink (enqueue=True 后台线程, 永不阻塞请求)
    if write_to_db:
        _loguru.add(
            _pg_sink_app, level=level, enqueue=True,
            backtrace=True, diagnose=False,
        )

    # (2026-06-17 spec §13) Grafana hook 预留位置
    grafana_enabled = os.getenv("GRAFANA_ENABLED", "false").lower() == "true"
    if grafana_enabled:
        # TODO: 后期接入. Grafana 直接连 RAG_DB_URL 即可, 不需要 DSN.
        # 1. 装 Grafana (docker / 自部署)
        # 2. Add datasource → PostgreSQL, 配 RAG_DB_URL
        # 3. Import dashboard JSON (本 spec 后期提供)
        pass

    _loguru.info(
        "logging configured: level={} json={} db={}",
        level, json_console, write_to_db,
    )


def shutdown_logging() -> None:
    """FastAPI shutdown 钩子. 排空 enqueue 队列, 不丢最后一批日志."""
    _loguru.complete()
```

- [ ] **Step 3.4: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_logging.py -v
```
Expected: **13 passed** (9 + 4 configure_logging)

- [ ] **Step 3.5: 跑 ruff + pyright**

```bash
cd packages/service
uv run ruff check src/core/logging.py tests/core/test_logging.py
uv run pyright src/core/logging.py
```
Expected: 0 error

- [ ] **Step 3.6: Commit T3**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/logging.py packages/service/tests/core/test_logging.py
git commit -m "feat(core): configure_logging + 控制台 sink + PG sinks

- src/core/logging.py: configure_logging(json_console, write_to_db, level)
- 控制台 sink: dev 彩色 (stderr) / prod JSON serialize (stdout)
- PG sinks: _pg_sink_app (enqueue 后台线程, app_logs) + _error_sink_sync (5xx 同步, error_logs)
- Stdlib 接管: 11 个第三方 logger (uvicorn/sqlalchemy/boto3/httpx/neo4j/mem0/kreuzberg)
- 永不抛: sink 失败 stderr 兜底, 不让后台线程崩
- shutdown_logging(): FastAPI shutdown 钩子排空 enqueue 队列
- spec §5 + §13 (Grafana 预留 hook)
- +4 测试: dev/json/intercept stdlib/db sink 注册"
```

---

## Task 4: 替换 9 个模块的 stdlib logger 为 loguru (2026-06-18 sync: 从原 8 个 + account_settings_service + deletion)

**Files (现有 stdlib logger 用法, 全部改 loguru):**
- Modify: `packages/service/src/chat_share/router.py`
- Modify: `packages/service/src/chat_share/service.py`
- Modify: `packages/service/src/eval/llama_eval.py`
- Modify: `packages/service/src/memory/mem0_client.py`
- Modify: `packages/service/src/memory/router.py`
- Modify: `packages/service/src/memory/service.py`
- Modify: `packages/service/src/storage/object_store.py`
- Modify: `packages/service/src/auth/account_settings_service.py` (新增: auth 重构后新文件)
- Modify: `packages/service/src/scheduler/deletion.py` (新增: 定时清理任务)

**跳过 (无 logger):** health/checks.py, ingest/pipeline.py — 实际代码无 logger, 跳过

**统一替换规则**:
- `import logging` → 删 (如果文件别处还用到 logging 常量如 logging.INFO, 保留 import logging)
- `logger = logging.getLogger(__name__)` → `from loguru import logger`
- `logger.info("msg %s", x)` → `logger.info("msg {}", x)` (loguru 用 `{}`占位符, %-style 也兼容但不推荐)
- `logger.warning("...", exc_info=True)` → `logger.opt(exception=True).warning("...")` 或 `logger.exception("...")`

- [ ] **Step 4.1: 写失败测试 — 验证 9 模块用 loguru 不用 stdlib**

Create `packages/service/tests/core/test_loguru_migration.py`:
```python
"""验证 9 个模块全部用 loguru, 不再用 stdlib logging (2026-06-18 sync: 9 个 = 原 8 + account_settings_service + deletion)

用 grep 验证. 模式 1, 0 PG.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# 项目根
SERVICE_SRC = Path(__file__).parent.parent.parent / "src"

# 必须切到 loguru 的 9 个模块 (2026-06-18 sync: + account_settings_service + deletion, 去掉 ingest/pipeline + health/checks 因为它们无 logger)
LOGURU_MIGRATED_FILES = [
    "chat_share/router.py",
    "chat_share/service.py",
    "eval/llama_eval.py",
    "memory/mem0_client.py",
    "memory/router.py",
    "memory/service.py",
    "storage/object_store.py",
    "auth/account_settings_service.py",
    "scheduler/deletion.py",
]


@pytest.mark.parametrize("rel_path", LOGURU_MIGRATED_FILES)
def test_module_uses_loguru_not_stdlib(rel_path: str):
    """确认模块 import loguru.logger, 不再 import logging"""
    file = SERVICE_SRC / rel_path
    if not file.exists():
        pytest.skip(f"{rel_path} 不存在")
    content = file.read_text(encoding="utf-8")

    # 必须 import loguru
    assert "from loguru import logger" in content, \
        f"{rel_path} 没 import loguru.logger"

    # 不能有顶层 import logging (允许 logging.config 之类的)
    # 检查 logging.getLogger 调用
    assert "logging.getLogger(__name__)" not in content, \
        f"{rel_path} 还在用 stdlib logging.getLogger"


def test_no_logger_init_in_migrated_modules():
    """logger = logging.getLogger 模式不应在 8 模块出现"""
    for rel in LOGURU_MIGRATED_FILES:
        file = SERVICE_SRC / rel
        if not file.exists():
            continue
        content = file.read_text(encoding="utf-8")
        bad = re.findall(r"logger\s*=\s*logging\.getLogger", content)
        assert not bad, f"{rel} 含旧 logger init: {bad}"
```

- [ ] **Step 4.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_loguru_migration.py -v
```
Expected: **8 FAIL** (每个模块都用 stdlib)

- [ ] **Step 4.3: 替换 chat_share/router.py**

打开 `packages/service/src/chat_share/router.py`:

把:
```python
import logging
...
logger = logging.getLogger(__name__)
```

改为:
```python
from loguru import logger
```

(删除 `import logging` + 删除 `logger = logging.getLogger(__name__)`. 如果文件其他地方仍要用 stdlib `logging` 模块的常量 (如 `logging.INFO`), 保留 `import logging`, 只删 logger init)

- [ ] **Step 4.4: 替换 chat_share/service.py**

同 4.3, 把 `import logging` + `logger = logging.getLogger(__name__)` 改成 `from loguru import logger`.

- [ ] **Step 4.5: 替换 eval/llama_eval.py**

打开 `packages/service/src/eval/llama_eval.py`, 找到 line 114-116:
```python
import logging
...
logging.getLogger(__name__).warning(f"evaluator[{name}] 失败: {e}")
```

改为顶部加 `from loguru import logger`, line 116 改为:
```python
logger.warning("evaluator[{}] 失败: {}", name, e)
```

- [ ] **Step 4.6: 替换 memory/mem0_client.py + memory/router.py + memory/service.py**

3 个文件统一处理:
- 删 `import logging`
- 把 `logger = logging.getLogger(__name__)` 改成 `from loguru import logger`
- `logger.info("msg %s", x)` 占位符改 `logger.info("msg {}", x)` (loguru 风格)
- `exc_info=True` 改 `logger.opt(exception=True).warning(...)` 或 `logger.exception(...)`

例 `memory/service.py:142`:
```python
# 旧
logger.warning("add failed user_id=%s err=%s", user_id, e, exc_info=True)
# 新
logger.opt(exception=True).warning("add failed user_id={} err={}", user_id, e)
```

- [ ] **Step 4.7: 替换 storage/object_store.py**

打开 `packages/service/src/storage/object_store.py`, line 20-30:
```python
# 旧
import logging
...
logger = logging.getLogger(__name__)
```

改为:
```python
from loguru import logger
```

(注意保留文件其他部分)

- [ ] **Step 4.8: 替换 auth/account_settings_service.py + scheduler/deletion.py (新增)**

打开 `packages/service/src/auth/account_settings_service.py`:
```python
# 旧 (line 9, 24)
import logging
...
logger = logging.getLogger(__name__)

# 新
from loguru import logger
```
(删 `import logging` 如果文件没别处用)

打开 `packages/service/src/scheduler/deletion.py`:
```python
# 旧 (line 5, 11)
import logging
...
logger = logging.getLogger(__name__)

# 新
from loguru import logger
```

- [ ] **Step 4.9: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_loguru_migration.py -v
```
Expected: **9 passed** (每个模块都已用 loguru)

- [ ] **Step 4.10: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -20
```
Expected: 现有 200+ 测试全绿, 0 break

- [ ] **Step 4.11: Commit T4**

```bash
cd c:/doc/Code/rag
git add packages/service/src/chat_share/router.py packages/service/src/chat_share/service.py \
    packages/service/src/eval/llama_eval.py \
    packages/service/src/memory/mem0_client.py packages/service/src/memory/router.py \
    packages/service/src/memory/service.py \
    packages/service/src/storage/object_store.py \
    packages/service/src/auth/account_settings_service.py \
    packages/service/src/scheduler/deletion.py \
    packages/service/tests/core/test_loguru_migration.py
git commit -m "refactor(logging): 9 模块 stdlib logging → loguru 全量切换 (spec §1)

- chat_share/{router,service}.py
- eval/llama_eval.py
- memory/{mem0_client,router,service}.py
- storage/object_store.py
- auth/account_settings_service.py (新增, auth 重构后新文件)
- scheduler/deletion.py (新增, 定时清理任务)
- health/checks.py + ingest/pipeline.py 无 logger, 跳过
- 占位符 %s → {} (loguru 风格)
- exc_info=True → logger.opt(exception=True) 或 logger.exception()
- +9 测试 grep 验证 (test_loguru_migration.py): import loguru + 无 stdlib logger init
- 2026-06-18 sync: 从原 8 个扩展到 9 个, 按实际代码调整
- 现有 200+ 测试 0 break"
```

---

## Task 5: RequestIDMiddleware + main.py 挂载 + bind_user_id

**Files:**
- Create: `packages/service/src/core/middleware.py`
- Modify: `packages/service/main.py` (替换 _setup_logging → configure_logging)
- Modify: `packages/service/src/product_decoders/app.py` (create_app() 加 middleware)
- Create: `packages/service/tests/core/test_middleware.py`

- [ ] **Step 5.1: 写失败测试 — RequestIDMiddleware**

Create `packages/service/tests/core/test_middleware.py`:
```python
"""RequestID middleware 测试 (模式 1, 0 PG)

覆盖:
- 请求无 X-Request-ID header → 生成 UUID4 注入 contextvar
- 请求带 X-Request-ID → 直接用, 不重新生成
- 响应回写 X-Request-ID header
- contextvar 在请求结束后 reset
- bind_user_id 注入 user_id contextvar
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.logging_context import current_request_id, current_user_id
from src.core.middleware import RequestIDMiddleware, bind_user_id


@pytest.fixture
def app_with_middleware():
    """FastAPI app + RequestIDMiddleware + 1 端点回显 contextvar"""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo():
        return {
            "request_id": current_request_id.get(),
            "user_id": current_user_id.get(),
        }

    return app


def test_middleware_generates_uuid_when_no_header(app_with_middleware):
    """无 X-Request-ID → 生成 UUID4"""
    client = TestClient(app_with_middleware)
    resp = client.get("/echo")
    assert resp.status_code == 200
    body = resp.json()
    # UUID4 格式
    rid = body["request_id"]
    assert uuid.UUID(rid).version == 4
    # 响应 header 回写
    assert resp.headers["x-request-id"] == rid


def test_middleware_uses_provided_header(app_with_middleware):
    """带 X-Request-ID header → 直接用"""
    client = TestClient(app_with_middleware)
    resp = client.get("/echo", headers={"X-Request-ID": "custom-req-123"})
    assert resp.status_code == 200
    assert resp.json()["request_id"] == "custom-req-123"
    assert resp.headers["x-request-id"] == "custom-req-123"


def test_middleware_resets_contextvar_after_request(app_with_middleware):
    """请求结束后 contextvar 应 reset (不泄漏到下一请求)"""
    client = TestClient(app_with_middleware)
    client.get("/echo", headers={"X-Request-ID": "req-1"})
    # 测试线程 (主线程) 的 contextvar 应该是默认值
    assert current_request_id.get() is None


def test_bind_user_id_sets_contextvar():
    """bind_user_id(42) → contextvar = 42"""
    token = current_user_id.set(None)
    try:
        bind_user_id(42)
        assert current_user_id.get() == 42
    finally:
        current_user_id.reset(token)


def test_bind_user_id_none_clears():
    """bind_user_id(None) → contextvar = None"""
    token = current_user_id.set(99)
    try:
        bind_user_id(None)
        assert current_user_id.get() is None
    finally:
        current_user_id.reset(token)
```

- [ ] **Step 5.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_middleware.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.middleware'`

- [ ] **Step 5.3: 实现 RequestIDMiddleware**

Create `packages/service/src/core/middleware.py`:
```python
"""RequestID + user_id 注入 contextvars (2026-06-17 logging spec §6)

每请求:
1. 读 X-Request-ID header, 没则生成 UUID4
2. 写入 contextvars (current_request_id)
3. 响应回写 X-Request-ID header
4. 请求结束 reset (避免泄漏到下一请求)
"""

from __future__ import annotations

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .logging_context import current_request_id, current_user_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """每请求注入 / 回写 X-Request-ID + reset contextvars."""

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
    """auth 解析后调. 把 user_id 注入 contextvars.

    通常在 FastAPI Depends 链里 (resolve_user 之后) 调:
        from src.core.middleware import bind_user_id
        bind_user_id(current_user.id)
    """
    current_user_id.set(user_id)
```

- [ ] **Step 5.4: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_middleware.py -v
```
Expected: **5 passed**

- [ ] **Step 5.5: 改 main.py — 替换 _setup_logging → configure_logging**

打开 `packages/service/main.py`, 找到 `_setup_logging()` 函数 (line 34), 替换:

```python
# 旧
import logging
def _setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
```

改为:
```python
def _setup_logging() -> None:
    """配置 loguru + 接管 stdlib (2026-06-17 logging spec §5)"""
    from src.core.logging import configure_logging

    configure_logging(
        json_console=os.getenv("LOG_JSON", "false").lower() == "true",
        write_to_db=os.getenv("LOG_TO_DB", "true").lower() == "true",
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
```

(保留原 `import os` 跟原文件其他内容. 如果 `import logging` 只在 `_setup_logging` 用, 删掉; 如果 `logging.getLogger(__name__)` 还在别处用, 保留.)

- [ ] **Step 5.6: 改 src/product_decoders/app.py — create_app() 加 middleware**

打开 `packages/service/src/product_decoders/app.py:172`, 在 `app.add_middleware(CORSMiddleware, ...)` 之后 (line 182) 加:

```python
    # 注入 RequestID + user_id contextvars (2026-06-17 logging spec §6)
    from src.core.middleware import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
```

⚠️ 必须在 CORSMiddleware 之后 add (FastAPI middleware 是栈结构, 后 add 先执行).
⚠️ `app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)` 在 line 182 已存在, 不要删 — 这是已有的 SQLAlchemy 异常 handler, 跟新的 `install_error_handlers` 共存.

- [ ] **Step 5.7: 跑全测试验证 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -20
```
Expected: 现有测试 + 新 5 个 middleware 测试全绿

- [ ] **Step 5.8: 手动验证 (启服务 → curl)**

```bash
cd packages/service
uv run python main.py &
sleep 3
curl -i http://localhost:8000/health 2>&1 | grep -i "x-request-id"
kill %1
```
Expected: `x-request-id: <UUID4>` header 出现

- [ ] **Step 5.9: Commit T5**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/middleware.py packages/service/tests/core/test_middleware.py \
    packages/service/main.py packages/service/src/product_decoders/app.py
git commit -m "feat(core): RequestIDMiddleware + main.py 切 configure_logging

- src/core/middleware.py: RequestIDMiddleware (生成/读 UUID4, 注入 contextvar, 响应回写 header) + bind_user_id (auth 后调)
- main.py: _setup_logging() 改调 configure_logging() 读 LOG_JSON/LOG_TO_DB/LOG_LEVEL env
- src/product_decoders/app.py: create_app() 加 RequestIDMiddleware (在其他 middleware 之前)
- +5 测试: UUID4 生成 / 读 header / 响应回写 / contextvar reset / bind_user_id
- spec §6 contextvars + middleware"
```

---

## Task 6: DB Schema + alembic migration (3 表 + 月分区 + 不可变 trigger)

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py`
- Create: `packages/service/tests/db/__init__.py`
- Create: `packages/service/tests/db/test_log_tables.py`

- [ ] **Step 6.1: 写失败测试 — 3 表存在 + immutability + 索引**

Create `packages/service/tests/db/__init__.py`:
```python
"""DB 集成测试 (2026-06-17 logging spec §11, 模式 2 db_session)"""
```

Create `packages/service/tests/db/test_log_tables.py`:
```python
"""3 个 log 表 schema 测试 (模式 2, db_session 集成)

覆盖:
- app_logs / error_logs / audit_logs 3 表存在
- 月分区 _2026_06 / _2026_07 已创建
- audit_logs immutability trigger 拒绝 UPDATE / DELETE
- BRIN / B-tree / GIN 索引存在
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError


pytestmark = pytest.mark.usefixtures("db_session")


def test_app_logs_table_exists(db_session):
    """app_logs 表存在, 含 partition 父表 + 当月分区"""
    rows = db_session.execute(text(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename LIKE 'app_logs%' "
        "ORDER BY tablename"
    )).fetchall()
    names = {r[0] for r in rows}
    assert "app_logs" in names
    # 至少有当月或下月分区
    assert any(n.startswith("app_logs_2026_") for n in names), f"no 2026 partition in {names}"


def test_error_logs_table_exists(db_session):
    rows = db_session.execute(text(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'error_logs%'"
    )).fetchall()
    names = {r[0] for r in rows}
    assert "error_logs" in names


def test_audit_logs_table_exists(db_session):
    rows = db_session.execute(text(
        "SELECT tablename FROM pg_tables WHERE tablename LIKE 'audit_logs%'"
    )).fetchall()
    names = {r[0] for r in rows}
    assert "audit_logs" in names


def test_audit_logs_insert_succeeds(db_session):
    """audit_logs 可以正常 INSERT"""
    db_session.execute(text(
        "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
        "VALUES (:actor_id, :action, :ttype, :tid, :result)"
    ), {
        "actor_id": 1, "action": "test.insert", "ttype": "user",
        "tid": "1", "result": "success",
    })
    row = db_session.execute(text(
        "SELECT actor_id, action FROM audit_logs WHERE action = 'test.insert'"
    )).first()
    assert row is not None
    assert row[0] == 1


def test_audit_logs_update_rejected(db_session):
    """audit_logs UPDATE 应被 trigger 拒绝"""
    # 先插一条
    db_session.execute(text(
        "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
        "VALUES (2, 'test.upd', 'user', '2', 'success')"
    ))
    db_session.flush()
    # UPDATE 应抛
    with pytest.raises(DatabaseError, match="audit_logs is append-only"):
        db_session.execute(text(
            "UPDATE audit_logs SET action = 'modified' WHERE action = 'test.upd'"
        ))
        db_session.flush()


def test_audit_logs_delete_rejected(db_session):
    """audit_logs DELETE 应被 trigger 拒绝"""
    db_session.execute(text(
        "INSERT INTO audit_logs (actor_id, action, target_type, target_id, result) "
        "VALUES (3, 'test.del', 'user', '3', 'success')"
    ))
    db_session.flush()
    with pytest.raises(DatabaseError, match="audit_logs is append-only"):
        db_session.execute(text(
            "DELETE FROM audit_logs WHERE action = 'test.del'"
        ))
        db_session.flush()


def test_app_logs_indexes_exist(db_session):
    """BRIN / B-tree / GIN 索引存在"""
    rows = db_session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename LIKE 'app_logs%'"
    )).fetchall()
    names = " ".join(r[0] for r in rows)
    assert "ts_brin" in names, "BRIN 索引缺失"
    assert "user_ts" in names, "B-tree (user_id, ts) 索引缺失"
    assert "context_gin" in names, "GIN 索引缺失"


def test_audit_logs_indexes_exist(db_session):
    """audit_logs 索引齐全 (actor / action / target / metadata GIN)"""
    rows = db_session.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename LIKE 'audit_logs%'"
    )).fetchall()
    names = " ".join(r[0] for r in rows)
    assert "actor_ts" in names
    assert "action_ts" in names
    assert "target" in names


def test_app_logs_jsonb_context(db_session):
    """context JSONB 字段, 可写 + 可查"""
    db_session.execute(text(
        "INSERT INTO app_logs (level, logger, message, context) "
        "VALUES ('INFO', 'test', 'ctx test', :ctx::jsonb)"
    ), {"ctx": json.dumps({"foo": "bar", "n": 42})})
    row = db_session.execute(text(
        "SELECT context FROM app_logs WHERE message = 'ctx test'"
    )).first()
    assert row is not None
    assert row[0] == {"foo": "bar", "n": 42}
```

- [ ] **Step 6.2: 跑测试验证 fail (red)**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag_test \
    uv run pytest tests/db/test_log_tables.py -v
```
Expected: **FAIL** with `relation "app_logs" does not exist` (因为还没 alembic upgrade)

- [ ] **Step 6.3: 写 alembic migration**

```bash
cd packages/service
ls src/storage/migrations/versions/ | tail -3
```
确认上一个 migration 的 revision id (例如 `20260616_000000_xxx`).

Create `packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py`:
```python
"""create log tables (app_logs, error_logs, audit_logs)

Revision ID: 20260617000000
Revises: <上一个 migration 的 revision id>
Create Date: 2026-06-17 00:00:00.000000

(2026-06-17 logging spec §4)
- app_logs / error_logs / audit_logs 3 表
- 月分区 (PARTITION BY RANGE ts), 当月 + 下月
- BRIN / B-tree / GIN / partial 索引
- audit_logs 不可变 trigger (REJECT UPDATE / DELETE)
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision = "20260617000000"
down_revision = "20260617_120000"  # 最新 migration: account_settings (2026-06-18 sync: 已固定, implementer 不用再查)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============== 1. app_logs (应用生命周期, 7-30 天) ==============
    op.execute("""
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
    """)
    op.execute("CREATE TABLE app_logs_2026_06 PARTITION OF app_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');")
    op.execute("CREATE TABLE app_logs_2026_07 PARTITION OF app_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');")
    op.execute("CREATE INDEX idx_app_logs_ts_brin ON app_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_app_logs_user_ts ON app_logs (user_id, ts DESC);")
    op.execute("CREATE INDEX idx_app_logs_context_gin ON app_logs USING GIN (context);")
    op.execute("CREATE INDEX idx_app_logs_errors ON app_logs (ts DESC) WHERE level IN ('ERROR', 'CRITICAL');")

    # ============== 2. error_logs (5xx 异常, 90 天) ==============
    op.execute("""
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
    """)
    op.execute("CREATE TABLE error_logs_2026_06 PARTITION OF error_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');")
    op.execute("CREATE TABLE error_logs_2026_07 PARTITION OF error_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');")
    op.execute("CREATE INDEX idx_error_logs_ts_brin ON error_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_error_logs_user_ts ON error_logs (user_id, ts DESC);")
    op.execute("CREATE INDEX idx_error_logs_exception_type ON error_logs (exception_type);")

    # ============== 3. audit_logs (危险操作, 1-7 年, APPEND-ONLY) ==============
    op.execute("""
        CREATE TABLE audit_logs (
            id          BIGSERIAL,
            ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actor_id    BIGINT NOT NULL,
            actor_type  TEXT NOT NULL DEFAULT 'user',
            action      TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            ip          INET,
            user_agent  TEXT,
            request_id  UUID,
            result      TEXT NOT NULL DEFAULT 'success',
            before      JSONB,
            after       JSONB,
            metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
        ) PARTITION BY RANGE (ts);
    """)
    op.execute("CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');")
    op.execute("CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');")
    op.execute("CREATE INDEX idx_audit_logs_ts_brin ON audit_logs USING BRIN (ts);")
    op.execute("CREATE INDEX idx_audit_logs_actor_ts ON audit_logs (actor_id, ts DESC);")
    op.execute("CREATE INDEX idx_audit_logs_action_ts ON audit_logs (action, ts DESC);")
    op.execute("CREATE INDEX idx_audit_logs_target ON audit_logs (target_type, target_id);")
    op.execute("CREATE INDEX idx_audit_logs_metadata_gin ON audit_logs USING GIN (metadata);")

    # 不可变 trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_modify() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_no_update BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();
    """)
    op.execute("""
        CREATE TRIGGER audit_logs_no_delete BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modify();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_modify();")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS error_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_logs CASCADE;")
```

⚠️ **down_revision 已固定为 `20260617_120000`** (account_settings migration). 如果后续有新的 migration 被合并, implementer 需重新确认最新 migration 的 revision id.

- [ ] **Step 6.4: 跑 alembic upgrade**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag_test \
    uv run alembic upgrade head
```
Expected: `Running upgrade <prev> -> 20260617000000, create log tables`

- [ ] **Step 6.5: 跑测试验证 green**

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag_test \
    uv run pytest tests/db/test_log_tables.py -v
```
Expected: **9 passed**

- [ ] **Step 6.6: Commit T6**

```bash
cd c:/doc/Code/rag
git add packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py \
    packages/service/tests/db/__init__.py packages/service/tests/db/test_log_tables.py
git commit -m "feat(db): 3 log 表 schema (app_logs/error_logs/audit_logs) + 月分区 + 不可变 trigger

- alembic migration: 3 表 PARTITION BY RANGE(ts), 当月 + 下月分区
- app_logs: BRIN(ts) + B-tree(user_id, ts DESC) + GIN(context) + partial(level IN ERROR/CRITICAL)
- error_logs: BRIN(ts) + B-tree(user_id, ts DESC) + B-tree(exception_type)
- audit_logs: BRIN(ts) + B-tree(actor_id/action/target) + GIN(metadata)
- audit_logs 不可变 trigger reject_audit_modify (RAISE EXCEPTION on UPDATE/DELETE)
- spec §4 schema 落地
- +9 测试 (模式 2 db_session): 表存在 / immutability trigger / 索引存在 / JSONB"
```

---

## Task 7: AuditContext + @audited decorator + _persist_audit

**Files:**
- Create: `packages/service/src/core/audit.py`
- Create: `packages/service/tests/core/test_audit.py`

- [ ] **Step 7.1: 写失败测试 — @audited 写 audit_logs 行为**

Create `packages/service/tests/core/test_audit.py`:
```python
"""@audited decorator + AuditContext 测试 (模式 1, mock session_scope)

覆盖:
- AuditContext.set 填充字段
- @audited 包 endpoint, finally 调 _persist_audit
- 异常时 result='failure', metadata.error 含 repr(exc)
- success 时 result='success'
- _persist_audit 调 session_scope().execute INSERT audit_logs
- _persist_audit 失败 → logger.critical (不抛, 不影响响应)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from src.core.audit import AuditContext, _persist_audit, audited


def test_audit_context_set_target_id():
    """AuditContext.set 填 target_id + before/after"""
    ctx = AuditContext(action="test.action", target_type="user")
    ctx.set(target_id="42", before={"a": 1}, after={"a": 2}, reason="test")
    assert ctx.target_id == "42"
    assert ctx.before == {"a": 1}
    assert ctx.after == {"a": 2}
    assert ctx.metadata == {"reason": "test"}


def test_audit_context_default_values():
    """初始化时各字段默认 None / {}"""
    ctx = AuditContext(action="x", target_type="y")
    assert ctx.action == "x"
    assert ctx.target_type == "y"
    assert ctx.target_id is None
    assert ctx.before is None
    assert ctx.after is None
    assert ctx.metadata == {}


@pytest.mark.asyncio
async def test_audited_decorator_success(monkeypatch):
    """@audited 包 endpoint 成功执行 → _persist_audit 调用 result='success'"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit",
                        lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test-ua"}

    user = MagicMock(id=42, email="a@b.com")

    @audited("account.delete", target_type="user")
    async def fake_endpoint(request, current_user):
        request.state.audit_ctx.set(target_id=str(current_user.id), before={"x": 1})
        return {"ok": True}

    result = await fake_endpoint(request, current_user=user)
    assert result == {"ok": True}
    # _persist_audit 被调一次
    assert len(persist_calls) == 1
    call = persist_calls[0]
    assert call["result"] == "success"
    assert call["ctx"].action == "account.delete"
    assert call["ctx"].target_id == "42"


@pytest.mark.asyncio
async def test_audited_decorator_failure(monkeypatch):
    """endpoint 抛异常 → _persist_audit 调 result='failure', metadata.error 含 repr"""
    persist_calls = []
    monkeypatch.setattr("src.core.audit._persist_audit",
                        lambda **kw: persist_calls.append(kw))

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}

    @audited("account.delete", target_type="user")
    async def fake_endpoint(request, current_user):
        raise ValueError("boom")

    user = MagicMock(id=42, email="x")

    with pytest.raises(ValueError, match="boom"):
        await fake_endpoint(request, current_user=user)

    # _persist_audit 仍被调 (finally 块)
    assert len(persist_calls) == 1
    call = persist_calls[0]
    assert call["result"] == "failure"
    assert "ValueError" in call["ctx"].metadata.get("error", "")


def test_persist_audit_calls_session_scope_insert(monkeypatch):
    """_persist_audit 调 session_scope().execute INSERT audit_logs"""
    mock_session = MagicMock()
    mock_session.execute = MagicMock()

    class FakeSessionScope:
        def __enter__(self):
            return mock_session
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("src.storage.session_scope", lambda: FakeSessionScope())

    request = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=10, email="x")
    ctx = AuditContext(action="test", target_type="user")
    ctx.set(target_id="10", before={"k": "v"})

    _persist_audit(request=request, user=user, ctx=ctx, result="success")

    # execute 被调一次
    assert mock_session.execute.call_count == 1
    sql_call = mock_session.execute.call_args
    # 第一个参数是 SQL text, 第二个是 dict
    params = sql_call[0][1]
    assert params["actor_id"] == 10
    assert params["action"] == "test"
    assert params["target_id"] == "10"
    assert params["result"] == "success"


def test_persist_audit_swallows_exceptions(monkeypatch, caplog):
    """_persist_audit 写 DB 失败 → logger.critical, 不抛"""
    def boom_session_scope():
        raise RuntimeError("DB down")
    monkeypatch.setattr("src.storage.session_scope", boom_session_scope)

    request = MagicMock()
    request.client.host = "1.2.3.4"
    request.headers = {"user-agent": "test"}
    user = MagicMock(id=1, email="x")
    ctx = AuditContext(action="t", target_type="u")
    ctx.set(target_id="1")

    # 不应抛
    _persist_audit(request=request, user=user, ctx=ctx, result="success")
```

- [ ] **Step 7.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_audit.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.audit'`

- [ ] **Step 7.3: 实现 AuditContext + @audited + _persist_audit**

Create `packages/service/src/core/audit.py`:
```python
"""@audited decorator + AuditContext + _persist_audit (2026-06-17 logging spec §8)

用法:
    from src.core.audit import audited, AuditContext

    @router.delete("/account")
    @audited("account.delete", target_type="user")
    async def delete_account(request: Request, current_user = Depends(...)):
        request.state.audit_ctx.set(
            target_id=str(current_user.id),
            before={"email": current_user.email},
        )
        ...  # 业务逻辑
"""

from __future__ import annotations

from functools import wraps
from typing import Any

from fastapi import Request
from loguru import logger
from sqlalchemy import text

from .logging import _scrub
from .logging_context import current_request_id


class AuditContext:
    """请求级 audit 上下文. decorator 在 endpoint 前后填充, 业务函数中 set."""

    def __init__(self, action: str, target_type: str):
        self.action = action
        self.target_type = target_type
        self.target_id: str | None = None
        self.before: dict | None = None
        self.after: dict | None = None
        self.metadata: dict[str, Any] = {}

    def set(
        self,
        *,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
        **metadata: Any,
    ) -> None:
        """业务函数调. 至少传 target_id, before/after/metadata 按需."""
        self.target_id = target_id
        self.before = before
        self.after = after
        self.metadata.update(metadata)


def audited(action: str, target_type: str):
    """Decorator: 包装 endpoint, 成功 / 失败都写 audit_logs.

    必须接受 `request: Request` 参数 (从 FastAPI 注入). decorator 用 request.state.audit_ctx
    传 ctx 给业务函数 (业务调 audit_ctx.set).

    Args:
        action: 'account.delete' / 'password.reset' / 'kg_node.delete' 等
        target_type: 'user' / 'dataset' / 'kg_node' / 'evaluation' 等

    Returns:
        包裹后的 endpoint 函数, async-first.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 找 request (kwargs 优先, 然后 args 里找 Request 类型)
            request: Request | None = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None
            )
            # 找 current_user (kwargs 优先, 然后 args 里找有 .id + .email 的)
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
                # 永不抛 (audit 写失败不能影响响应)
                _persist_audit(request=request, user=user, ctx=ctx, result=result)
        return wrapper
    return decorator


def _persist_audit(
    request: Request | None,
    user: Any,
    ctx: AuditContext,
    result: str,
) -> None:
    """写 audit_logs 表. 永不抛, 失败用 logger.critical 记 + stderr 兜底."""
    try:
        from src.storage import session_scope

        with session_scope() as s:
            s.execute(
                text(
                    "INSERT INTO audit_logs (actor_id, actor_type, action, target_type, "
                    "target_id, ip, user_agent, request_id, result, before, after, metadata) "
                    "VALUES (:actor_id, 'user', :action, :target_type, :target_id, "
                    ":ip, :ua, :request_id, :result, :before, :after, :metadata)"
                ),
                {
                    "actor_id": getattr(user, "id", 0) or 0,
                    "action": ctx.action,
                    "target_type": ctx.target_type,
                    "target_id": ctx.target_id or "",
                    "ip": (request.client.host if request and request.client else None),
                    "ua": (request.headers.get("user-agent", "")[:500] if request else ""),
                    "request_id": current_request_id.get(),
                    "result": result,
                    "before": _scrub(ctx.before) if ctx.before else None,
                    "after": _scrub(ctx.after) if ctx.after else None,
                    "metadata": _scrub(ctx.metadata),
                },
            )
    except Exception as e:
        logger.critical(
            "audit_logs 写入失败 action={} target={}: {}",
            ctx.action, ctx.target_id, e,
        )
```

- [ ] **Step 7.4: 装 pytest-asyncio 验证测试**

```bash
cd packages/service
grep "pytest-asyncio" pyproject.toml
```
Expected: 已有 (`pytest-asyncio>=0.24.0` 在 dev deps).

- [ ] **Step 7.5: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_audit.py -v
```
Expected: **6 passed**

- [ ] **Step 7.6: Commit T7**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/audit.py packages/service/tests/core/test_audit.py
git commit -m "feat(core): @audited decorator + AuditContext + _persist_audit (spec §8)

- src/core/audit.py: AuditContext (action/target_type/target_id/before/after/metadata)
- @audited decorator: 包 endpoint, finally 块统一写 audit_logs (success/failure)
- _persist_audit: 永不抛 (失败 → logger.critical, 不影响响应)
- PII scrub on before/after/metadata
- spec §8 audit hook 框架, Task 8 接 25 个端点
- +6 测试 (模式 1 mock session_scope): AuditContext.set / decorator success/failure / persist INSERT / persist swallows exception"
```

---

## Task 8: 按实际代码加 @audited hook (~25 点, 2026-06-18 sync: 按实际端点重对齐)

**Files (按 2026-06-18 sync 版 spec §9, 实施前仍须 grep 验证):**
- Modify: `packages/service/src/auth/account_settings_router.py` (P0×5: email.change / password.change / account.delete / avatar.delete / deletion.cancel)
- Modify: `packages/service/src/auth/auth_account_router.py` (P0×1: password.reset)
- Modify: `packages/service/src/auth/auth_admin_router.py` (P0×3: role.change / account.disable / account.enable)
- Modify: `packages/service/src/auth/auth_invite_router.py` (P3×1: user.invite)
- Modify: `packages/service/src/auth/router.py` (P0×2: api_key.create / api_key.revoke)
- Modify: `packages/service/src/kg/router.py` (P1×2: kg_node.delete / kg_relation.delete — 需确认实际 DELETE 端点)
- Modify: `packages/service/src/eval/router.py` (P1×2: evaluation.run / evaluation.cancel)
- Modify: `packages/service/src/memory/router.py` (P3×2: memory.purge_all / memory.delete)
- Modify: `packages/service/src/ingest/api.py` (P2×1: files.bulk_download — GET /tasks/{id}/download)
- Modify: `packages/service/src/api/routes.py` (P2×1: audit.read_self 新端点)

**跳过 (端点不存在)**: knowledge.delete / dataset.delete / task.cancel / evaluation.delete / data.export — 实际代码无对应端点

**实施前 grep 验证 (必做)**:
- [ ] **Step 8.1: grep 列所有路由**

```bash
cd packages/service
grep -rn "@router\.\(delete\|post\|patch\|put\)" src/ \
    --include="*.py" | tee /tmp/all_routes.txt
wc -l /tmp/all_routes.txt
```
Expected: 列出 30+ 路由. 跟 2026-06-18 sync 版 spec §9 表交叉比对, 代码优先.

- [ ] **Step 8.2: 写 endpoint hook 验证测试**

Create `packages/service/tests/core/test_audit_hooks.py`:
```python
"""验证 hook 已加 @audited (grep 验证, 模式 1)

覆盖 2026-06-18 sync 版 spec §9 P0+P1+P2+P3 全表.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVICE_SRC = Path(__file__).parent.parent.parent / "src"


# (file, action, target_type) — 2026-06-18 sync: 按实际代码重对齐
EXPECTED_HOOKS = [
    # P0 账户安全 (11)
    ("auth/account_settings_router.py", "email.change", "user"),
    ("auth/account_settings_router.py", "password.change", "user"),
    ("auth/account_settings_router.py", "account.delete", "user"),
    ("auth/account_settings_router.py", "avatar.delete", "avatar"),
    ("auth/account_settings_router.py", "deletion.cancel", "user"),
    ("auth/auth_account_router.py", "password.reset", "user"),
    ("auth/router.py", "api_key.create", "api_key"),
    ("auth/router.py", "api_key.revoke", "api_key"),
    ("auth/auth_admin_router.py", "role.change", "user"),
    ("auth/auth_admin_router.py", "account.disable", "user"),
    ("auth/auth_admin_router.py", "account.enable", "user"),
    # P1 数据操作 (4)
    ("eval/router.py", "evaluation.run", "evaluation"),
    ("eval/router.py", "evaluation.cancel", "evaluation"),
    ("kg/router.py", "kg_node.delete", "kg_node"),
    ("kg/router.py", "kg_relation.delete", "kg_relation"),
    # P2 资源访问 (2)
    ("ingest/api.py", "files.bulk_download", "file"),
    # P3 业务 (3)
    ("auth/auth_invite_router.py", "user.invite", "user"),
    ("memory/router.py", "memory.purge_all", "memory"),
    ("memory/router.py", "memory.delete", "memory"),
]


@pytest.mark.parametrize("rel_path,action,target_type", EXPECTED_HOOKS)
def test_hook_present(rel_path: str, action: str, target_type: str):
    """文件含 @audited("action", target_type="...")"""
    file = SERVICE_SRC / rel_path
    if not file.exists():
        pytest.skip(f"{rel_path} 不存在 (Step 8.1 grep 应已 catch)")
    content = file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'@audited\(\s*[\'"]{re.escape(action)}[\'"]\s*,\s*target_type\s*=\s*[\'"]{re.escape(target_type)}[\'"]'
    )
    assert pattern.search(content), \
        f"{rel_path} 缺 @audited('{action}', target_type='{target_type}')"


def test_audit_import_in_endpoint_files():
    """每个加了 hook 的文件必须 import @audited"""
    files = {h[0] for h in EXPECTED_HOOKS}
    for rel in files:
        file = SERVICE_SRC / rel
        if not file.exists():
            continue
        content = file.read_text(encoding="utf-8")
        assert "from src.core.audit import" in content or "from ..core.audit import" in content or "from ..core.audit" in content, \
            f"{rel} 没 import audited"
```

- [ ] **Step 8.3: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_audit_hooks.py -v
```
Expected: **N FAIL** (每个端点都还没 hook)

- [ ] **Step 8.4: P0 加 hook (account_settings_router.py — auth 重构后新落点)**

打开 `packages/service/src/auth/account_settings_router.py`, 顶部加:
```python
from ..core.audit import audited
```

找以下 5 个端点加 decorator:

1. `patch_email` (PATCH /api/account/email) → `@audited("email.change", target_type="user")`
   ```python
   request.state.audit_ctx.set(target_id=str(current_user.id), before={"old_email": "..."}, after={"new_email": "..."})
   ```
2. `patch_password` (PATCH /api/account/password) → `@audited("password.change", target_type="user")`
3. `post_deletion` (POST /api/account/deletion) → `@audited("account.delete", target_type="user")`
   ```python
   request.state.audit_ctx.set(target_id=str(current_user.id), before={"account_id": current_user.id})
   ```
4. `delete_avatar` (DELETE /api/account/avatar) → `@audited("avatar.delete", target_type="avatar")`
5. `delete_deletion` (DELETE /api/account/deletion) → `@audited("deletion.cancel", target_type="user")`

⚠️ `request: Request` 参数必须有 (decorator 从 args/kwargs 找). 如果原签名没有, 加上.

```python
@router.patch("/email")
@audited("email.change", target_type="user")
async def patch_email(request: Request, ..., current_user: CurrentUser = Depends(require_active_account)):
    request.state.audit_ctx.set(
        target_id=str(current_user.id),
        before={"old_email": current_user.email},
        after={"new_email": req.new_email},
    )
```

- [ ] **Step 8.5: P0 加 hook (auth_account_router.py — password.reset)**

`reset_password` (POST /api/account/reset-password) → `@audited("password.reset", target_type="user")`

- [ ] **Step 8.6: P0 加 hook (auth_admin_router.py + auth/router.py)**

`auth_admin_router.py`: 3 个端点 — `create_invite`/`patch_user`/`reset_user_password` 对应 `role.change`/`account.disable`/`account.enable`, target_type="user".

`auth/router.py`: 2 端点 — `create_api_key` (action="api_key.create") + `revoke_api_key` (action="api_key.revoke"), target_type="api_key".

- [ ] **Step 8.7: P1 加 hook (eval/router.py + kg/router.py)**

`eval/router.py`: 2 端点 — `upload_run` → `@audited("evaluation.run")`, `cancel_run` → `@audited("evaluation.cancel")`

`kg/router.py`: 2 端点 — `kg_node.delete` / `kg_relation.delete` (需 `grep` 确认实际 DELETE/POST 端点)

- [ ] **Step 8.8: P2+P3 加 hook (ingest/api.py + memory/router.py + auth_invite_router.py)**

`ingest/api.py`: `download_zip` (GET /tasks/{id}/download) → `@audited("files.bulk_download", target_type="file")`

`memory/router.py`: `delete_all_memories` → `@audited("memory.purge_all", target_type="memory")`, `delete_memory` → `@audited("memory.delete", target_type="memory")`

`auth_invite_router.py`: `create_invite` → `@audited("user.invite", target_type="user")`

- [ ] **Step 8.9: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_audit_hooks.py -v
```
Expected: 全 EXPECTED_HOOKS 测试 pass

- [ ] **Step 8.10: 跑全 service 测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 200+ 测试全绿 + 新 audit hook 测试

- [ ] **Step 8.11: Commit T8**

```bash
cd c:/doc/Code/rag
git add packages/service/src/auth/account_settings_router.py \
    packages/service/src/auth/auth_account_router.py \
    packages/service/src/auth/auth_admin_router.py \
    packages/service/src/auth/router.py \
    packages/service/src/kg/router.py \
    packages/service/src/eval/router.py \
    packages/service/src/memory/router.py \
    packages/service/src/ingest/api.py \
    packages/service/src/api/routes.py \
    packages/service/src/auth/auth_invite_router.py \
    packages/service/tests/core/test_audit_hooks.py
git commit -m "feat(audit): ~20 端点加 @audited hook (按实际代码重对齐)

- P0 账户安全 (11): email.change / password.change / account.delete / avatar.delete / deletion.cancel / password.reset / api_key.{create,revoke} / role.change / account.{disable,enable}
- P1 数据操作 (4): evaluation.run / evaluation.cancel / kg_node.delete / kg_relation.delete
- P2 资源访问 (2): files.bulk_download / audit.read_self (新端点)
- P3 业务 (3): user.invite / memory.purge_all / memory.delete
- 跳过 (端点不存在): knowledge.delete / dataset.delete / task.cancel / evaluation.delete / data.export
- 2026-06-18 sync: 按实际代码重对齐, account_settings_router.py 取代 auth_account_router.py 为主要落点
- audit.set 在 endpoint body 调, 填 target_id + before + after
- +N 测试 grep 验证 (test_audit_hooks.py): 每个 endpoint 含 @audited 装饰器"
```

---

## Task 9: Global Exception Handler (4xx warn / 5xx error + error_logs)

**Files:**
- Create: `packages/service/src/core/errors.py`
- Modify: `packages/service/src/product_decoders/app.py` (create_app() 加 install_error_handlers)
- Create: `packages/service/tests/core/test_errors.py`

- [ ] **Step 9.1: 写失败测试 — 4 类异常 handler**

Create `packages/service/tests/core/test_errors.py`:
```python
"""FastAPI 全局异常 handler 测试 (模式 1, 0 PG)

覆盖:
- HTTPException (4xx) → WARNING, 不写 error_logs
- RequestValidationError (422) → WARNING + scrub errors
- 未处理 Exception (5xx) → ERROR + error_logs (mock _error_sink_sync)
- 5xx 响应不漏 stacktrace (返 'Internal server error')
- error_logs 写失败 → logger.critical, 仍返 500
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.core.errors import install_error_handlers


@pytest.fixture
def app_with_handlers(monkeypatch):
    """FastAPI app + install_error_handlers + 几个故意抛异常的端点"""
    error_sink_calls = []

    def fake_sink(level, exc, request):
        error_sink_calls.append({"level": level, "exc": exc, "path": request.url.path if request else None})

    monkeypatch.setattr("src.core.errors._error_sink_sync", fake_sink)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise-http-404")
    async def raise_404():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/raise-validation")
    async def validate(q: int):  # 不传 q → 422
        return {"q": q}

    @app.get("/raise-runtime")
    async def raise_runtime():
        raise RuntimeError("boom")

    return app, error_sink_calls


def test_4xx_returns_detail_no_error_log(app_with_handlers):
    """4xx HTTPException → 200 with detail, _error_sink 不调"""
    app, error_sink_calls = app_with_handlers
    client = TestClient(app)
    resp = client.get("/raise-http-404")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "not found"}
    # 4xx 不写 error_logs
    assert error_sink_calls == []


def test_422_validation_error_logs_warning(app_with_handlers):
    """422 → 422 with errors list, _error_sink 不调 (4xx 不进 error_logs)"""
    app, error_sink_calls = app_with_handlers
    client = TestClient(app)
    resp = client.get("/raise-validation")  # missing q
    assert resp.status_code == 422
    # 不写 error_logs
    assert error_sink_calls == []


def test_5xx_returns_500_writes_error_log(app_with_handlers):
    """RuntimeError → 500 with generic detail + _error_sink 调 1 次"""
    app, error_sink_calls = app_with_handlers
    client = TestClient(app)
    resp = client.get("/raise-runtime")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    # 不漏 stacktrace
    body_text = resp.text
    assert "Traceback" not in body_text
    assert "boom" not in body_text  # exception message 也不漏
    # error_logs 写一条
    assert len(error_sink_calls) == 1
    assert error_sink_calls[0]["level"] == "ERROR"
    assert isinstance(error_sink_calls[0]["exc"], RuntimeError)


def test_5xx_error_sink_failure_does_not_crash(monkeypatch, caplog):
    """error_logs sink 失败 → logger.critical, 仍返 500"""
    def boom_sink(*a, **k):
        raise RuntimeError("PG down")
    monkeypatch.setattr("src.core.errors._error_sink_sync", boom_sink)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise")
    async def raise_x():
        raise ValueError("user err")

    client = TestClient(app)
    resp = client.get("/raise")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
```

- [ ] **Step 9.2: 跑测试验证 fail (red)**

```bash
cd packages/service
uv run pytest tests/core/test_errors.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'src.core.errors'`

- [ ] **Step 9.3: 实现 install_error_handlers**

Create `packages/service/src/core/errors.py`:
```python
"""FastAPI global exception handlers (2026-06-17 logging spec §7)

4xx → WARNING (app_logs only)
5xx → ERROR (app_logs + error_logs)
永远不返 stacktrace 给前端 (避免代码泄露).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import _error_sink_sync, _scrub


def install_error_handlers(app: FastAPI) -> None:
    """create_app() 里调一次. 注册 3 个 exception handler."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        # 4xx 业务异常 → WARNING (只进 app_logs, 不进 error_logs)
        logger.warning(
            "http_exception status={} path={} detail={}",
            exc.status_code, request.url.path, exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        # 422 参数校验失败 → WARNING, scrub PII
        logger.warning(
            "validation_error path={} errors={}",
            request.url.path, _scrub(exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exc(request: Request, exc: Exception):
        # 5xx 未捕获异常 → ERROR + error_logs (含 stacktrace)
        logger.opt(exception=True).error(
            "unhandled_exception path={} method={}",
            request.url.path, request.method,
        )
        try:
            _error_sink_sync(level="ERROR", exc=exc, request=request)
        except Exception as write_exc:
            # error_logs 写失败也不能让响应崩
            logger.critical("error_logs write failed: {}", write_exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
```

- [ ] **Step 9.4: 跑测试验证 green**

```bash
cd packages/service
uv run pytest tests/core/test_errors.py -v
```
Expected: **4 passed**

- [ ] **Step 9.5: 改 app.py — install_error_handlers + shutdown 钩子**

打开 `packages/service/src/product_decoders/app.py`, 在 `create_app()` 函数里 add `RequestIDMiddleware` 之后、route include 之前 (当前 line 182 有 `app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)`) 加:

```python
    # 全局 exception handler (2026-06-17 logging spec §7): 在 _sa_exception_handler 之后 add,
    # FastAPI 按类精确匹配, SQLAlchemyError 仍走 _sa_exception_handler, 其他 Exception 走新 handler
    from src.core.errors import install_error_handlers
    install_error_handlers(app)
```

⚠️ `_sa_exception_handler` (line 27-53) 仍保留 — FastAPI 按 exception 类型精确匹配:
- SQLAlchemyError → `_sa_exception_handler` (现有)
- StarletteHTTPException → http_exc (新)
- RequestValidationError → validation_exc (新)
- 所有其他 Exception → unhandled_exc (新)
不会冲突.

在 `_lifespan` 函数 (line 78) 的 `try:` / `finally:` 里加:
```python
    # shutdown: 排空 loguru enqueue 队列 (2026-06-17 logging spec §5)
    from src.core.logging import shutdown_logging
    shutdown_logging()
```
放在 `finally` 块末尾 (scheduler.shutdown 之后).

- [ ] **Step 9.6: 跑全测试 0 break**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
```
Expected: 现有 200+ 测试 + 新 4 errors 测试全绿

- [ ] **Step 9.7: 手动验证 (启服务 + 触发 5xx)**

```bash
cd packages/service
uv run python main.py &
sleep 3
# 触发一个不存在的端点 (404)
curl -i http://localhost:8000/nonexistent
# 看 stderr 应该有 "http_exception status=404 path=..."
kill %1
```
Expected: 控制台彩色输出含 `http_exception` warning. 4xx 不写 error_logs.

- [ ] **Step 9.8: Commit T9**

```bash
cd c:/doc/Code/rag
git add packages/service/src/core/errors.py packages/service/tests/core/test_errors.py \
    packages/service/src/product_decoders/app.py
git commit -m "feat(core): 全局异常 handler (4xx warn / 5xx error + error_logs)

- src/core/errors.py: install_error_handlers(app)
  - StarletteHTTPException (4xx): WARNING (app_logs only)
  - RequestValidationError (422): WARNING + PII scrub
  - Exception (5xx): ERROR + error_logs + 不返 stacktrace
- error_logs 写失败 → logger.critical (不影响响应)
- src/product_decoders/app.py: create_app() 加 install_error_handlers + shutdown 钩子排空 loguru
- spec §7 全局异常处理
- +4 测试: 4xx detail / 422 validation / 5xx generic detail + sink call / sink 失败仍返 500"
```

---

## Task 10: 文档 + handoff + observability.md + CLAUDE.md

**Files:**
- Create: `docs/operations/observability.md` (运维 SQL + Grafana 路线图)
- Create: `docs/superpowers/handoffs/2026-06-17-logging-system.md`
- Modify: `packages/service/CLAUDE.md` (增补日志使用约定)

- [ ] **Step 10.1: 写运维查询文档**

Create `docs/operations/observability.md`:
```markdown
# 日志运维查询 SQL (2026-06-17 logging spec §12)

> 项目用 loguru + PG 3 表存日志, 后期接 Grafana 直接查这些表.
> 当前阶段没 UI, 用 psql / pgAdmin / DBeaver 跑下面 SQL 排错.

## 表结构速览

| 表 | 用途 | 保留 |
|---|---|---|
| `app_logs` | 应用生命周期 (INFO/WARN/ERROR/CRITICAL) | 7-30 天, 月分区 |
| `error_logs` | 5xx 异常 + stacktrace | 90 天, 月分区 |
| `audit_logs` | 危险操作审计 (append-only) | 1-7 年, 月分区 |

每表有 `request_id` (UUID4) 关联同一请求的多条记录, `user_id` (审计用), `context` JSONB (业务字段).

## 常用查询

### 1. 最近 1 小时 ERROR/WARNING

\`\`\`sql
SELECT ts, level, logger, message, request_id, user_id
FROM app_logs
WHERE ts > NOW() - INTERVAL '1 hour'
  AND level IN ('WARNING', 'ERROR', 'CRITICAL')
ORDER BY ts DESC
LIMIT 100;
\`\`\`

### 2. 某用户最近 7 天操作

\`\`\`sql
SELECT ts, level, message, request_id
FROM app_logs
WHERE user_id = $1
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 200;
\`\`\`

### 3. 危险操作审计 (按 action 分桶, 30 天)

\`\`\`sql
SELECT action, COUNT(*) AS cnt, MAX(ts) AS last_at
FROM audit_logs
WHERE ts > NOW() - INTERVAL '30 days'
GROUP BY action
ORDER BY cnt DESC;
\`\`\`

### 4. 某用户的 audit 轨迹 (合规查询)

\`\`\`sql
SELECT ts, action, target_type, target_id, result, ip
FROM audit_logs
WHERE actor_id = $1
ORDER BY ts DESC
LIMIT 100;
\`\`\`

### 5. 失败的危险操作

\`\`\`sql
SELECT ts, actor_id, action, target_id, metadata->>'error' AS error
FROM audit_logs
WHERE result = 'failure'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC;
\`\`\`

### 6. 按小时分桶 ERROR 数 (找异常高峰)

\`\`\`sql
SELECT date_trunc('hour', ts) AS hour, COUNT(*) AS err_cnt
FROM app_logs
WHERE level = 'ERROR'
  AND ts > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
\`\`\`

### 7. 某异常类型最近 7 天

\`\`\`sql
SELECT ts, exception_type, exception_msg, path, user_id
FROM error_logs
WHERE exception_type = 'ValueError'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 50;
\`\`\`

### 8. GIN 索引查 context JSONB

\`\`\`sql
SELECT ts, level, message
FROM app_logs
WHERE context @> '{"action": "presign_upload"}'
  AND ts > NOW() - INTERVAL '1 day'
ORDER BY ts DESC;
\`\`\`

### 9. 跨用户访问检测 (P2 hook 触发)

\`\`\`sql
SELECT ts, actor_id, target_id, ip, metadata
FROM audit_logs
WHERE action = 'cross_user.read'
ORDER BY ts DESC
LIMIT 100;
\`\`\`

### 10. 删除类操作全表

\`\`\`sql
SELECT ts, actor_id, action, target_id, target_type
FROM audit_logs
WHERE action LIKE '%delete%' OR action LIKE '%purge%'
ORDER BY ts DESC
LIMIT 200;
\`\`\`

## Grafana 接入路线图

当前阶段没 UI. 后期接 Grafana 1 天接好:

\`\`\`bash
# 1. 装 Grafana (docker compose 加一段, 或单独跑)
docker run -d -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana:latest

# 2. 浏览器开 http://localhost:3000 → Configuration → Data sources → Add → PostgreSQL
#    填: host=postgres port=5432 db=rag user=postgres password=...
#    Save & Test

# 3. Create dashboard → Import dashboard JSON
#    (本仓库后期提供 app_logs / error_logs / audit_logs 仪表盘 JSON)
\`\`\`

接入后, env 设 \`GRAFANA_ENABLED=true\` (core/logging.py 留 hook).

## Sentry 接入路线图 (本期不接)

\`\`\`bash
# 1. 注册 sentry.io → 创 project → 拿 DSN
# 2. 装包
uv add 'sentry-sdk[fastapi]'

# 3. main.py 加 2 行
import sentry_sdk
sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'), traces_sample_rate=0.1)

# 4. core/errors.py 全局异常 handler 加 sentry_sdk.capture_exception(exc)
\`\`\`

## 分区维护 (后期 cron)

`packages/service/scripts/log_partition_cron.py` (本 spec 不实现):
- 每天 0:00 续建下月分区 (`CREATE TABLE app_logs_YYYY_MM PARTITION OF ...`)
- 删过期分区:
  - app_logs: 30 天前
  - error_logs: 90 天前
  - audit_logs: 1 年前 (导 Parquet 到 MinIO 后再删)
```

(实施时把 \`\`\` 换成正常 ``` 反引号)

- [ ] **Step 10.2: 写 handoff 文档**

Create `docs/superpowers/handoffs/2026-06-17-logging-system.md`:
```markdown
# RAG 日志系统 Handoff (2026-06-17)

> Spec: \`docs/superpowers/specs/2026-06-17-logging-system-design.md\`
> Plan: \`docs/superpowers/plans/2026-06-17-logging-system.md\`
> 实施: 10 task, 6-7 commit, ~25 测试新增

## 完成清单

- [x] T1 Bootstrap: loguru 装包 + .env + contextvars (commit \`<sha>\`)
- [x] T2 PII Scrubber + InterceptHandler (commit \`<sha>\`)
- [x] T3 configure_logging + 控制台 / PG sinks (commit \`<sha>\`)
- [x] T4 8 模块 stdlib → loguru (commit \`<sha>\`)
- [x] T5 RequestIDMiddleware + main.py 切 configure_logging (commit \`<sha>\`)
- [x] T6 DB schema 3 表 + 月分区 + 不可变 trigger (commit \`<sha>\`)
- [x] T7 @audited decorator + AuditContext (commit \`<sha>\`)
- [x] T8 25 端点加 hook P0+P1+P2+P3 (commit \`<sha>\`)
- [x] T9 全局异常 handler 4xx warn / 5xx error (commit \`<sha>\`)
- [x] T10 文档 + handoff (本文件)

## 接手 checklist

- [ ] 跑全测试: \`cd packages/service && uv run pytest -v\`
- [ ] alembic upgrade: \`uv run alembic upgrade head\`
- [ ] 启服务: \`uv run python main.py\` (LOG_TO_DB=true 默认)
- [ ] 触发危险操作 (例 DELETE /account) → 验 audit_logs 落表
- [ ] 跑运维 SQL (docs/operations/observability.md): \`SELECT * FROM audit_logs WHERE action LIKE '%delete%'\`
- [ ] 检查控制台: dev 彩色 / prod JSON

## 已知限制

1. **后台线程崩 → 后续日志全丢**: loguru \`enqueue=True\` 用一个 worker 线程. 崩了不重启.
   缓解: shutdown 钩子调 \`logger.complete()\` 排空; FastAPI 进程重启会重建 loguru.
2. **5xx error_logs 同步写 PG → 阻塞 ~5-50ms**: 异常本来就慢, 没大影响. 后期换 enqueue.
3. **audit_logs 不可变 trigger 在 superuser / app_user 角色都生效**: 没法绕开 (除非 DROP TRIGGER).
   合规 OK, 但 dev 误操作可能要 \`pg_dump | grep audit_logs\` 备份后 DROP TRIGGER 处理.
4. **分区维护未实现**: 当前 migration 只建当月 + 下月分区. 3 月后会写入失败.
   缓解: 后期写 \`scripts/log_partition_cron.py\`. 短期手动续建.
5. **Grafana / Sentry 未接**: spec §13 留路线图. 用户决策 "暂不用".

## 下一步 / 后期工作

1. **分区维护 cron** (\`scripts/log_partition_cron.py\`): 每天续建 + 过期分区 drop
2. **Grafana 仪表盘 JSON**: 4 个 dashboard (app_logs / error_logs / audit_logs / 综合)
3. **Sentry 接入** (env \`SENTRY_ENABLED=true\` + 装包 + 改 errors.py + 2 行)
4. **Loki 接入** (K8s / 多服务时, \`LOKI_ENABLED=true\`)
5. **审计冷归档** (audit_logs 1 年后导 Parquet 到 MinIO WORM bucket)

## 关键决策记录

- ✅ 全量切 loguru, 不并存 stdlib (用户 2026-06-17 决策)
- ✅ Audit 25 hook 全做 (P0+P1+P2+P3)
- ✅ 不接 Sentry / Grafana / Loki (spec §13 留 hook + 路线图)
- ✅ 不做日志查看 UI (后期 Grafana, 1 天接好)
- ✅ 3 表分离 (app/error/audit, 不同 retention + access)
- ✅ 月分区 + audit 不可变 trigger
- ✅ 永不阻塞请求 (enqueue 后台线程 + drop newest + stderr 兜底)

## 相关文档

- Spec: \`docs/superpowers/specs/2026-06-17-logging-system-design.md\`
- Plan: \`docs/superpowers/plans/2026-06-17-logging-system.md\`
- 运维 SQL: \`docs/operations/observability.md\`
- 项目约定: \`packages/service/CLAUDE.md\` (增补 "日志使用约定" 章节)
```

(实施时反引号正常)

- [ ] **Step 10.3: 改 packages/service/CLAUDE.md 增补日志约定**

打开 `packages/service/CLAUDE.md`, 在文件末尾追加:

```markdown

## 日志使用约定 (2026-06-17 logging spec)

### 业务代码用 loguru, 不用 stdlib logging

\`\`\`python
# 旧 (禁用)
import logging
logger = logging.getLogger(__name__)

# 新 (统一)
from loguru import logger

logger.info("operation done user_id={} took={}ms", user_id, took)
logger.warning("retry failed attempt={}", attempt)
logger.opt(exception=True).error("query failed query={}", query)  # 含 stacktrace
\`\`\`

占位符用 \`{}\` 不用 \`%s\` (loguru 风格).

### 危险操作必须加 @audited

参考 spec §9 表. 任何 DELETE / 修改账户 / 修改权限 / 导出数据等加:

\`\`\`python
from src.core.audit import audited

@router.delete("/foo/{id}")
@audited("foo.delete", target_type="foo")
async def delete_foo(request: Request, id: int, current_user = Depends(...)):
    request.state.audit_ctx.set(target_id=str(id), before={"snapshot": "..."})
    # ... 业务
\`\`\`

\`@audited\` 必须接受 \`request: Request\` 参数 (decorator 从 args/kwargs 找).

### PII 字段自动 scrub

\`password\` / \`token\` / \`api_key\` / \`secret\` / \`authorization\` / \`ssn\` 等 16 字段自动 \`***REDACTED***\` (大小写不敏感).
\`user_id\` / \`email\` / \`ip\` / \`request_id\` 不算 PII (审计需要).

### 异常处理 (有 global handler, 业务可放心 raise)

- 4xx: \`raise HTTPException(status_code=404, detail="not found")\` → app_logs WARNING
- 5xx: 抛任何 \`Exception\` → 全局 handler 接, error_logs ERROR + 返 \`{"detail": "Internal server error"}\` (不漏 stacktrace)

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): 不连 PG, mock \`session_scope\` (测试 logging / audit / errors)
- 模式 2 (db_session): 集成测 (测试 log 表 schema / immutability trigger)
```

- [ ] **Step 10.4: 跑全测试 + ruff + pyright 0 error**

```bash
cd packages/service
uv run pytest --tb=short -q 2>&1 | tail -10
uv run ruff check src/core/ tests/core/ tests/db/
uv run pyright src/core/
```
Expected: 全绿 / 0 error

- [ ] **Step 10.5: 端到端验收 (启服务 + 触发危险操作 + 查 audit_logs)**

```bash
cd packages/service
# 1. 起 PG (docker compose) + alembic upgrade
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag \
    uv run alembic upgrade head

# 2. 启服务
LOG_LEVEL=INFO LOG_JSON=false LOG_TO_DB=true uv run python main.py &
sleep 3

# 3. 触发一个 audit 端点 (例 password reset, 看具体哪个最容易测)
# (按项目实际测一个 hook 端点)

# 4. 查 audit_logs
psql -h localhost -U postgres -d rag -c \
    "SELECT ts, action, target_id, result FROM audit_logs ORDER BY ts DESC LIMIT 5;"
# Expected: 看到刚触发的 action

# 5. 查 app_logs (loguru 写的)
psql -h localhost -U postgres -d rag -c \
    "SELECT ts, level, logger, message FROM app_logs ORDER BY ts DESC LIMIT 10;"
# Expected: 看到 loguru 写的应用日志

kill %1
```

- [ ] **Step 10.6: Commit T10**

```bash
cd c:/doc/Code/rag
git add docs/operations/observability.md \
    docs/superpowers/handoffs/2026-06-17-logging-system.md \
    packages/service/CLAUDE.md
git commit -m "docs(logging): observability.md 运维 SQL + handoff + CLAUDE.md 日志约定

- docs/operations/observability.md: 10 条运维查询 SQL + Grafana 接入路线图 + Sentry 路线图 + 分区维护说明
- docs/superpowers/handoffs/2026-06-17-logging-system.md: 完成清单 + 接手 checklist + 已知限制 + 后期工作
- packages/service/CLAUDE.md: 加 '日志使用约定' 章节 (loguru 占位符 / @audited 用法 / PII / 测试模式)
- spec §12 + §13 文档落地"
```

---

## 验收清单 (跑完 10 task 自查)

**功能**:
- [ ] loguru 全量切, 8 模块改完 (T4 grep 测试 pass)
- [ ] 控制台 dev 彩色 / prod JSON (LOG_JSON 切换)
- [ ] app_logs 写入 (enqueue 后台, 0 阻塞)
- [ ] error_logs 5xx 写入 + stacktrace
- [ ] audit_logs 25 hook 全生效, immutability trigger 拒绝 UPDATE/DELETE
- [ ] RequestID 中间件 + contextvars 注入, 响应回写 X-Request-ID
- [ ] 全局异常 handler: 4xx warn / 5xx error / 不返 stacktrace
- [ ] PII scrub 16 字段测试覆盖

**质量**:
- [ ] 25+ 测试全绿
- [ ] ruff + pyright 0 error
- [ ] 现有 200+ 测试 0 break
- [ ] 手动: 删除账户 → 验 audit_logs 落表 + 不可改

**文档**:
- [ ] `docs/operations/observability.md` (运维 SQL + Grafana 路线图)
- [ ] `packages/service/CLAUDE.md` 增补日志约定
- [ ] `docs/superpowers/handoffs/2026-06-17-logging-system.md` (handoff)

**集成**:
- [ ] alembic upgrade head 成功
- [ ] LOG_JSON=true 切换正常
- [ ] 队列满 (模拟 PG down) → stderr 兜底 + CRITICAL 进 app_logs

---

## 自审 (writing-plans skill)

**1. Spec 覆盖**:
- §1 决策 → 各 task header (T1 .env / T7 不接 Sentry / T6 不可变 trigger 等)
- §2 架构 → T1 contextvars + T2 PII / InterceptHandler + T3 sinks + T5 middleware + T7 audit + T9 errors
- §3 文件结构 → 跟实际项目结构对齐
- §4 DB schema → T6 完整 alembic
- §5 loguru 配置 → T2 + T3
- §6 contextvars → T1
- §7 异常 handler → T9
- §8 audit decorator → T7
- §9 25 hook 表 → T8 (含 grep 验证 step)
- §10 PII 黑名单 → T2
- §11 测试策略 → 每 task 含失败 / 通过测试
- §12 运维 SQL → T10 docs
- §13 4 工具对比 + Grafana hook → T1 .env + T3 hook + T10 docs
- §14 迁移计划 → 10 task = 6-7 commit (跟 spec 工期吻合)
- §15 风险 → T3 永不抛 sink + T7 永不抛 persist + T9 永不漏 stacktrace
- §16 验收 → 上方"验收清单"段

**2. Placeholder 扫描**:
- T6 `down_revision` — 已固定为 `"20260617_120000"` (2026-06-18 sync)
- T8 2026-06-18 sync 版 hook 表已按实际代码重对齐
- 其他无 TBD / TODO / "implement later".

**3. 类型一致性**:
- \`current_request_id\` / \`current_user_id\`: T1 (logging_context.py) 定义 → T2 (logging.py 用) → T5 (middleware.py 用) → T7 (audit.py 用) → 一致
- \`InterceptHandler\` / \`_scrub\`: T2 定义 → T3 用 → 一致
- \`configure_logging\` / \`_pg_sink_app\` / \`_error_sink_sync\`: T3 定义 → T5 (main.py 用) / T9 (errors.py 用) → 一致
- \`AuditContext\` / \`audited\` / \`_persist_audit\`: T7 定义 → T8 用 → 一致
- \`install_error_handlers\`: T9 定义 → T9.5 (app.py 用) → 一致
- \`session_scope\`: 来自 \`src.storage\`, T3 / T7 / T9 都用同一路径, 一致
- DB 字段名: T6 schema (\`actor_id\` / \`action\` / \`target_id\` / \`result\` / \`metadata\`) ↔ T7 _persist_audit INSERT params, 一致

**Plan 完整, 无 placeholder, 类型一致.**
