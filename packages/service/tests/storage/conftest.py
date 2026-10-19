"""storage 测试 fixture

(2026-06-29) 删除 pg_engine fixture: 真连 PG 违反 CLAUDE.md §强制测试隔离 (所有 test 禁直连 PG).
db_session (模式 2 集成测) 也已删, 整组 dead. reset_storage_engine 保留 — 只 reset 模块级
_engine 单例, 不连 PG, 单测 autouse mock 用.

URL 走 src.common.db_url.get_rag_db_url() (PG_* 5 env), 不再读 RAG_DB_URL.

CI 集成测 (模式 2) 改走 tests/integration/test_*_e2e.py + 真外部服务 (PG / MinIO / Docker).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def reset_storage_engine():
    """重置 storage.engine 模块级 _engine 单例, 单测不真连 dev DB."""
    from src.storage import engine as engine_mod

    engine_mod._engine = None
    yield
    if engine_mod._engine is not None:
        engine_mod._engine.dispose()
        engine_mod._engine = None
