# FastAPI 教程

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 Python/TS 工程师，需要理解本项目为什么这样用、能怎么扩展

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

FastAPI 是一个基于 Python 类型注解的异步 Web 框架，由 Sebastián Ramírez 于 2018 年开源，2024-2025 年已成为 Python 社区最受欢迎的 REST API 框架之一。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **FastAPI** | 异步、类型安全、自动生成 OpenAPI 文档 | 社区活跃、性能好、类型安全 |
| **Flask** | 同步、轻量、生态成熟 | 缺少异步支持，依赖手动文档生成 |
| **Django** | 全栈、ORM 内置、大而全 | 太重，本项目后端只是 API 层 |
| **Starlette** | 底层 ASGI 框架 | FastAPI 基于 Starlette，但需要更多样板代码 |

**FastAPI 的核心卖点**：
- **类型驱动的 API 验证**：利用 Python 3.6+ 类型注解自动做请求校验 + 序列化，零模板代码
- **自动 OpenAPI 文档**：每个端点自动生成 Swagger UI（`/docs`）+ ReDoc（`/redoc`）
- **异步原生**：底层用 Starlette + asyncio，天然支持高并发 IO（数据库、HTTP、AI API 调用）
- **Pydantic 深度集成**：请求体/响应体模型自动校验、文档展示

**不适合什么**：前后端不分离的模板渲染（Django 更合适）、纯低延迟 TCP 服务（直接 asyncio 或 Go）。

---

## 二、安装 & 开发环境

### 2.1 版本要求

- Python ≥ 3.14（项目 `pyproject.toml` 要求）
- FastAPI ≥ 0.136.3（依赖 `pyproject.toml` 锁版本）

### 2.2 包管理

项目使用 `uv`（Rust 编写的 Python 包管理器，比 pip 快 10-100 倍）：

```bash
# 安装项目依赖
cd packages/service
uv sync

# 安装 fastapi（已配在 pyproject.toml，上面 uv sync 已包含）
# 单独验证版本
uv run python -c "import fastapi; print(fastapi.__version__)"
```

### 2.3 开发环境

项目推荐使用以下工具链：

- **IDE**：VSCode + Python extension（加载 `pyproject.toml` 自动识别 Python 解释器路径）
- **格式化**：`ruff format`（`uv run ruff format`）
- **Lint**：`ruff check`（`uv run ruff check --fix`）
- **类型检查**：`pyright`（`uv run pyright`，必须 0 error）
- **测试**：`pytest`（`uv run pytest`）

> ⚠️ 本项目的 CLAUDE.md 强制格式校验顺序：format → lint → pyright → pytest，不可颠倒。

---

## 三、基础语法 & 类型系统

### 3.1 类型注解基础

Python 3.10+ 类型注解在 FastAPI 中不仅仅是文档，它们驱动运行时校验：

```python
from __future__ import annotations  # 3.11+ 默认，3.10 需加

def greet(name: str, age: int = 18) -> dict[str, str | int]:
    return {"name": name, "age": age}
```

### 3.2 Pydantic 模型

FastAPI 用 Pydantic v2（内置在 FastAPI 中）定义请求和响应结构：

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="用户名")
    email: str = Field(..., pattern=r"^\S+@\S+\.\S+$")
    age: int = Field(default=18, ge=0, le=150)
```

项目中有大量这样的模型定义，例如 `src/middleware/auth.py:58-84`（简化为示意，`is_admin` 实际是 `@property`，非 Pydantic field）：

```python
class CurrentUser(BaseModel):
    id: int
    public_token: str
    role: str = "user"
    is_account: bool = False
    account_id: int | None = None
    email: str | None = None
    display_name: str | None = None
    is_active: bool = True
```

### 3.3 async/await

FastAPI 原生支持 async 路由，IO 密集型操作无需手动管理线程池：

```python
@app.get("/users/{id}")
async def get_user(id: int):
    async with async_session() as session:
        user = await session.get(User, id)
        return user
