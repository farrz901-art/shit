"""ApprovalService 单元测试 — TDD 红绿循环"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
    RejectReason,
)
from src.approvals.service import ApprovalNotFoundError, ApprovalService, InvalidStateError
from src.utils.timezone import HKT


def _user(id_: int = 1) -> MagicMock:
    """mock CurrentUser-like 对象 (id + is_admin)"""
    u = MagicMock()
    u.id = id_
    u.is_admin = True
    return u


async def test_submit_creates_pending_approval() -> None:
    """submit 写 review=pending, apply=none, submitter_id, created_at, JSON payload"""
    repo = MagicMock()
    captured: dict = {}

    async def fake_add(a: Approval) -> None:
        captured["approval"] = a

    async def fake_commit() -> None:
        captured["committed"] = True

    repo.add = fake_add
    repo.commit = fake_commit
    repo.refresh = AsyncMock()  # service.submit 末尾 await refresh(approval)
    svc = ApprovalService(repo=repo)

    submitter = _user(id_=42)
    result = await svc.submit(
        kind=ApprovalKind.QA,
        payload={"dataset_id": "ds1", "question": "q", "answer": "a"},
        submitter=submitter,
    )

    assert isinstance(result, Approval)
    assert result.kind == "qa"
    assert result.review_status == ApprovalReviewStatus.PENDING.value
    assert result.apply_status == ApprovalApplyStatus.NONE.value
    assert result.submitter_id == 42
    # payload JSON 字符串化
    assert json.loads(result.payload) == {"dataset_id": "ds1", "question": "q", "answer": "a"}
    assert result.created_at is not None
    assert captured.get("committed") is True


async def test_approve_pending_sets_approved_and_reviewer() -> None:
    """approve pending 项: review=approved, apply=none (BGTask 还没跑), reviewer_id, reviewed_at"""
    pending = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.PENDING.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=pending)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    reviewer = _user(id_=99)
    result = await svc.approve(1, reviewer)

    assert result.review_status == ApprovalReviewStatus.APPROVED.value
    assert result.apply_status == ApprovalApplyStatus.NONE.value  # BGTask 还没跑
    assert result.reviewer_id == 99
    assert result.reviewed_at is not None
    repo.commit.assert_awaited_once()


async def test_approve_non_pending_raises_invalid_state() -> None:
    """非 pending 状态调 approve → 409 InvalidStateError"""
    approved = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=approved)
    svc = ApprovalService(repo=repo)

    with pytest.raises(InvalidStateError):
        await svc.approve(1, _user())


async def test_approve_nonexistent_raises_not_found() -> None:
    """id 不存在 → ApprovalNotFoundError"""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    svc = ApprovalService(repo=repo)

    with pytest.raises(ApprovalNotFoundError):
        await svc.approve(999, _user())


async def test_reject_pending_sets_rejected_with_reason_and_note() -> None:
    """reject pending 项: review=rejected (终态), rejection_reason=key, rejection_note=note"""
    pending = Approval(
        id=2,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.PENDING.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=pending)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    result = await svc.reject(2, RejectReason.DUPLICATE, "跟 ds1:doc-12 重复", _user(id_=99))

    assert result.review_status == ApprovalReviewStatus.REJECTED.value
    assert result.rejection_reason == "duplicate"
    assert result.rejection_note == "跟 ds1:doc-12 重复"
    assert result.reviewer_id == 99
    assert result.reviewed_at is not None


async def test_reject_non_pending_raises_invalid_state() -> None:
    """非 pending 状态调 reject → InvalidStateError"""
    rejected = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.REJECTED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=rejected)
    svc = ApprovalService(repo=repo)

    with pytest.raises(InvalidStateError):
        await svc.reject(1, RejectReason.LOW_QUALITY, None, _user())


async def test_retry_approved_failed_resets_apply_to_none() -> None:
    """retry (approved, failed) → review 保持 approved, apply: failed → none (BGTask 重跑)"""
    failed = Approval(
        id=3,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.FAILED.value,
        submitter_id=10,
        error_msg="Dify 502",
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=failed)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    result = await svc.retry(3, _user(id_=99))

    assert result.review_status == ApprovalReviewStatus.APPROVED.value  # 保持
    assert result.apply_status == ApprovalApplyStatus.NONE.value  # 清掉 failed
    assert result.error_msg is None  # 清掉


async def test_retry_non_failed_raises_invalid_state() -> None:
    """非 (approved, failed) 状态调 retry → InvalidStateError

    4 个非法场景都测:
    - pending (还没批)
    - approved + none (还没尝试)
    - approved + applied (已成功, 不该重试)
    - rejected (终态, 不再尝试)
    """
    for review, apply in [
        (ApprovalReviewStatus.PENDING.value, ApprovalApplyStatus.NONE.value),
        (ApprovalReviewStatus.APPROVED.value, ApprovalApplyStatus.NONE.value),
        (ApprovalReviewStatus.APPROVED.value, ApprovalApplyStatus.APPLIED.value),
        (ApprovalReviewStatus.REJECTED.value, ApprovalApplyStatus.NONE.value),
    ]:
        a = Approval(
            id=1,
            kind="qa",
            payload="{}",
            review_status=review,
            apply_status=apply,
            submitter_id=10,
            created_at=datetime.now(HKT),
        )
        repo = MagicMock()
        repo.get = AsyncMock(return_value=a)
        svc = ApprovalService(repo=repo)

        with pytest.raises(InvalidStateError):
            await svc.retry(1, _user())


async def test_mark_applied_sets_applied_and_applied_at() -> None:
    """mark_applied 写 apply=applied + applied_at=now(). 调 executor 内部用."""
    approved = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=approved)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    result = await svc.mark_applied(1)

    assert result.apply_status == ApprovalApplyStatus.APPLIED.value
    assert result.applied_at is not None


async def test_mark_failed_sets_failed_and_error_msg() -> None:
    """mark_failed 写 apply=failed + error_msg=前 1000 字符. 关键: 不能 silently zero."""
    approved = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10,
        created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=approved)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    long_msg = "x" * 1500
    result = await svc.mark_failed(1, long_msg)

    assert result.apply_status == ApprovalApplyStatus.FAILED.value
    # 截断到 1000 字符 (跟 spec 一致)
    assert result.error_msg is not None
    assert len(result.error_msg) == 1000
    assert result.error_msg == "x" * 1000
    assert result.applied_at is None
