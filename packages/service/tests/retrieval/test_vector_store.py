"""测试 PGVectorStore 公开 API (内部走 LC, 全 mock)"""

from unittest.mock import MagicMock, patch

import pytest

from src.common.document import RAGDoc
from src.retrieval.vector_store import (
    AsyncPGVectorStore,
    PGVectorConfig,
    PGVectorStore,
    _get_embed_dim,
    add_to_vector_store,
    delete_from_vector_store,
)


def test_pgvector_config_connection_string(monkeypatch):
    """connection_string 走 get_rag_db_url() 单一构造点"""
    monkeypatch.setenv("PG_HOST", "localhost")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASSWORD", "p")
    monkeypatch.setenv("PG_DATABASE", "d")
    cfg = PGVectorConfig()
    assert cfg.connection_string == "postgresql+psycopg://u:p@localhost:5432/d"


def test_pgvector_config_from_env(monkeypatch):
    """from_env 拼对字段"""
    monkeypatch.setenv("PG_HOST", "h")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASSWORD", "p")
    monkeypatch.setenv("PG_DATABASE", "d")
    cfg = PGVectorConfig.from_env()
    assert cfg.host == "h"
    assert cfg.user == "u"


class TestPGVectorConfigFromEnv:
    """PGVectorConfig.from_env() 从 PG_* env 读取"""

    def test_from_env_reads_all_vars(self, monkeypatch):
        """from_env 只读 5 个连接 env; vector_dim/index_type/hnsw_*/ivfflat_lists 走 dataclass 默认值."""
        monkeypatch.setenv("PG_HOST", "pg.internal")
        monkeypatch.setenv("PG_PORT", "6432")
        monkeypatch.setenv("PG_USER", "rag_user")
        monkeypatch.setenv("PG_PASSWORD", "s3cret")
        monkeypatch.setenv("PG_DATABASE", "prod_rag")
        # 即使设了旧的 PG_VECTOR_DIM / PG_INDEX_TYPE / PG_HNSW_* / PG_IVFFLAT_LISTS 也不再读
        monkeypatch.setenv("PG_VECTOR_DIM", "1536")
        monkeypatch.setenv("PG_INDEX_TYPE", "ivfflat")
        monkeypatch.setenv("PG_HNSW_M", "32")
        monkeypatch.setenv("PG_HNSW_EF_CONSTRUCTION", "256")
        monkeypatch.setenv("PG_IVFFLAT_LISTS", "200")

        cfg = PGVectorConfig.from_env()
        assert cfg.host == "pg.internal"
        assert cfg.port == 6432
        assert cfg.user == "rag_user"
        assert cfg.password == "s3cret"
        assert cfg.database == "prod_rag"
        # 5 个向量索引字段不读 env, 走 dataclass 默认值
        assert cfg.vector_dim is None
        assert cfg.index_type == "hnsw"
        assert cfg.hnsw_m == 16
        assert cfg.hnsw_ef_construction == 200
        assert cfg.ivfflat_lists == 100

    def test_from_env_uses_defaults_when_unset(self, monkeypatch):
        """env 全部未设时, from_env() 跟 PGVectorConfig() 默认值一致"""
        for k in [
            "PG_HOST",
            "PG_PORT",
            "PG_USER",
            "PG_PASSWORD",
            "PG_DATABASE",
        ]:
            monkeypatch.delenv(k, raising=False)

        cfg = PGVectorConfig.from_env()
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.vector_dim is None
        assert cfg.index_type == "hnsw"

    def test_pgvector_store_init_uses_env(self, monkeypatch):
        """PGVectorStore() 不传参时走 from_env()"""
        monkeypatch.setenv("PG_HOST", "env-host")
        store = PGVectorStore()
        assert store._config.host == "env-host"


def test_pgvector_store_init_default():
    """PGVectorStore() 默认构造 - _vs / _pg_engine / _sa_engine 全 None (lazy)"""
    store = PGVectorStore()
    assert store._config is not None
    assert store._vs is None
    assert store._pg_engine is None
    assert store._sa_engine is None


def test_async_pgvector_store_init():
    store = AsyncPGVectorStore()
    assert store._config is not None
    assert store._vs is None


