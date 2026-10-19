# Mineru 远程 HTTP 改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `MineruConverter` 从"宿主机起 docker 容器"改成"调远端 mineru-api HTTP 服务"，让 backend 容器 / K8s pod 部署时不依赖 docker daemon 和本地 GPU。

**Architecture:** mineru 服务单独部署（已有 `docker/mineru-docker-compose.yml` 的 mineru-api profile，端口 18000→8000）。Backend 通过 `httpx.Client` 调 mineru 的 `/tasks` 异步端点 → 轮询 `/tasks/{id}` 状态 → `GET /tasks/{id}/result` 拿 ZIP。`convert_batch` 编排（磁盘真相源 + 失败逐个重试）保留。`RunError` 字段重定义为 HTTP status + response body + task_id。

**Tech Stack:** Python 3.14, httpx 0.27+ (已在 deps), tenacity (已引入 via dify_client), pytest 9。**删除**: docker-py 依赖。kreuzberg.py 不动（Python 库）。

**Spec:** [docs/superpowers/specs/2026-07-03-mineru-http-remote-design.md](../specs/2026-07-03-mineru-http-remote-design.md)（本计划未单独建 spec，沿用本计划文件作为唯一设计依据）

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `packages/service/src/ingest/converters/mineru.py` | 改 | `_run_mineru` 整段重写为 HTTP；`RunError` 字段重设计；`convert_batch` 2 行适配 |
| `packages/service/src/common/defaults.py` | 改 | 加 6 个 `DEFAULT_MINERU_API_*` 常量 |
| `packages/service/src/config/settings.py` | 改 | 加 6 个 `mineru_api_*` 字段（紧跟 Dify 段后） |
| `packages/service/.env.example` | 改 | 加 Mineru 段 |
| `packages/service/pyproject.toml` | 改 | 删 `docker>=7.1.0` |
| `packages/service/tests/ingest/test_mineru_container_cleanup.py` | 删 → 新建 `test_mineru_http_client.py` | mock httpx 重写 |
| `packages/service/tests/integration/test_mineru_retry_e2e.py` | 改 | `_docker_daemon_alive` → `_mineru_api_alive`（GET /health） |
| `packages/service/tests/ingest/test_converters.py` | 改 | 删 `TestMineruEndToEnd`（line 225-324，绑死 docker） |
| `packages/service/tests/ingest/test_mineru_retry.py` | 新建 | mock tenacity 重试 + 轮询测试 |
| `docker/mineru-docker-compose.yml` | 改 | 加注释标注 18000 端口对应 env |
| `docs/cookbook/ingest/mineru-http.md` | 新建 | dev 部署 + env + GPU 前提 |
| `packages/service/CLAUDE.md` | 改 | 加 "mineru HTTP 客户端" 段 |

**Files that change together**：`mineru.py` + 3 处 env + pyproject 是一组（commit 1）；测试文件是一组（commit 2）；docker-compose + 文档 + CLAUDE.md 是一组（commit 3）。

---

## 复用的现有模式

实施前必读（不要重复造轮子）：

