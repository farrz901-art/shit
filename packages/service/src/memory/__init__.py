"""memory 子包: 记忆层 (mem0 self-host pgvector, 2026-06-16)"""

from .mem0_client import Mem0Store, _build_config, _default_mem0_factory
from .schemas import (
    AddRequest,
    DeleteResponse,
    MemoryHit,
    MemoryListResponse,
    SearchRequest,
    SearchResponse,
    TurnMessage,
    UpdateRequest,
)
from .service import MemoryService, _resolve_mem0_user_id

__all__ = [
    "Mem0Store",
    "_build_config",
    "_default_mem0_factory",
    "MemoryService",
    "_resolve_mem0_user_id",
    "SearchRequest",
    "SearchResponse",
    "MemoryHit",
    "AddRequest",
    "TurnMessage",
    # Phase 2 (2026-06-16)
    "MemoryListResponse",
    "UpdateRequest",
    "DeleteResponse",
]