@patch("sqlalchemy.create_engine")
@patch("langchain_postgres.PGVectorStore.create_sync")
@patch("langchain_postgres.PGEngine.from_connection_string")
def test_pgvector_store_lazy_build(mock_engine_factory, mock_create_sync, mock_sa_create):
    """PGVectorStore.vector_store lazy 构造 + 注入 embedder"""
    mock_engine_factory.return_value = MagicMock()
    mock_create_sync.return_value = MagicMock()
    mock_sa_create.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    _ = store.vector_store  # 触发 lazy

    mock_engine_factory.assert_called_once()
    mock_create_sync.assert_called_once()


@patch("sqlalchemy.create_engine")
@patch("langchain_postgres.PGVectorStore.create_sync")
@patch("langchain_postgres.PGEngine.from_connection_string")
def test_pgvector_store_add(mock_engine_factory, mock_create_sync, mock_sa_create):
    """add(docs) 调 LC add_texts(texts, metadatas)"""
    mock_engine_factory.return_value = MagicMock()
    mock_lc_store = MagicMock()
    mock_lc_store.add_texts.return_value = ["id1", "id2"]
    mock_create_sync.return_value = mock_lc_store
    mock_sa_create.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    docs = [
        RAGDoc(text="t1", metadata={"ref_doc_id": "doc-A"}),
        RAGDoc(text="t2", metadata={"ref_doc_id": "doc-A"}),
    ]
    ids = store.add(docs)
    assert ids == ["id1", "id2"]
    mock_lc_store.add_texts.assert_called_once_with(
        ["t1", "t2"],
        metadatas=[{"ref_doc_id": "doc-A"}, {"ref_doc_id": "doc-A"}],
    )


def test_pgvector_store_add_empty():
    """空 list 不触发 vector_store lazy 构造"""
    store = PGVectorStore()  # 无 embedder 也 OK (空 list 不触发 vector_store)
    assert store.add([]) == []


def test_pgvector_store_no_embedder_raises():
    """vector_store 属性触发但无 embedder 抛 RuntimeError"""
    store = PGVectorStore()  # no embedder
    with pytest.raises(RuntimeError, match="embedder"):
        _ = store.vector_store


@patch("src.retrieval.vector_store._delete_by_ref_doc_id")
@patch("sqlalchemy.create_engine")
@patch("langchain_postgres.PGVectorStore.create_sync")
@patch("langchain_postgres.PGEngine.from_connection_string")
def test_pgvector_store_delete_by_ref_doc_id(mock_engine_factory, mock_create_sync, mock_sa_create, mock_delete):
    """delete([ref_doc_id]) 走原生 SQL 按 metadata 删, 不是按主键 (回归 P0 错误 15)"""
    mock_engine_factory.return_value = MagicMock()
    mock_create_sync.return_value = MagicMock()
    mock_sa_create.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    store.delete(["doc-A", "doc-B"])

    mock_delete.assert_called_once()
    args = mock_delete.call_args[0]
    # args = (sa_engine, "rag_embeddings", ["doc-A", "doc-B"])
    assert args[1] == "rag_embeddings"
    assert args[2] == ["doc-A", "doc-B"]


def test_pgvector_store_delete_empty_noop():
    store = PGVectorStore()
    store.delete([])  # 不应抛 (不触发 engine)


def test_async_pgvector_store_no_embedder_raises():
    import asyncio

    store = AsyncPGVectorStore()
    with pytest.raises(RuntimeError, match="embedder"):
        asyncio.run(store.aconnect())


class TestGetEmbedDim:
    """_get_embed_dim() 从 EMBED_DIMENSIONS env 派生维度, 默认 1024 (BGE)"""

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("EMBED_DIMENSIONS", raising=False)
        assert _get_embed_dim() == 1024

    def test_reads_env_when_set(self, monkeypatch):
        monkeypatch.setenv("EMBED_DIMENSIONS", "1536")
        assert _get_embed_dim() == 1536


def test_add_to_vector_store_empty():
    assert add_to_vector_store([], MagicMock()) == []


def test_delete_from_vector_store_empty():
    """空 list 不触发任何调用"""
    mock_vs = MagicMock()
    delete_from_vector_store([], mock_vs)
    mock_vs.delete.assert_not_called()


def test_delete_from_vector_store_passthrough():
    """delete_from_vector_store 调 vector_store.delete(doc_ids)"""
    mock_vs = MagicMock()
    delete_from_vector_store(["id1", "id2"], mock_vs)
    mock_vs.delete.assert_called_once_with(["id1", "id2"])