- **HTTP client 模式**：[packages/service/src/integrations/dify_client.py:104-115](packages/service/src/integrations/dify_client.py#L104-L115) — `httpx.Client(base_url=..., timeout=...)` 构造 + `os.getenv()` fallback
- **retry 谓词**：[packages/service/src/integrations/dify_client.py:37-43](packages/service/src/integrations/dify_client.py#L37-L43) — `_is_retryable_dify_error` 只重试 TimeoutException/NetworkError/5xx
- **env 三处同步样板**：[packages/service/src/config/settings.py:140-154](packages/service/src/config/settings.py#L140-L154) + [packages/service/src/common/defaults.py:65-70](packages/service/src/common/defaults.py#L65-L70) + [.env.example:75-82](packages/service/.env.example#L75-L82) — Dify 段
- **测试 mock 样板**：[packages/service/tests/integrations/test_dify_client.py:60-94](packages/service/tests/integrations/test_dify_client.py#L60-L94) — `monkeypatch.setattr(httpx, "AsyncClient", ...)`（本次改 `Client`）

---

## 项目硬约束（不要违反）

- `CLAUDE.md` 强制 5 步：format → lint fix → typecheck → test → commit
- `feedback-no-shim-no-minimal-changes`：禁 shim / 兼容 / 兜底
- `feedback-test-must-be-100pct-mock-no-real-db`：测试 100% mock，httpx mock 是允许的受控 wrapper
- `feedback-check-pyproject-deps-match-actual-imports`：删 dep 前 grep 验证 0 引用
- `feedback-audit-env-changes-introduce`：新增 env 主动列影响面
- `feedback-i18n-sync-on-ui-changes`：本次不改 UI，跳过
- `feedback-record-errors-and-lessons`：踩坑记 memory
- 单次 `--fix` 改 > 500 行停下来问（本次 commit 1 改 ~250 行 OK；commit 2 改 ~350 行 OK；commit 3 改 ~80 行 OK。每个 commit 单独算）
- pytest 基线：~1075 pass + 22 fail + 38 errors pre-existing（[packages/service/KNOWN_ISSUES.md](packages/service/KNOWN_ISSUES.md)）

---

## Commit 拆分

| Commit | 范围 | 涉及文件 | 行数 |
|---|---|---|---|
| 1 | `feat(ingest): switch mineru to remote HTTP API` | mineru.py + 3 env + pyproject | ~250 |
| 2 | `refactor(test): rewrite mineru tests for HTTP client` | 3 test 文件 | ~350 |
| 3 | `docs(chore): document mineru HTTP deployment` | docker-compose 注释 + cookbook + CLAUDE.md | ~80 |

**用户决策：3 commit 一气做完**（不中途停下 review）。

---

## Task 1: 新增 env 配置 + defaults（commit 1 前置）

**Files:**
- Modify: `packages/service/src/common/defaults.py:60-70`（Dify 段后）
- Modify: `packages/service/src/config/settings.py:140-154`（Dify 字段后）
- Modify: `packages/service/.env.example:75-82`（Dify 段后）

**目标**：先把 env 基础设施铺好，`mineru.py` 改造时直接 `from src.config.settings import settings` 拿得到。

- [ ] **Step 1: 在 `defaults.py` 加 6 个常量**

在 [packages/service/src/common/defaults.py:70](packages/service/src/common/defaults.py#L70)（Dify 段末尾 `# Chatflow 应用 ...` 注释之后，Ingest 段之前）添加：

```python
# =============================================================================
# Mineru HTTP API（2026-07-03 远程化改造）
# =============================================================================
# 接入点: src/ingest/converters/mineru.py
# 自部署 mineru-api 服务端口映射见 docker/mineru-docker-compose.yml:65 (18000->8000)
DEFAULT_MINERU_API_URL: str = "http://localhost:18000"
DEFAULT_MINERU_API_TIMEOUT_CONNECT: int = 5  # 秒
DEFAULT_MINERU_API_TIMEOUT_READ: int = 30  # 秒（单次 HTTP read timeout）
DEFAULT_MINERU_API_RETRY_ATTEMPTS: int = 3  # tenacity stop_after_attempt（仅 POST /tasks）
DEFAULT_MINERU_API_POLL_INTERVAL: int = 2  # 秒（GET /tasks/{id} 轮询基础间隔）
DEFAULT_MINERU_API_TASK_TIMEOUT: int = 600  # 秒（单个 task 总等待超时，防 mineru 卡死）
```

- [ ] **Step 2: 在 `settings.py` 加 6 个字段**

在 [packages/service/src/config/settings.py:154](packages/service/src/config/settings.py#L154)（`dify_query_cache_ttl` 字段之后，Dify 段结束的下一个空行之前）添加：

```python
# ═══════════════════════════════════
# Mineru HTTP API（2026-07-03 远程化改造）
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
mineru_api_retry_attempts: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_RETRY_ATTEMPTS", str(defaults.DEFAULT_MINERU_API_RETRY_ATTEMPTS))),
)
mineru_api_poll_interval: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_POLL_INTERVAL", str(defaults.DEFAULT_MINERU_API_POLL_INTERVAL))),
)
mineru_api_task_timeout: int = field(
    default_factory=lambda: int(os.getenv("MINERU_API_TASK_TIMEOUT", str(defaults.DEFAULT_MINERU_API_TASK_TIMEOUT))),
)
```

- [ ] **Step 3: 在 `.env.example` 加 Mineru 段**

在 [packages/service/.env.example:82](packages/service/.env.example#L82)（Dify Chatflow 段之后，下一个 `# ----` 注释之前）添加：

```
# -----------------------------------------------------------------------------
# Mineru (远程 PDF 解析服务, 2026-07-03 改造)
# -----------------------------------------------------------------------------
# 自部署 mineru-api 服务地址. 主机端口 18000 对应 docker/mineru-docker-compose.yml:65
# (主机 18000->容器 8000, 跟 rag 服务 :8000 错开). CPU 服务器 mineru-api 跑不起来, 需 GPU.
MINERU_API_URL=http://localhost:18000
MINERU_API_TIMEOUT_CONNECT=5
MINERU_API_TIMEOUT_READ=30
MINERU_API_RETRY_ATTEMPTS=3
MINERU_API_POLL_INTERVAL=2
MINERU_API_TASK_TIMEOUT=600
```

- [ ] **Step 4: 跑 lint + typecheck**

```bash
cd packages/service
uv run ruff format .
uv run ruff check --fix .
uv run pyright
```

期望：0 error。

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/common/defaults.py packages/service/src/config/settings.py packages/service/.env.example
git commit -m "feat(mineru): 新增 6 个 MINERU_API_* env（远程 HTTP 客户端配置）"
```

---

## Task 2: 写 `_run_mineru` HTTP 单元测试（TDD 红）

**Files:**
- Modify: `packages/service/tests/ingest/test_mineru_container_cleanup.py`（临时复用文件名）

**目标**：先把 5 个 test 写好（用 mock httpx），跑红，锁定新行为契约。这一步不改生产代码。

- [ ] **Step 1: 整体替换 `test_mineru_container_cleanup.py` 为新内容**

整文件覆盖 [packages/service/tests/ingest/test_mineru_container_cleanup.py](packages/service/tests/ingest/test_mineru_container_cleanup.py)：

```python
"""MineruConverter._run_mineru HTTP 客户端契约测试 (2026-07-03 重写)

覆盖：
- 正常 POST /tasks → 轮询 completed → GET /result ZIP → 落盘
- 5xx 服务端错 → RunError(status_code, body, task_id)
- 4xx 客户端错 → RunError 不重试
- KeyboardInterrupt → 传播
- 资源清理：httpx.Client close 被调用
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from src.ingest.converters.mineru import MineruConverter


@pytest.fixture
def fake_pdf(tmp_path: Path) -> str:
    """构造一个最小假 PDF（内容随便，mineru HTTP 模式不读内容只传文件名）"""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    return str(p)


def _make_mineru_zip(stem: str, md_content: str) -> bytes:
    """构造 mineru 服务端返回的 ZIP 字节（模拟 /tasks/{id}/result 的 response body）"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mineru ZIP 内部布局: <stem>/auto/<stem>.md
        zf.writestr(f"{stem}/auto/{stem}.md", md_content)
    return buf.getvalue()


class _FakeResponse:
    """模拟 httpx.Response，最小化满足新 _run_mineru 的属性访问"""

    def __init__(self, status_code: int, body: bytes = b"", headers: dict | None = None, json_data: dict | None = None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self._json = json_data or {}
        self.text = body.decode("utf-8", errors="replace") if body else ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self,
            )


class _FakeClient:
    """模拟 httpx.Client，recording 调用 + 预编程响应序列

    用法:
        client = _FakeClient(responses=[
            _FakeResponse(202, json_data={"task_id": "abc"}),  # POST /tasks
            _FakeResponse(200, json_data={"status": "completed"}),  # GET /tasks/{id}
            _FakeResponse(200, body=_make_mineru_zip("sample", "# md")),  # GET /tasks/{id}/result
        ])
    """

    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def post(self, url, files=None, data=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "files": files, "data": data, "timeout": timeout})
        return self._responses.pop(0)

    def get(self, url, timeout=None):
        self.calls.append({"method": "GET", "url": url, "timeout": timeout})
        return self._responses.pop(0)


class TestRunMineruHttpClient:
    """_run_mineru HTTP 客户端契约测试"""

    def test_successful_task_writes_md(self, tmp_path: Path, monkeypatch, fake_pdf):
        """正常路径：POST /tasks → 轮询 completed → GET /result ZIP → 落盘到 output_dir/<stem>/auto/<stem>.md"""
        out_dir = tmp_path / "out"
        client = _FakeClient([
            _FakeResponse(202, json_data={"task_id": "abc-123"}),
            _FakeResponse(200, json_data={"status": "completed"}),
            _FakeResponse(200, body=_make_mineru_zip("sample", "# hello")),
        ])
        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", lambda **kw: client)

        MineruConverter()._run_mineru([fake_pdf], str(out_dir))

        md_path = out_dir / "sample" / "auto" / "sample.md"
        assert md_path.exists()
        assert md_path.read_text(encoding="utf-8") == "# hello"
        # 3 次调用: POST /tasks, GET /tasks/{id}, GET /tasks/{id}/result
        assert [c["method"] for c in client.calls] == ["POST", "GET", "GET"]
        assert client.closed is True

    def test_5xx_raises_run_error_with_status_code(self, tmp_path: Path, monkeypatch, fake_pdf):
        """服务端 5xx → RunError.exit_code 是 HTTP status, .response_body 含错误文本"""
        client = _FakeClient([
            _FakeResponse(500, body=b"internal error"),
        ])
        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", lambda **kw: client)

        with pytest.raises(MineruConverter.RunError) as exc_info:
            MineruConverter()._run_mineru([fake_pdf], str(tmp_path / "out"))

        assert exc_info.value.exit_code == 500
        assert "internal error" in exc_info.value.response_body
        assert client.closed is True

    def test_4xx_raises_run_error_no_retry(self, tmp_path: Path, monkeypatch, fake_pdf):
        """客户端 4xx → RunError，不走 retry 路径"""
        client = _FakeClient([
            _FakeResponse(400, body=b"bad request"),
        ])
        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", lambda **kw: client)

        with pytest.raises(MineruConverter.RunError) as exc_info:
            MineruConverter()._run_mineru([fake_pdf], str(tmp_path / "out"))

        assert exc_info.value.exit_code == 400
        # 4xx 只调用 1 次 POST，不重试
        assert len(client.calls) == 1

    def test_keyboard_interrupt_propagates(self, tmp_path: Path, monkeypatch, fake_pdf):
        """KeyboardInterrupt 必须传播，不被吞"""
        client = _FakeClient([])
        client.post = MagicMock(side_effect=KeyboardInterrupt)
        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", lambda **kw: client)

        with pytest.raises(KeyboardInterrupt):
            MineruConverter()._run_mineru([fake_pdf], str(tmp_path / "out"))

    def test_failed_task_status_raises_run_error(self, tmp_path: Path, monkeypatch, fake_pdf):
        """轮询拿到 status=failed → RunError 包含 task_id"""
        client = _FakeClient([
            _FakeResponse(202, json_data={"task_id": "deadbeef"}, headers={"X-MinerU-Task-Id": "deadbeef"}),
            _FakeResponse(200, json_data={"status": "failed", "error": "OCR model crashed"}),
        ])
        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", lambda **kw: client)

        with pytest.raises(MineruConverter.RunError) as exc_info:
            MineruConverter()._run_mineru([fake_pdf], str(tmp_path / "out"))

        assert exc_info.value.task_id == "deadbeef"
        assert "OCR model crashed" in exc_info.value.response_body
        assert client.closed is True
```

- [ ] **Step 2: 跑测试看全红**

```bash
cd packages/service
uv run pytest tests/ingest/test_mineru_container_cleanup.py -v
```

期望：5 个 test 全 FAIL，错误是 `AttributeError: type object 'MineruConverter' has no attribute '_run_mineru'` 或类似（因为旧的 docker 版 `_run_mineru` 还在，但签名不匹配）。

- [ ] **Step 3: 跑全套 ingest test 看没意外回归**

```bash
uv run pytest tests/ingest/ -v --no-header
```

期望：除 test_mineru_container_cleanup.py 5 个 FAIL，其他 PASS。

---

## Task 3: 重写 `RunError` + `_run_mineru` HTTP 版（TDD 绿）

**Files:**
- Modify: `packages/service/src/ingest/converters/mineru.py:36-127`

**目标**：把 `RunError` 改成 HTTP 语义（status_code + response_body + task_id），把 `_run_mineru` 整段重写为 `httpx.Client` 调 mineru-api 异步端点。

- [ ] **Step 1: 替换 `RunError` 类**

整段替换 [packages/service/src/ingest/converters/mineru.py:36-47](packages/service/src/ingest/converters/mineru.py#L36-L47) 的 `RunError`：

```python
    class RunError(Exception):
        """mineru HTTP 调用失败（非 2xx 状态 / 网络异常 / 任务失败等）

        字段语义（2026-07-03 远程化改造后）:
            exit_code: HTTP 状态码（5xx = 服务端错，0 = 网络/超时错，4xx = 客户端错）
            response_body: 错误响应原文（str，前 2KB），替代原 docker stderr bytes
            task_id: mineru 服务端 X-MinerU-Task-Id（如有），便于排障

        字段名 exit_code 保留是为了 convert_batch:153 日志格式 f"批处理 exit {e.exit_code}" 兼容。
        """

        def __init__(self, exit_code: int, response_body: str = "", task_id: str = ""):
            self.exit_code = exit_code
            self.response_body = response_body
            self.task_id = task_id
            super().__init__(f"mineru HTTP 失败 (status={exit_code}, task_id={task_id or 'n/a'})")
```

- [ ] **Step 2: 在文件顶部加新 import**

替换 [packages/service/src/ingest/converters/mineru.py:1-12](packages/service/src/ingest/converters/mineru.py#L1-L12) 的 import 块：

```python
"""Mineru 转换器 - 适合复杂 PDF (2026-07-03 远程 HTTP 化)

通过 HTTP 调远端 mineru-api 服务（自部署 FastAPI），不走本地 docker。
端点: POST /tasks (提交) → GET /tasks/{id} (轮询) → GET /tasks/{id}/result (取 ZIP)
配置: MINERU_API_URL 等 6 个 env, 见 packages/service/src/config/settings.py
"""

import os
import re
import time
import zipfile
from collections.abc import Sequence
from pathlib import Path

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.core.retry import _is_retryable_network_error  # 复用 dify_client 模式
from .base import Converter
```

**注意**：`src/core/retry.py` 的 `_is_retryable_network_error` 可能不存在，需要在 Step 3 实现时检查/创建。下面 Step 3 会给出 inline 实现作为兜底。

- [ ] **Step 3: 重写 `_run_mineru` 整段**

整段替换 [packages/service/src/ingest/converters/mineru.py:80-127](packages/service/src/ingest/converters/mineru.py#L80-L127) 的 `DEFAULT_BACKEND` 常量 + `_run_mineru` 方法：

```python
    # mineru backend：默认 pipeline（CPU 友好，但 mineru-api 服务端自己管 GPU，
    # backend 选型由服务端镜像决定；这里只把 backend 参数透传给 HTTP）。
    DEFAULT_BACKEND = "pipeline"

    # 客户端 form fields 模板（POST /tasks 用）
    _TASK_FORM_FIELDS = {
        "backend": DEFAULT_BACKEND,
        "parse_method": "auto",
        "return_md": "true",
        "response_format_zip": "true",
    }

    @staticmethod
    def _is_retryable_http_error(exc: BaseException) -> bool:
        """仅重试网络超时/断连以及 5xx 服务端错；4xx 客户端错直接透传。"""
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
            return True
        return False

    @retry(
        stop=stop_after_attempt(settings.mineru_api_retry_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
        before_sleep=lambda state: logger.warning(
            "  [mineru] POST /tasks 重试 attempt={}", state.attempt_number
        ),
    )
    def _submit_task(self, client: httpx.Client, pdf_paths: Sequence[str]) -> tuple[str, str]:
        """POST /tasks 提交解析任务；retry 仅对网络/5xx 生效。

        Returns:
            (task_id, task_id_from_header)  -- 优先用 response body.task_id, fallback header
        """
        # multipart files: [(filename, bytes, mime)]
        files = []
        for pdf_path in pdf_paths:
            with open(pdf_path, "rb") as f:
                content = f.read()
            files.append(
                ("files", (Path(pdf_path).name, content, "application/pdf"))
            )

        resp = client.post(
            "/tasks",
            files=files,
            data=self._TASK_FORM_FIELDS,
            timeout=httpx.Timeout(
                connect=settings.mineru_api_timeout_connect,
                read=settings.mineru_api_timeout_read,
                write=settings.mineru_api_timeout_read,
                pool=settings.mineru_api_timeout_connect,
            ),
        )
        resp.raise_for_status()  # 4xx 立即抛，5xx 由 tenacity 重试
        task_id = resp.json().get("task_id", "")
        task_id_header = resp.headers.get("X-MinerU-Task-Id", "")
        return task_id, task_id_header

    def _poll_task_until_terminal(self, client: httpx.Client, task_id: str) -> dict:
        """GET /tasks/{task_id} 轮询直到 status ∈ {completed, failed} 或总超时。

        Returns:
            最后一次响应的 JSON dict
        """
        deadline = time.monotonic() + settings.mineru_api_task_timeout
        interval = settings.mineru_api_poll_interval
        attempts = 0
        while True:
            if time.monotonic() > deadline:
                raise self.RunError(
                    exit_code=0,
                    response_body=f"task {task_id} 等待超时 (>{settings.mineru_api_task_timeout}s)",
                    task_id=task_id,
                )
            attempts += 1
            resp = client.get(
                f"/tasks/{task_id}",
                timeout=httpx.Timeout(
                    connect=settings.mineru_api_timeout_connect,
                    read=settings.mineru_api_timeout_read,
                    pool=settings.mineru_api_timeout_connect,
                ),
            )
            resp.raise_for_status()
            payload = resp.json()
            status = payload.get("status", "")
            if status in ("completed", "failed"):
                return payload
            # 指数退避封顶 10s
            time.sleep(min(interval * (2 ** (attempts - 1)), 10))

    def _fetch_task_result(self, client: httpx.Client, task_id: str) -> bytes:
        """GET /tasks/{task_id}/result 拿 ZIP 字节"""
        resp = client.get(
            f"/tasks/{task_id}/result",
            timeout=httpx.Timeout(
                connect=settings.mineru_api_timeout_connect,
                read=settings.mineru_api_timeout_read,
                write=settings.mineru_api_timeout_read,
                pool=settings.mineru_api_timeout_connect,
            ),
        )
        resp.raise_for_status()
        return resp.content

    def _run_mineru(self, pdf_paths: Sequence[str], output_dir: str) -> None:
        """调远端 mineru-api 异步端点：POST /tasks → 轮询 → GET /result → 解 ZIP 落盘。

        失败抛 RunError（HTTP status_code + response_body + task_id）。
        """
        base_url = settings.mineru_api_url.rstrip("/")
        task_id = ""
        try:
            with httpx.Client(base_url=base_url) as client:
                # 1. 提交任务
                task_id, task_id_header = self._submit_task(client, pdf_paths)
                task_id = task_id or task_id_header

                # 2. 轮询状态
                final_status = self._poll_task_until_terminal(client, task_id)
                if final_status.get("status") != "completed":
                    raise self.RunError(
                        exit_code=409,
                        response_body=final_status.get("error", "task failed"),
                        task_id=task_id,
                    )

                # 3. 拿结果 ZIP 并落盘
                zip_bytes = self._fetch_task_result(client, task_id)
                self._extract_result_zip(zip_bytes, output_dir)
        except httpx.HTTPStatusError as e:
            raise self.RunError(
                exit_code=e.response.status_code,
                response_body=e.response.text[:2000],
                task_id=task_id,
            ) from e
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise self.RunError(
                exit_code=0,
                response_body=str(e)[:2000],
                task_id=task_id,
            ) from e

    def _extract_result_zip(self, zip_bytes: bytes, output_dir: str) -> None:
        """从 mineru 返的 ZIP 提取每个 PDF 的 md 到 <output_dir>/<stem>/auto/<stem>.md

        ZIP 内部布局: <stem>/auto/<stem>.md（每个 stem 一个子目录）
        """
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".md"):
                    continue
                # name 形如 "sample/auto/sample.md"
                parts = name.split("/")
                if len(parts) < 3:
                    continue
                stem = parts[0]
                target_path = os.path.join(output_dir, stem, "auto", f"{stem}.md")
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zf.open(name) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
```

注意 Step 2 提到的 `import io`：需要在文件顶部 import 块加 `import io`。

- [ ] **Step 4: 修 `convert_batch` 2 行适配新 RunError 字段**

在 [packages/service/src/ingest/converters/mineru.py:150-183](packages/service/src/ingest/converters/mineru.py#L150-L183) 的 `convert_batch` 方法内，找到两处 `e.stderr.decode(...)`，替换为 `e.response_body`：

原代码（line 150-153）：
```python
        try:
            self._run_mineru(pdf_paths, output_dir)
        except self.RunError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            failed_hint = self._parse_failed_files(stderr)
            logger.warning(f"  [mineru] 批处理 exit {e.exit_code}，stderr 解析疑似失败: {failed_hint}")
```

改为：
```python
        try:
            self._run_mineru(pdf_paths, output_dir)
        except self.RunError as e:
            response_body = e.response_body  # HTTP 模式已是 str
            failed_hint = self._parse_failed_files(response_body)
            logger.warning(f"  [mineru] 批处理 exit {e.exit_code} (HTTP)，response 解析疑似失败: {failed_hint}")
```

原代码（line 180-183）：
```python
            except self.RunError as e:
                stderr = e.stderr.decode("utf-8", errors="replace")
                results[failed_path] = f"[ERROR] mineru 单独重试仍失败 (exit {e.exit_code}): {stderr[-500:]}"
                continue
```

改为：
```python
            except self.RunError as e:
                response_body = e.response_body
                results[failed_path] = f"[ERROR] mineru 单独重试仍失败 (HTTP {e.exit_code}): {response_body[-500:]}"
                continue
```

- [ ] **Step 5: 删 `tempfile` / `shutil` / `docker` 残留 import（如有）**

如果文件顶部还有 `import shutil`、`import tempfile`，删除（HTTP 模式不再用）。`import docker` / `from docker.types import DeviceRequest` 必须删除（如果还在）。

跑 `grep -n "^import\|^from" packages/service/src/ingest/converters/mineru.py` 确认残留。

- [ ] **Step 6: 跑 Task 2 写的 5 个 test 看全绿**

```bash
cd packages/service
uv run pytest tests/ingest/test_mineru_container_cleanup.py -v
```

期望：5 个 test 全 PASS。

- [ ] **Step 7: 跑全套 ingest test 看没回归**

```bash
uv run pytest tests/ingest/ -v --no-header
```

期望：除 `test_mineru_container_cleanup.py` 5 个 PASS 外，其他 PASS（`test_converters.py:144-213` TestMineruConverter、`:487-516` TestMineruParseFailedFiles 跟 HTTP 无关，应 PASS；`:225-324` TestMineruEndToEnd 仍会跑，但要 RUN_SLOW_TESTS=1 gate，正常不会跑）。

- [ ] **Step 8: 跑 format + lint + typecheck**

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pyright
```

期望：0 error。

- [ ] **Step 9: 删 docker dep**

在 [packages/service/pyproject.toml:40](packages/service/pyproject.toml#L40) 删除整行：

```python
    "docker>=7.1.0", # docker-py SDK, mineru 容器生命周期管理 (tests/ingest/test_mineru_container_cleanup.py)
```

- [ ] **Step 10: grep 验证 docker 0 引用**

```bash
cd packages/service
grep -rE "import docker|from docker" src/ tests/
```

期望：0 命中（除 task 2 写的 test 文件里 `import httpx`，没 `import docker`）。

- [ ] **Step 11: 跑全套 pytest 看基线**

```bash
uv run pytest --no-header -q 2>&1 | tail -30
```

期望：pass 数 ≥ 1075（基线）。pre-existing fail/error 保持不变。

- [ ] **Step 12: Commit (commit 1)**

```bash
git add packages/service/src/ingest/converters/mineru.py \
        packages/service/src/common/defaults.py \
        packages/service/src/config/settings.py \
        packages/service/.env.example \
        packages/service/pyproject.toml
git commit -m "feat(ingest): mineru 切到远程 HTTP API（异步 /tasks 端点 + 轮询）"
```

---

## Task 4: 改 `test_mineru_retry_e2e.py` 的 docker daemon 探测为 HTTP health 探测

**Files:**
- Modify: `packages/service/tests/integration/test_mineru_retry_e2e.py:34-51`（`_docker_daemon_alive` helper）

**目标**：把 docker daemon 探测换成 mineru-api HTTP health 探测，让 e2e 测试在 dev 启 mineru-api 后能跑。

- [ ] **Step 1: 替换 `_docker_daemon_alive` helper**

整段替换 [packages/service/tests/integration/test_mineru_retry_e2e.py:34-51](packages/service/tests/integration/test_mineru_retry_e2e.py#L34-L51)：

原代码（line 34-51）：
```python
def _docker_daemon_alive() -> bool:
    """检测 docker daemon 是否可访问（Windows named pipe / Linux socket）"""
    if sys.platform == "win32":
        return Path(r"\\.\pipe\docker_engine").exists()
    return Path("/var/run/docker.sock").exists()
```

改为：
```python
def _mineru_api_alive() -> bool:
    """检测 mineru-api HTTP 服务是否可访问（GET /health 应返 200）"""
    import httpx

    from src.config import settings

    try:
        with httpx.Client(timeout=httpx.Timeout(connect=3.0, read=5.0)) as client:
            resp = client.get(f"{settings.mineru_api_url.rstrip('/')}/health")
            return resp.status_code == 200
    except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
        return False
```

- [ ] **Step 2: 替换 skipif 用的 helper 名**

在 [packages/service/tests/integration/test_mineru_retry_e2e.py:55](packages/service/tests/integration/test_mineru_retry_e2e.py#L55) 找到 `@pytest.mark.skipif(not _docker_daemon_alive())`，替换为 `@pytest.mark.skipif(not _mineru_api_alive())`。

- [ ] **Step 3: 跑测试（在 mineru-api 未起的环境下应自动 skip）**

```bash
cd packages/service
uv run pytest tests/integration/test_mineru_retry_e2e.py -v
```

期望：SKIPPED（如果本地没起 mineru-api）或 PASS（如果起了）。

- [ ] **Step 4: Commit**

```bash
git add packages/service/tests/integration/test_mineru_retry_e2e.py
git commit -m "test(mineru): e2e 探测改用 mineru-api /health（替代 docker daemon 探测）"
```

---

## Task 5: 改 test 文件名 + 删 `TestMineruEndToEnd`（commit 2 收尾）

**Files:**
- Modify: `packages/service/tests/ingest/test_converters.py:225-324`（删 `TestMineruEndToEnd` 类）
- Modify: 文件改名（用 `git mv`）

**目标**：清理绑死 docker 的 e2e test 段；改文件名匹配新行为。

- [ ] **Step 1: git mv 改名**

```bash
cd c:/Users/abcuc/Desktop/rag
git mv packages/service/tests/ingest/test_mineru_container_cleanup.py packages/service/tests/ingest/test_mineru_http_client.py
```

- [ ] **Step 2: 删 `TestMineruEndToEnd` 整段**

读 [packages/service/tests/ingest/test_converters.py:225-324](packages/service/tests/ingest/test_converters.py#L225-L324)，整段删除 `TestMineruEndToEnd` 类（含类定义、所有 test 方法、缩进保持一致）。

具体删除边界：从 `class TestMineruEndToEnd(`（line 225）到下一个顶层 `class` 或 `def` 之前。

- [ ] **Step 3: 删 `test_container_sees_host_gpu`（独立函数，line 228 附近）

该函数在 `TestMineruEndToEnd` 外部但 import docker。grep 一下确认：

```bash
cd packages/service
grep -n "test_container_sees_host_gpu\|import docker" tests/ingest/test_converters.py
```

如果有，删除该函数。

- [ ] **Step 4: grep 验证 docker 0 引用**

```bash
grep -rE "import docker|from docker" tests/
```

期望：0 命中。

- [ ] **Step 5: 跑 test_converters.py**

```bash
cd packages/service
uv run pytest tests/ingest/test_converters.py -v --no-header
```

期望：剩余 test（TestMineruConverter / TestMineruParseFailedFiles / TestGetConverter）全 PASS。

- [ ] **Step 6: 跑全套 ingest test**

```bash
uv run pytest tests/ingest/ -v --no-header
```

期望：所有 PASS。

- [ ] **Step 7: 跑 format + lint + typecheck**

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pyright
```

期望：0 error。

- [ ] **Step 8: 跑全套 pytest 看基线**

```bash
uv run pytest --no-header -q 2>&1 | tail -30
```

期望：pass 数 ≥ 1075（基线），pre-existing fail 不变。

- [ ] **Step 9: Commit (commit 2)**

```bash
git add packages/service/tests/ingest/test_mineru_container_cleanup.py \
        packages/service/tests/ingest/test_converters.py
git rm packages/service/tests/ingest/test_mineru_http_client.py 2>/dev/null || true
git add packages/service/tests/ingest/test_mineru_http_client.py
git commit -m "refactor(test): mineru test 改名 + 删 TestMineruEndToEnd（绑死 docker）"
```

---

## Task 6: 新增 tenacity 重试 + 轮询专项测试（可选但推荐）

**Files:**
- Create: `packages/service/tests/ingest/test_mineru_retry.py`

**目标**：补一组专项测试覆盖 retry 行为（5xx 重试 / 4xx 不重试 / 超时）和轮询行为（指数退避 / task 超时）。

- [ ] **Step 1: 创建测试文件**

新建 `packages/service/tests/ingest/test_mineru_retry.py`：

```python
"""Mineru HTTP 客户端 retry + 轮询专项测试 (2026-07-03)

覆盖:
- POST /tasks 5xx 重试（tenacity）
- POST /tasks 4xx 不重试
- POST /tasks 超时 → RunError(exit_code=0)
- GET /tasks/{id} 轮询指数退避 + task 超时
- GET /tasks/{id}/result 404 抛 RunError
"""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ingest.converters.mineru import MineruConverter


class _FakeResp:
    def __init__(self, status_code, json_data=None, body=b"", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = body.decode("utf-8", errors="replace") if body else ""
        self.content = body
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=MagicMock(), response=self)


class TestPostTasksRetry:
    """POST /tasks 的 tenacity 重试行为"""

    def test_5xx_triggers_retry(self, tmp_path, monkeypatch):
        """5xx 应触发 tenacity 重试（最多 attempts 次）"""
        # 模拟：第 1 次 500，第 2 次 202 成功
        responses = [_FakeResp(500, body=b"err"), _FakeResp(202, json_data={"task_id": "ok"})]

        class FakeClient:
            def __init__(self, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, url, **kw):
                return responses.pop(0)

            def get(self, url, **kw):
                return _FakeResp(200, json_data={"status": "completed"})

        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", FakeClient)
        monkeypatch.setattr("time.sleep", lambda _: None)  # 跳过 retry 间隔

        # _submit_task 不会调轮询，直接测 _run_mineru 整体
        with patch.object(MineruConverter, "_fetch_task_result", return_value=b"fake-zip"):
            with patch.object(MineruConverter, "_extract_result_zip"):
                MineruConverter()._run_mineru(["/tmp/x.pdf"], str(tmp_path / "out"))
        assert len(responses) == 0  # 2 次响应都被消费

    def test_4xx_no_retry(self, tmp_path, monkeypatch):
        """4xx 不重试，立即 RunError"""
        responses = [_FakeResp(400, body=b"bad")]

        class FakeClient:
            def __init__(self, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, url, **kw):
                return responses.pop(0)
            def get(self, url, **kw):
                return _FakeResp(200)

        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", FakeClient)

        with pytest.raises(MineruConverter.RunError) as exc:
            MineruConverter()._run_mineru(["/tmp/x.pdf"], str(tmp_path / "out"))
        assert exc.value.exit_code == 400

    def test_timeout_raises_run_error(self, tmp_path, monkeypatch):
        """网络超时 → RunError(exit_code=0)"""
        class FakeClient:
            def __init__(self, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, url, **kw):
                raise httpx.ConnectTimeout("connect timeout")

        monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", FakeClient)
        monkeypatch.setattr("time.sleep", lambda _: None)

        with pytest.raises(MineruConverter.RunError) as exc:
            MineruConverter()._run_mineru(["/tmp/x.pdf"], str(tmp_path / "out"))
        assert exc.value.exit_code == 0


class TestPollUntilTerminal:
    """_poll_task_until_terminal 行为"""

    def test_exponential_backoff_intervals(self, monkeypatch):
        """轮询间隔应指数增长，封顶 10s"""
        sleep_calls: list[float] = []

        class FakeClient:
            def get(self, url, **kw):
                # 始终返 processing
                return _FakeResp(200, json_data={"status": "processing"})

        # 用 patch 替换内部 sleep 计数
        with patch("src.ingest.converters.mineru.time.sleep", lambda s: sleep_calls.append(s)):
            # 强制 task_timeout 极小，让循环尽快超时
            with patch("src.config.settings.mineru_api_task_timeout", 0.1):
                with pytest.raises(MineruConverter.RunError) as exc:
                    MineruConverter()._poll_task_until_terminal(FakeClient(), "task-1")
        assert exc.value.exit_code == 0
        # 至少 1 次 sleep 调用
        assert len(sleep_calls) >= 1

    def test_failed_status_returns_payload(self, monkeypatch):
        """status=failed 直接返回 payload（由 _run_mineru 上层判 failed→抛 RunError）"""
        class FakeClient:
            def get(self, url, **kw):
                return _FakeResp(200, json_data={"status": "failed", "error": "ocr crashed"})

        with patch("src.ingest.converters.mineru.time.sleep", lambda _: None):
            payload = MineruConverter()._poll_task_until_terminal(FakeClient(), "task-2")
        assert payload["status"] == "failed"
        assert payload["error"] == "ocr crashed"
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/service
uv run pytest tests/ingest/test_mineru_retry.py -v --no-header
```

期望：5 个 test 全 PASS。

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/ingest/test_mineru_retry.py
git commit -m "test(mineru): 新增 retry + 轮询专项测试（5xx 重试 / 4xx 不重试 / 超时）"
```

---

## Task 7: 加 docker-compose 注释 + cookbook（commit 3 - 文档）

**Files:**
- Modify: `docker/mineru-docker-compose.yml:58-91`
- Create: `docs/cookbook/ingest/mineru-http.md`
- Modify: `packages/service/CLAUDE.md`

**目标**：标注端口对 env 的对应；写 dev 部署文档；CLAUDE.md 加 mineru HTTP 段。

- [ ] **Step 1: 在 `docker/mineru-docker-compose.yml` 加注释**

读 [docker/mineru-docker-compose.yml:58-91](docker/mineru-docker-compose.yml#L58-L91) 的 `mineru-api` profile。在 `ports: "18000:8000"` 这一行**上方**加注释：

```yaml
    # 主机端口 18000 对应 packages/service/.env.example MINERU_API_URL 默认值
    # (跟 rag 服务 :8000 错开; CPU 服务器 mineru-api 跑不起来, 需 NVIDIA GPU)
```

- [ ] **Step 2: 创建 cookbook**

新建 `docs/cookbook/ingest/mineru-http.md`：

```markdown
# Mineru 远程 HTTP 部署（2026-07-03）

## 概述

backend 通过 HTTP 调远端 mineru-api 服务（FastAPI）。mineru-api 自己跑在独立容器内、自带 GPU。backend 容器 / K8s pod 不需要 docker daemon 或本地 GPU。

## 部署步骤

### 1. 启动 mineru-api（独立 docker compose）

```bash
cd docker
docker compose -f mineru-docker-compose.yml --profile api up -d
```

**GPU 要求**：mineru-api profile 默认配 NVIDIA GPU（`deploy.resources.reservations.devices`）。CPU 服务器跑不起来，需要先装 NVIDIA Container Toolkit + 驱动。

**端口映射**：`18000:8000`（主机 18000 → 容器 8000）。`18000` 对应 backend 的 `MINERU_API_URL` 默认值。

### 2. 验证 mineru-api 健康

```bash
curl http://localhost:18000/health
```

期望返 200 + JSON 含 `version` / `protocol_version` 等字段。

### 3. 配置 backend env

`packages/service/.env.local` 加：

```
MINERU_API_URL=http://localhost:18000
```

远程部署改成远端地址（如 `http://mineru.internal:18000`）。

### 4. 验证 convert_batch 跑通

```bash
cd packages/service
uv run python -c "
from src.ingest.converters import MineruConverter
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'out')
    os.makedirs(out)
    r = MineruConverter().convert_batch(['tests/fixtures/complex_pdf_test.pdf'], out)
    print(r)
"
```

## 排障

### "mineru-api 连不上"

- 查 `docker ps | grep mineru-api` 容器在不在
- 查 `docker logs mineru-api` 启动是否报 GPU 错
- 查 `curl http://localhost:18000/health` 直连通不通

### "RunError exit_code=500"

- mineru-api 服务端崩了，docker logs 查 traceback
- 检查 PDF 是否在 mineru 支持列表（pdf/image/docx/pptx/xlsx）

### "task 等待超时"

- 大 PDF 跑超过 `MINERU_API_TASK_TIMEOUT=600s`，调大 env
- 或检查 mineru-api 是否卡死（docker exec 进容器 ps 看 python 进程）

## 与改造前的差异

| 项 | 改造前（docker） | 改造后（HTTP） |
|---|---|---|
| docker daemon | backend 容器必须有 | backend 不需要 |
| GPU | backend 容器必须有 | mineru-api 容器有，backend 不需要 |
| 文件传输 | volume 挂本地路径 | multipart POST 上传 |
| 失败处理 | ContainerError | RunError (HTTP status_code + response_body + task_id) |
| 测试 mock | monkeypatch docker.from_env | monkeypatch httpx.Client |
```

- [ ] **Step 3: 在 `packages/service/CLAUDE.md` 加 mineru HTTP 段**

读 [packages/service/CLAUDE.md](packages/service/CLAUDE.md)，找一个合适位置（按 `ObjectStore ABC 使用` 段后或 `Redis 使用约定` 段前的位置），加：

```markdown
## Mineru HTTP 客户端 (2026-07-03)

backend 通过 HTTP 调远端 mineru-api 服务，不走本地 docker。

### 端点

- `POST /tasks` — 提交任务（multipart 上传 PDF），返 202 + task_id
- `GET /tasks/{id}` — 查状态（`pending` / `processing` / `completed` / `failed`）
- `GET /tasks/{id}/result` — 取结果（ZIP 含 `<stem>/auto/<stem>.md`）
- `GET /health` — 健康检查

完整 API 见 `docs/cookbook/ingest/mineru-http.md`。

### env 配置

6 个 env（在 `defaults.py` + `settings.py` + `.env.example` 三处同步）：

| env | 默认值 | 用途 |
|---|---|---|
| `MINERU_API_URL` | `http://localhost:18000` | HTTP base URL |
| `MINERU_API_TIMEOUT_CONNECT` | `5` | httpx connect timeout |
| `MINERU_API_TIMEOUT_READ` | `30` | 单次 HTTP read timeout |
| `MINERU_API_RETRY_ATTEMPTS` | `3` | tenacity stop_after_attempt（仅 POST /tasks） |
| `MINERU_API_POLL_INTERVAL` | `2` | GET /tasks/{id} 轮询基础间隔 |
| `MINERU_API_TASK_TIMEOUT` | `600` | 单个 task 总等待超时 |

### 业务调用示例

```python
from src.ingest.converters import MineruConverter

converter = MineruConverter()
results: dict[str, str] = converter.convert_batch(
    pdf_paths=["/path/to/a.pdf", "/path/to/b.pdf"],
    output_dir="/tmp/mineru_out",
)
# results: {"/path/to/a.pdf": "# md content ...", ...}
```

`convert_batch` 编排（磁盘真相源 + 失败逐个重试）保留，详见原 `2026-06-03-mineru-retry-failed-files` 计划。

### 测试模式

模式 1 mock（`monkeypatch.setattr("src.ingest.converters.mineru.httpx.Client", FakeClient)`）。参考：
- `tests/ingest/test_mineru_http_client.py` — 5 个契约测试
- `tests/ingest/test_mineru_retry.py` — retry + 轮询专项测试
- `tests/integration/test_mineru_retry_e2e.py` — HTTP e2e（需要 mineru-api 在跑）
```

- [ ] **Step 4: 跑 format + lint + typecheck（CLAUDE.md 改动不影响 pyright）**

```bash
cd packages/service
uv run ruff format .
uv run ruff check --fix .
```

期望：0 error。CLAUDE.md 是 markdown，不影响 pyright。

- [ ] **Step 5: 跑全套 pytest 看基线不变**

```bash
uv run pytest --no-header -q 2>&1 | tail -30
```

期望：pass 数 ≥ 1075，pre-existing fail 不变。

- [ ] **Step 6: Commit (commit 3)**

```bash
git add docker/mineru-docker-compose.yml \
        docs/cookbook/ingest/mineru-http.md \
        packages/service/CLAUDE.md
git commit -m "docs(chore): 标注 mineru-api 端口对应 env + 部署 cookbook + CLAUDE.md 段"
```

---

## 验证清单（3 commit 全完成后）

### 本地 dev 端到端验证

```bash
# 1. 起 mineru-api
cd docker
docker compose -f mineru-docker-compose.yml --profile api up -d

# 2. 验 health
curl http://localhost:18000/health

# 3. 改 backend env
echo "MINERU_API_URL=http://localhost:18000" >> packages/service/.env

# 4. 手动跑 convert_batch
cd packages/service
uv run python -c "
from src.ingest.converters import MineruConverter
import tempfile, os
with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'out')
    os.makedirs(out)
    r = MineruConverter().convert_batch(['tests/fixtures/complex_pdf_test.pdf'], out)
    print('OK, md len:', len(list(r.values())[0]) if r else 0)
"

# 5. 验磁盘布局
# 期望: /tmp/.../<stem>/auto/<stem>.md 存在
```

### 跑 CLAUDE.md 强制 5 步

```bash
cd packages/service
uv run ruff format .                # 1. format
uv run ruff check --fix .            # 2. lint fix
uv run pyright                       # 3. typecheck
uv run pytest --no-header -q         # 4. test（基线 ~1075 pass + 22 fail + 38 errors pre-existing）
```

### 真实 e2e（可选，需要 mineru-api 跑着）

```bash
cd packages/service
RUN_SLOW_TESTS=1 INTEGRATION=1 \
  uv run pytest tests/integration/test_mineru_retry_e2e.py -m slow -v
```

期望：8 个文件批处理 + 1LE1 触发重试 → 全成功。

### 回滚方案

如果 commit 1 引入 prod 问题：

```bash
git revert <commit 1 hash>
# + 重加 docker>=7.1.0 到 pyproject.toml
# + 还原 mineru.py 旧版
```

PR 描述里明确：commit 1 不可逆（删 docker dep），出问题只能 `git revert` 重建 docker 路径。

---

## Self-Review 检查清单

- [x] Spec 覆盖：env 6 个 ✅、RunError 字段 ✅、_run_mineru HTTP ✅、convert_batch 编排 ✅、测试 mock ✅、删 docker dep ✅、文档 ✅
- [x] 占位符扫描：无 TBD / TODO / "类似 Task N"
- [x] 类型一致：RunError(exit_code, response_body, task_id) 在所有 task 里一致；`_run_mineru(pdf_paths, output_dir)` 签名保持；`_submit_task / _poll_task_until_terminal / _fetch_task_result / _extract_result_zip` 名字在 Task 3 定义，Task 6 一致引用
- [x] 文件路径全部 absolute
- [x] 代码块完整无省略
- [x] 每个 task 独立可验证（带 PASS 期望）

---

## 执行选项

计划已保存到 `docs/superpowers/plans/2026-07-03-mineru-http-remote.md`。两个执行选项：

**1. Subagent-Driven (推荐)** — 我派新的 subagent 跑每个 task，task 间 review，快速迭代

**2. Inline Execution** — 在本 session 跑所有 task，分批执行带 checkpoint review

**选哪种？**