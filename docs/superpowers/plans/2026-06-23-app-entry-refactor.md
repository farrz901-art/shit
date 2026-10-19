# 后端入口重构 + 字典自动 seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task.

**Goal:** 把 create_app/lifespan 从 product_decoders/app.py 抽出到 src/core/, decode/series 下沉到子模块, lifespan 中启动时自动 seed 字典.

**Architecture:** 4 新/改文件 + 1 删 + 15 测试文件 import 路径替换. create_app 搬走后与原签名一致.

---

## 任务分解

### Task 1: src/core/lifespan.py (新增)

**Files:**
- Create: packages/service/src/core/lifespan.py

- [ ] **Step 1: 创建 lifespan.py**

从 product_decoders/app.py _lifespan 搬来, 加上字典 seed / logging / redis. 需要读取 app.py 的 ConfigLoader + ProductDecoder 用于 decode 路由.

实际 lifespan 不含 ConfigLoader/ProductDecoder (它们在 decode 路由内按需创建).

```python
"""src/core/lifespan.py (2026-06-23)"""
from __future__ import annotations
import asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

_log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """FastAPI lifespan: startup = seed + health scheduler, shutdown = purge + logging + redis."""
    # STARTUP
    _setup_logging()
    _setup_redis()
    _setup_dictionaries()
    from src.health import start_health_loop
    task = asyncio.create_task(start_health_loop(interval_s=5.0))
    from src.scheduler import register_schedulers
    scheduler = register_schedulers()
    try:
        yield
    finally:
        # SHUTDOWN
        scheduler.shutdown(wait=False)
        await _stop_health_loop(task)
        from src.core.logging import shutdown_logging
        shutdown_logging()
        try:
            from src.core.redis_client import shutdown_redis
            await shutdown_redis()
        except Exception as exc:
            _log.warning('shutdown_redis err=%s', exc)


def _setup_logging():
    """loguru 初始化 (移植自 main.py)."""
    from src.core.logging import configure_logging
    configure_logging(
        json_console=os.getenv('LOG_JSON', 'false').lower() == 'true',
        write_to_db=os.getenv('LOG_TO_DB', 'true').lower() == 'true',
        level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    )


def _setup_redis():
    """Redis 连通性检查 (移植自 main.py)."""
    import socket
    try:
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        with socket.create_connection((host, port), timeout=2):
            pass
    except Exception as e:
        _log.warning('Redis warmup fail: %s (degraded mode)', e)


def _setup_dictionaries():
    """字典 seed + check + subscriber + warmup (移植自 main.py)."""
    # 1. seed
    try:
        from scripts.seed_dictionaries import run_seed
        d, i = run_seed()
        _log.info('dict seed: %s new dicts + %s new items', d, i)
    except Exception as e:
        _log.warning('dict seed fail: %s', e)
    # 2. check
    try:
        from scripts.check_dictionary_refs import check_consistency
        check_consistency()
    except RuntimeError:
        raise
    except Exception as e:
        _log.warning('dict check skip: %s', e)
    # 3. subscriber
    try:
        from src.lookups.cache import start_invalidation_subscriber
        start_invalidation_subscriber()
    except Exception as e:
        _log.warning('lookup subscriber fail: %s', e)
    # 4. warmup
    try:
        from src.permissions.cache import warmup_page_keys_sync
        keys = warmup_page_keys_sync()
        _log.info('page_keys warmup: %s pages', len(keys))
    except Exception as e:
        _log.warning('page_keys warmup fail: %s', e)


async def _stop_health_loop(task):
    from src.health import stop_health_loop
    await stop_health_loop(task)
```

- [ ] **Step 2: Run tests (no tests for this file yet, just verify import works)**

```bash
cd packages/service
python -c 'from src.core.lifespan import _lifespan; print("ok")'
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/core/lifespan.py
git commit -m "refactor: lifespan.py - startup/shutdown with auto dict seed"
```

### Task 2: src/core/app_factory.py (new)

**Files:**
- Create: packages/service/src/core/app_factory.py

- [ ] **Step 1: Create app_factory.py**

From product_decoders/app.py extract create_app(). Remove ConfigLoader/ProductDecoder.
Keep: FastAPI init, CORS, error handlers, middleware, register_routers, OpenAPI metadata.
Add: include decoder_router from product_decoders.router.

