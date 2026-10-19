# Mineru 远程 HTTP 化设计 (2026-07-06)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this design task-by-task. Implementation plan saved to `docs/superpowers/plans/2026-07-06-mineru-http-remote.md`.

**Date:** 2026-07-06
**Status:** 待批准
**Author:** brainstorm skill (7 sections / 8 clarifying rounds)
**Supersedes:** `docs/superpowers/plans/2026-07-03-mineru-http-remote.md` (旧 plan 决策冲突, 同步覆盖)

---

## 0. 背景与目标

### 现状

`MineruConverter._run_mineru()` 当前用 `docker.from_env()` + `client.containers.run("mineru:latest", "mineru -p /app/input -o /app/output -b pipeline", ...)` 每个 PDF 批跑一次新容器. 输入挂本地 `tempfile.TemporaryDirectory`, 输出挂调用方传的 `output_dir` (通常是 `settings.paths.output_dir`).

`docker/mineru-docker-compose.yml:58-91` 已定义 `mineru-api` profile (FastAPI 长驻服务, 主机端口 18000 → 容器 8000, 自带 NVIDIA GPU + `/health` 探活), **但 backend 代码完全没接它**. 现状是 "docker 临时容器路径" 和 "docker 长驻 HTTP 服务" 并存但只用前者.

### 根问题 (用户业务视角)

backend 容器 / K8s pod 部署时, docker-py 路径要求:

1. **后端容器必须有 docker daemon** (跑 `client.containers.run`) - 与 K8s 无 Docker 哲学冲突
2. **后端容器必须有 GPU** (mineru 内部 vLLM) - GPU 是稀缺资源, 不应绑死 backend
3. **每个 PDF 批起新容器** - 模型冷启动慢, 资源浪费
4. **backend 升级 / 扩缩容需要重启 mineru 镜像加载** - 部署慢

### 目标

把 `MineruConverter` 从 "宿主机起 docker 容器" 改成 "调远端 mineru-api HTTP 服务", 让 backend 容器 / K8s pod 部署时不依赖 docker daemon 和本地 GPU. mineru 服务单独部署在带 GPU 的节点上, 通过 HTTP 暴露.

### 非目标

- 不改 `Converter` 基类接口 (`convert` / `convert_batch` / `can_handle` / `resolve_md_path`)
- 不改 `pipeline.py` 调用方 (`pipeline.py:302-305` 同步调 `convert_batch`, 期望 `dict[str, str]`)
- 不动 mineru 镜像 / docker-compose 服务端编排 (已落)
- 不改前端
- 不改其他 converter (kreuzberg / ezdxf)
- 不引入异步全链路冒泡 (FastAPI 同步 router 保持同步)

---

## 1. 架构总览 + 模块边界

### 三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: src/ingest/pdf_processing/converters/mineru.py       │
│  ─── Converter 编排层 ───                                       │
│  职责:                                                          │
│    • convert_batch() 编排 (磁盘真相源 + 失败逐个重试)           │
│    • 按 PDF 大小选 sync/async 路由                              │
│    • PDF 级 asyncio.Semaphore 限流                              │
│    • 调 MineruClient                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: src/ingest/pdf_processing/converters/                │
│           mineru_client.py  (新)                                │
│  ─── HTTP 客户端 ───                                            │
│  职责:                                                          │
│    • submit_sync(pdf_paths) -> dict[stem, md_content]           │
│    • submit_async(pdf_paths) -> task_id                        │
│    • poll_until_terminal(task_id) -> dict                      │
│    • download_result(task_id) -> bytes (ZIP)                   │
│    • RunError 统一异常 (exit_code, response_body, task_id)     │
│    • tenacity 仅对 POST 重试 (5xx + 网络错)                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: 远端 mineru-api FastAPI (自部署, 已有 compose)        │
│  /file_parse (sync)  /tasks (async)  /tasks/{id}  /result      │
└─────────────────────────────────────────────────────────────────┘
```

### 关键边界

- `MineruClient` 只管 HTTP, **不读磁盘 / 不解析 PDF 内容 / 不决定路由**——可单独测. 协议跟 mineru 绑死, 不复用给其他 converter
- `MineruConverter` 只管编排, **不直接用 `httpx`**——可单独测编排逻辑 (mock `MineruClient`)
- 阈值 (`sync_max_bytes=5MB`) 和并发数 (`max_concurrent_batches=3`) 走 env, 不写死
- `RunError` 提到 client 模块 (converter 复用), 3 字段保持: `exit_code: int` / `response_body: str` / `task_id: str`

### `RunError` 定义 (提到 client 模块)

```python
class RunError(Exception):
    """mineru HTTP 调用失败

    字段语义:
        exit_code: HTTP 状态码 (5xx=服务端错, 0=网络/超时错, 4xx=客户端错, 409=task failed)
        response_body: 错误响应原文 (str, 前 2KB)
        task_id: 服务端 X-MinerU-Task-Id (如有)
    """

    def __init__(
        self,
        exit_code: int,
        response_body: str = "",
        task_id: str = "",
    ) -> None:
        self.exit_code = exit_code
        self.response_body = response_body
        self.task_id = task_id
        super().__init__(
            f"mineru HTTP 失败 (status={exit_code}, task_id={task_id or 'n/a'})"
        )
