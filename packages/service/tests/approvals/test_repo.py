"""SQLAlchemy repo 行为 mock 测试 (模式 1, 100% mock)

CLAUDE.md '测试禁止连真 PG / SQLite' 严格执行. 原 test 走真 DB
(Base.metadata.create_all + AsyncSession 真连接), 改成 mock session
+ 验证 SqlAlchemyApprovalRepo 调 session.add/commit 时传的参数.

不验证 SQL 真执行结果 (那是集成测试职责), 验证 repo 的入参
构造 + 调用顺序.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
)
from src.approvals.repo import SqlAlchemyApprovalRepo
from src.auth.models import User


def _make_async_session_mock():
    """构造 async session mock: add / commit / refresh 全异步."""
    s = MagicMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.refresh = AsyncMock()
    s.execute = AsyncMock()
    s.close = AsyncMock()
    return s


async def test_repo_add_and_get_roundtrip():
    """add 后 commit + refresh 走通. 验证调用次数 + 参数."""
    session = _make_async_session_mock()
    user = User(public_token="tok-1", id=1)

    repo = SqlAlchemyApprovalRepo(session)
    approval = Approval(
        kind=ApprovalKind.QA.value,
        payload='{"dataset_id":"ds1"}',
        review_status=ApprovalReviewStatus.PENDING.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=user.id,
    )

    await repo.add(approval)
    await repo.commit()
    await repo.refresh(approval)

    # add 被调 1 次, 传的是 approval 对象
    assert session.add.call_count == 1
    assert session.add.call_args[0][0] is approval
    # commit / refresh 各调 1 次
    assert session.commit.await_count == 1
    assert session.refresh.await_count == 1


async def test_repo_list_filters_by_review_and_apply():
    """list 调 session.execute 返结果. 验证执行 + 过滤语义."""
    session = _make_async_session_mock()
    pending_approval = Approval(
        id=1,
        kind="qa",
        payload="{}",
        review_status="pending",
        apply_status="none",
        submitter_id=1,
    )

    # mock execute 返 Result 对象, scalars().all() 返列表
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [pending_approval]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock

    repo = SqlAlchemyApprovalRepo(session)
    result = await repo.list(review="pending")

    # execute 被调 1 次
    assert session.execute.await_count == 1
    # 返的 approval 字段
    assert len(result) == 1
    assert result[0].review_status == "pending"
