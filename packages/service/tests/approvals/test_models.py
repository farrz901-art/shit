"""Approval model + 3 enum 单元测试"""

from __future__ import annotations

from sqlalchemy import inspect

from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
    RejectReason,
)


def test_approval_review_status_values() -> None:
    """3 个 review status, 跟 spec 锁定一致"""
    assert {s.value for s in ApprovalReviewStatus} == {"pending", "approved", "rejected"}


def test_approval_apply_status_values() -> None:
    """3 个 apply status"""
    assert {s.value for s in ApprovalApplyStatus} == {"none", "applied", "failed"}


def test_reject_reason_values() -> None:
    """6 个预设原因 key, 跟前端 Select 1:1"""
    assert {s.value for s in RejectReason} == {
        "duplicate",
        "low_quality",
        "incomplete",
        "wrong_category",
        "format_issue",
        "other",
    }


def test_approval_kind_values() -> None:
    """5 个 kind (2026-06-16 加 like 用于满意按钮)"""
    assert {s.value for s in ApprovalKind} == {"qa", "triple", "batch", "optimize", "like"}


def test_approval_table_columns() -> None:
    """字段名 + 类型 + 默认值锁死, 防止 schema drift"""
    mapper = inspect(Approval)
    cols = {c.key: c for c in mapper.columns}

    assert "id" in cols
    assert "kind" in cols
    assert "payload" in cols
    # 关键: 2 状态轴
    assert "review_status" in cols
    assert "apply_status" in cols
    # default 是 DefaultGenerator, 通过 .arg 拿到枚举值
    review_default = cols["review_status"].default  # type: ignore[attr-defined]
    apply_default = cols["apply_status"].default  # type: ignore[attr-defined]
    assert review_default.arg == ApprovalReviewStatus.PENDING.value  # type: ignore[attr-defined]
    assert apply_default.arg == ApprovalApplyStatus.NONE.value  # type: ignore[attr-defined]
    # 必填外键
    assert "submitter_id" in cols
    assert "reviewer_id" in cols
    # 拒绝: 原因 key + 补充 (other 时)
    assert "rejection_reason" in cols
    assert "rejection_note" in cols
    # 写库失败: 错误消息
    assert "error_msg" in cols
    # 时间戳
    assert "created_at" in cols
    assert "reviewed_at" in cols
    assert "applied_at" in cols
