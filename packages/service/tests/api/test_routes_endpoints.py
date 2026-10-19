"""api/routes.py 端点测试 — 含 schema 校验 + endpoint mock (mode 1, 0 PG/Redis)"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import router
from src.api.schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceNode,
)

# ============================================================
# Schema 校验测试 (纯 Pydantic, 无外部依赖)
# ============================================================


class TestQueryRequestSchema:
    def test_valid_defaults(self):
        """query 必填, top_k/user_id 有默认值"""
        req = QueryRequest(query="hello", user_id=None, top_k=5)
        assert req.top_k == 5
        assert req.user_id is None

    def test_with_all_fields(self):
        req = QueryRequest(query="test query", user_id="user1", top_k=10)
        assert req.query == "test query"
        assert req.user_id == "user1"
        assert req.top_k == 10

    def test_top_k_ge_1(self):
        with pytest.raises(ValueError, match="top_k"):
            QueryRequest(query="test", user_id=None, top_k=0)

    def test_top_k_le_100(self):
        with pytest.raises(ValueError, match="top_k"):
            QueryRequest(query="test", user_id=None, top_k=101)

    def test_empty_query_invalid(self):
        with pytest.raises(ValueError, match="query"):
            QueryRequest(query="", user_id=None, top_k=5)

    def test_query_too_long(self):
        with pytest.raises(ValueError, match="query"):
            QueryRequest(query="x" * 2001, user_id=None, top_k=5)


class TestIngestRequestSchema:
    def test_valid(self):
        req = IngestRequest(input_dir="/in", output_dir="/out")
        assert req.input_dir == "/in"

    def test_none_paths(self):
        req = IngestRequest(input_dir=None, output_dir=None)
        assert req.input_dir is None
        assert req.output_dir is None


class TestResponseSchemas:
    def test_source_node_defaults(self):
        sn = SourceNode(file_path="", page_label="", text="")
        assert sn.file_path == ""
        assert sn.page_label == ""

    def test_source_node_full(self):
        sn = SourceNode(file_path="/a.pdf", page_label="3", text="内容")
        assert sn.file_path == "/a.pdf"

    def test_query_response_defaults(self):
        resp = QueryResponse(response="ans", sources=[], latency_ms=0.0)
        assert resp.response == "ans"
        assert resp.sources == []
        assert resp.latency_ms == 0.0

    def test_query_response_with_sources(self):
        sn = SourceNode(file_path="", page_label="", text="src")
        resp = QueryResponse(response="ans", sources=[sn], latency_ms=0.0)
        assert len(resp.sources) == 1

    def test_ingest_response_defaults(self):
        resp = IngestResponse(status="ok", processed=0, errors=0)
        assert resp.processed == 0
        assert resp.errors == 0


# ============================================================
# 端点 mock 测试 (patch 懒导入模块, 不连 PG/Redis)
# ============================================================


class TestHealthEndpoint:
    """health 端点 — 无外部依赖, 已有 1 个 test, 补 1 个 404"""

    def test_health_returns_ok(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_unknown_route_returns_404(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/api/v1/unknown")
        assert resp.status_code == 404


class TestQueryEndpoint:
    """POST /api/v1/query — 懒导入 generation / retrieval"""

    @patch("src.retrieval.get_vector_store")
    @patch("src.retrieval.get_embedder")
    @patch("src.generation.build_query_engine")
    @patch("src.generation.query")
    def test_query_success(self, mock_query, mock_qe, mock_embedder, mock_vs):
        mock_vs.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()
        mock_qe.return_value = MagicMock()
        mock_query.return_value = MagicMock(response="这是答案", sources=[])

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/api/v1/query", json={"query": "测试"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "这是答案"
        assert data["sources"] == []
        assert isinstance(data["latency_ms"], float)
        assert data["latency_ms"] > 0

    @patch("src.retrieval.get_vector_store")
    @patch("src.retrieval.get_embedder")
    @patch("src.generation.build_query_engine")
    @patch("src.generation.query")
    def test_query_with_sources(self, mock_query, mock_qe, mock_embedder, mock_vs):
        mock_vs.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()
        mock_qe.return_value = MagicMock()
        mock_query.return_value = MagicMock(
            response="answer",
            sources=[{"file_path": "/doc.pdf", "page_label": "3", "text": "内容片段"}],
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/api/v1/query", json={"query": "test", "top_k": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "内容片段"

    @patch("src.retrieval.get_vector_store")
    @patch("src.retrieval.get_embedder")
    @patch("src.generation.build_query_engine")
    def test_query_returns_500_on_error(self, mock_qe, mock_embedder, mock_vs):
        mock_vs.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()
        mock_qe.side_effect = RuntimeError("LLM 挂了 /path/to/secret")

        app = FastAPI()
        app.include_router(router)
        # (2026-06-26 ERR-001) 装全局 exception handler, 模拟 create_app() 行为
        from src.core.errors import install_error_handlers

        install_error_handlers(app)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/query", json={"query": "test"})
        assert resp.status_code == 500
        # 关键: 不再泄露 str(e) 给客户端, 改用全局 handler 统一 "Internal server error"
        assert resp.json()["detail"] == "Internal server error"
        # str(e) 内容不能出现在 response body
        assert "secret" not in resp.json()["detail"]

    def test_query_422_on_invalid_input(self):
        """Pydantic 校验失败 → 422"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/api/v1/query", json={"top_k": 0})
        assert resp.status_code == 422


class TestIngestEndpoint:
    """POST /api/v1/ingest — 懒导入 ingest"""

    @patch("src.ingest.process_files")
    def test_ingest_success(self, mock_process_files):
        mock_process_files.return_value = {
            "document": {"processed": ["file1.pdf"], "errors": []},
        }

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ingest",
            json={"input_dir": "/in", "output_dir": "/out"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1
        assert data["errors"] == 0

    @patch("src.ingest.process_files")
    def test_ingest_no_files(self, mock_process_files):
        mock_process_files.return_value = None

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ingest",
            json={"input_dir": "/empty", "output_dir": "/out"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_files"
        assert data["processed"] == 0
        assert data["errors"] == 0

    @patch("src.ingest.process_files")
    def test_ingest_returns_500_on_error(self, mock_process_files):
        mock_process_files.side_effect = RuntimeError("解析器挂了 /secret/file/path")

        app = FastAPI()
        app.include_router(router)
        # (2026-06-26 ERR-001) 装全局 exception handler
        from src.core.errors import install_error_handlers

        install_error_handlers(app)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/ingest",
            json={"input_dir": "/in", "output_dir": "/out"},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"
        assert "secret" not in resp.json()["detail"]

    def test_ingest_422_on_invalid_type(self):
        """非字符串路径 → 422"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/ingest",
            json={"input_dir": 123, "output_dir": "/out"},
        )
        assert resp.status_code == 422
