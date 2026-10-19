"""ingest 子包共享辅助函数 (2026-07-06).

pdf_processing/ 和 pre_analysis/ 共用的工具函数抽到这里,
避免跨子包 import (pre_analysis/router.py → pdf_processing/router.py).
"""

from __future__ import annotations

import hashlib
import os

from ..middleware.auth import CurrentUser


def user_hash_for(token: str) -> str:
    """sha256(token)[:8] — 跟现有 user_hash 约定一致."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def _check_token(user: CurrentUser) -> str:
    """鉴权上下文 → user token 字符串 (供 user_hash_for 等老接口用)."""
    return user.public_token


def _uri_for_backend(backend: str, key: str) -> str:
    """backend 名 (object_store.backend_name() 返值) → URI 字符串.

    local: 'local://{key}'
    minio/s3: 's3://{OBJECT_STORE_S3_BUCKET}/{key}'
    """
    if backend == "local":
        return f"local://{key}"
    if backend in ("s3", "minio"):
        bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
        return f"s3://{bucket}/{key}"
    raise ValueError(f"未知 backend: {backend!r}")
