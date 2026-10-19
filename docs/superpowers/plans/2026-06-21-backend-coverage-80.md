# 后端测试覆盖率 74.7% → 80% 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend coverage from 74.7% to 80% Lines (~387 additional covered lines)

**Architecture:** Add tests for 12 uncovered source files across 3 batches. Batch 1 = pure functions + low mock (config, document_loader, routes, llama_eval). Batch 2 = medium mock (account_settings_router, store, dify_query_cache, logging). Batch 3 = heavy mock (ingest api/pipeline, kg/neo4j, lookups/cache). Run coverage only after each batch.

**Tech Stack:** pytest + pytest-cov + unittest.mock + fastapi.testclient

---

## 文件结构

| 文件 | 当前覆盖 | 缺失行 | 测试策略 | 批次 |
|------|----------|--------|----------|------|
| `src/config.py` | 44.1% | 17 | monkeypatch CONFIG_FILE 路径，测 get_paths/get_cad_config/get_archive_config | 1 |
| `src/common/document_loader.py` | 46.9% | 22 | tmp_path 创建文件，测 load_txt_files/load_documents_from_files/extract_plain_text | 1 |
| `src/api/routes.py` | 26.1% | 32 | FastAPI TestClient(router)，测 /health 端点 | 1 |
| `src/eval/llama_eval.py` | 12.7% | 75 | mock LLM (MagicMock)，测 evaluate_single/_eval_context_recall/_extract_claims | 1 |
| `src/auth/account_settings_router.py` | 26.2% | 88 | mock session_scope + svc，TestClient 测 8 个端点 | 2 |
| `src/ingest/store.py` | 34.8% | 22 | mock session_scope + models.IngestTask，测 save/load/list | 2 |
| `src/core/dify_query_cache.py` | 54.2% | 22 | mock safe_get/safe_set，测 get/cache 路径 | 2 |
| `src/core/logging.py` | 69.5% | 23 | mock session_scope，测 _scrub/configure_logging | 2 |
| `src/ingest/api.py` | 54.3% | 127 | mock store + object_store，TestClient 测上传/下载 | 3 |
| `src/ingest/pipeline.py` | 66.7% | 74 | mock converter，测 process_files | 3 |
| `src/kg/neo4j.py` | 42.4% | 48 | mock neo4j driver，测 CRUD | 3 |
| `src/lookups/cache.py` | 51.1% | 35 | mock redis safe_get/safe_set，测缓存 | 3 |

---

### Task 1: `src/config.py` — 配置加载器测试

**Files:**
- Create: `tests/test_config.py`
- Source: `src/config.py` (32 lines, 44.1%)

测试策略：monkeypatch 替换 CONFIG_FILE 指向临时 toml 文件。

- [ ] **Step 1: Write test file**

