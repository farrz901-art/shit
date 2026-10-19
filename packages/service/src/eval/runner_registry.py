"""进程内运行状态表

- 取消信号: dict[evaluation_id -> asyncio.Event], 后台 task 在每题前检查
- 重启恢复: 启动时扫 status='running' 的记录, 标 failed (写 "服务重启中断")
  避免"僵尸 running" 永久挂在前端

⚠️ 多 worker 部署 (uvicorn --workers N) 不支持, 需换 Redis. 本 spec YAGNI 单进程.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from ..storage.session import session_scope
from ..utils.timezone import HKT
from .models import Evaluation

# evaluation_id -> asyncio.Event (set = 取消信号)
_cancel_events: dict[int, asyncio.Event] = {}


def register_cancel_event(evaluation_id: int, event: asyncio.Event) -> None:
    """后台 task 启动时注册 (覆盖式: 同 id 重启时替换)"""
    _cancel_events[evaluation_id] = event


def unregister_cancel_event(evaluation_id: int) -> None:
    """后台 task 结束时清理 (completed / failed / cancelled 都调)"""
    _cancel_events.pop(evaluation_id, None)


def request_cancel(evaluation_id: int) -> bool:
    """HTTP cancel handler 调, 触发取消 + 持久化

    Returns:
        True = 成功 set (后台 task 还活着)
        False = id 不在表里 (已结束或从未注册)
    """
    event = _cancel_events.get(evaluation_id)
    if event is None:
        return False
    event.set()
    # 持久化取消请求 (进程重启恢复用)
    with session_scope() as s:
        e = s.get(Evaluation, evaluation_id)
        if e is not None and e.cancel_requested_at is None:
            e.cancel_requested_at = datetime.now(HKT)
    return True


def recover_orphaned_running() -> int:
    """启动时调一次: 把所有 status='running' 的 evaluation 标 failed

    Returns:
        修复的记录数
    """
    count = 0
    with session_scope() as s:
        orphans = s.query(Evaluation).filter(Evaluation.status == "running").all()
        for e in orphans:
            e.status = "failed"
            e.error_message = "服务重启中断"
            e.finished_at = datetime.now(HKT)
            count += 1
    return count