```

`exit_code` 字段名保留是为了 `convert_batch` 日志格式 `f"批处理 exit {e.exit_code}"` 兼容 ([packages/service/src/ingest/pdf_processing/converters/mineru.py:153](packages/service/src/ingest/pdf_processing/converters/mineru.py#L153)).

---

## 2. HTTP 客户端 `MineruClient` 详细设计

**位置**: `packages/service/src/ingest/pdf_processing/converters/mineru_client.py` (新文件, 跟 `mineru.py` 同目录)

### 公共 API (用户视角)

```python
class MineruClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_connect: float = 5.0,
        timeout_read: float = 30.0,
        timeout_download: float = 600.0,    # 拉 ZIP 比单次 GET 慢
        retry_attempts: int = 3,
        backend: str = "pipeline",
        parse_method: str = "auto",
    ) -> None: ...

    def submit_sync(self, pdf_paths: Sequence[str]) -> dict[str, str]:
        """POST /file_parse (multipart files + form fields).
        return_md=true, response_format_zip=false (不写服务端磁盘, 拿 JSON results).
        Returns: {pdf_stem: md_content}."""

    def submit_async(self, pdf_paths: Sequence[str]) -> str:
        """POST /tasks (multipart files + form fields).
        response_format_zip=true (服务端写 <stem>/auto/<stem>.md).
        Returns: task_id (str)."""

    def poll_until_terminal(
        self, task_id: str, *, timeout: int = 600, poll_interval: float = 2.0
    ) -> dict:
        """GET /tasks/{id} 轮询直到 status ∈ {completed, failed}.
        Returns: 最后一次响应的 JSON dict (含 status / error / file_names).
        Raises: RunError(exit_code=0, response_body=超时信息, task_id)."""

    def download_result(self, task_id: str) -> bytes:
        """GET /tasks/{id}/result → ZIP 字节."""

    def close(self) -> None: ...    # 显式释放 httpx.Client 池

    # context manager 支持: with MineruClient(...) as c:
```

### 核心实现要点

#### 2.1 httpx.Client 复用

`__init__` 构造一次 `httpx.Client(base_url=base_url)`, 所有方法共享; `close()` 释放; 支持 `with` 语法.

#### 2.2 multipart files 构造

读所有 PDF 字节 → `[("files", (filename, content, "application/pdf"))]`. 一次性读完: 同步路径只接 ≤5MB, 异步路径跟官方 client 一致.

#### 2.3 tenacity 仅对 POST 重试

仿 [packages/service/src/integrations/dify_client.py:37-43](packages/service/src/integrations/dify_client.py#L37-L43):

```python
def _is_retryable(exc: BaseException) -> bool:
    """只重试网络/超时 + 5xx 服务端错; 4xx + task failed 不重试"""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


@retry(
    stop=stop_after_attempt(retry_attempts),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable),
    before_sleep=lambda rs: logger.warning(
        "  [mineru] HTTP 重试 attempt={} exc={}",
        rs.attempt_number, type(rs.outcome.exception()).__name__,
    ),
    reraise=True,
)
def _post(self, path: str, files: list, data: dict) -> httpx.Response:
    return self._client.post(
        path, files=files, data=data,
        timeout=httpx.Timeout(connect=self.timeout_connect, read=self.timeout_read,
                              write=self.timeout_read, pool=self.timeout_connect),
    )
```

#### 2.4 异常统一

`submit_*` / `poll` / `download_result` 内捕获 `httpx.HTTPStatusError` / `TimeoutException` / `NetworkError`, 统一转 `RunError`:

```python
try:
    resp = self._post("/tasks", files=files, data=self._async_form_fields)
except httpx.HTTPStatusError as e:
    raise RunError(
        exit_code=e.response.status_code,
        response_body=e.response.text[:2000],
        task_id=e.response.headers.get("X-MinerU-Task-Id", ""),
    ) from e
except (httpx.TimeoutException, httpx.NetworkError) as e:
    raise RunError(exit_code=0, response_body=str(e)[:2000]) from e
```

#### 2.5 同步 / 异步 form fields

```python
# 同步路径 form fields (response_format_zip=false, 不写服务端磁盘)
_SYNC_FORM_FIELDS = {
    "backend": "pipeline",
    "parse_method": "auto",
    "return_md": "true",
    "response_format_zip": "false",
}

