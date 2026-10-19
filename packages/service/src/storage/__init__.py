"""SQLAlchemy 2.0 存储层

公开 API:
- Base: DeclarativeBase, 业务 model 都继承
- get_engine: 惰性单例 Engine
- init_db: create_all (dev/test 用, 受 env 开关)
- session_scope: 事务 context manager
- get_session: FastAPI Depends 用的 generator
- get_object_store: 惰性单例 ObjectStore (env 切 local|minio, 2026-06-16 MinIO 集成)

切 PostgreSQL: 配 PG_* 5 env, 跑 alembic upgrade head (URL 在代码里用 get_rag_db_url() 拼)
切对象存储: 改 OBJECT_STORE_BACKEND 环境变量 (local|minio)
"""

from .base import Base
from .engine import get_engine, init_db
from .object_store import (
    LocalFSObjectStore,
    MinioObjectStore,
    ObjectMeta,
    ObjectNotFound,
    ObjectStore,
    ObjectStoreError,
    get_object_store,
)
from .session import get_session, session_scope

__all__ = [
    "Base",
    "get_engine",
    "init_db",
    "get_session",
    "session_scope",
    "get_object_store",
    "ObjectStore",
    "ObjectStoreError",
    "ObjectNotFound",
    "LocalFSObjectStore",
    "MinioObjectStore",
    "ObjectMeta",
]
