"""APScheduler 注册 + 注销清理 (7 天到期 anonymize + delete) + chat 30d hard-delete"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from ..auth.account_settings_service import purge_pending_deletions


def register_deletion_jobs(scheduler: AsyncIOScheduler) -> None:
    """注册注销清理 job. 每天 03:00 Asia/Hong_Kong 跑 1 次.

    业务: 找出 deletion_requested_at < (now - 7 天) 的 Account, anonymize 关联 User
    + delete Account (CASCADE EmailChange / DeletionRestore / PasswordReset).
    """
    scheduler.add_job(
        _run_purge,
        "cron",
        hour=3,
        minute=0,
        id="purge_pending_deletions",
        replace_existing=True,
    )
    logger.info("已注册 APScheduler job: purge_pending_deletions (每天 03:00 Asia/Hong_Kong)")


def _run_purge() -> None:
    """job 入口. 包 try/except 防止单次失败导致 scheduler 停摆."""
    try:
        count = purge_pending_deletions()
        logger.info("purge_pending_deletions: 已清理 {} 个到期账号", count)
    except Exception as e:
        logger.opt(exception=True).error("purge_pending_deletions 失败: {}", e)


# (2026-06-19 chat spec §8) chat 30d hard-delete cron
# 跟 deletion job 错开 5 分钟 (03:00 → 03:05), 避免同一时段 DB 写满


def register_chat_jobs(scheduler: AsyncIOScheduler) -> None:
    """注册 chat hard-delete job. 每天 03:05 Asia/Hong_Kong 跑 1 次.

    业务: 30d 前软删的 conv + 关联 msgs 真删 (GDPR right to erasure).
    跟 deletion job 错开 5 分钟 (03:00 → 03:05), 避免同一时段 DB 写满.
    """
    scheduler.add_job(
        _run_chat_hard_delete,
        "cron",
        hour=3,
        minute=5,
        id="chat_hard_delete_30d",
        replace_existing=True,
    )
    logger.info("已注册 APScheduler job: chat_hard_delete_30d (每天 03:05 Asia/Hong_Kong)")


def _run_chat_hard_delete() -> None:
    """job 入口. 包 try/except 防止单次失败导致 scheduler 停摆."""
    try:
        # 防循环: 顶层 from ..chat.service 触发 import chain (chat service 用了 session_scope)
        from ..chat.service import hard_delete_old_soft_deleted  # noqa: E402

        result = hard_delete_old_soft_deleted(days=30)
        logger.info("chat_hard_delete_30d 完成: {}", result)
    except Exception as e:
        logger.opt(exception=True).error("chat_hard_delete_30d 失败: {}", e)