# 异步路径 form fields (response_format_zip=true, 服务端写文件)
_ASYNC_FORM_FIELDS = {
    "backend": "pipeline",
    "parse_method": "auto",
    "return_md": "true",
    "response_format_zip": "true",
}
```

`backend` / `parse_method` 走 `__init__` 注入, 同步异步两路径共用同一 `backend`.

#### 2.6 轮询细节

- 用 `time.monotonic()` 做 deadline, 避免 `time.time()` 受 NTP 跳变影响
- 退避: 基础 `poll_interval`, 指数 `interval * 2^(attempts-1)`, 封顶 10s
- 拿到 `completed` / `failed` 立刻返 payload, 不睡
- 超时抛 `RunError(exit_code=0, response_body=f"task ... 等待超时 (>Xs)", task_id=...)`

#### 2.7 模块导入规则 (CLAUDE.md §函数内 import 规范)

模块顶层 `import httpx, tenacity, loguru, src.config.settings` 全允许. `_is_retryable` 用顶层 helper (不嵌套).

---

## 3. Converter 编排层 (`mineru.py` 重写)

**位置不变**: `packages/service/src/ingest/pdf_processing/converters/mineru.py`

继承 `Converter`, 保持 `convert` / `convert_batch` / `resolve_md_path` / `can_handle` 公共方法签名.

### 类形态

```python
class MineruConverter(Converter):
    name = "mineru"
    extensions = [...]   # 跟现状一致 (PDF + 图片 + Office)

    def __init__(self) -> None:
        # 不在 __init__ 里建 client, semaphore 限流要复用
        pass

    @staticmethod
    def can_handle(info) -> bool: return True    # 跟现状一致

    @staticmethod
    def resolve_md_path(...) -> str: ...          # 跟现状一致

    def convert(self, pdf_path, output_path) -> str:
        return self.convert_batch([pdf_path], os.path.dirname(output_path)).get(pdf_path, "")

    def convert_batch(self, pdf_paths, output_dir) -> dict[str, str]:
        """编排: PDF 级 semaphore → 逐个 _run_one → 磁盘真相源 → 失败逐个重试"""
        if not pdf_paths: return {}
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 第 1 轮: 并发跑 (受 semaphore 限)
        results: dict[str, str] = {}
        for p in pdf_paths:
            try:
                results.update(self._run_one(p, output_dir))
            except RunError as e:
                logger.warning("  [mineru] {} 第 1 轮失败 HTTP {} task_id={} body={}",
                               Path(p).name, e.exit_code, e.task_id, e.response_body[:200])

        # 磁盘真相源 (跟现状一致): 扫 output_dir/<stem>/auto/<stem>.md
        retry_targets: list[str] = []
        for pdf_path in pdf_paths:
            md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
            if os.path.exists(md_path):
                if pdf_path not in results:
                    with open(md_path, encoding="utf-8") as f:
                        results[pdf_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(pdf_path).stem)
                if content:
                    results[pdf_path] = content
                else:
                    retry_targets.append(pdf_path)

        if not retry_targets:
            return results

        # 第 2 轮: 失败逐个重试 (单独跑, 单文件不会触发 mineru 内部 batch 并发)
        logger.info("  [mineru] 第 1 轮缺 {} 个文件输出, 单独重试: {}",
                    len(retry_targets), [Path(p).name for p in retry_targets])
        for failed in retry_targets:
            try:
                results.update(self._run_one(failed, output_dir))
                md_path = self.resolve_md_path(failed, output_dir, method="auto")
                if os.path.exists(md_path) and failed not in results:
                    with open(md_path, encoding="utf-8") as f:
                        results[failed] = f.read()
                elif failed not in results:
                    content = self._find_md_in_subdirs(output_dir, Path(failed).stem)
                    if content:
                        results[failed] = content
            except RunError as e:
                results[failed] = f"[ERROR] mineru 重试仍失败 (HTTP {e.exit_code}): {e.response_body[-500:]}"

        return results

    async def _run_one_async(self, pdf_path: str, output_dir: str) -> dict[str, str]:
        """单 PDF: semaphore 限流 + 选 sync/async 路径 + 调 client"""
        async with self._get_semaphore():
            stem = Path(pdf_path).stem
            size = os.path.getsize(pdf_path)
            is_small = size <= settings.mineru_api_sync_max_bytes

            with MineruClient(
                base_url=settings.mineru_api_url,
                timeout_connect=settings.mineru_api_timeout_connect,
                timeout_read=settings.mineru_api_timeout_read,
                timeout_download=settings.mineru_api_timeout_download,
                retry_attempts=settings.mineru_api_retry_attempts,
            ) as client:
                if is_small:
                    md_map = client.submit_sync([pdf_path])
                    md = md_map.get(stem, "")
                    if not md:
                        raise RunError(
                            404, response_body=f"sync 响应无 stem={stem}", task_id="",
                        )
                    self._write_md(output_dir, stem, md)
                    return {pdf_path: md}
                else:
                    task_id = client.submit_async([pdf_path])
                    payload = client.poll_until_terminal(
                        task_id,
                        timeout=settings.mineru_api_task_timeout,
                        poll_interval=settings.mineru_api_poll_interval,
                    )
                    if payload.get("status") != "completed":
                        raise RunError(
                            409,
                            response_body=payload.get("error", "task failed"),
                            task_id=task_id,
                        )
                    zip_bytes = client.download_result(task_id)
                    self._extract_result_zip(zip_bytes, output_dir)
                    md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
                    with open(md_path, encoding="utf-8") as f:
                        return {pdf_path: f.read()}

    def _run_one(self, pdf_path: str, output_dir: str) -> dict[str, str]:
        """同步包装 _run_one_async (FastAPI 同步 router 友好)"""
        return asyncio.run(self._run_one_async(pdf_path, output_dir))

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """模块级懒初始化 semaphore (env 控默认 3)"""
        global _mineru_semaphore
        if _mineru_semaphore is None:
            _mineru_semaphore = asyncio.Semaphore(
                settings.mineru_api_max_concurrent_batches,
            )
        return _mineru_semaphore

    def _write_md(self, output_dir: str, stem: str, md: str) -> None:
        """写 md 到 <output_dir>/<stem>/auto/<stem>.md (同步路径不走 ZIP, 直接写)"""
        target = os.path.join(output_dir, stem, "auto", f"{stem}.md")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(md)

    def _extract_result_zip(self, zip_bytes: bytes, output_dir: str) -> None:
        """异步路径: 从 mineru 返的 ZIP 提取每个 PDF 的 md
        防御: 拒绝绝对路径 / .. 跳出 output_dir (跟官方 client 一致)
        """
        output_dir_abs = os.path.abspath(output_dir)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".md"):
                    continue
                parts = name.split("/")
                if len(parts) < 3:
                    continue
                target = os.path.abspath(os.path.join(output_dir, *parts))
                if not target.startswith(output_dir_abs + os.sep):
                    logger.warning("  [mineru] ZIP 跳过越界路径: {}", name)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
```

### 关键决策

#### 3.1 `_run_one` 用 `asyncio.run` per-PDF 同步包装

- 因为 `Converter` 基类的 `convert_batch` 是同步方法 (`pipeline.py:305` 同步调用), 不能直接 await
- **替代方案**: `convert_batch` 改 async 全链路冒泡 → pipeline 改 async → 影响太大
- **`asyncio.run` per-PDF 性能损失**: 每个 PDF 起事件循环 ~5ms, 对 mineru 跑几十秒 ~几百秒的总耗时可忽略
- **替代方案**: 用 `anyio.from_thread.run_sync` / `nest_asyncio`——复杂度收益不成正比

#### 3.2 semaphore 跨 converter 实例共享

- 用模块级单例 `_mineru_semaphore`, 确保 100 个 `MineruConverter()` 共享同一限流池
- 懒初始化, 不在 import 时强制读 settings (避免 settings 还未加载时的副作用)

#### 3.3 同步路径直接写盘

服务端不写文件 (`response_format_zip=false`), client 拿 JSON 后 converter 直接 `open(...).write(md)`, 避免 ZIP 来回.

#### 3.4 ZIP 防越界

照搬官方 client, 拒绝绝对路径 + `..` 跳出 `output_dir_abs` 的条目.

---

## 4. env 三件套 + pyproject.toml

### 9 个 env (新增, 三处同步)

| env | 默认值 | 用途 |
|---|---|---|
| `MINERU_API_URL` | `http://localhost:18000` | HTTP base URL |
| `MINERU_API_TIMEOUT_CONNECT` | `5` | httpx connect timeout (秒) |
| `MINERU_API_TIMEOUT_READ` | `30` | 单次 HTTP read (submit + poll, 秒) |
| `MINERU_API_TIMEOUT_DOWNLOAD` | `600` | GET /tasks/{id}/result 拉 ZIP (秒) |
| `MINERU_API_RETRY_ATTEMPTS` | `3` | tenacity stop_after_attempt (仅 POST) |
| `MINERU_API_POLL_INTERVAL` | `2` | GET /tasks/{id} 轮询基础间隔 (秒) |
| `MINERU_API_TASK_TIMEOUT` | `600` | 单个 task 总等待超时 (秒) |
| `MINERU_API_SYNC_MAX_BYTES` | `5242880` (5MB) | 单 PDF ≤ 此值走 `/file_parse` |
| `MINERU_API_MAX_CONCURRENT_BATCHES` | `3` | PDF 级 semaphore (配服务端限流 3) |

