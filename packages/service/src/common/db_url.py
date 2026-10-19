"""PG 连接 URL 构造器 (2026-06-18 重构).

源 = PG_* 5 个 env (跟 Docker POSTGRES_* / Django DATABASES / psql 习惯一致).
产物 = postgresql+psycopg URL (SQLAlchemy / Alembic / pgvector 标准接口).

URL 只在 SQLAlchemy / pgvector 调用点构造, 不在 env 里出现.
"""

from __future__ import annotations

import os
from urllib.parse import quote

from . import defaults


def get_rag_db_url() -> str:
    """从 PG_* env 构造 SQLAlchemy 用的 postgresql+psycopg URL.

    密码 / user / database 自动 URL-encode (quote safe=''),
    避免 @ : / 等特殊字符炸 URL 解析.

    默认值从 src.common.defaults 拿 (集中管理, 禁止硬编码).
    """
    host = os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST)
    port = int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT)))
    user = os.getenv("PG_USER", defaults.DEFAULT_PG_USER)
    password = os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD)
    database = os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE)
    return (
        f"postgresql+psycopg://{quote(user, safe='')}:"
        f"{quote(password, safe='')}@"
        f"{host}:{port}/{quote(database, safe='')}"
    )
