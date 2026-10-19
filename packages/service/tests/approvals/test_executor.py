"""executor apply_approval 测试 — 4 kind dispatch + 真行为 (失败捕获)"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.approvals.executor import apply_approval
from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
)
from src.approvals.service import ApprovalService


def _approval(kind: ApprovalKind, payload: dict, apply: str = ApprovalApplyStatus.NONE.value) -> Approval:
    return Approval(
        id=1,
        kind=kind.value,
        payload=json.dumps(payload, ensure_ascii=False),
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=apply,
        submitter_id=10,
        created_at=MagicMock(),
    )


async def test_qa_kind_calls_create_document_by_text() -> None:
    """QA kind: 调 DifyDatasets.createDocumentByText, 同步 Neo4j 可选"""
    a = _approval(ApprovalKind.QA, {"dataset_id": "ds1", "question": "q", "answer": "a"})
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock(return_value={"id": "doc-1"})
        with patch("src.approvals.executor.KgClient") as MockKg:
            MockKg.return_value.batch_upsert_triples = MagicMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()
    # apply_status 应该 = applied (在 mark_applied 之后)
    assert a.apply_status == ApprovalApplyStatus.APPLIED.value
    assert a.applied_at is not None


async def test_qa_with_sync_to_neo4j_also_calls_kg() -> None:
    """QA + sync_to_neo4j=true → 额外调 KgClient.batch_upsert_triples"""
    a = _approval(
        ApprovalKind.QA,
        {"dataset_id": "ds1", "question": "q", "answer": "a", "sync_to_neo4j": True, "tags": ["W21"]},
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock()
        with patch("src.approvals.executor.KgClient") as MockKg:
            MockKg.return_value.batch_upsert_triples = MagicMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()
    MockKg.return_value.batch_upsert_triples.assert_called_once()


async def test_triple_kind_calls_kg_only() -> None:
    """TRIPLE kind: 只调 KgClient.batch_upsert_triples, 不调 Dify"""
    a = _approval(
        ApprovalKind.TRIPLE,
        {
            "rows": [
                {
                    "from_label": "X",
                    "from_key": "k",
                    "from_value": "v",
                    "rel_type": "R",
                    "to_label": "Y",
                    "to_key": "k",
                    "to_value": "v",
                    "properties": {},
                }
            ]
        },
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        with patch("src.approvals.executor.KgClient") as MockKg:
            MockKg.return_value.batch_upsert_triples = MagicMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_not_called()
    MockKg.return_value.batch_upsert_triples.assert_called_once()
    assert a.apply_status == ApprovalApplyStatus.APPLIED.value


async def test_batch_kind_loops_dify_create() -> None:
    """BATCH kind: 循环每行调 Dify, 聚合"""
    a = _approval(
        ApprovalKind.BATCH,
        {
            "dataset_id": "ds1",
            "rows": [
                {"question": "q1", "answer": "a1"},
                {"question": "q2", "answer": "a2"},
            ],
        },
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock()
        await apply_approval(1, svc, repo=repo)

    assert MockDify.createDocumentByText.await_count == 2
    assert a.apply_status == ApprovalApplyStatus.APPLIED.value


async def test_optimize_kind_calls_dify() -> None:
    """OPTIMIZE kind: 调 Dify.createDocumentByText 存改进后回答 (必传 question+improved_answer)"""
    a = _approval(
        ApprovalKind.OPTIMIZE,
        {"dataset_id": "ds1", "question": "原问题", "improved_answer": "改进后回答", "reason": "改了什么"},
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock()
        await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()


async def test_optimize_missing_question_marks_failed() -> None:
    """OPTIMIZE 缺 question 字段 → KeyError → BGTask 捕获 → apply=failed (fail-fast, 符合 no-shim 原则)"""
    a = _approval(ApprovalKind.OPTIMIZE, {"dataset_id": "ds1", "improved_answer": "改进后"})
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        # 即使 Dify 不抛错, executor 内部 KeyError 触发 mark_failed
        MockDify.createDocumentByText = AsyncMock()
        await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_not_called()  # 缺字段根本到不了 Dify
    assert a.apply_status == ApprovalApplyStatus.FAILED.value
    assert a.error_msg is not None
    assert "question" in a.error_msg  # KeyError: 'question' 出现在 error_msg
    assert a.applied_at is None


async def test_apply_exception_marks_failed_with_error_msg() -> None:
    """关键: Dify 抛异常 → 写 apply=failed + error_msg 含原 message, 不让 BGTask 崩"""
    a = _approval(ApprovalKind.QA, {"dataset_id": "ds1", "question": "q", "answer": "a"})
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock(side_effect=RuntimeError("Dify 502: upstream timeout"))
        await apply_approval(1, svc, repo=repo)

    assert a.apply_status == ApprovalApplyStatus.FAILED.value
    assert a.error_msg is not None
    assert "Dify 502" in a.error_msg
    assert a.applied_at is None