```python
"""src/core/app_factory.py: FastAPI factory (2026-06-23)"""
from __future__ import annotations
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.core.lifespan import _lifespan
from src.core.middleware import RequestIDMiddleware

async def _sa_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """SQLAlchemy global fallback (from old app.py)."""
    _log.error(...)
    return JSONResponse(status_code=500, content={"detail": f"DB error: {type(exc).__name__}"})

def create_app() -> FastAPI:
    app = FastAPI(title='RAG + ...', lifespan=_lifespan, ...)
    app.add_middleware(CORSMiddleware, ...)
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)
    app.add_middleware(RequestIDMiddleware)
    from src.core.errors import install_error_handlers
    install_error_handlers(app)
    from src import register_routers
    register_routers(app)
    from src.product_decoders.router import router as decoder_router
    app.include_router(decoder_router)
    return app
```

The full metadata, CORS config, OpenAPI tags etc. should be copied verbatim from the old app.py.

- [ ] **Step 2: Verify import**

`ash
cd packages/service


### Task 2: src/core/app_factory.py (new)

**Files:**
- Create: packages/service/src/core/app_factory.py

- [ ] **Step 1: Create app_factory.py**

From product_decoders/app.py extract create_app(). Remove ConfigLoader/ProductDecoder.
Keep: FastAPI init, CORS, error handlers, middleware, register_routers, OpenAPI metadata.
Add: include decoder_router from product_decoders.router.

```python
"""src/core/app_factory.py: FastAPI factory (2026-06-23)"""
from __future__ import annotations
import os, logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.core.lifespan import _lifespan
from src.core.middleware import RequestIDMiddleware

_log = logging.getLogger(__name__)


async def _sa_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _log.error('SQLAlchemy unhandled: %s %s', request.method, request.url.path, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": f"DB error: {type(exc).__name__}"})


def create_app() -> FastAPI:
    app = FastAPI(
        title='RAG + Product Decoder Service',
        description='...',
        lifespan=_lifespan,
        ... # full metadata from old app.py
    )
    # CORS
    allowed_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, ...)
    # Error handlers
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)
    app.add_middleware(RequestIDMiddleware)
    from src.core.errors import install_error_handlers
    install_error_handlers(app)
    # Routes
    from src import register_routers
    register_routers(app)
    from src.product_decoders.router import router as decoder_router
    app.include_router(decoder_router)
    return app
