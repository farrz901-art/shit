"""SQLAlchemy Engine 工厂 (PG only, 2026-06-15 / 2026-06-18 refactor)

- URL 走 src.common.db_url.get_rag_db_url() (PG_* 5 env 拼, 2026-06-18 重构)
- get_engine(): 惰性单例, pool_pre_ping=True, pool_size=5, max_overflow=10
- init_db(): dev/test 跑 create_all, 受 RAG_AUTO_CREATE_SCHEMA 开关

旧 SQLite 适配 (journal_mode PRAGMA / check_same_thread) 已删除 — 跟 spec 一致, 无 shim.
"""

from __future__ import annotations

import os
import re

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.common.db_url import get_rag_db_url

from .base import Base

# 启动期懒加载; URL 从 src.common.db_url.get_rag_db_url() 拿 (PG_* 5 env source of truth)
_engine: Engine | None = None


def _make_engine(url: str) -> Engine:
    """PG-only: 统一 pool 配置.

    pool_pre_ping=True: 防连接过期 (PG idle timeout / 重启)
    pool_size=5 + max_overflow=10: 适合 FastAPI 多 worker
    """
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


def get_engine() -> Engine:
    """惰性单例 Engine. 首次创建时验证连接可用, 密码错/连不上直接抛明确错误."""
    global _engine
    if _engine is None:
        url = get_rag_db_url()
        _engine = _make_engine(url)
        # 验证连接: 密码错/端口错/库不存在 → 立刻暴露, 不等业务查询时才炸成 500
        try:
            with _engine.connect() as conn:
                conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        except Exception as e:
            _engine.dispose()
            _engine = None
            raise RuntimeError(
                f"数据库连接失败: {e}\n"
                f"  URL: {_mask_password(url)}\n"
                f"  请检查 PG_* 5 个环境变量, 或确认 docker PG 正在运行"
            ) from e
        logger.info(f"[storage] 数据库引擎已初始化: {_mask_password(url)}")
    return _engine


def _mask_password(url: str) -> str:
    """隐藏 URL 中的密码, 防日志泄漏"""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def init_db() -> None:
    """建表 (仅 dev/test 用, 生产走 Alembic).

    受 RAG_AUTO_CREATE_SCHEMA=1 开关, 默认关闭 (保护生产).
    """
    if os.getenv("RAG_AUTO_CREATE_SCHEMA") != "1":
        logger.info("[storage] 已跳过 init_db (设置 RAG_AUTO_CREATE_SCHEMA=1 启用)")
        return
    logger.warning("[storage] 自动建表, 仅限 dev/test")
    Base.metadata.create_all(get_engine())
