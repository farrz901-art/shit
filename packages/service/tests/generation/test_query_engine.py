"""测试 QueryEngine LCEL 链 (全 mock)"""

from unittest.mock import MagicMock, patch

from src.generation.query_engine import (
    QueryResult,
    _LCQueryEngine,
    build_query_engine,
    query,
)


def test_query_result_from_response_no_sources():
    r = QueryResult.from_response("ans", source_docs=None)
    assert r.response == "ans"
    assert r.sources == []


def test_query_result_from_response_with_docs():
    doc = MagicMock()
    doc.page_content = "context"
    doc.metadata = {"file_path": "/a.md", "page_label": "1"}
    r = QueryResult.from_response("ans", source_docs=[doc])
    assert r.response == "ans"
    assert len(r.sources) == 1
    assert r.sources[0]["file_path"] == "/a.md"
    assert r.sources[0]["text"] == "context"


def test_query_result_text_truncation():
    doc = MagicMock()
    doc.page_content = "x" * 500
    doc.metadata = {}
    r = QueryResult.from_response("ans", source_docs=[doc])
    assert r.sources[0]["text"].endswith("...")
    assert len(r.sources[0]["text"]) <= 203  # 200 + "..."


def test_lc_query_engine_invoke():
    """_LCQueryEngine.query 把 chain 输出 dict 转 QueryResult"""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = {"response": "ans", "docs": []}
    qe = _LCQueryEngine(mock_chain)
    r = qe.query("q?")
    assert r.response == "ans"


def test_build_query_engine_callable():
    """build_query_engine 构造返 _LCQueryEngine (vector_store / llm 全 mock)"""
    mock_vs = MagicMock()
    mock_vs._embedder = None
    mock_vs.vector_store.as_retriever.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_llm = MagicMock()
    qe = build_query_engine(mock_vs, mock_embedder, llm=mock_llm, top_k=5)
    assert isinstance(qe, _LCQueryEngine)


def test_query_function_passthrough():
    """模块级 query() 转发到 query_engine.query"""
    mock_qe = MagicMock()
    mock_qe.query.return_value = QueryResult(response="r", sources=[])
    r = query("q?", mock_qe)
    assert r.response == "r"


def test_get_llm_returns_llm():
    from src.generation.query_engine import get_llm

    with patch("src.generation.llm.OpenAILLM") as mock_class:
        mock_instance = mock_class.return_value
        mock_instance.llm = "mocked_llm"
        llm = get_llm(llm_type="openai", model="gpt-4o-mini")
        assert llm == "mocked_llm"
