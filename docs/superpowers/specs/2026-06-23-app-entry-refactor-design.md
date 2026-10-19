# 后端入口重构 + 字典自动 seed 设计

**日期**: 2026-06-23
**状态**: 设计稿

---

## Context

### 问题

1. 入口混乱: product_decoders/app.py 混了 3 类职责
   - FastAPI 工厂 (create_app, CORS, error handlers, 路由注册)
   - 产品解码业务 (ConfigLoader, ProductDecoder, /decode, /series)
   - OpenAPI 元数据 (title, description, tags)
2. 启动流程不一致: 两个入口路径行为不同
   - uvicorn main:app -> create_app() lifespan -> 无字典 seed
   - python main.py serve -> cmd_serve() -> 有字典 seed
3. 字典 seed 不自动: 加页面需手动跑 seed_dictionaries
4. 15 个测试文件写死旧 import 路径

### 决策记录

| 决策 | 选择 | 原因 |
|---|---|---|
| 入口文件名 | main.py | 有 CLI 子命令 (ingest), 已有全项目引用 |
| create_app 位置 | src.core.app_factory | 跟业务无关,应对核心层 |
| lifespan 位置 | src.core.lifespan | 含字典 seed/health/shutdown |
| decode 路由 | src.product_decoders.router | 下沉子模块,业务内聚 |
| 字典 seed 方式 | lifespan 启动时自动跑 run_seed | 幂等,不用手动 CLI |
| role_permissions 补齐 | seed 脚本自动插 | 加 page_key 一行 yaml 搞定 |

---

## 目录结构

```
现在:
packages/service/
  main.py (271行)              -- 引导 + CLI
  src/product_decoders/
    app.py (287行)             -- create_app + decode/series 路由 + lifespan
    __init__.py               -- export create_app, ConfigLoader, ProductDecoder
    engine.py
    config_loader.py

改后:
packages/service/
  main.py (约 80行)            -- 仅引导 + CLI (瘦身)
  src/core/
    app_factory.py (新增)      -- create_app() 纯工厂
    lifespan.py (新增)         -- 启动/关闭 (seed + health + shutdown)
    errors.py (已有)
    middleware.py (已有)
  src/product_decoders/
    __init__.py (改)           -- export router
    router.py (新增)           -- /decode + /series 路由
    app.py (删)               -- 删除
    engine.py (不变)
    config_loader.py (不变)
```

---
## 组件设计

### src/core/app_factory.py

负责: 创建 FastAPI 实例 + 挂中间件 + 注册路由 + 挂 lifespan
不含: 任何业务 import (ConfigLoader/ProductDecoder)

```python
from src.core.lifespan import _lifespan
from src.core.errors import install_error_handlers
from src.core.middleware import RequestIDMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title=..., lifespan=_lifespan, ...)
    app.add_middleware(CORSMiddleware, ...)
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)
    app.add_middleware(RequestIDMiddleware)
    install_error_handlers(app)
    from src import register_routers
    register_routers(app)
    from src.product_decoders.router import router as decoder_router
    app.include_router(decoder_router)
    return app
```

OpenAPI description 和 tags 保留在 app_factory (框架元数据, 非业务).

### src/core/lifespan.py

负责: 启动/关闭钩子, 统一所有入口的启动行为

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # === STARTUP ===
    _setup_logging()            # loguru
    _setup_redis()             # Redis 连通性检查
    _setup_dictionaries()      # seed + check + warmup <-- 关键
    task = asyncio.create_task(start_health_loop(...))
    scheduler = register_schedulers()
    yield
    # === SHUTDOWN ===
    scheduler.shutdown()
    await stop_health_loop(task)
    shutdown_logging()
    await shutdown_redis()
```

_setup_dictionaries() 移植自当前 main.py, 4 步:
1. run_seed() - 字典 seed (幂等, 缺啥补啥)
2. check_consistency() - fail-fast 校验
3. start_invalidation_subscriber() - Redis 广播
4. warmup_page_keys_sync() - 预热权限缓存

### src/product_decoders/router.py

三条内联路由改为标准 FastAPI router:

```python
router = APIRouter(tags=['product-decoder'])