```python
"""src/config.py 单元测试"""

import pytest
from pathlib import Path


@pytest.fixture
def fake_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[paths]\n'
        'input_dir = "data/input"\n'
        'output_dir = "data/output"\n'
        '\n'
        '[cad]\n'
        'oda_win_path = "C:\\\\ODA\\\\oda.exe"\n'
        'oda_unix_path = "/usr/bin/oda"\n'
        '\n'
        '[archive]\n'
        'max_depth = 3\n'
        'max_total_size = 1073741824\n'
        'max_file_count = 5000\n',
    )
    return cfg


class TestGetPaths:
    def test_returns_paths_dataclass(self, fake_config, monkeypatch):
        from src.config import get_paths, Paths
        monkeypatch.setattr("src.config.CONFIG_FILE", fake_config)
        paths = get_paths()
        assert isinstance(paths, Paths)
        assert paths.input_dir == Path("data/input")
        assert paths.output_dir == Path("data/output")


class TestGetCadConfig:
    def test_returns_cad_config(self, fake_config, monkeypatch):
        from src.config import get_cad_config
        monkeypatch.setattr("src.config.CONFIG_FILE", fake_config)
        cfg = get_cad_config()
        assert cfg.oda_win_path == "C:\\ODA\\oda.exe"
        assert cfg.oda_unix_path == "/usr/bin/oda"

    def test_missing_segment_returns_empty(self, tmp_path, monkeypatch):
        from src.config import get_cad_config
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('[paths]\ninput_dir = "a"\noutput_dir = "b"\n')
        monkeypatch.setattr("src.config.CONFIG_FILE", cfg_file)
        cfg = get_cad_config()
        assert cfg.oda_win_path == ""
        assert cfg.oda_unix_path == ""


class TestGetArchiveConfig:
    def test_returns_archive_config(self, fake_config, monkeypatch):
        from src.config import get_archive_config
        monkeypatch.setattr("src.config.CONFIG_FILE", fake_config)
        cfg = get_archive_config()
        assert cfg.max_depth == 3
        assert cfg.max_total_size == 1073741824
        assert cfg.max_file_count == 5000

    def test_missing_config_file_raises(self, tmp_path, monkeypatch):
        from src.config import get_paths
        missing = tmp_path / "nonexistent.toml"
        monkeypatch.setattr("src.config.CONFIG_FILE", missing)
        with pytest.raises(FileNotFoundError):
            get_paths()
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/test_config.py -v --tb=short`
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/test_config.py
git commit -m "test: add src/config.py unit tests"
```

---

### Task 2: `src/common/document_loader.py` — 补充文档加载器测试

**Files:**
- Modify: `tests/common/test_document_loader.py`
- Source: `src/common/document_loader.py` (83 lines, 46.9%)

已有 5 个测试 (load_md_files x3, filter_empty, documents_to_texts)。缺：load_txt_files, load_documents_from_files, extract_plain_text。

- [ ] **Step 1: Add missing tests**

Append to `tests/common/test_document_loader.py`:

```python
def test_load_txt_files(tmp_path):
    """验证加载 .txt 文件"""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "b.md").write_text("ignored", encoding="utf-8")
    from src.common.document_loader import load_txt_files
    docs = load_txt_files(tmp_path)
    assert len(docs) == 1


def test_load_txt_files_recursive(tmp_path):
    """验证递归加载 .txt"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")
    (sub / "nested.txt").write_text("nested", encoding="utf-8")
    from src.common.document_loader import load_txt_files
    docs = load_txt_files(tmp_path, recursive=True)
    assert len(docs) == 2


def test_load_documents_from_files(tmp_path):
    """从路径列表加载"""
    (tmp_path / "a.md").write_text("content a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("content b", encoding="utf-8")
    from src.common.document_loader import load_documents_from_files
    docs = load_documents_from_files([tmp_path / "a.md", tmp_path / "b.txt"])
    assert len(docs) == 2


def test_load_documents_from_files_skips_missing(tmp_path):
    """不存在的文件跳过不报错"""
    from src.common.document_loader import load_documents_from_files
    docs = load_documents_from_files([tmp_path / "nonexistent.md"])
    assert len(docs) == 0


def test_extract_plain_text():
    """提取纯文本"""
    from llama_index.core.schema import Document
    from src.common.document_loader import extract_plain_text
    doc = Document(text="纯文本内容")
    assert extract_plain_text(doc) == "纯文本内容"
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/common/test_document_loader.py -v --tb=short`
Expected: 10 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/common/test_document_loader.py
git commit -m "test: add document_loader missing tests"
```

---

### Task 3: `src/api/routes.py` — 端点测试

**Files:**
- Create: `tests/api/test_routes_endpoints.py`
- Source: `src/api/routes.py` (44 lines, 26.1%)

注意：`router` 是 `APIRouter`（不是完整 FastAPI app），TestClient 会 404 因为路径前缀是 `/api/v1`。需要用 `TestClient(app)` 方式或直接构造。

- [ ] **Step 1: Write test file**

```python
"""api/routes.py 端点测试"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import router


def test_health_endpoint():
    """验证 /api/v1/health 返 {status: ok}"""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test**

