"""SQLAlchemy repo — 真实实现, 跟 ApprovalService 协作.

接口严格跟 src/approvals/service.py 的 ApprovalRepo Protocol 一致.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Approval


class SqlAlchemyApprovalRepo:
    """Approval repo — SQLAlchemy AsyncSession 包装.

    接口 (跟 ApprovalRepo Protocol 1:1):
    - async get(id) -> Approval | None
    - async list(*, review, apply, submitter_id, skip, limit) -> list[Approval]
    - async add(approval) -> None
    - async commit() -> None
    - async refresh(approval) -> None
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> Approval | None:
        return await self._session.get(Approval, id)

    async def list(
        self,
        *,
        review: str | None = None,
        apply: str | None = None,
        submitter_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Approval]:
        stmt = select(Approval)
        if review is not None:
            stmt = stmt.where(Approval.review_status == review)
        if apply is not None:
            stmt = stmt.where(Approval.apply_status == apply)
        if submitter_id is not None:
            stmt = stmt.where(Approval.submitter_id == submitter_id)
        stmt = stmt.order_by(Approval.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, approval: Approval) -> None:
        self._session.add(approval)

    async def commit(self) -> None:
        await self._session.commit()

    async def refresh(self, approval: Approval) -> None:
        await self._session.refresh(approval)