```

项目中的路由根据场景混用 async 和 sync 函数。IO 密集型操作（数据库、外部 API）用 async，纯计算走 sync。（FastAPI 自动在线程池中运行 sync 函数，不阻塞事件循环。）

### 3.4 Union 与 Optional

```python
from typing import Union  # 3.10+ 用 X | Y

def get_item(id: int, flag: bool | None = None) -> dict | list:
    ...
```

---

## 四、核心概念

### 4.1 路由（Router）

FastAPI 用 `APIRouter` 组织路由分组，每个模块一个 router 文件：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/system", summary="查询系统监控状态")
async def health_system():
    ...
```

项目中的 `src/health/router.py:15` 正是这样定义的。每个业务模块（auth、chat、ingest、kg 等）都有自己的 router。

### 4.2 依赖注入（Depends）

FastAPI 最核心的设计模式。`Depends` 实现声明式依赖管理和自动解析：

```python
from fastapi import Depends

async def get_current_user(token: str = Header(...)):
    # 解析 token → CurrentUser
    ...

@router.get("/profile")
async def profile(user = Depends(get_current_user)):
    return user
```

项目中 auth 模块广泛使用 `Depends(require_super_admin)`（`src/health/router.py:36`）做鉴权。

### 4.3 中间件（Middleware）

中间件在请求进入路由前和响应返回前各执行一次。项目注册了 2 个中间件：

```python
# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# RequestID 中间件（src/core/middleware.py）
app.add_middleware(RequestIDMiddleware)
```

配置参见 `src/core/app_factory.py:131-148`。

### 4.4 BackgroundTasks

FastAPI 内置轻量级后台任务，无需 Celery：

```python
from fastapi import BackgroundTasks

def write_log(message: str):
    ...

@router.post("/notify")
async def notify(background_tasks: BackgroundTasks):
    background_tasks.add_task(write_log, "操作已记录")
    return {"ok": True}
```

项目在多个模块使用了 `BackgroundTasks`（`src/ingest/api.py:21`、`src/eval/router.py:23`）。

### 4.5 Pydantic 模型与异常处理

FastAPI 自动做请求体校验，不合法的请求自动返回 422。项目注册了全局异常处理器：

```python
@app.exception_handler(RequestValidationError)
async def validation_exc(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
```

见 `src/core/errors.py:36-45`。

### 4.6 Lifespan（生命周期）

FastAPI 的 lifespan 替代了废弃的 startup/shutdown 事件：

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 启动
    _setup_logging()
    _setup_redis()
    yield
    # 关闭
    shutdown_logging()
    await shutdown_redis()
```

项目 `src/core/lifespan.py:155-198` 实现了完整的启动/关闭流程：logging 配置 → Redis 连通性探测 → 字典 seed → 健康检查循环 → 调度器注册。

---

## 五、常用命令 & 工具链

```bash
# 启动开发服务（主入口，自动清理占端口进程）
cd packages/service
uv run python main.py

# 同上，用 uvicorn 直起（调试时方便加 --reload）
uv run uvicorn main:app --reload --port 8000

# 访问文档
open http://localhost:8000/docs    # Swagger UI (Windows 用 start 替代 open)
open http://localhost:8000/redoc   # ReDoc

# 跑 ingest 离线任务
uv run python main.py ingest /path/to/dir