```

- [ ] **Step 2: Verify import**

```bash
cd packages/service
python -c 'from src.core.app_factory import create_app; print("ok")'
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/core/app_factory.py
git commit -m "refactor: app_factory.py - create_app factory"
```
### Task 3: src/product_decoders/router.py + __init__.py (create + update)

**Files:**
- Create: packages/service/src/product_decoders/router.py
- Delete: packages/service/src/product_decoders/app.py
- Modify: packages/service/src/product_decoders/__init__.py

- [ ] **Step 1: Create router.py**

Copy the 3 routes and schemas (DecodeRequest, SeriesInfo) from old app.py into a proper router:

```python
"""product_decoders/router.py (2026-06-23)"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .config_loader import ConfigLoader
from .engine import ProductDecoder

_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'configs' / 'product_decoders'
_CONFIGS_DIR = Path(os.environ.get('PRODUCT_DECODERS_CONFIGS', str(_CONFIGS_DIR)))
_loader = ConfigLoader(config_dir=str(_CONFIGS_DIR))
_decoder = ProductDecoder(_loader)

router = APIRouter(tags=['product-decoder'])

class DecodeRequest(BaseModel):
    model: str = Field(..., description='Full product code, e.g. 1LE0001-1AA42-1AA4')

class SeriesInfo(BaseModel):
    series: str; manufacturer: str; name: str; prefix: str

@router.post('/decode', summary='Decode product code')
async def decode(req: DecodeRequest):
    try:
        result = _decoder.decode(req.model)
        result['llm_view'] = _decoder.build_llm_view(result)
        return result
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

@router.get('/series', response_model=list[SeriesInfo])
async def list_series():
    return _decoder.list_series()

@router.get('/product-decoder/health')
async def decoder_health():
    return {'status': 'ok', 'series_count': len(_decoder.list_series())}
```

- [ ] **Step 2: Update __init__.py**

```python
# __init__.py -- remove create_app, add router
from .config_loader import ConfigLoader
from .engine import ProductDecoder
from .router import router, decode, list_series

__all__ = ['ConfigLoader', 'ProductDecoder', 'router']
```

- [ ] **Step 3: Delete app.py**

```bash
git rm packages/service/src/product_decoders/app.py
```

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/product_decoders/router.py
git add packages/service/src/product_decoders/__init__.py
git commit -m "refactor: move decode/series routes to product_decoders/router.py, delete app.py"
```
### Task 4: Update main.py (simplify)

**Files:**
- Modify: packages/service/main.py

- [ ] **Step 1: Replace create_app import**

```python
# Line 25: change import
from src.core.app_factory import create_app  # was: from src.product_decoders import create_app
```

- [ ] **Step 2: Remove 3 setup functions**

Delete _setup_logging(), _setup_redis(), _setup_dictionaries() from main.py.
These are now in src/core/lifespan.py and run automatically on startup.

- [ ] **Step 3: Simplify cmd_serve()**

```python
def cmd_serve(host, port, reload=True, no_kill_port=False):
    # 删掉 _setup_logging, _setup_redis, _setup_dictionaries 这三行
    # lifespan 内已包含
    if not no_kill_port:
        _kill_port_holder(port)
    uvicorn.run(create_app(), host=host, port=port, reload=reload)
```

- [ ] **Step 4: Verify**

```bash
cd packages/service
python -c 'from main import app; print("ok")'
```

- [ ] **Step 5: Commit**

```bash
git add packages/service/main.py
git commit -m "refactor: main.py - simplify, setup moved to lifespan"
```

### Task 5: Update 15 test files (import paths)

**Files:**
- Modify: 15 test files (mechanical import path change)

- [ ] **Step 1: Bulk sed replace**

```bash
cd packages/service
grep -rl "from src.product_decoders.app import create_app" tests/ | xargs sed -i "s/from src.product_decoders.app import create_app/from src.core.app_factory import create_app/g"
grep -rl "from src.product_decoders import create_app" tests/ | xargs sed -i "s/from src.product_decoders import create_app/from src.core.app_factory import create_app/g"
```

Also update src/__init__.py comment if it references old path:

```bash
sed -i 's|rag/product_decoders/app.py|src/core/app_factory.py|g' src/__init__.py
```

- [ ] **Step 2: Run pytest to verify all imports resolve**

```bash
cd packages/service
python -m pytest tests/ -x --co -q 2>&1 | head -20
# Should show all files collected, no import errors
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: update 15 test files import paths to src.core.app_factory"
```

### Task 6: seed_dictionaries.py - auto-insert role_permissions

**Files:**
- Modify: packages/service/scripts/seed_dictionaries.py

- [ ] **Step 1: Add _sync_page_key_permissions()**

After inserting a new page_key item, call _sync_page_key_permissions(key):

```python
from datetime import datetime
from src.permissions.models import RolePermission

def _sync_page_key_permissions(page_key: str):
    """Auto-insert role_permissions rows for new page_key."""
    log = logging.getLogger(__name__)
    with session_scope() as s:
        for role_name, allowed in [('user', False), ('admin', True)]:
            exists = s.execute(
                select(RolePermission).where(
                    RolePermission.role_name == role_name,
                    RolePermission.page_key == page_key,
                )
            ).first()
            if not exists:
                s.add(RolePermission(
                    role_name=role_name, page_key=page_key,
                    allowed=allowed,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ))
                log.info('auto-perm: role=%s page=%s allowed=%s', role_name, page_key, allowed)
```

In run_seed(), after inserting a page_key item, call this function.

- [ ] **Step 2: Run seed to verify**

```bash
cd packages/service
python -m scripts.seed_dictionaries
Expected: "0 new dicts + 0 new items" (already seeded)
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/scripts/seed_dictionaries.py
git commit -m "feat: seed_dictionaries auto-insert role_permissions for new page_key"
```

### Task 7: Remove redundant migration 20260623_000000

**Files:**
- Delete: packages/service/src/storage/migrations/versions/20260623_000000_add_buyers_permission.py

- [ ] **Step 1: Delete migration**

```bash
git rm packages/service/src/storage/migrations/versions/20260623_000000_add_buyers_permission.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove migration 20260623 - seed now auto-creates role_permissions"
```

### Task 8: Final verification

- [ ] **Run full test suite**

```bash
cd packages/service
uv run pytest -x --co -q
# Expected: all tests pass (0 new failures)
```

- [ ] **Run pyright**

```bash
uv run pyright
# Expected: 0 errors
```

- [ ] **Run ruff**

```bash
uv run ruff check --fix
uv run ruff format
```

---