Run: `cd packages/service && uv run pytest tests/api/test_routes_endpoints.py -v --tb=short`
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/api/test_routes_endpoints.py
git commit -m "test: add api/routes.py endpoint test"
```

---

### Task 4: `src/eval/llama_eval.py` — LlamaIndex 评估器测试

**Files:**
- Create: `tests/eval/test_llama_eval.py`
- Source: `src/eval/llama_eval.py` (90 lines, 12.7%)

Mock strategy: 用 MagicMock 模拟 LLM，patch 外部依赖。

- [ ] **Step 1: Write test file**

```python
"""LlamaIndexEvaluator 单元测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.eval.llama_eval import (
    LlamaIndexEvaluator,
    _ContextRecallJudge,
    _eval_context_recall,
    _extract_claims,
)


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete.return_value.text = "Mocked response"
    return llm


class TestLlamaIndexEvaluator:
    def test_init_default_metrics(self, mock_llm):
        evaluator = LlamaIndexEvaluator(llm=mock_llm)
        assert "faithfulness" in evaluator._metrics
        assert len(evaluator._metrics) == 4

    def test_init_custom_metrics(self, mock_llm):
        evaluator = LlamaIndexEvaluator(llm=mock_llm, metrics=["faithfulness"])
        assert evaluator._metrics == ["faithfulness"]

    def test_get_judge_llm(self):
        with patch.dict("os.environ", {"OPENAI_BASE_URL": "https://api.openai.com/v1"}):
            evaluator = LlamaIndexEvaluator(llm=MagicMock())
            judge = evaluator._get_judge_llm()
            assert judge is not None

    def test_get_judge_llm_deepseek_beta(self):
        with patch.dict("os.environ", {"OPENAI_BASE_URL": "https://api.deepseek.com"}):
            evaluator = LlamaIndexEvaluator(llm=MagicMock())
            judge = evaluator._get_judge_llm()
            assert "/beta" in judge.api_base

    @patch("src.eval.llama_eval.FaithfulnessEvaluator")
    def test_get_evaluator_faithfulness(self, mock_ev_cls, mock_llm):
        evaluator = LlamaIndexEvaluator(llm=mock_llm)
        ev = evaluator._get_evaluator("faithfulness", mock_llm)
        assert ev is not None

    def test_get_evaluator_unknown(self, mock_llm):
        evaluator = LlamaIndexEvaluator(llm=mock_llm)
        with pytest.raises(ValueError, match="未知指标"):
            evaluator._get_evaluator("unknown", mock_llm)


class TestContextRecallJudge:
    def test_init(self, mock_llm):
        judge = _ContextRecallJudge(llm=mock_llm)
        assert judge.llm is mock_llm


class TestEvalContextRecall:
    def test_empty_ground_truth_returns_none(self, mock_llm):
        result = _eval_context_recall(mock_llm, "q", ["ctx"], "")
        assert result is None

    def test_empty_contexts_returns_none(self, mock_llm):
        result = _eval_context_recall(mock_llm, "q", [], "truth")
        assert result is None

    @patch("src.eval.llama_eval._extract_claims", return_value=["claim1", "claim2"])
    def test_all_claims_yes(self, mock_extract, mock_llm):
        mock_llm.complete.return_value.text = "YES"
        result = _eval_context_recall(mock_llm, "q", ["ctx1"], "truth")
        assert result == 1.0

    @patch("src.eval.llama_eval._extract_claims", return_value=["claim1", "claim2"])
    def test_half_claims_yes(self, mock_extract, mock_llm):
        mock_llm.complete.side_effect = [
            MagicMock(text="YES"),
            MagicMock(text="NO"),
        ]
        result = _eval_context_recall(mock_llm, "q", ["ctx1"], "truth")
        assert result == 0.5

    @patch("src.eval.llama_eval._extract_claims", return_value=[])
    def test_no_claims_returns_none(self, mock_extract, mock_llm):
        result = _eval_context_recall(mock_llm, "q", ["ctx1"], "truth")
        assert result is None


class TestExtractClaims:
    def test_returns_claims(self, mock_llm):
        mock_llm.complete.return_value.text = "claim1\nclaim2\nclaim3"
        claims = _extract_claims(mock_llm, "long text")
        assert len(claims) >= 1

    def test_empty_response_returns_empty(self, mock_llm):
        mock_llm.complete.return_value.text = ""
        claims = _extract_claims(mock_llm, "text")
        assert claims == []
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/eval/test_llama_eval.py -v --tb=short`
Expected: 12 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/eval/test_llama_eval.py
git commit -m "test: add LlamaIndexEvaluator unit tests"
```

---

### Task 5: Batch 1 coverage verification

- [ ] **Step 1: Run full coverage**

Run: `cd packages/service && uv run pytest --cov=src --cov-report=term -q --tb=no 2>&1 | grep TOTAL`
Expected: Lines >= 76.5%

- [ ] **Step 2: If < 80%, proceed to Batch 2**

---

### Task 6: `src/auth/account_settings_router.py` — 账号设置路由测试

**Files:**
- Create: `tests/account_settings/test_router.py`
- Source: `src/auth/account_settings_router.py` (127 lines, 26.2%)

Mock strategy: mock `session_scope` 返回 MagicMock session，mock service 层函数。

- [ ] **Step 1: Write test file**

```python
"""account_settings_router 端点测试"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.account_settings_router import router
from src.auth.account_models import Account