# 测试
uv run pytest
uv run pytest tests/test_api_contract.py  # 前后端契约测试
```

---

## 六、项目集成点

### 6.1 项目结构

```
packages/service/
├── main.py                     # 入口，uvicorn / CLI
├── pyproject.toml              # 依赖+工具配置
├── src/
│   ├── core/
│   │   ├── app_factory.py      # FastAPI 工厂 create_app()
│   │   ├── errors.py           # 全局异常处理器
│   │   ├── lifespan.py         # 启动/关闭生命周期
│   │   ├── middleware.py       # RequestID 中间件
│   │   ├── logging.py          # loguru 配置
│   │   └── redis_client.py     # Redis facade
│   ├── middleware/auth.py      # 鉴权 -> CurrentUser
│   ├── health/router.py        # 监控检查路由
│   ├── chat/router.py          # 聊天路由
│   ├── ingest/api.py           # 文档摄取路由
│   ├── kg/router.py            # 知识图谱路由
│   ├── auth/                   # 账号系统
│   ├── permissions/            # RBAC 权限
│   └── ...
```

### 6.2 配置入口

- **环境变量**：`.env.local`（`main.py:14` 在 import 前加载）
- **Settings 类**：`src/config/settings.py`
- **启动流程**：`main.py:24` → `create_app()` → 挂载所有 router → lifespan 初始化

### 6.3 API 前缀

项目路由按功能模块分配前缀：

| 路由模块 | 前缀 | 标签 |
|---------|------|------|
| health | `/api/health` | health |
| auth | `/api/auth` | auth |
| account | `/api/account` | account |
| chat | `/api/chat` | chat |
| ingest | `/api/ingest` | ingest |
| kg | `/api/kg` | kg |
| evaluate | `/api/evaluate` | evaluate |
| approvals | `/api/approvals` | approvals |
| memory | `/api/memory` | memory |
| permissions | `/api/permissions` | permissions |
| lookups | `/api/lookups` | lookups |

---

## 七、项目代码示例

### 7.1 应用工厂模式

`src/core/app_factory.py:53-169` 展示了 FastAPI 应用的标准工厂模式：

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG + 产品订货号解析服务",
        version="0.2.0",
        lifespan=_lifespan,
    )

    # CORS 中间件
    app.add_middleware(CORSMiddleware, allow_origins=allow_origins, ...)

    # 异常处理器
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)

    # RequestID 中间件
    app.add_middleware(RequestIDMiddleware)

    # 挂载路由
    from src.product_decoders.router import router as decoder_router
    app.include_router(decoder_router)

    from src import register_routers
    register_routers(app)

    return app
```

关键设计点：
- **无全局状态**：`create_app()` 是纯工厂，调用才创建实例，方便测试时创建不同的 app 对象
- **中间件注册有顺序**：CORS → Exception Handler → RequestID，顺序影响请求处理链

### 7.2 依赖注入鉴权

`src/health/router.py:18-37` 用 `Depends(require_super_admin)` 做鉴权：

```python
router = APIRouter(prefix="/api/health", tags=["health"])

@router.get(
    "/system",
    summary="查询系统监控状态",
    description="返回系统 5 类核心组件的聚合监控状态...",
    responses={
        200: {"description": "5 类检查的聚合结果"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin (权限不足)"},
    },
)
def health_system(_user: CurrentUser = Depends(require_super_admin)):
    return _cache.get_cached_health()
```

设计点：
- `Depends(require_super_admin)` 自动解析鉴权，路由函数只需关注业务逻辑
- `_user` 以下划线开头，虽未被函数体直接引用但必须声明——Depends 需要它来触发鉴权
- `responses` 字典为 OpenAPI 文档提供错误状态码说明

### 7.3 全局异常处理器

`src/core/errors.py:19-61` 注册三类异常处理器，确保不向客户端泄露 stacktrace：

```python
def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        logger.warning("http_exception status={} path={}", exc.status_code, request.url.path)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exc(request: Request, exc: RequestValidationError):
        logger.warning("validation_error path={}", request.url.path)
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_exc(request: Request, exc: Exception):
        logger.opt(exception=True).error("unhandled_exception path={}", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### 7.4 Lifespan 生命周期管理

`src/core/lifespan.py:155-198` 展示了完整的启动/关闭语义：

```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # ----- 启动 -----
    _setup_logging()              # 1. 配置 loguru
    _setup_redis()                # 2. Redis 连通性探测
    subscriber_task = _setup_dictionaries()  # 3. 字典 seed
    await _async_setup_dictionaries()        # 4. 字典一致性校验
    health_task = asyncio.create_task(
        start_health_loop(interval_s=5.0))   # 5. 健康检查循环
    scheduler = register_schedulers()        # 6. 定时任务
    try:
        yield
    finally:
        # ----- 关闭 (逆序) -----
        subscriber_task.cancel()
        scheduler.shutdown(wait=False)
        await stop_health_loop(health_task)
        shutdown_logging()
        await shutdown_redis()