> `backend` / `parse_method` 暂不开放 env 覆盖, 硬编 `_SYNC_FORM_FIELDS` / `_ASYNC_FORM_FIELDS` 常量为 `"pipeline"` / `"auto"`。未来如需切 `vlm-transformers` 等, 另起 spec (YAGNI).

### `packages/service/src/common/defaults.py` (Dify 段后, Ingest 段前加)

```python
# =============================================================================
# Mineru HTTP API (2026-07-06 远程化改造)
# =============================================================================
# 接入点: src/ingest/pdf_processing/converters/mineru.py + mineru_client.py
# 自部署 mineru-api 服务端口映射见 docker/mineru-docker-compose.yml:65 (18000->8000)
DEFAULT_MINERU_API_URL: str = "http://localhost:18000"
DEFAULT_MINERU_API_TIMEOUT_CONNECT: int = 5
DEFAULT_MINERU_API_TIMEOUT_READ: int = 30
DEFAULT_MINERU_API_TIMEOUT_DOWNLOAD: int = 600
DEFAULT_MINERU_API_RETRY_ATTEMPTS: int = 3
DEFAULT_MINERU_API_POLL_INTERVAL: int = 2
DEFAULT_MINERU_API_TASK_TIMEOUT: int = 600
DEFAULT_MINERU_API_SYNC_MAX_BYTES: int = 5 * 1024 * 1024
DEFAULT_MINERU_API_MAX_CONCURRENT_BATCHES: int = 3
```

### `packages/service/src/config/settings.py` (Dify 字段后, Ingest 段前加)

```python
# ═══════════════════════════════════
# Mineru HTTP API (2026-07-06 远程化改造)
# ═══════════════════════════════════
mineru_api_url: str = field(
    default_factory=lambda: os.getenv("MINERU_API_URL", defaults.DEFAULT_MINERU_API_URL),
)
mineru_api_timeout_connect: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_TIMEOUT_CONNECT", str(defaults.DEFAULT_MINERU_API_TIMEOUT_CONNECT))),
)
mineru_api_timeout_read: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_TIMEOUT_READ", str(defaults.DEFAULT_MINERU_API_TIMEOUT_READ))),
)
mineru_api_timeout_download: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_TIMEOUT_DOWNLOAD", str(defaults.DEFAULT_MINERU_API_TIMEOUT_DOWNLOAD))),
)
mineru_api_retry_attempts: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_RETRY_ATTEMPTS", str(defaults.DEFAULT_MINERU_API_RETRY_ATTEMPTS))),
)
mineru_api_poll_interval: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_POLL_INTERVAL", str(defaults.DEFAULT_MINERU_API_POLL_INTERVAL))),
)
mineru_api_task_timeout: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_TASK_TIMEOUT", str(defaults.DEFAULT_MINERU_API_TASK_TIMEOUT))),
)
mineru_api_sync_max_bytes: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_SYNC_MAX_BYTES", str(defaults.DEFAULT_MINERU_API_SYNC_MAX_BYTES))),
)
mineru_api_max_concurrent_batches: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_MAX_CONCURRENT_BATCHES", str(defaults.DEFAULT_MINERU_API_MAX_CONCURRENT_BATCHES))),
)
```

### `packages/service/.env.example` (Dify 段后加)

```bash
# -----------------------------------------------------------------------------
# Mineru (远程 PDF 解析服务, 2026-07-06 改造)
# -----------------------------------------------------------------------------
# 自部署 mineru-api 服务地址. 主机端口 18000 对应 docker/mineru-docker-compose.yml:65
# (主机 18000->容器 8000, 跟 rag 服务 :8000 错开). CPU 服务器 mineru-api 跑不起来, 需 NVIDIA GPU.
MINERU_API_URL=http://localhost:18000
MINERU_API_TIMEOUT_CONNECT=5
MINERU_API_TIMEOUT_READ=30
MINERU_API_TIMEOUT_DOWNLOAD=600
MINERU_API_RETRY_ATTEMPTS=3
MINERU_API_POLL_INTERVAL=2
MINERU_API_TASK_TIMEOUT=600
MINERU_API_SYNC_MAX_BYTES=5242880
MINERU_API_MAX_CONCURRENT_BATCHES=3
```

### `packages/service/pyproject.toml` 删 `docker>=7.1.0`

```diff
-    "docker>=7.1.0", # docker-py SDK, mineru 容器生命周期管理
```

**删 dep 前 grep 验证 0 引用** ([feedback-check-pyproject-deps-match-actual-imports](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-check-pyproject-deps-match-actual-imports.md)):

```bash
grep -rE "import docker|from docker\b" packages/service/src packages/service/tests
```

期望: 0 命中. `mineru.py` 重写后 0 docker import.