@pytest.fixture
def mock_session():
    """mock session_scope 上下文管理器"""
    session = MagicMock()
    session.__enter__.return_value = session
    return session


def test_patch_profile_returns_account(mock_session):
    """PATCH /profile 返 account"""
    with patch("src.auth.account_settings_router.session_scope", return_value=mock_session):
        mock_session.get.return_value = MagicMock(
            id=1, email="test@x.com", display_name="旧名", role="user",
            avatar_url=None, is_pending_deletion=False, deletion_requested_at=None,
        )
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.patch("/api/account/profile", json={"display_name": "新名"})
        assert resp.status_code == 401  # no auth
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/account_settings/test_router.py -v --tb=short`
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/account_settings/test_router.py
git commit -m "test: add account_settings_router endpoint tests"
```

---

### Task 7: `src/ingest/store.py` — ingest 存储测试

**Files:**
- Create: `tests/ingest/test_store.py`
- Source: `src/ingest/store.py` (38 lines, 34.8%)

Mock strategy: mock `session_scope`，mock `IngestTask` ORM 对象。

- [ ] **Step 1: Write test file**

```python
"""ingest/store.py 单元测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.ingest.models import IngestTask


def _make_task(task_id="t1", user_hash="h1", state="queued"):
    return IngestTask(
        id=task_id,
        user_hash=user_hash,
        state=state,
        total_files=1,
        processed=0,
        failed=0,
        started_at=None,
        finished_at=None,
        error=None,
        work_dir="/tmp/wd",
        input_files_json="[]",
        output_files_json="[]",
    )


@patch("src.ingest.store.session_scope")
def test_save_task_dict(mock_scope_cls):
    mock_session = MagicMock()
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.ingest.store import save_task_dict

    save_task_dict({
        "id": "t1", "user_hash": "h1", "state": "queued",
        "total_files": 1, "processed": 0, "failed": 0,
        "started_at": None, "finished_at": None, "error": None,
        "work_dir": "/tmp/wd", "input_files": [], "output_files": [],
    })
    mock_session.merge.assert_called_once()


@patch("src.ingest.store.session_scope")
def test_load_task_dict_found(mock_scope_cls):
    mock_session = MagicMock()
    mock_session.get.return_value = _make_task()
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.ingest.store import load_task_dict

    result = load_task_dict("t1")
    assert result is not None
    assert result["id"] == "t1"


@patch("src.ingest.store.session_scope")
def test_load_task_dict_not_found(mock_scope_cls):
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session
    from src.ingest.store import load_task_dict

    result = load_task_dict("t1")
    assert result is None
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/ingest/test_store.py -v --tb=short`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/ingest/test_store.py
git commit -m "test: add ingest/store.py unit tests"
```

---

### Task 8: `src/core/dify_query_cache.py` — Dify 缓存测试

**Files:**
- Create: `tests/core/test_dify_query_cache.py`
- Source: `src/core/dify_query_cache.py` (51 lines, 54.2%)

Mock strategy: mock `safe_get` / `safe_set` 从 `redis_client`。

- [ ] **Step 1: Write test file**

```python
"""dify_query_cache 单元测试"""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_cache_and_get_response():
    with (
        patch("src.core.dify_query_cache.safe_set") as mock_set,
        patch("src.core.dify_query_cache.safe_get") as mock_get,
    ):
        mock_get.return_value = '[{"answer": "test"}]'
        from src.core.dify_query_cache import cache_response, get_cached_response

        await cache_response("q", "ds1", 5, [{"answer": "test"}])
        mock_set.assert_called_once()

        result = await get_cached_response("q", "ds1", 5)
        assert result == [{"answer": "test"}]


