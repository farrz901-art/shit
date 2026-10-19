"""pgvector 向量库封装 (LangChain PGVectorStore + PGEngine)

公开 API: PGVectorStore (sync) + AsyncPGVectorStore + PGVectorConfig + add_to_vector_store
+ delete_from_vector_store + init_pgvector + get_vector_store.

内部走 langchain_postgres:
- PGEngine.from_connection_string → async psycopg3 wrapper
- PGVectorStore.create_sync(engine, embedding_service, table_name=rag_embeddings)
- delete 按 metadata.ref_doc_id 走 SA Engine 跑 raw SQL (Spike 偏差 #3)
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.common.db_url import get_rag_db_url
from src.common.document import RAGDoc

if TYPE_CHECKING:
    from langchain_postgres import PGEngine
    from langchain_postgres import PGVectorStore as LCPGVectorStore


# LC PGVectorStore 表名 (跟 alembic migration T4 一致)
_VECTOR_TABLE = "rag_embeddings"


@dataclass
class PGVectorConfig:
    """pgvector 配置. 5 个连接字段从 PG_* env 派生. 向量索引调参是 dataclass 默认值."""

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag"
    vector_dim: int | None = None  # None = 用 _get_embed_dim()
    index_type: str = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    ivfflat_lists: int = 100

    @property
    def connection_string(self) -> str:
        """URL 走 get_rag_db_url() 单一构造点, 保证密码 URL-encoding 一致."""
        return get_rag_db_url()

    @classmethod
    def from_env(cls) -> PGVectorConfig:
        """从 PG_* env 构造 (业务侧要求 PGVectorConfig 字段, 不用 URL 字符串)."""
        from ..common import defaults

        return cls(
            host=os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
            port=int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
            user=os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
            password=os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
            database=os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
        )


class PGVectorStore:
    """业务包装. 公开 API 同名 (add / delete / query), 内部走 LC PGVectorStore.

    持有 2 个 engine (Spike 偏差 #3):
    - _pg_engine (PGEngine): 给 LC PGVectorStore 用 (async psycopg3)
    - _sa_engine (sqlalchemy.Engine): 给 raw SQL DELETE (sync)
    PGEngine.close() 是 coroutine, sync 路径不可靠, 所以 sync 操作走独立 SA Engine.
    """

    def __init__(self, config: PGVectorConfig | None = None, embedder: Any | None = None):
        self._config = config or PGVectorConfig.from_env()
        self._embedder = embedder
        self._vs: LCPGVectorStore | None = None
        self._pg_engine: PGEngine | None = None
        self._sa_engine: Any | None = None  # sqlalchemy.Engine

    @property
    def config(self) -> PGVectorConfig:
        return self._config

    @property
    def vector_store(self) -> LCPGVectorStore:
        if self._vs is None:
            from langchain_postgres import PGEngine
            from langchain_postgres import PGVectorStore as LCPGVectorStore
            from sqlalchemy import create_engine

            if self._embedder is None:
                raise RuntimeError(
                    "PGVectorStore 需要传入 embedder. LC PGVectorStore.create_sync "
                    "构造期需要 OpenAIEmbeddings 实例. 调用方应显式注入."
                )
            self._pg_engine = PGEngine.from_connection_string(url=self._config.connection_string)
            self._sa_engine = create_engine(self._config.connection_string)
            # embedder 是项目 OpenAIEmbedder 包装, .embedder 拿 LC OpenAIEmbeddings 实例
            inner = self._embedder.embedder if hasattr(self._embedder, "embedder") else self._embedder
            self._vs = LCPGVectorStore.create_sync(
                engine=self._pg_engine,
                embedding_service=inner,
                table_name=_VECTOR_TABLE,
            )
        return self._vs

    def add(self, documents: Sequence[RAGDoc], batch_size: int = 100) -> list[str]:
        """add - metadata 应含 ref_doc_id (上层产生, 文档级标识), 用于 delete 按文档清."""
        if not documents:
            return []
        texts_ = [d.text for d in documents]
        metadatas = [d.metadata for d in documents]
        return self.vector_store.add_texts(texts_, metadatas=metadatas)

    def delete(self, doc_ids: Sequence[str], ref_doc_id: str | None = None) -> None:
        """按 ref_doc_id 删 - 沿用原 ref_doc_id 删除语义.

        签名兼容老调用:
        - `delete([doc_id])` -> 按 ref_doc_id IN ([doc_id]) 删
        - `delete([], ref_doc_id="doc-A")` -> 按 ref_doc_id = "doc-A" 删
        """
        ids = list(doc_ids) if doc_ids else ([ref_doc_id] if ref_doc_id else [])
        if not ids:
            return
        # 触发 lazy build (拿到 _sa_engine)
        _ = self.vector_store
        _delete_by_ref_doc_id(self._sa_engine, _VECTOR_TABLE, ids)

    def query(self, query_embedding: list[float], top_k: int = 5, filter: dict | None = None) -> Any:
        """按 vector cosine 检索, 返 LC Document 列表."""
        return self.vector_store.similarity_search_by_vector(query_embedding, k=top_k, filter=filter)

    def close(self) -> None:
        """sync 路径 close. PGEngine.close 是 coroutine, sync 没法清, 只清 SA Engine."""
        if self._sa_engine is not None:
            self._sa_engine.dispose()
        self._vs = None
        self._pg_engine = None
        self._sa_engine = None


class AsyncPGVectorStore:
    """异步版. 走 LC PGVectorStore.create (async 工厂) + aadd_texts / asimilarity_search_by_vector."""

    def __init__(self, config: PGVectorConfig | None = None, embedder: Any | None = None):
        self._config = config or PGVectorConfig.from_env()
        self._embedder = embedder
        self._vs: LCPGVectorStore | None = None
        self._engine: PGEngine | None = None

    @property
    def config(self) -> PGVectorConfig:
        return self._config

    async def aconnect(self) -> None:
        from langchain_postgres import PGEngine
        from langchain_postgres import PGVectorStore as LCPGVectorStore

        if self._embedder is None:
            raise RuntimeError("AsyncPGVectorStore 需要传入 embedder")
        self._engine = PGEngine.from_connection_string(url=self._config.connection_string)
        inner = self._embedder.embedder if hasattr(self._embedder, "embedder") else self._embedder
        self._vs = await LCPGVectorStore.create(
            engine=self._engine,
            embedding_service=inner,
            table_name=_VECTOR_TABLE,
        )

    async def aadd(self, documents: Sequence[RAGDoc]) -> list[str]:
        if not documents:
            return []
        assert self._vs is not None
        return await self._vs.aadd_texts(
            texts=[d.text for d in documents],
            metadatas=[d.metadata for d in documents],
        )

    async def adelete(self, doc_ids: Sequence[str]) -> None:
        if not doc_ids:
            return
        assert self._engine is not None
        await _adelete_by_ref_doc_id(self._engine, _VECTOR_TABLE, list(doc_ids))

    async def adisconnect(self) -> None:
        if self._engine is not None:
            aclose = getattr(self._engine, "close", None)
            if aclose is not None:
                await aclose()
        self._vs = None
        self._engine = None


def _delete_by_ref_doc_id(engine: Any, table_name: str, ref_doc_ids: list[str]) -> None:
    """按 langchain_metadata->>'ref_doc_id' = ANY(:rids) 删 (sync).

    engine 是 sqlalchemy.Engine (不是 PGEngine), 因为 PGEngine 是 async wrapper,
    sync raw SQL 走独立 SA Engine. langchain_metadata 已 ALTER 成 jsonb, ->>'k' 走 GIN.
    """
    assert table_name.isidentifier(), f"table_name must be SQL identifier, got: {table_name!r}"
    sql = text(f"DELETE FROM {table_name} WHERE langchain_metadata->>'ref_doc_id' = ANY(:rids)")
    with engine.connect() as conn:
        conn.execute(sql, {"rids": ref_doc_ids})
        conn.commit()


async def _adelete_by_ref_doc_id(engine: PGEngine, table_name: str, ref_doc_ids: list[str]) -> None:
    """async 版 - PGEngine async aconnect."""
    assert table_name.isidentifier(), f"table_name must be SQL identifier, got: {table_name!r}"
    sql = text(f"DELETE FROM {table_name} WHERE langchain_metadata->>'ref_doc_id' = ANY(:rids)")
    # PGEngine.aconnect 是 runtime 方法但 langchain_postgres 1.x stub 不全, 这里 pyright 反馈
    # 走显式 type: ignore (reportAttributeAccessIssue)
    async with engine.aconnect() as conn:  # type: ignore[reportAttributeAccessIssue]
        await conn.execute(sql, {"rids": ref_doc_ids})
        await conn.commit()


def get_vector_store(config: PGVectorConfig | None = None, use_async: bool = False) -> Any:
    if use_async:
        return AsyncPGVectorStore(config or PGVectorConfig.from_env())
    return PGVectorStore(config)


def init_pgvector(config: PGVectorConfig | None = None, force: bool = False) -> None:
    """初始化 pgvector + rag_embeddings 表 (走 LC PGEngine + 修正 JSONB / vector index).

    生产用 alembic migration (T4). 此函数用于 dev tooling (重置 schema).
    实际跑 4 步, 跟 Spike T0 偏差对齐:
    1. CREATE EXTENSION vector
    2. PGEngine.init_vectorstore_table (但建出来 langchain_metadata 是 json + 无 vector index)
    3. ALTER langchain_metadata 转 jsonb + 建 GIN (跟项目 JSONB 规约一致)
    4. apply_vector_index(HNSWIndex) 建真实 HNSW
    """
    # 重依赖 lazy: langchain_postgres + sqlalchemy 冷启动 ~1.2s, 非向量路径不需要
    from langchain_postgres import PGEngine  # noqa: E402
    from langchain_postgres import PGVectorStore as LCPGVectorStore  # noqa: E402
    from langchain_postgres.v2.indexes import HNSWIndex  # noqa: E402
    from sqlalchemy import create_engine  # noqa: E402

    config = config or PGVectorConfig.from_env()
    pg_engine = PGEngine.from_connection_string(url=config.connection_string)
    sa_engine = create_engine(config.connection_string)  # 跑 raw SQL ALTER / 索引

    # 1. pgvector 扩展 (LC 不管)
    with sa_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    # 2. LC 标准建表 (Spike: 只建 pkey + langchain_metadata=json)
    pg_engine.init_vectorstore_table(
        table_name=_VECTOR_TABLE,
        vector_size=config.vector_dim or _get_embed_dim(),
        overwrite_existing=force,
    )

    # 3. (Spike 偏差 #1) ALTER 转 jsonb + 建 GIN (项目 JSONB 规约)
    with sa_engine.connect() as conn:
        conn.execute(
            text(
                f"ALTER TABLE {_VECTOR_TABLE} "
                "ALTER COLUMN langchain_metadata TYPE jsonb "
                "USING langchain_metadata::jsonb"
            )
        )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_VECTOR_TABLE}_metadata_gin_idx "
                f"ON {_VECTOR_TABLE} USING gin (langchain_metadata jsonb_path_ops)"
            )
        )
        conn.commit()

    # 4. (Spike 偏差 #2) 建 HNSW vector index
    # 防循环: embedder 顶层 import 会触发 langchain_openai 加载 (~800ms)
    from .embedder import get_embedder  # noqa: E402

    store = LCPGVectorStore.create_sync(
        engine=pg_engine,
        embedding_service=get_embedder().embedder,
        table_name=_VECTOR_TABLE,
    )
    store.apply_vector_index(
        HNSWIndex(
            name=f"{_VECTOR_TABLE}_hnsw_idx",
            m=config.hnsw_m,
            ef_construction=config.hnsw_ef_construction,
        )
    )

    sa_engine.dispose()


def _get_embed_dim() -> int:
    """向量列维度从 EMBED_DIMENSIONS env 派生, 默认 1024 (BGE).

    单一来源: 跟 embedder 模型输出维度绑定, 避免 PG_VECTOR_DIM 跟 EMBED_DIMENSIONS 漂移.
    """
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))


def add_to_vector_store(
    documents: Sequence[RAGDoc],
    vector_store: PGVectorStore,
    embedder: Any | None = None,
    batch_size: int = 100,
) -> list[str]:
    if not documents:
        return []
    return vector_store.add(documents, batch_size=batch_size)


def delete_from_vector_store(doc_ids: Sequence[str], vector_store: PGVectorStore) -> None:
    if not doc_ids:
        return
    vector_store.delete(doc_ids)
