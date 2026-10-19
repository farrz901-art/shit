# Loguru 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 Python 工程师

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

Loguru 是一个 Python 第三方日志库，定位是"零配置 + 比 stdlib logging 更好用 + 现代化特性"。它用一个 `logger` 单例对象取代 stdlib 的 `logging.getLogger(__name__)`，提供彩色输出、文件轮转、异步、结构化日志、异常 traceback 一行配置等开箱即用能力。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Loguru** | 零配置第三方日志 | 比 stdlib logging 易用太多 |
| **stdlib logging** | 内置日志 | 模板代码多，格式化繁琐 |
| **structlog** | 结构化日志（JSON） | 适合云原生 / ELK，但 API 较复杂 |
| **logbook** | 第三方日志 | 生态小，维护频率低 |
| **picologging** | 高性能日志 | 性能场景，对接 stdlib 接口 |

**Loguru 解决的核心问题**：
- **零配置**：`from loguru import logger; logger.info("hi")` 立即能用
- **彩色输出**：终端 / 文件自动着色
- **文件轮转**：`logger.add("file.log", rotation="100 MB")` 一行
- **异常 traceback**：`logger.opt(exception=True).error("...")` 包含完整堆栈
- **结构化**：自带 `serialize=True` 输出 JSON，完美对接 ELK / Langfuse

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
uv add "loguru>=0.7,<1.0"
# 项目已配 (pyproject.toml:9)
```

### 2.2 环境

Loguru 零配置即可用，但生产环境一般要：

- 配置 stdout 彩色 + 文件不带色
- 文件按大小 / 时间轮转
- 异步写（不阻塞主流程）
- 拦截 stdlib logging（让第三方库也走 loguru）

```python
# src/core/logging.py (项目)
import sys
from loguru import logger

logger.remove()  # 清掉默认 stderr handler
logger.add(sys.stderr, level="INFO", colorize=True, serialize=False)  # dev 彩色
logger.add("logs/app.log", level="DEBUG", rotation="100 MB", retention="30 days",
           serialize=True, enqueue=True)  # 生产 JSON + 轮转
```

---

## 三、基础语法 & 类型系统

### 3.1 基本使用

```python
from loguru import logger

logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告")
logger.error("错误")
logger.critical("致命")
```

### 3.2 格式化（`{}` 占位符）

Loguru 用 `{}`（不是 `{}` 也不是 `%s`）：

```python
name = "Alice"
age = 30
logger.info("User {} is {} years old", name, age)         # 输出：User Alice is 30 years old
logger.info("User {name} is {age} years old", name=name, age=age)
```

### 3.3 异常 traceback

```python
try:
    1 / 0
except ZeroDivisionError:
    logger.opt(exception=True).error("除零错误")
    # 自动附加完整 traceback