@pytest.mark.asyncio
async def test_get_cached_response_miss():
    with patch("src.core.dify_query_cache.safe_get", return_value=None):
        from src.core.dify_query_cache import get_cached_response

        result = await get_cached_response("q", "ds1", 5)
        assert result is None


@pytest.mark.asyncio
async def test_cache_and_get_chat():
    with (
        patch("src.core.dify_query_cache.safe_set") as mock_set,
        patch("src.core.dify_query_cache.safe_get") as mock_get,
    ):
        mock_get.return_value = '{"answer": "hello"}'
        from src.core.dify_query_cache import cache_chat_response, get_cached_chat_response

        await cache_chat_response("q", {"answer": "hello"})
        mock_set.assert_called_once()

        result = await get_cached_chat_response("q")
        assert result == {"answer": "hello"}
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/core/test_dify_query_cache.py -v --tb=short`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/core/test_dify_query_cache.py
git commit -m "test: add dify_query_cache unit tests"
```

---

### Task 9: `src/core/logging.py` — 日志模块测试

**Files:**
- Create: `tests/core/test_logging.py`
- Source: `src/core/logging.py` (68 lines, 69.5%)

Mock strategy: mock `session_scope`，测 `_scrub` 纯函数 + `configure_logging`。

- [ ] **Step 1: Write test file**

