"""schemas Pydantic 模型测试"""

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError


def _load_schemas():
    src_dir = Path(__file__).resolve().parent.parent.parent / "src"
    spec = importlib.util.spec_from_file_location("schemas", src_dir / "api" / "schemas.py")
    assert spec is not None and spec.loader is not None, f"spec 解析失败: {src_dir / 'api' / 'schemas.py'}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def schemas():
    return _load_schemas()


def test_query_request_valid(schemas):
    """QueryRequest 正常构造"""
    req = schemas.QueryRequest(query="test query", user_id="user1", top_k=10)
    assert req.query == "test query"
    assert req.user_id == "user1"
    assert req.top_k == 10


def test_query_request_defaults(schemas):
    """QueryRequest 默认值"""
    req = schemas.QueryRequest(query="test")
    assert req.user_id is None
    assert req.top_k == 5


def test_query_request_top_k_minimum(schemas):
    """top_k 必须 >= 1"""
    with pytest.raises(ValidationError):
        schemas.QueryRequest(query="test", top_k=0)


def test_query_request_top_k_maximum(schemas):
    """top_k 必须 <= 100"""
    with pytest.raises(ValidationError):
        schemas.QueryRequest(query="test", top_k=101)


def test_source_node_defaults(schemas):
    """SourceNode 默认值"""
    node = schemas.SourceNode()
    assert node.file_path == ""
    assert node.page_label == ""
    assert node.text == ""


def test_query_response_defaults(schemas):
    """QueryResponse 默认值"""
    resp = schemas.QueryResponse(response="answer")
    assert resp.sources == []
    assert resp.latency_ms == 0.0


def test_ingest_request_optional_fields(schemas):
    """IngestRequest 可选字段均可为 None"""
    req = schemas.IngestRequest()
    assert req.input_dir is None
    assert req.output_dir is None


def test_ingest_request_with_values(schemas):
    """IngestRequest 带值"""
    req = schemas.IngestRequest(input_dir="/data/in", output_dir="/data/out")
    assert req.input_dir == "/data/in"
    assert req.output_dir == "/data/out"


def test_ingest_response_defaults(schemas):
    """IngestResponse 默认值"""
    resp = schemas.IngestResponse(status="ok")
    assert resp.status == "ok"
    assert resp.processed == 0
    assert resp.errors == 0


def test_ingest_response_with_counts(schemas):
    """IngestResponse 带计数"""
    resp = schemas.IngestResponse(status="done", processed=10, errors=1)
    assert resp.processed == 10
    assert resp.errors == 1
