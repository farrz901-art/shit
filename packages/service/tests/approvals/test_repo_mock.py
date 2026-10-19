"""approvals/repo.py mock 单元测试 (mode 1, 不连 PG)"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.approvals.models import Approval


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.get.return_value = Approval(id=1, kind="qa", review_status="pending", apply_status="none")
    return session


@pytest.mark.asyncio
async def test_get_returns_approval(mock_session):
    from src.approvals.repo import SqlAlchemyApprovalRepo

    repo = SqlAlchemyApprovalRepo(mock_session)
    result = await repo.get(1)
    assert result is not None
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_none_when_missing():
    session = AsyncMock()
    session.get.return_value = None
    from src.approvals.repo import SqlAlchemyApprovalRepo

    repo = SqlAlchemyApprovalRepo(session)
    result = await repo.get(999)
    assert result is None


@pytest.mark.asyncio
async def test_add_calls_session_add():
    # (2026-07-08) SA session.add 是 sync; 用 MagicMock 替 AsyncMock 避免 _execute_mock_call
    # 返 coroutine 被 GC, 触发 'coroutine was never awaited' RuntimeWarning.
    session = MagicMock()
    from src.approvals.repo import SqlAlchemyApprovalRepo

    repo = SqlAlchemyApprovalRepo(session)
    approval = Approval(id=2, kind="qa", review_status="pending", apply_status="none")
    await repo.add(approval)
    session.add.assert_called_once_with(approval)


@pytest.mark.asyncio
async def test_commit_calls_session_commit():
    session = AsyncMock()
    from src.approvals.repo import SqlAlchemyApprovalRepo

    repo = SqlAlchemyApprovalRepo(session)
    await repo.commit()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_list_filters_by_review():
    session = AsyncMock(spec=AsyncMock)
    # Mock await session.execute(...) → Result → scalars() → all() → []
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    from src.approvals.repo import SqlAlchemyApprovalRepo

    repo = SqlAlchemyApprovalRepo(session)
    result = await repo.list(review="pending")
    assert result == []
