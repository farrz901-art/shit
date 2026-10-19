# Python 教程

> 📅 创建日期：2026-06-25
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

Python 是一门强调代码可读性和开发效率的高级编程语言。Python 3.14（2025 年 10 月发布）带来模板字符串、类型注解改进、Zstd 支持等新能力。本项目用 Python 3.14 + uv（Rust 写的包管理器）。

**同类对比：**

| 语言 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Python** | 高生产力动态语言 | AI/ML 生态最丰富，AI/LLM 项目首选 |
| **TypeScript** | Node.js 全栈 | 前端必备，但 AI 库（LangChain/LlamaIndex/PyTorch）Python 才有 |
| **Go** | 高性能静态语言 | 性能更好，但 AI 库少 |
| **Rust** | 系统级 | AI 库开始有，但生态远不如 Python |
| **Java/Kotlin** | 企业级 | 太重 |

**Python 解决的核心问题**：
- **快速原型**：动态类型 + REPL，5 分钟能跑通一个 AI demo
- **AI / ML 生态**：PyTorch / LangChain / LlamaIndex / NumPy / Pandas
- **胶水语言**：用 C 扩展 / ctypes 调底层库

---

## 二、安装 & 开发环境

### 2.1 版本

- Python 3.14（项目 `packages/service/pyproject.toml:6` `requires-python = ">=3.14"`）
- uv 0.4+（Rust 写的包管理器，比 pip 快 10-100x）

### 2.2 安装 Python 3.14

Windows 推荐用 `pyenv-win` 或官方安装包：

```bash
# pyenv-win
pyenv install 3.14
pyenv global 3.14

# 验证
python --version
# Python 3.14.x
```

### 2.3 uv 安装

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux / WSL
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证
uv --version
```

### 2.4 项目初始化

```bash
cd packages/service
uv sync            # 安装所有依赖（含 dev 依赖）
```

### 2.5 开发工具链（项目 CLAUDE.md 强制）

- **format**：`uv run ruff format`
- **lint**：`uv run ruff check --fix` / `uv run ruff check`
- **type**：`uv run pyright`（必须 0 error）
- **test**：`uv run pytest`（~1075 tests pass）
- **coverage**：`uv run pytest`（自动 coverage 报告）

---

## 三、基础语法 & 类型系统

### 3.1 类型注解

```python
def greet(name: str, age: int = 18) -> dict[str, str | int]:
    return {"name": name, "age": age}
```

### 3.2 Pydantic 模型

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=r"^\S+@\S+\.\S+$")
    age: int = Field(default=18, ge=0, le=150)
```

### 3.3 async / await

```python
import asyncio

async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### 3.4 dataclass（轻量级数据类）

```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0
    tags: list[str] = field(default_factory=list)
```

### 3.5 上下文管理器

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def db_session():
    session = Session()
    try:
        yield session
    finally:
        await session.close()
```

### 3.6 类型联合（3.10+）

```python
def process(value: int | str | None) -> str:
    if value is None:
        return "empty"
    return str(value)
```

### 3.7 match-case（3.10+）

```python
match command.split():
    case ["quit"]:
        return "bye"
    case ["load", filename]:
        return f"loading {filename}"
    case ["save", filename, *rest]:
        return f"saving {filename} (extras: {rest})"
    case _:
        return "unknown"
```

---

## 四、核心概念

### 4.1 GIL（Global Interpreter Lock）

CPython 解释器同一时刻只允许一个线程执行 Python 字节码。**IO 密集型**任务用多线程 / asyncio 没问题，**CPU 密集型**用 `multiprocessing` 或 C 扩展（NumPy / Cython）。

### 4.2 装饰器

```python
from functools import wraps

def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result
    return wrapper
```

项目广泛使用：`@router.post()`（FastAPI）、`@audited`（审计）、`@staticmethod` / `@classmethod`（OO）。

### 4.3 生成器 / 迭代器

```python
def read_large_file(path: str):
    with open(path) as f:
        for line in f:        # 逐行迭代，不一次性加载
            yield line.strip()
```

### 4.4 鸭子类型

Python 是动态类型，类型不匹配由 duck test 保证行为正确。

### 4.5 魔术方法

`__init__` / `__str__` / `__repr__` / `__eq__` / `__hash__` / `__len__` / `__getitem__` 等，定义类的行为。

### 4.6 模块系统

```python
# 相对导入
from ..storage.session import session_scope
# 绝对导入
from src.storage.session import session_scope
```

项目用 `src/` 布局（`pyproject.toml` 配 `pythonpath = ["src", "."]`），便于测试和打包。

---

## 五、常用命令 & 工具链

