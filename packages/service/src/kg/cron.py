"""kg_extract_items 7d hard-delete cron (PR3 Task 17, v3)

跟 chat soft-delete 30d cron 同一模式:
- session_scope 走标准 PG session
- 行数返 CleanupResult dataclass
- loguru INFO 日志
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from src.storage import session_scope


@dataclass
class CleanupResult:
    deleted_count: int = 0


def cleanup_old_extract_items(days: int = 7) -> CleanupResult:
    """删除 created_at < NOW() - INTERVAL '{days} days' 的 kg_extract_items

    Args:
        days: 删除阈值, 默认 7

    Returns:
        CleanupResult(deleted_count=N)
    """
    days = int(days)
    sql = text(f"DELETE FROM kg_extract_items WHERE created_at < NOW() - INTERVAL '{days} days'")
    with session_scope() as session:
        result = session.execute(sql)
        # rowcount attribute is set on real DB results; mock-friendly fallback
        deleted_count = getattr(result, "rowcount", 0) or 0
    logger.info("kg_extract_items cron cleanup days={} deleted={}", days, deleted_count)
    return CleanupResult(deleted_count=deleted_count)
