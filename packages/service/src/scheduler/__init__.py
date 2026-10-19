"""APScheduler 启动入口"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def register_schedulers() -> AsyncIOScheduler:
    """注册所有定时任务. 返 scheduler (供 lifespan 启停).

    当前注册的 job:
    - purge_pending_deletions: 每天 03:00 Asia/Hong_Kong, 清理到期 pending_deletion 账号
    - chat_hard_delete_30d: 每天 03:05 Asia/Hong_Kong, 真删 30d 前软删的 chat (2026-06-19 spec §8)
    """
    # 防循环: 顶层 from .deletion 触发 scheduler 启动时强制装载 chat service
    from .deletion import register_chat_jobs, register_deletion_jobs  # noqa: E402

    scheduler = AsyncIOScheduler(timezone="Asia/Hong_Kong")
    register_deletion_jobs(scheduler)
    register_chat_jobs(scheduler)  # (2026-06-19 chat spec §8) 30d hard-delete
    scheduler.start()
    return scheduler