```

### 3.4 结构化（serialize=True）

```python
logger.add("logs/app.json", serialize=True)
logger.info("user_login", user_id=42, ip="1.2.3.4")
# 输出 JSON 一行：{"text": "user_login", "record": {"extra": {"user_id": 42, "ip": "1.2.3.4"}}, ...}
```

### 3.5 自定义级别

```python
# Loguru 内置只有 DEBUG/INFO/WARNING/ERROR/CRITICAL 五个
# 业务自定义级别（如 AUDIT）
logger.level("AUDIT", no=35, color="<green>")
logger.log("AUDIT", "用户 {} 修改了 {}", "alice", "user_role")
```

### 3.6 绑定上下文（bind）

```python
# 整个模块绑定 request_id，所有日志自动带
logger_with_ctx = logger.bind(request_id="abc-123")
logger_with_ctx.info("hello")
# {"text": "hello", "record": {"extra": {"request_id": "abc-123"}}}
```

---

## 四、核心概念

### 4.1 Logger（单例）

`from loguru import logger` 拿到的是模块级单例，全局共享。**禁止**自己 `import loguru; loguru.logger.new()` 重新创建（会破坏全局 sink）。

### 4.2 Sink（输出端）

`logger.add(sink)` 注册一个输出端。sink 可以是：
- 文件路径字符串
- `sys.stderr` / `sys.stdout`
- 可调用对象（自定义处理函数，如 `def sink(msg): ...`）

### 4.3 Level（级别）

5 个内置级别，按严重度从低到高：

```
DEBUG < INFO < WARNING < ERROR < CRITICAL
```

通过 `logger.level()` 加自定义级别。filter 表达式可控制每个 sink 的最低输出级别。

### 4.4 Rotation（轮转）

```python
logger.add("app.log", rotation="100 MB")    # 按大小
logger.add("app.log", rotation="00:00")     # 每天午夜
logger.add("app.log", rotation="1 week")    # 每周
```

### 4.5 Retention（保留期）

```python
logger.add("app.log", retention="30 days")  # 自动删 30 天前
```

### 4.6 Compression（压缩）

```python
logger.add("app.log", rotation="100 MB", compression="zip")
```

### 4.7 Enqueue（异步队列）

```python
logger.add("app.log", enqueue=True)         # 异步写文件，不阻塞主线程
# 强烈推荐在多线程 / async 项目用
```

### 4.8 PII Scrub

项目 `src/core/logging.py` 的 `_scrub()` 函数（推测）：

```python
import re

_PII_KEYS = {"password", "token", "api_key", "secret", "authorization", "ssn"}

def _scrub(extra: dict) -> dict:
    return {
        k: "***REDACTED***" if k.lower() in _PII_KEYS else v
        for k, v in extra.items()
    }
```

---

## 五、常用命令 & 工具链

项目里 loguru 不需要单独命令。但配合 `pytest` / `ruff` 的使用：

```bash
# 测试时禁用 loguru 输出
uv run pytest --log-cli-level=ERROR

# 格式化（项目 CLAUDE.md 强制 ruff）
uv run ruff format
uv run ruff check --fix
```

---

## 六、项目集成点

### 6.1 项目**强制**使用 Loguru 替代 stdlib logging

`packages/service/pyproject.toml:9`：

```toml
"loguru>=0.7,<1.0", # 全量切换 stdlib logging (2026-06-17 spec §1)
```

`packages/service/CLAUDE.md` 明确：

> 业务代码使用 loguru, 不用 stdlib logging
> 旧（禁用）: `import logging; logger = logging.getLogger(__name__)`
> 新（统一）: `from loguru import logger`

### 6.2 项目日志架构

```
业务代码 (loguru.info)
    ↓
src/core/logging.py (configure_logging)
    ↓
    ├── sys.stderr (dev 彩色)
    ├── app_logs PG 表 (生产 JSON enqueue 写)
    └── error_logs PG 表 (生产 ERROR+ 单独写)
```

### 6.3 启动配置

`src/core/lifespan.py:35-44`：

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

启动顺序：

1. `_setup_logging` — 配置 loguru
2. `_setup_redis` — 探测 Redis
3. `_setup_dictionaries` — 字典 seed
4. `start_health_loop` — 5s 轮询

### 6.4 拦截 stdlib logging

项目用 `InterceptHandler` 接管所有 stdlib logging（包括 SQLAlchemy、httpx、uvicorn 等第三方库），统一走 loguru 输出：

```python
# src/core/logging.py (推测)
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # 拿到 stdlib log，转发给 loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

效果：`uvicorn` / `sqlalchemy` / `httpx` 的日志格式跟项目一致。

### 6.5 关闭流程

`src/core/lifespan.py:187-189`（推测）：

```python
finally:
    from src.core.logging import shutdown_logging
    shutdown_logging()  # 排空 enqueue 队列
```

### 6.6 全局异常 handler 写 PG

`src/core/errors.py:47-61`：

