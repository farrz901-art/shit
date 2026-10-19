"""LC PGVectorStore schema 迁移: llamaindex_embeddings → rag_embeddings

替换旧版 PGVectorStore (单表 5 列) 到 LangChain PGVectorStore 单表 schema
(langchain_id / content / embedding / langchain_metadata JSONB).

ref_doc_id 从老表独立列迁到 langchain_metadata.ref_doc_id JSONB key.
JSONB (非 LC 默认 json) + GIN 索引, 符合项目 JSONB 规约.

老表 llamaindex_embeddings 保留 7 天, P3 follow-up 单独 DROP.

Revision ID: 20260629_000000
Revises: 20260626_000000
Create Date: 2026-06-29
"""

from __future__ import annotations

import os

from alembic import op

# revision identifiers
revision: str = "20260629_000000"
down_revision: str | None = "20260626_000000"
branch_labels: str | None = None
depends_on: str | None = None


def _get_embed_dim() -> int:
    """从 env 读 embedding 维度, 跟 EMBED_DIMENSIONS 单源一致."""
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))


def upgrade() -> None:
    """建 rag_embeddings 表 (jsonb metadata) + HNSW + GIN + INSERT FROM 老表.

    注: 这里直接写 CREATE TABLE 等价 SQL, 不调 LC PGEngine.init_vectorstore_table.
    (a) alembic 应该 reproducible, 不依赖 LC 库版本变化时 schema 改动
    (b) LC 默认 langchain_metadata 是 json 不是 jsonb (跟项目 JSONB 规约冲突), 直接 SQL 建 jsonb
    """
    dim = _get_embed_dim()

    # 0. 确保 pgvector 扩展存在 (dev DB 已装, 防御性写)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. 建新表 (LC PGVectorStore 标准 schema, langchain_metadata jsonb 不是 json)
    op.execute(f"""
        CREATE TABLE rag_embeddings (
            langchain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content TEXT NOT NULL,
            embedding vector({dim}),
            langchain_metadata JSONB DEFAULT '{{}}'::jsonb
        );
    """)

    # 2. HNSW 索引 (vector cosine) — LC init_vectorstore_table 不自动建
    op.execute("""
        CREATE INDEX rag_embeddings_hnsw_idx
            ON rag_embeddings USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200);
    """)

    # 3. GIN 索引 (JSONB metadata, 加速 ref_doc_id 删除走 @> 操作符)
    op.execute("""
        CREATE INDEX rag_embeddings_metadata_gin_idx
            ON rag_embeddings USING gin (langchain_metadata jsonb_path_ops);
    """)

    # 4. 一次性数据迁移 (若老表存在且有数据)
    # 老表: id, text, metadata, ref_doc_id, embedding
    # 新表: langchain_id, content, langchain_metadata (含 ref_doc_id), embedding
    # 用 DO 块包裹防止老表不存在时整个 migration 炸
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'llamaindex_embeddings') THEN
                INSERT INTO rag_embeddings (langchain_id, content, langchain_metadata, embedding)
                SELECT
                    id,
                    text,
                    COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('ref_doc_id', ref_doc_id::text),
                    embedding
                FROM llamaindex_embeddings;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """删 rag_embeddings (老表仍在, 业务回滚到旧 schema 即可)"""
    op.execute("DROP INDEX IF EXISTS rag_embeddings_metadata_gin_idx;")
    op.execute("DROP INDEX IF EXISTS rag_embeddings_hnsw_idx;")
    op.execute("DROP TABLE IF EXISTS rag_embeddings;")