```

设计原则：启动和关闭严格逆序，确保资源不泄漏。

### 7.5 测试用依赖覆盖

FastAPI 允许在测试时覆盖依赖，见项目测试中的常见模式：

```python
# 测试时用 mock 替换鉴权依赖
app.dependency_overrides[require_super_admin] = lambda: CurrentUser(
    id=1, is_admin=True, ...
)
```

---

## 八、项目没用到的能力 / 进阶方向

以下 FastAPI 能力项目当前未使用，但值得了解：

| 特性 | 用途 | 什么场景可能加 |
|------|------|---------------|
| **WebSocket** | 实时双向通信（聊天、进度推送） | 如果前端需要流式对话效果 |
| **FileResponse / StreamingResponse** | 流式返回大文件 | 当前大文件通过 MinIO presigned URL 直传 |
| **Sub-application / Mount** | 挂载独立 ASGI 应用 | 如果将来有独立的管理后台 API |
| **OAuth2 scopes** | 细粒度权限 | 当前用 `require_super_admin` 二值权限，复杂 RBAC 可用 scope |
| **GraphQL（通过 Strawberry）** | 灵活数据查询 | 前端需要自定义查询字段时 |
| **Jinja2 Templates** | 服务端渲染 HTML | 不会用——项目前端是 Next.js 独立部署 |
| **Dependency Overrides** | 测试时替换依赖 | 已经在测试中使用了（见 §7.5） |
| **Server-Sent Events** | 单向实时推送 | 日志/进度推送场景 |

**建议关注**：WebSocket 对于流式 AI 响应（token-by-token 输出）非常有用，如果后续集成 LLM streaming 可以考虑。

---

## 九、最佳实践 & 常见坑

### 项目风格指南

1. **每个 router 加 docstring**——FastAPI 会原样渲染成接口说明（项目 CLAUDE.md 强制）
2. **Pydantic model 加 `Field(description=...)`**——字段说明会进 schema
3. **`@router.post(..., response_model=..., summary="...")`**——summary 是接口标题
4. **按 tag 分组**——`@router.get(..., tags=["知识图谱"])`，文档侧边栏按业务模块折叠
5. **4xx 用 `HTTPException`，5xx 让全局 handler 接**——见 `src/core/errors.py`

### 常见坑

1. **循环 import 陷阱**：`src/middleware/auth.py` 不能顶层 import `src.auth.*`，因为 `src/auth/__init__.py` 也会 import auth middleware，形成循环。解法：所有 auth 模块引用用 lazy import（函数内 import）。
2. **`asyncio.run()` + lifespan 冲突**：FastAPI lifespan 在 running event loop 里，不能在 lifespan 内再调 `asyncio.run()`。项目 `src/core/lifespan.py:118-148` 提供了异步版 `_async_setup_dictionaries()` 规避此问题。
3. **uvicorn reload 模式**：`uvicorn main:app --reload` 在 Windows 下可能不稳定，特别是在 WSL 2 + Docker 混用时。如果遇到文件变更不触发重载，试试 `python main.py` 入口（内部也调 uvicorn，但多一层端口清理）。
4. **CORS 配置与 cookie**：`allow_credentials=True` 时，`allow_origins` 不能是 `["*"]`，必须显式列出域名。项目 `src/core/app_factory.py:125-139` 已按环境区分配置。
5. **Request 对象的生命周期**：不要在 `Depends` 函数里把 `request` 存到全局变量——Starlette 在请求结束后会清理 `request` 对象。正确做法用 `request.state.xxx` 存储请求级数据。

---

## 📚 参考

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [FastAPI 教程](https://fastapi.tiangolo.com/tutorial/)
- [FastAPI 高级用户指南](https://fastapi.tiangolo.com/advanced/)
- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [Starlette 文档](https://www.starlette.io/)
- [uv Python 包管理器](https://docs.astral.sh/uv/)

---

**状态：** 🚧 样例

**最后更新：** 2026-06-19