### env 影响面主动列 ([feedback-audit-env-changes-introduce](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-audit-env-changes-introduce.md))

| 维度 | 影响 |
|---|---|
| 默认值 | `http://localhost:18000` (dev 期望启 `docker compose --profile api up`); 远程部署需覆盖 |
| 网络前提 | backend 必须能访问 `MINERU_API_URL`; 本地 docker 用 `localhost:18000`, 跨主机用 IP/域名 |
| env 切换 | 远程部署改 `MINERU_API_URL=http://gpu-host:18000`; 阈值/并发数可独立调 |
| 旧路径兼容 | **不兼容**——删 docker dep, docker 容器路径永久下线 |
| GPU 前提 | mineru-api 服务端需 NVIDIA GPU (CPU 跑不起来); backend 自身无 GPU 要求 |

---

## 5. 测试策略 (4 个文件)

**位置**: `packages/service/tests/ingest/` 下 4 个文件, 全 mock httpx (**0 真实 HTTP**, [feedback-test-must-be-100pct-mock-no-real-db](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-test-must-be-100pct-mock-no-real-db.md))

### 文件 1: `test_mineru_client.py` — HTTP 调度器契约

**测什么**: `MineruClient` 单文件调度的 HTTP 路径 (不涉及 semaphore / 阈值路由)