```bash
cd packages/service

# 包管理
uv sync                           # 安装依赖
uv add <pkg>                      # 加运行时依赖
uv add --dev <pkg>                # 加开发依赖
uv remove <pkg>                   # 移除
uv run <command>                  # 在 venv 内跑命令

# 工具
uv run python main.py             # 启动服务
uv run pytest                     # 测试
uv run pytest tests/test_x.py     # 单文件测试
uv run pytest -k "test_name"      # 按名字过滤
uv run pyright                    # 类型检查
uv run ruff format                # 格式化
uv run ruff check --fix           # Lint 自动修
uv run ruff check                 # Lint 只读
```

---

## 六、项目集成点

### 6.1 项目结构

```
packages/service/
├── main.py                     # 入口，argparse 子命令
├── pyproject.toml              # 依赖 + 工具配置
├── src/                        # 业务源码
│   ├── core/                   # 核心（app_factory, errors, lifespan, redis）
│   ├── middleware/             # 鉴权
│   ├── db/                     # ORM 模型 + 迁移
│   ├── chat/ chat_share/       # 聊天模块
│   ├── kg/                     # 知识图谱
│   ├── auth/ permissions/      # 鉴权 / RBAC
│   ├── ingest/                 # 文档摄取
│   ├── retrieval/ generation/  # RAG
│   ├── memory/                 # Mem0
│   ├── storage/                # MinIO / S3
│   └── lookups/                # 字典
├── alembic/                    # DB 迁移
├── tests/                      # 测试
│   ├── unit/
│   ├── integration/
│   └── contract/
├── configs/                    # 配置
├── prompts/                    # LLM prompt 模板
└── scripts/                    # 工具脚本
```

### 6.2 关键依赖

```toml
# pyproject.toml 关键依赖
requires-python = ">=3.14"
"fastapi>=0.136.3"                # Web 框架
"pydantic>=2"                     # 数据验证
"sqlalchemy>=2"                   # ORM
"asyncpg>=0.30"                   # 异步 PG 驱动
"psycopg[binary]>=3.2"            # 同步 PG 驱动
"alembic>=1.13"                   # 迁移
"llama-index>=0.14.22"            # RAG 框架
"llama-index-embeddings-huggingface>=0.7.0"
"llama-index-llms-ollama>=0.10.1"
"llama-index-vector-stores-postgres>=0.8.1"
"mem0ai[nlp]>=2.0.5"
"redis>=5"                        # Redis 客户端
"langfuse>=2"                     # LLM 可观测
"loguru>=0.7"                     # 日志
"httpx>=0.27"                     # HTTP 客户端
"uvicorn[standard]>=0.32"         # ASGI 服务器
```

### 6.3 启动入口

`main.py:14` 在 import 前加载 `.env.local`：

```python
from dotenv import load_dotenv
load_dotenv(".env.local")  # Neo4j 在模块加载时读 env，必须先 load

import uvicorn
from src.core.app_factory import create_app

app = create_app()  # 让 `uvicorn main:app` 直接跑
```

### 6.4 配置约定

- **环境变量**：`.env.local`（gitignore）
- **Settings 类**：`src/config/settings.py`
- **常量集中**：`packages/service/const/index.ts` 风格（实际是 `const/index.py`）

---

## 七、项目代码示例

### 7.1 应用工厂 + lifespan

`src/core/app_factory.py:53-169`：

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG + 产品订货号解析服务",
        version="0.2.0",
        lifespan=_lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=allow_origins, ...)
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)
    app.add_middleware(RequestIDMiddleware)
    # ... 挂载 router
    return app
```

### 7.2 Pydantic 模型 + 字段描述

`src/middleware/auth.py:58-84`：

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
    avatar_url: str | None = None
    is_pending_deletion: bool = False
    deletion_requested_at: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "super_admin")
```

### 7.3 异步 LLM 调用

`src/generation/llm.py`（推测）：

```python
from llama_index.llms.openai_like import OpenAILike

class OpenAILLM:
    def __init__(self):
        self._llm = OpenAILike(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_BASE_URL"),
        )

    async def acomplete(self, prompt: str) -> str:
        response = await self._llm.acomplete(prompt)
        return response.text
```

### 7.4 SQLAlchemy session_scope 模式

`src/storage/session.py`：

```python
from contextlib import contextmanager
from sqlalchemy.orm import Session

@contextmanager
def session_scope() -> Session:
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### 7.5 审计装饰器

`src/core/audit.py`：

```python
from functools import wraps
from loguru import logger