```python
@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    logger.opt(exception=True).error(
        "unhandled_exception path={} method={}",
        request.url.path,
        request.method,
    )
    try:
        _error_sink_sync(level="ERROR", exc=exc, request=request)  # 写 error_logs 表
    except Exception as write_exc:
        logger.critical("error_logs write failed: {}", write_exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

---

## 七、项目代码示例

### 7.1 业务代码

项目 `src/chat/router.py`（典型）：

```python
from loguru import logger

@router.post("/conversations")
async def create_conversation(payload: ..., user: CurrentUser = Depends(...)):
    logger.info("create_conversation user_id={} title={}", user.id, payload.title)
    conv = svc.create_conversation(user_id=user.id, title=payload.title or "新对话")
    logger.info("create_conversation done conv_id={}", conv.id)
    return conv
```

### 7.2 异常处理（带 traceback）

`src/kg/router.py`（典型）：

```python
@router.get("/graph/{entity}")
def get_graph(entity: str):
    try:
        return kg_client.query(entity)
    except Exception:
        logger.opt(exception=True).error(
            "kg_query_failed entity={}",
            entity,
        )
        raise HTTPException(500, "知识图谱查询失败")
```

### 7.3 上下文绑定（per request_id）

`src/core/middleware.py`（推测）：

```python
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        import uuid
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        with logger.contextualize(request_id=request_id, path=request.url.path):
            response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
```

效果：每个请求的所有日志自动带 `request_id`，便于 grep 关联。

### 7.4 配置 + DB 写入

`src/core/logging.py`（推测）：

```python
import sys
from loguru import logger
from src.storage.session import session_scope
from src.db.models import AppLog, ErrorLog

def configure_logging(*, json_console: bool, write_to_db: bool, level: str):
    logger.remove()
    # 1. stderr (dev 彩色 / prod JSON)
    logger.add(sys.stderr, level=level, colorize=not json_console, serialize=json_console)

    if write_to_db:
        # 2. 写 app_logs 表（后台 enqueue）
        def pg_sink(message):
            record = message.record
            with session_scope() as s:
                log = AppLog(
                    level=record["level"].name,
                    message=record["message"],
                    module=record["name"],
                    extra=_scrub(record["extra"]),
                    created_at=record["time"],
                )
                s.add(log)
        logger.add(pg_sink, level=level, enqueue=True)
```

### 7.5 错误日志单独处理

```python
def _error_sink_sync(level: str, exc: Exception, request: Request):
    """错误级别单独写 error_logs 表，带 stacktrace"""
    from src.db.models import ErrorLog
    with session_scope() as s:
        s.add(ErrorLog(
            level=level,
            exc_type=type(exc).__name__,
            exc_message=str(exc),
            traceback=traceback.format_exc(),
            method=request.method,
            path=request.url.path,
            user_id=getattr(request.state, "user_id", None),
        ))
```

### 7.6 PII 自动脱敏

```python
_PII_KEYS = {"password", "token", "api_key", "secret", "authorization", "ssn"}

def _scrub(extra: dict) -> dict:
    return {
        k: "***REDACTED***" if k.lower() in _PII_KEYS else v
        for k, v in extra.items()
    }

logger.info("user_login", user_id=42, password="abc123", token="xyz")
# 自动变成 user_id=42, password=***REDACTED***, token=***REDACTED***
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Loguru 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`add(sink, format=...)` 自定义格式** | 自定义输出模板 | 团队需要特定格式时 |
| **`@logger.catch` 装饰器** | 自动捕获异常 | 简化 try/except |
| **`logger.configure(extra=...)`** | 全局默认 extra | 部署环境标签等 |
| **Loguru + OpenTelemetry** | 标准化 tracing | 项目用 Langfuse 已覆盖 |
| **Loguru + Loki / Grafana** | 日志聚合可视化 | 暂用 PG 表 + Grafana（待评估） |
| **Loguru `patch()` 方法** | 改 stdlib 行为 | 已用 InterceptHandler 覆盖 |
| **多文件 sink** | 不同模块不同文件 | 项目统一写一张表 |
| **`logger.complete()`** | 协程结束 hook | async 场景 |

