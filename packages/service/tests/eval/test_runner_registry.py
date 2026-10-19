"""进程内取消事件表 + 启动时 running 标 failed (2026-06-16 重写 100% mock, 4 tests)

cover src/eval/runner_registry.py:
- register_cancel_event / unregister_cancel_event / request_cancel: 纯内存 dict, 无需 mock
- recover_orphaned_running: patch session_scope 替 mock session, 0 真 DB

(2026-07-09) request_cancel 路径里也走 session_scope 持久化, 测试必须 mock 掉,
否则连真 PG → "too many clients already" (CLAUDE.md 强制测试 100% mock).

0 真实 DB 连接, 0 dev DB writes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from src.eval.models import Evaluation
from src.eval.runner_registry import (
    recover_orphaned_running,
    register_cancel_event,
    request_cancel,
    unregister_cancel_event,
)

# ---------------- register / cancel ----------------


def test_register_and_request_cancel():
    """注册 -> 取消 -> 注销 全套. request_cancel 内部 session_scope mock 掉防连真 PG."""
    event = asyncio.Event()
    mock_session = MagicMock()
    # session.get(Evaluation, id) 返 None (测试不关心 PG 持久化细节)
    mock_session.get.return_value = None
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_session
    ctx.__exit__.return_value = False
    with patch("src.eval.runner_registry.session_scope", return_value=ctx):
        register_cancel_event(42, event)
        assert request_cancel(42) is True
        assert event.is_set()
        unregister_cancel_event(42)
        assert request_cancel(42) is False  # 已注销


def test_request_cancel_unknown_id():
    """未注册的 id -> False. 不调 session_scope 路径 (line 45 guard), 无需 mock."""
    assert request_cancel(99999) is False


# ---------------- recover_orphaned_running ----------------


def _patch_session(mock_session: MagicMock):
    """patch runner_registry.session_scope, 返回给定 mock session"""
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_session
    ctx.__exit__.return_value = False
    return patch("src.eval.runner_registry.session_scope", return_value=ctx)


def test_recover_orphaned_running_marks_failed():
    """启动恢复: status='running' 的全部标 failed + 写 error_message"""
    running_eval = MagicMock(spec=Evaluation)
    running_eval.id = 10
    running_eval.status = "running"
    running_eval.error_message = None
    running_eval.finished_at = None

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [running_eval]

    with _patch_session(mock_session):
        count = recover_orphaned_running()

    assert count == 1
    assert running_eval.status == "failed"
    assert "服务重启" in (running_eval.error_message or "")
    assert running_eval.finished_at is not None


def test_recover_skips_completed_evals():
    """completed 的不动: query(status=='running').all() 返空 (filter 排除)"""
    mock_session = MagicMock()
    # filter(status=='running') 的结果为空: 没有 running 的行
    mock_session.query.return_value.filter.return_value.all.return_value = []

    with _patch_session(mock_session):
        count = recover_orphaned_running()

    assert count == 0
    # filter 条件: Evaluation.status == "running" 被传入
    mock_session.query.return_value.filter.assert_called_once()