def audited(action: str, target_type: str = "unknown"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request") or args[0]
            ctx = request.state.audit_ctx
            ctx.set(action=action, target_type=target_type)
            try:
                result = await func(*args, **kwargs)
                ctx.set_status("success")
                return result
            except Exception as e:
                ctx.set_status("failure", error=str(e))
                raise
            finally:
                await ctx.flush()
        return wrapper
    return decorator
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Python 3.10+ / 3.14 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **结构化模式匹配（match-case）** | 多分支条件 | 复杂状态机用 |
| **PEP 695 类型参数语法**（3.12+）| `class Foo[T]:` | 简化泛型声明 |
| **`type` 语句**（3.12+）| 类型别名 | 复杂类型时用 |
| **`tomllib`**（3.11+）| 读 TOML 配置 | 配 alembic 用 |
| **Zstd 压缩**（3.14）| 比 zlib / gzip 更快 | 备份 / 日志压缩 |
| **`ExceptionGroup` + `except*`**（3.11+）| 多个异常聚合 | concurrent.futures 场景 |
| **`TaskGroup`**（3.11+）| 异步上下文管理 | 替代 `asyncio.gather` |
| **`Self` 类型**（3.11+）| 链式方法返回类型 | 复杂 OO 设计 |
| **`@override` decorator**（3.12+）| 显式标记重写 | 类继承调试 |
| **Per-interpreter GIL**（3.13+）| 多核并行 | CPU 密集型用 |

**建议关注**：`TaskGroup` 适合并行跑 LLM 嵌入 + 业务写库的复合任务。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **不删除代码注释**：改代码时保留所有原有注释
2. **使用中文注释**：所有代码注释用中文
3. **日志输出用中文**：所有 print/log 输出用中文
4. **优先使用项目已有组件**：函数、shadcn、ahook 等
5. **函数封装**：重复 3 遍以上就封装
6. **严禁绕过 pyright/oxlint 规则**
7. **严禁使用 cat>**：多次 cat 覆盖已有文件
8. **测试必须 mock，不连真 PG/Redis**（4 模式之一）
9. **业务 enum 必须走 lookup 字典**（不允许硬编 `StrEnum`）
10. **alembic 迁移必须可回滚**（写 downgrade 干净）

### Python 通用最佳实践

1. **类型注解全开**：所有函数 / 方法加类型注解
2. **dataclass 替代裸 dict**：有 schema 的数据用 `@dataclass` 或 Pydantic
3. **async 优先**：IO 密集型操作用 async / await
4. **`with` / `async with`**：所有资源用上下文管理器
5. **不用 `from foo import *`**：显式导入，便于静态分析
6. **测试用 pytest + pytest-mock**：`unittest.mock.patch` 而非 `monkeypatch`（项目偏好）
7. **不要 hardcode**：`config = "value"` → `config = os.getenv("KEY", "default")`

### 常见坑

1. **可变默认参数**：

```python
# 错：所有调用共享同一个 list
def add_item(item, items=[]):
    items.append(item)
    return items

# 对
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

2. **循环 import**：`auth_account_router` import `middleware.auth`，`middleware.auth` 顶层 import `src.auth.*` → 循环。用 lazy import（函数体内 import）解决

3. **`asyncio.run()` 在 running loop 内调用**：`lifespan` 在 event loop 内，不能再 `asyncio.run()`。项目用 `_async_setup_dictionaries()` 异步版（`src/core/lifespan.py:118-148`）

4. **Pydantic v1 vs v2 混用**：项目用 v2，注意 `model_dump()`（非 `dict()`）、`ConfigDict`（非 `class Config`）

5. **类型注解不准确**：`Sequence` 接受 list / tuple，但 `list` 不能接受 tuple。视情况用更宽泛类型

6. **同步代码里调 `asyncio.run`**：FastAPI 上下文内会报 "asyncio.run() cannot be called from a running event loop"

7. **Python 3.13+ GIL 行为变化**：3.13 引入实验性 free-threaded 模式（无 GIL），但 SQLAlchemy / Pydantic 等部分库仍未适配

8. **资源未关闭**：HTTP client / DB session / 文件句柄必须 `with` 块或 `try/finally`

---

## 📚 参考

- [Python 官方文档](https://docs.python.org/3.14/)
- [Python 3.14 新特性](https://docs.python.org/3/whatsnew/3.14.html)
- [PEP 8 编码规范](https://peps.python.org/pep-0008/)
- [PEP 484 类型注解](https://peps.python.org/pep-0484/)
- [uv 官方文档](https://docs.astral.sh/uv/)
- [Pydantic v2 文档](https://docs.pydantic.dev/latest/)
- [SQLAlchemy 2.x 文档](https://docs.sqlalchemy.org/en/20/)
- [项目 service/CLAUDE.md](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