**建议关注**：`@logger.catch` 装饰器在简单脚本里能省 try/except。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **业务代码统一用 loguru，禁用 stdlib logging**
2. **占位符用 `{}` 不用 `%s`**（loguru 风格）
3. **危险操作必须加 `@audited`**（DELETE / 改账户 / 改权限 / 导出）
4. **PII 字段自动 scrub**（`password` / `token` / `api_key` 等 18 字段）
5. **异常处理有 global handler**：4xx WARNING，5xx ERROR
6. **永不返 stacktrace 给前端**（避免代码泄露）

### 最佳实践

1. **logger.remove() 在启动时调用**：清掉默认 stderr handler，避免重复输出
2. **生产环境 `serialize=True` + `enqueue=True`**：JSON 输出 + 异步写不阻塞
3. **绑定 context 用 `logger.contextualize()` 上下文管理器**：

```python
with logger.contextualize(request_id="abc-123", user_id=42):
    do_something()  # 所有日志自动带 request_id + user_id
```

4. **`logger.opt(exception=True).error(...)` 替代 `logger.exception(...)`**：loguru 不支持 `.exception()`，必须用 opt(exception=True)
5. **关程序时 `shutdown_logging()`**：排空 enqueue 队列，否则最后几条日志丢失
6. **测试禁用 loguru 输出**：

```python
import pytest
from loguru import logger

@pytest.fixture(autouse=True)
def silence_loguru():
    logger.remove()
    yield
    logger.remove()
```

### 常见坑

1. **重复 `logger.add`**：每次启动都加 handler，会重复输出。`configure_logging` 必须先 `logger.remove()`
2. **Async 任务里混用 sync / async sink**：

```python
# 错：async 函数里调 sync PG 写
async def handle():
    logger.info(...)  # 如果 sink 是 sync + enqueue=True，OK；但 sync 没 enqueue 会阻塞

# 对：要么 enqueue=True（loguru 自己起 thread），要么用 async sink
```

3. **loguru 0.6 → 0.7 breaking**：自定义 `formatter` 函数签名变了（新增 `record_dict` 参数），升级前看 changelog

4. **`logger.bind()` 不能跨模块传递**：

```python
# 错：模块 A bind 的 ctx，模块 B 看不到
# logger_a = logger.bind(request_id="123")
# logger_b（不同 import）: 看不到 request_id

# 对：用 contextualize 上下文管理器
with logger.contextualize(request_id="123"):
    func_a()  # 在上下文里
    func_b()  # 在上下文里
```

5. **PII 字段漏掉**：

```python
logger.info("用户登录", user_email="alice@x.com")  # user_email 不在脱敏列表
# 解法：_PII_KEYS 加 "user_email"
```

6. **stacktrace 信息泄露**：production 必须 `logger.exception()` 截断，或者干脆不返给前端（项目做法是返 `{"detail": "Internal server error"}`）

7. **loguru 不支持 `LoggerAdapter`**：如果业务想做 per-class logger，得自己封装

8. **项目测试必须 mock loguru**：

```python
from unittest.mock import patch

@patch("src.chat.router.logger")
def test_chat(mock_logger):
    # 测试不依赖真实日志输出
    ...
```

---

## 📚 参考

- [Loguru 官方文档](https://loguru.readthedocs.io/)
- [Loguru GitHub](https://github.com/Delgan/loguru)
- [Loguru vs stdlib logging](https://loguru.readthedocs.io/en/stable/compare.html)
- [project service/CLAUDE.md §日志使用约定](../../packages/service/CLAUDE.md)
- [project service/CLAUDE.md §异常处理](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
