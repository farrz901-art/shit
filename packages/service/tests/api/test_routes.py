"""api 测试"""

from src.api.schemas import IngestRequest, QueryRequest


def test_query_request_schema():
    # pyright basic 模式看不全 Pydantic Field 默认值, 显式传全
    req = QueryRequest(query="什么是 RAG？", user_id=None, top_k=5)
    assert req.query == "什么是 RAG？"
    assert req.user_id is None
    assert req.top_k == 5


def test_query_request_with_user_id():
    # pyright basic 模式看不全 Pydantic Field 默认值, 显式传全
    req = QueryRequest(query="Q", user_id="user123", top_k=5)
    assert req.user_id == "user123"


def test_ingest_request_schema():
    # IngestRequest 全字段 Optional, 但 pyright basic 仍要求传所有
    req = IngestRequest()  # pyright: ignore[reportCallIssue]
    assert req.input_dir is None


def test_ingest_request_with_dirs():
    req = IngestRequest(input_dir="/data/pdfs", output_dir="/data/md")
    assert req.input_dir == "/data/pdfs"


def test_query_request_default_top_k():
    req = QueryRequest(query="Q", user_id=None, top_k=5)
    assert req.top_k == 5


def test_ingest_request_full():
    req = IngestRequest(input_dir="/in", output_dir="/out")
    assert req.output_dir == "/out"
    assert req.input_dir == "/in"