class DecodeRequest(BaseModel):
    model: str

class SeriesInfo(BaseModel):
    series: str
    manufacturer: str
    name: str
    prefix: str

@router.post('/decode', summary='解码订货号')
async def decode(req: DecodeRequest): pass

@router.get('/series', response_model=list[SeriesInfo])
async def list_series(): pass

@router.get('/product-decoder/health')
async def decoder_health(): pass
```

注意: 路由仍使用 app_factory 中 new 出的 ConfigLoader/ProductDecoder 实例,
通过 dependency injection 传入 (或用模块级单例).

### src/product_decoders/__init__.py (改)

```python
# 删 create_app export, 加 router
from .config_loader import ConfigLoader
from .engine import ProductDecoder
from .router import router

__all__ = ['ConfigLoader', 'ProductDecoder', 'router']
```

### main.py (瘦身)

```python
app = create_app()  # 模块级, uvicorn main:app 用

def cmd_serve():
    _kill_port_holder(port)
    uvicorn.run(app)  # lifespan 内已含 seed/logging/redis

def cmd_ingest():
    ...  # 不变
```

删除 _setup_logging, _setup_redis, _setup_dictionaries 三个函数.

---
## 测试改动

全部是 import 路径替换 (机械操作):

```python
# 改前
from src.product_decoders.app import create_app
# 改后
from src.core.app_factory import create_app

# 或改前
from src.product_decoders import create_app
# 改后
from src.core.app_factory import create_app
```

涉及 15 个文件:

| 文件 | 改动行数 |
|---|---|
| main.py | 2 (import + app = create_app()) |
| tests/auth/test_admin_users_api.py | 1 |
| tests/auth/test_admin_router_role.py | 1 |
| tests/auth/test_me.py | 1 |
| tests/auth/test_logout.py | 1 |
| tests/auth/test_login.py | 1 |
| tests/auth/test_seed_admin.py | 1 |
| tests/auth/test_invite_flow.py | 1 |
| tests/auth/test_password_reset.py | 1 |
| tests/auth/test_auth_cookie.py | 1 |
| tests/test_api_contract.py | 3 (3 处) |
| tests/ingest/test_web_apis.py | 1 |
| tests/product_decoders/test_product_decoder.py | 1 |
| tests/openapi/test_openapi_metadata.py | 1 |
| src/product_decoders/__init__.py | 1 |

test_main_cli.py 不需要改 (它 mock 而非 import).

---

## 字典自动 seed + 权限行补齐

### 修改 seed_dictionaries.py

在 run_seed() 的 page_key item 插入逻辑后, 加一步: 检测到新 page_key
时自动 INSERT role_permissions 行:

```python
def _sync_page_key_permissions(page_key: str):
    """确保 page_key 在 role_permissions 表里有行."""
    with session_scope() as s:
        for role_name in ('user', 'admin'):
            exists = s.execute(
                select(RolePermission).where(
                    RolePermission.role_name == role_name,
                    RolePermission.page_key == page_key,
                )
            ).first()
            if not exists:
                allowed = role_name == 'admin'  # admin=true, user=false
                s.add(RolePermission(
                    role_name=role_name, page_key=page_key,
                    allowed=allowed,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ))
```

这样加 page_key 后 role_permissions 自动补齐, 不需要 migration.

### 启动后流程

```
lifespan startup
  -> run_seed()
      -> 读 yaml -> UPSERT 字典 item
      -> 发现新 page_key -> INSERT role_permissions 行
  -> check_consistency()
  -> warmup_page_keys()
  -> 前端 GET /api/permissions/me 拿到新 page_key
  -> Header 渲染导航栏 -> 页面出现
```

---

## 安全与兼容

1. create_app() 签名不变, 测试全改 import 路径即通过
2. run_seed() 幂等, 已有数据不动
3. migration 20260623_000000 不再需要 (seed 自动补齐权限行)
   但已应用的 migration 脚本不影响运行
4. seed 失败不影响正常启动 (WARNING + 降级用 fallback)

---
