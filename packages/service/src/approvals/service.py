"""ApprovalService — 5 个方法 (submit/approve/reject/retry/apply).

service 层只跟 Approval model 跟 repo (一个 AsyncSession-like 对象) 打交道, 不 import router/executor.
executor 跟 service 之间的循环依赖避免: executor 直接 import repo 跟 enum, 不调 service.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from ..utils.timezone import HKT
from .models import Approval, ApprovalApplyStatus, ApprovalKind, ApprovalReviewStatus, RejectReason


class ApprovalRepo(Protocol):
    """repo 协议 — service 跟 executor 都用. 真实实现是 SQLAlchemy session 的包装."""

    async def get(self, id: int) -> Approval | None: ...
    async def list(
        self,
        *,
        review: str | None = None,
        apply: str | None = None,
        submitter_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Approval]: ...
    async def add(self, approval: Approval) -> None: ...
    async def commit(self) -> None: ...
    async def refresh(self, approval: Approval) -> None: ...


class ApprovalNotFoundError(Exception):
    """指定 id 不存在"""


class InvalidStateError(Exception):
    """状态机转换非法 (如: 已是 approved 又调 approve)"""


class CurrentUserLike(Protocol):
    """模仿 src.auth 的 CurrentUser, 避免 service 跟 auth 强耦合"""

    id: int
    is_admin: bool


class ApprovalService:
    def __init__(self, repo: ApprovalRepo) -> None:
        self._repo = repo

    async def submit(
        self,
        kind: ApprovalKind,
        payload: dict[str, Any],
        submitter: CurrentUserLike,
    ) -> Approval:
        """新建审核项, review=pending, apply=none. 任何登录用户可调."""
        approval = Approval(
            kind=kind.value,
            payload=json.dumps(payload, ensure_ascii=False),
            review_status=ApprovalReviewStatus.PENDING.value,
            apply_status=ApprovalApplyStatus.NONE.value,
            submitter_id=submitter.id,
            created_at=datetime.now(HKT),
        )
        await self._repo.add(approval)
        await self._repo.commit()
        await self._repo.refresh(approval)
        return approval

    async def approve(self, approval_id: int, reviewer: CurrentUserLike) -> Approval:
        """admin 批准. review: pending → approved, apply 保持 none (BGTask 排队中)."""
        approval = await self._get_or_raise(approval_id)
        if approval.review_status != ApprovalReviewStatus.PENDING.value:
            raise InvalidStateError(f"approval {approval_id} review_status={approval.review_status}, expected pending")
        approval.review_status = ApprovalReviewStatus.APPROVED.value
        approval.reviewer_id = reviewer.id
        approval.reviewed_at = datetime.now(HKT)
        await self._repo.commit()
        return approval

    async def reject(
        self,
        approval_id: int,
        reason: RejectReason,
        note: str | None,
        reviewer: CurrentUserLike,
    ) -> Approval:
        """admin 拒绝. review: pending → rejected (终态), 写 rejection_reason=key + rejection_note."""
        approval = await self._get_or_raise(approval_id)
        if approval.review_status != ApprovalReviewStatus.PENDING.value:
            raise InvalidStateError(f"approval {approval_id} review_status={approval.review_status}, expected pending")
        approval.review_status = ApprovalReviewStatus.REJECTED.value
        approval.rejection_reason = reason.value
        approval.rejection_note = note
        approval.reviewer_id = reviewer.id
        approval.reviewed_at = datetime.now(HKT)
        await self._repo.commit()
        return approval

    async def retry(self, approval_id: int, reviewer: CurrentUserLike) -> Approval:
        """admin 重试. apply: failed → none, review 保持 approved. 限制: 仅 (approved, failed) 可重试."""
        approval = await self._get_or_raise(approval_id)
        if not (
            approval.review_status == ApprovalReviewStatus.APPROVED.value
            and approval.apply_status == ApprovalApplyStatus.FAILED.value
        ):
            raise InvalidStateError(
                f"approval {approval_id} review={approval.review_status} apply={approval.apply_status}, "
                "expected (approved, failed)"
            )
        approval.apply_status = ApprovalApplyStatus.NONE.value
        approval.error_msg = None  # 清掉旧错误
        await self._repo.commit()
        return approval

    async def mark_applied(self, approval_id: int) -> Approval:
        """BGTask 调 — 写 apply=applied + applied_at=now()."""
        approval = await self._get_or_raise(approval_id)
        approval.apply_status = ApprovalApplyStatus.APPLIED.value
        approval.applied_at = datetime.now(HKT)
        await self._repo.commit()
        return approval

    async def mark_failed(self, approval_id: int, error_msg: str) -> Approval:
        """BGTask 调 — 写 apply=failed + error_msg=前 1000 字符. 不吞错误."""
        approval = await self._get_or_raise(approval_id)
        approval.apply_status = ApprovalApplyStatus.FAILED.value
        approval.error_msg = error_msg[:1000]
        await self._repo.commit()
        return approval

    async def _get_or_raise(self, approval_id: int) -> Approval:
        approval = await self._repo.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"approval {approval_id} not found")
        return approval