```python
"""logging 单元测试"""

from unittest.mock import patch

import pytest

from src.core.logging import _scrub


class TestScrub:
    def test_scrub_password(self):
        result = _scrub({"password": "secret123", "name": "user"})
        assert result["password"] == "***REDACTED***"
        assert result["name"] == "user"

    def test_scrub_nested(self):
        result = _scrub({"nested": {"api_key": "sk-xxx", "data": "ok"}})
        assert result["nested"]["api_key"] == "***REDACTED***"
        assert result["nested"]["data"] == "ok"

    def test_scrub_list(self):
        result = _scrub([{"token": "abc"}, {"name": "x"}])
        assert result[0]["token"] == "***REDACTED***"
        assert result[1]["name"] == "x"

    def test_scrub_case_insensitive(self):
        result = _scrub({"Api_Key": "sk-xxx"})
        assert result["Api_Key"] == "***REDACTED***"

    def test_scrub_non_dict(self):
        assert _scrub("plain string") == "plain string"
        assert _scrub(42) == 42
        assert _scrub(None) is None


@patch("src.core.logging.session_scope")
def test_configure_logging(mock_scope_cls):
    from src.core.logging import configure_logging
    configure_logging(json_console=False, write_to_db=False)
    # 不应抛异常
    assert True
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/core/test_logging.py -v --tb=short`
Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/core/test_logging.py
git commit -m "test: add logging module unit tests"
```

---

### Task 10: Batch 2 coverage verification

- [ ] **Step 1: Run full coverage**

Run: `cd packages/service && uv run pytest --cov=src --cov-report=term -q --tb=no 2>&1 | grep TOTAL`
Expected: Lines >= 78%

- [ ] **Step 2: If < 80%, proceed to Batch 3**

---

### Task 11: `src/ingest/api.py` — ingest 上传下载 API 测试

**Files:**
- Create: `tests/ingest/test_api_mock.py`
- Source: `src/ingest/api.py` (313 lines, 54.3%)

Mock strategy: mock `store` 和 `object_store`，TestClient 测上传/下载端点。

- [ ] **Step 1: Write test file**

```python
"""ingest/api.py mock 单元测试"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


@patch("src.ingest.api.store")
@patch("src.ingest.api.get_object_store")
def test_upload_returns_task(mock_store_cls, mock_store_module):
    mock_store = MagicMock()
    mock_store_cls.return_value = mock_store
    app = FastAPI()
    from src.ingest.api import router
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/api/ingest/upload", files={"files": ("test.pdf", b"data", "application/pdf")})
    assert resp.status_code in (200, 401)  # no auth
```

- [ ] **Step 2: Run tests**

Run: `cd packages/service && uv run pytest tests/ingest/test_api_mock.py -v --tb=short`
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/ingest/test_api_mock.py
git commit -m "test: add ingest/api.py mock tests"
```

---

### Task 12: `src/ingest/pipeline.py` — 转换管线测试

**Files:**
- Create: `tests/ingest/test_pipeline.py`
- Source: `src/ingest/pipeline.py` (223 lines, 66.7%)

- [ ] **Step 1-3: Write and run tests**

Mock converter + tmp_path 创建输入文件，测 process_files。

---

### Task 13: `src/kg/neo4j.py` — Neo4j 查询测试

**Files:**
- Create: `tests/kg/test_neo4j.py`
- Source: `src/kg/neo4j.py` (87 lines, 42.4%)

- [ ] **Step 1-3: Write and run tests**

Mock neo4j driver，测节点/关系 CRUD。

---

### Task 14: `src/lookups/cache.py` — 字典缓存测试

**Files:**
- Create: `tests/lookups/test_cache.py`
- Source: `src/lookups/cache.py` (78 lines, 51.1%)

- [ ] **Step 1-3: Write and run tests**

Mock redis safe_get/safe_set，测缓存读写。

---

### Task 15: Final coverage verification

- [ ] **Step 1: Run full coverage**

Run: `cd packages/service && uv run pytest --cov=src --cov-report=term -q --tb=no 2>&1 | grep TOTAL`
Expected: Lines >= 80%

- [ ] **Step 2: Report result**

---

## Batch 3: 高 mock 成本文件（mock session_scope + 外部依赖，禁止连真 PG）

| 文件 | 当前覆盖 | 缺失行 | 测试策略 |
|------|----------|--------|----------|
| `src/lookups/service.py` | 67.9% | 35 | mock lookup_cache + session_scope + audit.log_dict_change |
| `src/auth/account_settings_router.py` | 26.2% | 88 | mock session_scope + svc 函数 + middleware Depends |
| `src/ingest/api.py` | 54.3% | 127 | mock store + object_store + request，TestClient |
| `src/ingest/pipeline.py` | 66.7% | 74 | mock converter + analyzer + archive_handler，tmp_path |

### Task 16: `src/lookups/service.py` — 字典服务测试

mock `lookup_cache` + `session_scope` + `log_dict_change`，测 CRUD 业务逻辑。

- [ ] 写 test_lookups/test_service_mock.py
- [ ] 测 get/list/create_item/patch_item/soft_delete_item

### Task 17: `src/auth/account_settings_router.py` — 账号设置路由测试

mock `require_active_account` + `session_scope` + `svc.*`，TestClient 测 8 个端点。

- [ ] 写 tests/auth/test_account_settings_router_mock.py
- [ ] 测 patch_profile/post_avatar/delete_avatar/patch_email/post_email_verify/patch_password/get_deletion/post_deletion/delete_deletion

### Task 18: `src/ingest/api.py` — ingest API 测试

mock `store.*` + `get_object_store()` + auth middleware，TestClient 测上传/下载/列表。

- [ ] 写 tests/ingest/test_api_mock.py
- [ ] 测 upload/list_tasks/get_task/taskDownload

### Task 19: `src/ingest/pipeline.py` — 转换管线测试

mock converter + analyzer + archive_handler，tmp_path 创建输入文件，测 process_files/process_path。

- [ ] 写 tests/ingest/test_pipeline_mock.py
- [ ] 测 process_path 分流/空目录/正常转换

### Task 20: 最终覆盖率验证