**Mock 模式**: 仿 [packages/service/tests/integrations/test_dify_client.py:60-94](packages/service/tests/integrations/test_dify_client.py#L60-L94) 的 `_MockClient` + `_MockResp` 风格

```python
class _FakeResp:
    """httpx.Response 的最小替身"""
    def __init__(self, status_code, json_data=None, body=b"", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = body.decode("utf-8", errors="replace") if body else ""
        self.content = body
        self.headers = headers or {}

    def json(self): return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}",
                                        request=MagicMock(), response=self)


class _FakeClient:
    """httpx.Client 替身: 录制调用, 按预编程序列返响应"""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.closed = False
    def __enter__(self): return self
    def __exit__(self, *a): self.closed = True; return False
    def post(self, url, *, files=None, data=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "data": data, "files_count": len(files or [])})
        return self._responses.pop(0)
    def get(self, url, *, timeout=None):
        self.calls.append({"method": "GET", "url": url, "timeout": timeout})
        return self._responses.pop(0)
```

#### TestSubmitSync

- `test_sync_returns_md_map`: POST /file_parse 返 JSON results → `{stem: md_content}`
- `test_sync_4xx_raises_run_error`: 4xx 立即 RunError, 不重试 (只调 1 次)
- `test_sync_network_error_raises_run_error`: httpx.ConnectError → RunError(exit_code=0)

#### TestSubmitAsync

- `test_async_returns_task_id`: POST /tasks 返 202 → task_id
- `test_async_5xx_triggers_retry`: 第 1 次 500, 第 2 次 202 (mock `time.sleep` 跳过退避)

#### TestPollUntilTerminal

- `test_completed_returns_payload`: status=completed → 返 payload
- `test_failed_returns_payload`: status=failed → 返 payload (上层 `_run_one` 判定后转 RunError)
- `test_timeout_raises_run_error`: 轮询超过 task_timeout → RunError(exit_code=0)

#### TestDownloadResult

- `test_download_returns_zip_bytes`: GET /tasks/{id}/result → bytes

### 文件 2: `test_mineru_converter.py` — 编排层 (磁盘真相源 + 阈值路由)

**测什么**: `MineruConverter.convert_batch` 的编排 (mock `MineruClient`, 不真发 HTTP)

#### TestSyncVsAsyncRouting

- `test_small_pdf_routes_to_sync`: ≤ sync_max_bytes 走 submit_sync, submit_async 未被调
- `test_large_pdf_routes_to_async`: > sync_max_bytes 走 submit_async + poll + download

#### TestConvertBatchOrchestration

- `test_empty_input_returns_empty_dict`
- `test_missing_md_triggers_retry`: 第 1 轮跑完但磁盘无 md → 触发第 2 轮单独重试
- `test_retry_still_fails_marks_error`: 第 2 轮仍失败 → `results[path] = "[ERROR] ..."`

### 文件 3: `test_mineru_retry.py` — tenacity 重试 + 轮询退避

**测什么**: `_post` 的 tenacity 重试 + `poll_until_terminal` 的指数退避

#### TestPostRetry

- `test_5xx_triggers_retry_then_success`: 5xx 第 1 次, 202 第 2 次 → 返 task_id
- `test_4xx_no_retry`: 4xx 立即 RunError, 只调 1 次
- `test_network_error_triggers_retry`: httpx.ConnectError → 重试 → 成功
- `test_retry_exhausted_raises_run_error`: 3 次 5xx 后 reraise RunError(exit_code=500)

#### TestPollBackoff

- `test_exponential_backoff_cap`: 轮询间隔指数增长, 封顶 10s
- `test_completed_no_sleep_after_terminal`: status=completed 拿到立即返, 不再 sleep

### 文件 4: `test_mineru_semaphore.py` — 并发峰值 (峰值测试必备)

**测什么**: semaphore 实际限流效果 ([feedback-asyncio-sem-needs-peak-test](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-asyncio-sem-needs-peak-test.md))

```python
class TestPdfSemaphore:
    """asyncio.Semaphore 峰值测试"""

    @pytest.mark.asyncio
    async def test_peak_concurrency_matches_env(self, monkeypatch, tmp_path):
        """10 个 PDF 同时跑 → 同时最多 max_concurrent_batches 个进入临界区"""
        in_flight = 0
        peak = 0
        lock = asyncio.Lock()

        async def slow_submit(*a, **kw):
            nonlocal in_flight, peak
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1
            return "task-x"

        monkeypatch.setattr("...mineru.MineruClient.submit_async", slow_submit)
        monkeypatch.setattr("...mineru.MineruClient.poll_until_terminal",
                            lambda *a, **kw: {"status": "completed"})
        monkeypatch.setattr("...mineru.MineruClient.download_result",
                            lambda *a, **kw: b"")
        monkeypatch.setattr("...mineru.MineruConverter._extract_result_zip",
                            lambda *a, **kw: None)

        for i in range(10):
            (tmp_path / f"p{i}.pdf").write_bytes(b"%PDF-1.4\n")
        pdfs = [str(tmp_path / f"p{i}.pdf") for i in range(10)]

        await asyncio.gather(*[
            MineruConverter()._run_one_async(p, str(tmp_path))
            for p in pdfs
        ])
        assert peak <= 3, f"peak={peak} 超过 semaphore 上限"
        assert peak >= 2, f"peak={peak} 应该至少 2 验证并发真发生"

    def test_semaphore_is_module_level_singleton(self):
        """模块级 _mineru_semaphore 单例, 100 个 converter 实例共享"""
        # 断言 id(MineruConverter._get_semaphore()) 多次调用一致
```

### Mock 模式总结

| 测试文件 | mock 对象 | 0 真实依赖 |
|---|---|---|
| `test_mineru_client.py` | `httpx.Client` (`monkeypatch.setattr`) | ✅ |
| `test_mineru_converter.py` | `MineruClient` (`monkeypatch.setattr` 类) | ✅ |
| `test_mineru_retry.py` | `httpx.Client` + `time.sleep` | ✅ |
| `test_mineru_semaphore.py` | `MineruClient.{submit,poll,download}` | ✅ |

### 测试覆盖目标

- 模式 1 mock (CLAUDE.md 强制): 0 PG / 0 Redis / 0 Neo4j / 0 真实 HTTP / 0 真实 docker
- 现有 baseline 1075 pass + 22 fail + 38 errors pre-existing, 本 spec 不动
- 删除文件: `tests/ingest/test_mineru_container_cleanup.py` (绑死 docker) + `tests/integration/test_mineru_retry_e2e.py` 第 17-51 行 (`_docker_daemon_alive` helper) → 改 `_mineru_api_alive` HTTP 健康探测

---

## 6. commit 拆分 (5 commit) + 文档

### 5 commit 拆细 (按决策点 6)

#### Commit 1: `feat(mineru): 新增 MineruClient HTTP 调度器 + env 9 项 + defaults/settings/.env.example 同步`

| 范围 | 涉及文件 |
|---|---|
| 新建 `mineru_client.py` (~200 行: HTTP 调度器 + RunError) | `packages/service/src/ingest/pdf_processing/converters/mineru_client.py` |
| env 三件套同步 (8 个常量 + 字段 + .env.example) | `defaults.py` + `settings.py` + `.env.example` |
| 测试: `test_mineru_client.py` + `test_mineru_retry.py` (mock httpx) | `packages/service/tests/ingest/{test_mineru_client,test_mineru_retry}.py` |

**为什么先建 client 不动 converter**: client 独立可测, 零替换 `mineru.py` 现有 docker 路径. pyproject **不删 docker dep** (这版仍共存, commit 2 才删). 可独立 review / bisect.

#### Commit 2: `refactor(ingest): MineruConverter 切到 MineruClient + 阈值路由 + PDF 级 semaphore`

| 范围 | 涉及文件 |
|---|---|
| 重写 `mineru.py` (拆 `_run_one_async` + 阈值选 sync/async + semaphore + ZIP 防越界) | `packages/service/src/ingest/pdf_processing/converters/mineru.py` |
| 测试: `test_mineru_converter.py` (编排 + 阈值路由 + 失败重试) | `packages/service/tests/ingest/test_mineru_converter.py` |
| 删 docker 残留 (`tempfile` / `shutil` 导入如有) | 同 mineru.py |

#### Commit 3: `test(mineru): 删 docker-py 绑定测试 + 改 e2e health 探测`

| 范围 | 涉及文件 |
|---|---|
| 删 `test_mineru_container_cleanup.py` (绑死 docker 的旧 cleanup 测试) | `packages/service/tests/ingest/test_mineru_container_cleanup.py` |
| `test_converters.py` 删 `TestMineruEndToEnd` (绑死 docker 的 e2e 类) | `packages/service/tests/ingest/test_converters.py` |
| `test_mineru_retry_e2e.py` `_docker_daemon_alive` → `_mineru_api_alive` (GET /health) | `packages/service/tests/integration/test_mineru_retry_e2e.py` |
| 新建 `test_mineru_semaphore.py` (峰值测试) | `packages/service/tests/ingest/test_mineru_semaphore.py` |

#### Commit 4: `chore(deps): 删 docker-py 依赖`

| 范围 | 涉及文件 |
|---|---|
| `pyproject.toml` 删 `docker>=7.1.0` 整行 | `packages/service/pyproject.toml` |
| `uv.lock` 重新 lock (commit 自动包含) | `packages/service/uv.lock` |

**为什么 commit 4 单独拆**: 删 dep 是不可逆点 (决策点 7). 独立 commit 让 review 聚焦 "是否真没 docker 引用了", 出问题 revert 这个 commit + 重加 dep 即可, 不污染代码逻辑 commit. `grep -rE "import docker|from docker" src/ tests/` 必须 0 命中后才走.

#### Commit 5: `docs(chore): 标注 mineru-api 端口对应 env + 部署 cookbook + CLAUDE.md 段`

| 范围 | 涉及文件 |
|---|---|
| `docker/mineru-docker-compose.yml` mineru-api profile 加注释 (端口 18000 对应 `MINERU_API_URL` 默认值) | `docker/mineru-docker-compose.yml` |
| 新建 `docs/cookbook/ingest/mineru-http.md` (dev 部署 + env + GPU 前提 + 排障) | `docs/cookbook/ingest/mineru-http.md` |
| `packages/service/CLAUDE.md` 加 "Mineru HTTP 客户端 (2026-07-06)" 段 | `packages/service/CLAUDE.md` |

### 文档内容

#### `docker/mineru-docker-compose.yml`

在 `mineru-api` profile 的 `ports: "18000:8000"` 上方加注释:

```yaml
    # 主机端口 18000 对应 packages/service/.env.example MINERU_API_URL 默认值
    # (跟 rag 服务 :8000 错开; CPU 服务器 mineru-api 跑不起来, 需 NVIDIA GPU)
```

#### `docs/cookbook/ingest/mineru-http.md` (新建)

内容覆盖: 概述 / 部署步骤 / 排障表 / 改造前后差异表 (与本 spec 3.1 节"关键决策"同步).

#### `packages/service/CLAUDE.md` (在 "ObjectStore ABC 使用" 段后加)

内容覆盖: 模块边界 / 双路径选择 / 8 env 表 / 测试模式.

---

## 7. 验证清单 + 回滚方案 + 项目硬约束复核

### 验证清单

#### Commit 1 (client + env) 后跑

```bash
cd packages/service
uv run pytest tests/ingest/test_mineru_client.py tests/ingest/test_mineru_retry.py -v
uv run ruff format .
uv run ruff check --fix .
uv run pyright
```

期望: 8+5 = 13 个新 test 全 PASS, 0 lint / 0 pyright error.

#### Commit 2 (converter 切换) 后跑

```bash
cd packages/service
uv run pytest tests/ingest/ -v --no-header
```

期望: 除 `test_mineru_container_cleanup.py` (commit 3 删), 其他 ingest test 全 PASS. `test_converters.py::TestMineruConverter` + `TestMineruParseFailedFiles` 跟 HTTP 无关, 必须 PASS.

#### Commit 3 (测试清理) 后跑

```bash
cd packages/service
uv run pytest tests/ingest/ tests/integration/test_mineru_retry_e2e.py -v
```

期望:
- `test_mineru_container_cleanup.py` 0 命中 (已删)
- `test_converters.py::TestMineruEndToEnd` 0 命中 (已删)
- `test_mineru_retry_e2e.py` 自动 SKIP (dev 未起 mineru-api, HTTP health 探测返 False)
- `test_mineru_semaphore.py` peak ≤ 3, peak ≥ 2

#### Commit 4 (删 dep) 前必跑

```bash
cd packages/service
grep -rE "import docker|from docker\b" src/ tests/
```

期望: 0 命中 (commit 3 已删尽). 否则 **STOP**, 不删 dep.

#### Commit 4 (删 dep) 后跑

```bash
cd packages/service
uv lock                    # 重新 lock
uv run pyright             # 0 error
uv run pytest --no-header -q 2>&1 | tail -30
```

期望: pass 数 ≥ 1075 (基线), pre-existing 22 fail + 38 errors 保持不变.

#### Commit 5 (文档) 后跑

```bash
cd packages/service
uv run ruff format .    # 0 error
uv run ruff check .     # 0 error (markdown 不影响 pyright)
```

期望: 0 error.

### 完整本地 dev 端到端验证 (5 commit 全完后)

```bash
# 1. 起 mineru-api
cd docker
docker compose -f mineru-docker-compose.yml --profile api up -d
sleep 10   # 等模型加载

# 2. 验 health
curl http://localhost:18000/health
# 期望: {"status": "ok", "version": "...", "protocol_version": 2}

# 3. 改 backend env
echo "MINERU_API_URL=http://localhost:18000" >> packages/service/.env

# 4. 手动跑 convert_batch (小文件, 走 sync)
cd packages/service
uv run python -c "
from src.ingest.pdf_processing.converters import MineruConverter
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'out'); os.makedirs(out)
    r = MineruConverter().convert_batch(['tests/fixtures/complex_pdf_test.pdf'], out)
    print('小文件 sync 结果:', list(r.keys()), 'md len:', len(list(r.values())[0]) if r else 0)
"

# 5. 手动跑 convert_batch (大文件, 走 async)
dd if=/dev/urandom of=/tmp/large.pdf bs=1M count=10   # 10MB
uv run python -c "
from src.ingest.pdf_processing.converters import MineruConverter
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'out'); os.makedirs(out)
    r = MineruConverter().convert_batch(['/tmp/large.pdf'], out)
    print('大文件 async 结果:', list(r.keys()))
"

# 6. 验磁盘布局
ls -la /tmp/.../out/large/auto/large.md   # 期望存在
```

### 真实 e2e (可选, 需要 mineru-api 跑着)

```bash
cd packages/service
RUN_SLOW_TESTS=1 INTEGRATION=1 \
  uv run pytest tests/integration/test_mineru_retry_e2e.py -m slow -v
```

期望: 8 个文件批处理 + 1 个失败触发重试 → 全成功.

### 回滚方案

#### Commit 1-3 任意一 commit 引入 prod 问题

```bash
git revert <commit_hash>
# revert 后 mineru.py 自动回到 docker 路径, mineru_client.py 文件仍在但 0 调用, 安全
```

#### Commit 4 (删 docker dep) 后出问题

```bash
git revert <commit_4_hash>
# 重加 docker>=7.1.0 到 pyproject.toml
uv lock
uv sync
# mineru.py + mineru_client.py 仍在 (commit 1-3 未 revert), 但 mineru.py 现在用 MineruClient (commit 2 改了)
# → 必须连 revert commit 2 + 1 + 4 才能彻底回 docker 路径
```

**commit 4 的不可逆点**: 删 dep 跟 commit 1-2 强耦合. 回滚要 3 commit 一起 revert. 建议 commit 1-3 充分验证 (≥ 1 天 dev 跑) 后再走 commit 4.

#### Commit 5 (文档) 出问题

```bash
git revert <commit_5_hash>
# 0 代码影响, 仅 markdown 回滚
```

### 项目硬约束复核

| 约束 | 来源 | 本设计落实 |
|---|---|---|
| 5 步走 (format → lint → typecheck → test → commit) | [CLAUDE.md 工具链](c:/doc/Code/rag/CLAUDE.md) | 每个 commit 前必跑 |
| 禁 shim / 兼容 / 兜底 | [feedback-no-shim-no-minimal-changes](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-no-shim-no-minimal-changes.md) | 双路径是设计选择 (sync/async 阈值路由), 不是 shim |
| 测试 100% mock, 0 真实 DB/HTTP | [feedback-test-must-be-100pct-mock-no-real-db](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-test-must-be-100pct-mock-no-real-db.md) | 4 个测试文件全 mock httpx / MineruClient |
| 删 dep 前 grep 验证 0 引用 | [feedback-check-pyproject-deps-match-actual-imports](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-check-pyproject-deps-match-actual-imports.md) | commit 4 前 `grep -rE "import docker"` 必须 0 命中 |
| 新增 env 主动列影响面 | [feedback-audit-env-changes-introduce](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-audit-env-changes-introduce.md) | 设计 4/N 列了 8 env 影响面 |
| asyncio.Semaphore 配峰值测试 | [feedback-asyncio-sem-needs-peak-test](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-asyncio-sem-needs-peak-test.md) | `test_mineru_semaphore.py::test_peak_concurrency_matches_env` 必跑 |
| 删 BFF route 跑契约测试 | [.claude/CLAUDE.md 重构规则](c:/doc/Code/rag/.claude/CLAUDE.md) | 本 spec 不删 BFF route, 跳过 |
| 业务 enum 走 lookup 字典 | [packages/service/CLAUDE.md](packages/service/CLAUDE.md) | 不新增 StrEnum |
| alembic 迁移可回滚 | CLAUDE.md | 本 spec 不改 schema |
| `feedback-record-errors-and-lessons` | 用户总要求 | 实施期踩坑记 memory |
| 单次 `--fix` 改 > 500 行停下问 | CLAUDE.md | commit 1 (~250) / 2 (~300) / 3 (~350) / 4 (~5) / 5 (~150) 全在限额内 |
| pytest 基线 1075 + 22f + 38e pre-existing | [KNOWN_ISSUES.md](packages/service/KNOWN_ISSUES.md) | commit 4 后跑全套确认不变 |
| 函数内 import 规范 (E402) | CLAUDE.md 2026-07-06 spec | mineru_client.py 模块顶层全 import, 无函数内 |
| 分批提交大改动 | [feedback-commit-in-batches-for-large-changes](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-commit-in-batches-for-large-changes.md) | 5 commit 拆细 |
| 卡住 30 分钟 STOP 报告 | [feedback-stop-and-ask-dont-loop-on-infra](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-stop-and-ask-dont-loop-on-infra.md) | 实施期如遇 mineru-api 容器 / GPU 问题 STOP |
| 永远不要 git checkout 撤用户改 | [feedback-never-revert-user-edits](C:\Users\abcuc\.claude\projects\c--doc-Code-rag\memory\feedback-never-revert-user-edits.md) | commit 前 `git status` 确认无残留 |
| dev 别动辄跑全量测试 | [feedback-no-full-vitest-during-dev](C:\Users\abcuc\.projects\c--doc-Code-rag\memory\feedback-no-full-vitest-during-dev.md) | 开发期只跑改过的文件 |
| 改前端 URL 顺序 (先 BFF → 后端 → 前端) | .claude/CLAUDE.md | 本 spec 0 前端改动 |
| 类型 ignore 带具体错误码 + 注释 | CLAUDE.md | pyright 0 error 目标, 无 type: ignore |
| 测试隔离 4 模式 | [packages/service/CLAUDE.md](packages/service/CLAUDE.md) | 全模式 1 mock |

---

## 8. Spec 元数据

### 相关文档

- 旧 plan (覆盖式同步): `docs/superpowers/plans/2026-07-03-mineru-http-remote.md`
- 旧 spec 无关 (参考用): `docs/superpowers/specs/2026-07-02-mineru-minio-integration-design.md`
- mineru 客户端现状: [packages/service/src/ingest/pdf_processing/converters/mineru.py](packages/service/src/ingest/pdf_processing/converters/mineru.py)
- mineru 服务端编排: [docker/mineru-docker-compose.yml](docker/mineru-docker-compose.yml)
- mineru 客户端基线 wire map: [packages/service/src/ingest/pdf_processing/converters/](packages/service/src/ingest/pdf_processing/converters/)
- HTTP client 模式参考: [packages/service/src/integrations/dify_client.py:104-115](packages/service/src/integrations/dify_client.py#L104-L115)
- retry 谓词模式参考: [packages/service/src/integrations/dify_client.py:37-43](packages/service/src/integrations/dify_client.py#L37-L43)
- 测试 mock 样板: [packages/service/tests/integrations/test_dify_client.py:60-94](packages/service/tests/integrations/test_dify_client.py#L60-L94)
- env 三件套样板 (Dify 段): [packages/service/src/common/defaults.py:65-70](packages/service/src/common/defaults.py#L65-L70) + [packages/service/src/config/settings.py:140-154](packages/service/src/config/settings.py#L140-L154) + [packages/service/.env.example:75-82](packages/service/.env.example#L75-L82)

### 决策摘要 (来自 8 轮 brainstorms)

| # | 决策点 | 拍板 |
|---|---|---|
| 1 | HTTP 路径 | 双路径 (sync /file_parse + async /tasks) + PDF 级 semaphore |
| 2 | 范围 | 全包 (代码 + docker 注释 + cookbook + CLAUDE.md) |
| 3 | 实现粒度 | 拆 `MineruClient` (HTTP 调度器独立) |
| 4 | `/file_parse` 行为 | 服务端写文件 (默认行为, response_format_zip=true) |
| 5 | 同步阈值 | 5MB 可配 (env `MINERU_API_SYNC_MAX_BYTES`) |
| 6 | commit 拆分 | 5 commit 拆细 (client / converter / test / dep / doc) |
| 7 | docker dep 留不留 | commit 1 直接删 (不可逆, 现有 plan 方案) |
| 8 | spec / plan 文件 | 新写 spec + 覆盖式同步旧 plan |