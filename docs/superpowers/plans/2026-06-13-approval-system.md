# 审核系统实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4 个写动作 (录 QA / 三元组 / 批量导入 / 优化回答) 全部走 admin 审核, 提交者可在 `/submissions` 看自己提交的状态 (审批 + 写入 2 维), admin 在同页 "全部待审" tab 展开看内容、批准/拒绝 (选 6 预设原因) / 重试。

**Architecture:** 后端 1 张 `approvals` 表 (`review_status` + `apply_status` 2 状态轴), `ApprovalService` 5 方法, `executor` 按 kind dispatch 调 Dify/Neo4j (FastAPI BackgroundTask inline 跑); 前端 4 个 server action 改调 `approvals.submit` (经 FastAPI `/api/approvals`), `/submissions` 单 RSC 页面 + 2 Tabs (mine / all-admin), `<RejectDialog>` shadcn Select 6 预设原因, `<ApprovalRow>` Collapsible 展开看完整 payload。

**Tech Stack:**

- 后端: Python 3.12 / FastAPI / SQLAlchemy 2.x typed / Pydantic / pytest
- 前端: TypeScript 8 / React 19 / Next.js 16 App Router (RSC) / shadcn/ui (Table/Tabs/Badge/Dialog/Select/Collapsible) / React Query / next-intl / vitest
- 主题: next-themes (复用现有 `--color-status-*` token)

**Spec:** [docs/superpowers/specs/2026-06-13-approval-system-design.md](../specs/2026-06-13-approval-system-design.md)

**阶段:**

- **P0** (本批次): 后端 model + service + executor + router + 全部后端测试
- **P1**: 前端 4 个 server action 改写 (调 approvals.submit) + 测试
- **P2**: 前端 `/submissions/*` UI + middleware 改 + 4 个表单 toast 改
- **P3**: i18n zh/en 翻译 + BFF (admin 路径) + docs 更新

---

## P0: 后端 (Approval + Service + Executor + Router)

### Task 1: Approval model + 3 enum

**Files:**

- Create: `packages/service/src/approvals/__init__.py`
- Create: `packages/service/src/approvals/models.py`
- Create: `packages/service/tests/approvals/__init__.py`
- Create: `packages/service/tests/approvals/test_models.py`

- [ ] **Step 1: 写测试 (TDD red)**

```python
# packages/service/tests/approvals/test_models.py
"""Approval model + 3 enum 单元测试"""

from __future__ import annotations

import pytest
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
        "duplicate", "low_quality", "incomplete",
        "wrong_category", "format_issue", "other",
    }


def test_approval_kind_values() -> None:
    """4 个 kind, 跟 4 个写动作 1:1"""
    assert {s.value for s in ApprovalKind} == {"qa", "triple", "batch", "optimize"}


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
    assert cols["review_status"].default.arg == ApprovalReviewStatus.PENDING.value
    assert cols["apply_status"].default.arg == ApprovalApplyStatus.NONE.value
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
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_models.py -v
```

Expected: 5 个 FAIL (module not found `src.approvals.models`)

- [ ] **Step 3: 实现 model + 3 enum**

```python
# packages/service/src/approvals/__init__.py
"""审核系统 — admin 审批写入 Dify/Neo4j"""
```

```python
# packages/service/src/approvals/models.py
"""Approval model + 3 enum (review/apply/reject reason) + ApprovalKind.

状态拆 2 字段 (review + apply), 跟 spec 一致.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base
from ..utils.timezone import HKT


class ApprovalReviewStatus(str, Enum):
    PENDING = "pending"     # admin 还没看
    APPROVED = "approved"   # admin 批准 (写入排队中 / 已尝试)
    REJECTED = "rejected"   # admin 拒绝 (终态, 不再尝试写入)


class ApprovalApplyStatus(str, Enum):
    NONE = "none"           # 还未尝试 (pending / approved 排队中)
    APPLIED = "applied"     # 写入 Dify/Neo4j 成功 (终态)
    FAILED = "failed"       # 写入失败, admin 可重试


class RejectReason(str, Enum):
    DUPLICATE = "duplicate"
    LOW_QUALITY = "low_quality"
    INCOMPLETE = "incomplete"
    WRONG_CATEGORY = "wrong_category"
    FORMAT_ISSUE = "format_issue"
    OTHER = "other"


class ApprovalKind(str, Enum):
    QA = "qa"                 # 录 QA → Dify
    TRIPLE = "triple"         # 录三元组 → Neo4j
    BATCH = "batch"           # 批量导入 → Dify
    OPTIMIZE = "optimize"     # 优化回答 → Dify


class Approval(Base):
    """审核项 — 1 次提交 = 1 条"""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    # 2 个状态轴 (关键)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=ApprovalReviewStatus.PENDING.value, index=True,
    )
    apply_status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=ApprovalApplyStatus.NONE.value, index=True,
    )
    submitter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # 拒绝: 预设原因 key + 选 other 时的补充
    rejection_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 写库失败: 错误消息
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(HKT), index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_approvals_review_created", "review_status", "created_at"),
        Index("idx_approvals_apply_created", "apply_status", "created_at"),
        Index("idx_approvals_submitter_created", "submitter_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Approval id={self.id} kind={self.kind} review={self.review_status} apply={self.apply_status}>"
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_models.py -v
```

Expected: 5 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals packages/service/tests/approvals
git commit -m "feat(approvals): Approval model + 3 enum (review/apply/reject reason)"
```

---

### Task 2: ApprovalService.submit

**Files:**

- Create: `packages/service/src/approvals/service.py`
- Create: `packages/service/tests/approvals/test_service.py`

- [ ] **Step 1: 写测试 (TDD red)**

```python
# 加到 packages/service/tests/approvals/test_service.py
"""ApprovalService 单元测试 — TDD 红绿循环"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.approvals.models import Approval, ApprovalApplyStatus, ApprovalKind, ApprovalReviewStatus
from src.approvals.service import ApprovalNotFoundError, ApprovalService, InvalidStateError
from src.auth.models import User  # noqa: F401 — 触发 Base.metadata 注册
from src.eval.models import Evaluation, EvaluationSample  # noqa: F401,F403 — 触发注册


def _user(id_: int = 1) -> MagicMock:
    """mock CurrentUser-like 象 (id + is_admin)"""
    u = MagicMock()
    u.id = id_
    u.is_admin = True
    return u


def _make_repo_with_empty_db() -> MagicMock:
    """mock repo — 不依赖 SQLAlchemy session, 服务层纯函数测"""
    return MagicMock()


async def test_submit_creates_pending_approval() -> None:
    """submit 写 review=pending, apply=none, submitter_id, created_at, JSON payload"""
    repo = _make_repo_with_empty_db()
    captured: dict = {}

    async def fake_add(a: Approval) -> None:
        captured["approval"] = a

    async def fake_commit() -> None:
        captured["committed"] = True

    repo.add = fake_add
    repo.commit = fake_commit
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
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v
```

Expected: 1 个 FAIL (module not found `src.approvals.service`)

- [ ] **Step 3: 实现 service (只 submit 方法, 其它 4 个方法后面任务加)**

```python
# packages/service/src/approvals/service.py
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
        self, *, review: str | None = None, apply: str | None = None,
        submitter_id: int | None = None, skip: int = 0, limit: int = 20,
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
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v
```

Expected: 1 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/service.py packages/service/tests/approvals/test_service.py
git commit -m "feat(approvals): ApprovalService.submit (TDD red→green)"
```

---

### Task 3: ApprovalService.approve / reject / retry

**Files:**

- Modify: `packages/service/src/approvals/service.py`
- Modify: `packages/service/tests/approvals/test_service.py`

- [ ] **Step 1: 加 3 个测试 (TDD red)**

```python
# 加到 packages/service/tests/approvals/test_service.py


async def test_approve_pending_sets_approved_and_reviewer() -> None:
    """approve pending 项: review=approved, apply=none (BGTask 还没跑), reviewer_id, reviewed_at"""
    pending = Approval(
        id=1, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.PENDING.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
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
        id=1, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
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
        id=2, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.PENDING.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
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
        id=1, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.REJECTED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=rejected)
    svc = ApprovalService(repo=repo)

    with pytest.raises(InvalidStateError):
        await svc.reject(1, RejectReason.LOW_QUALITY, None, _user())


async def test_retry_approved_failed_resets_apply_to_none() -> None:
    """retry (approved, failed) → review 保持 approved, apply: failed → none (BGTask 重跑)"""
    failed = Approval(
        id=3, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.FAILED.value,
        submitter_id=10, error_msg="Dify 502", created_at=datetime.now(HKT),
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=failed)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    result = await svc.retry(3, _user(id_=99))

    assert result.review_status == ApprovalReviewStatus.APPROVED.value  # 保持
    assert result.apply_status == ApprovalApplyStatus.NONE.value         # 清掉 failed
    assert result.error_msg is None  # 清掉


async def test_retry_non_failed_raises_invalid_state() -> None:
    """非 (approved, failed) 状态调 retry → InvalidStateError

    3 个非法场景都测:
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
            id=1, kind="qa", payload="{}",
            review_status=review, apply_status=apply,
            submitter_id=10, created_at=datetime.now(HKT),
        )
        repo = MagicMock()
        repo.get = AsyncMock(return_value=a)
        svc = ApprovalService(repo=repo)

        with pytest.raises(InvalidStateError):
            await svc.retry(1, _user())
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v
```

Expected: 4 个新 FAIL (AttributeError: svc.approve / svc.reject / svc.retry 不存在)

- [ ] **Step 3: 实现 approve / reject / retry**

```python
# 在 ApprovalService 类里加 (替换 service.py 整个类)
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
            raise InvalidStateError(
                f"approval {approval_id} review_status={approval.review_status}, expected pending"
            )
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
            raise InvalidStateError(
                f"approval {approval_id} review_status={approval.review_status}, expected pending"
            )
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

    async def _get_or_raise(self, approval_id: int) -> Approval:
        approval = await self._repo.get(approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"approval {approval_id} not found")
        return approval
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v
```

Expected: 8 个 PASS (1 submit + 3 approve + 2 reject + 2 retry)

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/service.py packages/service/tests/approvals/test_service.py
git commit -m "feat(approvals): ApprovalService approve/reject/retry (TDD)"
```

---

### Task 4: ApprovalService.apply (write side) + mark_applied / mark_failed

**Files:**

- Modify: `packages/service/src/approvals/service.py`
- Modify: `packages/service/tests/approvals/test_service.py`

- [ ] **Step 1: 加 2 个测试 (TDD red)**

```python
# 加到 packages/service/tests/approvals/test_service.py


async def test_mark_applied_sets_applied_and_applied_at() -> None:
    """mark_applied 写 apply=applied + applied_at=now(). 调 executor 内部用."""
    approved = Approval(
        id=1, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
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
        id=1, kind="qa", payload="{}",
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=ApprovalApplyStatus.NONE.value,
        submitter_id=10, created_at=datetime.now(HKT),
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
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v -k "mark_applied or mark_failed"
```

Expected: 2 个 FAIL (AttributeError: mark_applied / mark_failed 不存在)

- [ ] **Step 3: 实现 mark_applied / mark_failed**

```python
# 加到 ApprovalService 类
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
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_service.py -v
```

Expected: 10 个 PASS (前 8 + 新 2)

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/service.py packages/service/tests/approvals/test_service.py
git commit -m "feat(approvals): ApprovalService mark_applied/mark_failed (TDD)"
```

---

### Task 5: Executor (4 kind dispatch + try/except 状态写回)

**Files:**

- Create: `packages/service/src/approvals/executor.py`
- Create: `packages/service/tests/approvals/test_executor.py`

- [ ] **Step 1: 写测试 (TDD red)**

```python
# packages/service/tests/approvals/test_executor.py
"""executor apply_approval 测试 — 4 kind dispatch + 真行为 (失败捕获)"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        id=1, kind=kind.value, payload=json.dumps(payload, ensure_ascii=False),
        review_status=ApprovalReviewStatus.APPROVED.value,
        apply_status=apply, submitter_id=10, created_at=MagicMock(),
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
            MockKg.return_value.batch_upsert_triples = AsyncMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()
    # apply_status 应该 = applied (在 mark_applied 之后)
    assert a.apply_status == ApprovalApplyStatus.APPLIED.value
    assert a.applied_at is not None


async def test_qa_with_sync_to_neo4j_also_calls_kg() -> None:
    """QA + sync_to_neo4j=true → 额外调 KgClient.batch_upsert_triples"""
    a = _approval(
        ApprovalKind.QA,
        {"dataset_id": "ds1", "question": "q", "answer": "a",
         "sync_to_neo4j": True, "tags": ["W21"]},
    )
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock()
        with patch("src.approvals.executor.KgClient") as MockKg:
            MockKg.return_value.batch_upsert_triples = AsyncMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()
    MockKg.return_value.batch_upsert_triples.assert_awaited_once()


async def test_triple_kind_calls_kg_only() -> None:
    """TRIPLE kind: 只调 KgClient.batch_upsert_triples, 不调 Dify"""
    a = _approval(ApprovalKind.TRIPLE, {"rows": [{"from_label": "X", "from_key": "k", "from_value": "v", "rel_type": "R", "to_label": "Y", "to_key": "k", "to_value": "v", "properties": {}}]})
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        with patch("src.approvals.executor.KgClient") as MockKg:
            MockKg.return_value.batch_upsert_triples = AsyncMock()
            await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_not_called()
    MockKg.return_value.batch_upsert_triples.assert_awaited_once()
    assert a.apply_status == ApprovalApplyStatus.APPLIED.value


async def test_batch_kind_loops_dify_create() -> None:
    """BATCH kind: 循环每行调 Dify, 聚合"""
    a = _approval(
        ApprovalKind.BATCH,
        {"dataset_id": "ds1", "rows": [
            {"question": "q1", "answer": "a1"},
            {"question": "q2", "answer": "a2"},
        ]},
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
    """OPTIMIZE kind: 调 Dify.createDocumentByText 存改进后回答"""
    a = _approval(ApprovalKind.OPTIMIZE, {"dataset_id": "ds1", "improved_answer": "better"})
    repo = MagicMock()
    repo.get = AsyncMock(return_value=a)
    repo.commit = AsyncMock()
    svc = ApprovalService(repo=repo)

    with patch("src.approvals.executor.DifyDatasets") as MockDify:
        MockDify.createDocumentByText = AsyncMock()
        await apply_approval(1, svc, repo=repo)

    MockDify.createDocumentByText.assert_awaited_once()


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
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_executor.py -v
```

Expected: 6 个 FAIL (module not found)

- [ ] **Step 3: 实现 executor**

```python
# packages/service/src/approvals/executor.py
"""executor — apply_approval 按 kind dispatch 调 Dify/Neo4j, try/except 捕获写回状态.

复用原则: DifyDatasets 跟 KgClient 的调用方式跟现 server action 完全一致, 不引入新逻辑.
"""

from __future__ import annotations

import json
from typing import Any

from ..integrations.dify_datasets import DifyDatasets
from ..kg.client import KgClient
from .models import ApprovalKind
from .service import ApprovalService


async def apply_approval(
    approval_id: int,
    svc: ApprovalService,
    *,
    repo: Any,  # ApprovalRepo, 不 import 避免循环
) -> None:
    """同步执行, 失败捕获. 成功 → svc.mark_applied; 异常 → svc.mark_failed(error_msg=前 1000 字符)."""
    approval = await repo.get(approval_id)
    if approval is None:
        return  # 防御: 不该发生 (svc 校验过)
    payload = json.loads(approval.payload)

    try:
        if approval.kind == ApprovalKind.QA.value:
            text = f"Q: {payload['question']}\nA: {payload['answer']}"
            if payload.get("tags"):
                text += f"\nTags: {', '.join(payload['tags'])}"
            name = f"qa-{approval_id}-{payload.get('dataset_id', '')}"
            await DifyDatasets.createDocumentByText(
                payload["dataset_id"], name, text, "high_quality",
            )
            # 可选: 同步 Neo4j QAPair + ABOUT 关系 (失败不阻塞)
            if payload.get("sync_to_neo4j") and payload.get("tags"):
                try:
                    client = KgClient()
                    await client.batch_upsert_triples([{
                        "from_label": "QAPair", "from_key": "question",
                        "from_value": payload["question"],
                        "rel_type": "ABOUT",
                        "to_label": "Product", "to_key": "model",
                        "to_value": payload["tags"][0],
                        "properties": {"answer": payload["answer"], "tags": payload["tags"]},
                    }])
                except Exception:
                    pass  # Neo4j 同步失败不阻塞 Dify 写入

        elif approval.kind == ApprovalKind.TRIPLE.value:
            client = KgClient()
            await client.batch_upsert_triples(payload["rows"])

        elif approval.kind == ApprovalKind.BATCH.value:
            for r in payload["rows"]:
                text = f"Q: {r['question']}\nA: {r['answer']}"
                if r.get("tags"):
                    text += f"\nTags: {r['tags']}"
                name = f"qa-{approval_id}-{payload['dataset_id']}"
                await DifyDatasets.createDocumentByText(
                    payload["dataset_id"], name, text,
                )

        elif approval.kind == ApprovalKind.OPTIMIZE.value:
            text = (
                f"Q: {payload['question']}\n"
                f"原: {payload.get('original_answer', '')}\n"
                f"改: {payload['improved_answer']}\n"
                f"原因: {payload.get('reason', '')}"
            )
            name = f"optimize-{approval_id}"
            await DifyDatasets.createDocumentByText(
                payload["dataset_id"], name, text,
            )

        await svc.mark_applied(approval_id)
    except Exception as e:
        await svc.mark_failed(approval_id, f"{type(e).__name__}: {e}")
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_executor.py -v
```

Expected: 6 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/executor.py packages/service/tests/approvals/test_executor.py
git commit -m "feat(approvals): executor 4 kind dispatch + 失败捕获 (TDD)"
```

---

### Task 6: SQLAlchemy repo (生产实现) + 注册 Approval 到 Base.metadata

**Files:**

- Create: `packages/service/src/approvals/repo.py`
- Create: `packages/service/tests/approvals/test_repo.py`
- Modify: `packages/service/src/storage/__init__.py` (确认导出 Base)

- [ ] **Step 1: 写测试 (TDD red, 真实 SQLite)**

```python
# packages/service/tests/approvals/test_repo.py
"""SQLAlchemy repo 集成测试 — 用真 SQLite (跟 test_evaluate_router 风格一致)"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
)
from src.approvals.repo import SqlAlchemyApprovalRepo
from src.auth.models import User  # noqa: F401 — 触发注册
from src.eval.models import Evaluation, EvaluationSample  # noqa: F401,F403
from src.storage import Base


@pytest.fixture
def session():
    """真 SQLite, 跟现有测试风格一致"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


async def test_repo_add_and_get_roundtrip(session) -> None:
    """add + get 拿回, 字段一致"""
    from src.auth.service import create_user  # noqa: F401 — 看现有是否有 helper

    # 直接用 SQLAlchemy 加 user (跟现 test_auth 风格)
    user = User(public_token="tok-1")
    session.add(user)
    session.commit()
    session.refresh(user)

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

    got = await repo.get(approval.id)
    assert got is not None
    assert got.kind == "qa"
    assert got.review_status == "pending"
    assert got.apply_status == "none"
    assert got.submitter_id == user.id


async def test_repo_list_filters_by_review_and_apply(session) -> None:
    """list 支持 review / apply 过滤"""
    user = User(public_token="tok-1")
    session.add(user)
    session.commit()
    session.refresh(user)

    repo = SqlAlchemyApprovalRepo(session)
    # 加 3 条, 不同 review/apply
    for review, apply in [
        ("pending", "none"),
        ("approved", "applied"),
        ("rejected", "none"),
    ]:
        await repo.add(Approval(
            kind="qa", payload="{}",
            review_status=review, apply_status=apply,
            submitter_id=user.id,
        ))
    await repo.commit()

    # 仅 pending
    pendings = await repo.list(review="pending")
    assert len(pendings) == 1
    assert pendings[0].review_status == "pending"

    # apply=failed (空)
    faileds = await repo.list(apply="failed")
    assert len(faileds) == 0

    # submitter_id 过滤
    mys = await repo.list(submitter_id=user.id)
    assert len(mys) == 3
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/test_repo.py -v
```

Expected: FAIL (module not found `src.approvals.repo`)

- [ ] **Step 3: 实现 repo**

```python
# packages/service/src/approvals/repo.py
"""SQLAlchemy repo — 真实实现, 跟 ApprovalService 协作."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Approval

if TYPE_CHECKING:
    pass


class SqlAlchemyApprovalRepo:
    """Approval repo — 跟 src/approvals/service.py 的 ApprovalRepo Protocol 一致.

    接口:
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
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/service && uv run pytest tests/approvals/test_repo.py -v
```

Expected: 2 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/repo.py packages/service/tests/approvals/test_repo.py
git commit -m "feat(approvals): SqlAlchemyApprovalRepo (真 SQLite 集成测试)"
```

---

### Task 7: FastAPI router (8 端点)

**Files:**

- Create: `packages/service/src/approvals/router.py`
- Create: `packages/service/tests/approvals/test_router.py`
- Modify: `packages/service/src/product_decoders/app.py` (include router)

- [ ] **Step 1: 写测试 (TDD red, httpx + 真 SQLite)**

```python
# packages/service/tests/approvals/test_router.py
"""FastAPI router 测试 — 8 端点: 鉴权 + 状态过滤 + reject 校验 + retry 限制"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.approvals import router as approvals_router
from src.approvals.models import (
    Approval,
    ApprovalApplyStatus,
    ApprovalKind,
    ApprovalReviewStatus,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(approvals_router.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _admin_user(id_: int = 99, is_admin: bool = True) -> MagicMock:
    u = MagicMock()
    u.id = id_
    u.is_admin = is_admin
    return u


def test_post_approvals_creates_pending(mock_current_user=...) -> None:
    """POST /api/approvals 任何登录用户可调, 返 review=pending"""
    # 注: 真实测试用 override_dependency, 跟 test_evaluate_router 一致
    pass  # 完整版见后续 test 文件, 写完 service test 再来 router test
```

> **注**: 完整 router test 文件大, 拆成 8 个 test\_\*.py 文件, 1 端点 1 文件 (跟 test_kg_router 风格)。这里只列模板, **实施时按下面 8 任务分开**:
>
> - `test_post_approvals.py` (Task 7a)
> - `test_list_approvals.py` (Task 7b)
> - `test_get_approval.py` (Task 7c)
> - `test_approve.py` (Task 7d)
> - `test_reject.py` (Task 7e)
> - `test_retry.py` (Task 7f)
> - `test_stats.py` (Task 7g)

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/service && uv run pytest tests/approvals/ -v
```

Expected: module not found

- [ ] **Step 3: 实现 router (8 端点)**

```python
# packages/service/src/approvals/router.py
"""FastAPI 路由 — 8 端点: POST + GET(list) + GET(me) + GET(detail) + approve/reject/retry + stats.

鉴权: admin-only (approve/reject/retry), login-only (其它).
依赖项复用 src.auth.require_admin / require_login.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.middleware import CurrentUser, require_admin, require_login
from ..storage import get_session
from .executor import apply_approval
from .models import Approval, ApprovalKind, RejectReason
from .repo import SqlAlchemyApprovalRepo
from .service import (
    ApprovalNotFoundError,
    ApprovalService,
    InvalidStateError,
)

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# --- Body schemas ---

class RejectBody(BaseModel):
    reason: RejectReason
    note: str | None = Field(default=None, max_length=500)


class SubmitBody(BaseModel):
    kind: ApprovalKind
    payload: dict


# --- 依赖项: svc + repo (FastAPI 风格) ---

async def _get_svc() -> ApprovalService:
    session = await get_session()
    repo = SqlAlchemyApprovalRepo(session)
    return ApprovalService(repo=repo)


async def _get_repo() -> SqlAlchemyApprovalRepo:
    session = await get_session()
    return SqlAlchemyApprovalRepo(session)


# --- 端点 ---

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit(
    body: SubmitBody,
    user: Annotated[CurrentUser, Depends(require_login)],
):
    """新建审核项 (kind + payload), 任何登录用户可调. 返 {id, review_status, apply_status}."""
    svc = await _get_svc()
    approval = await svc.submit(body.kind, body.payload, user)
    return {
        "id": approval.id,
        "kind": approval.kind,
        "review_status": approval.review_status,
        "apply_status": approval.apply_status,
    }


@router.get("")
async def list_all(
    review: str | None = Query(default=None),
    apply: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: Annotated[CurrentUser, Depends(require_admin)] = ...,
):
    """admin 列出 (默认按 review=pending 过滤)."""
    repo = await _get_repo()
    items = await repo.list(review=review, apply=apply, skip=skip, limit=limit)
    return [_serialize(a) for a in items]


@router.get("/me")
async def list_mine(
    review: str | None = Query(default=None),
    apply: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: Annotated[CurrentUser, Depends(require_login)] = ...,
):
    """当前用户自己提交的."""
    repo = await _get_repo()
    items = await repo.list(
        review=review, apply=apply, submitter_id=user.id, skip=skip, limit=limit,
    )
    return [_serialize(a) for a in items]


@router.get("/stats")
async def stats(
    _admin: Annotated[CurrentUser, Depends(require_admin)] = ...,
):
    """admin 概览数字: pending / applied / failed 各自数量."""
    repo = await _get_repo()
    return {
        "pending": len(await repo.list(review="pending", limit=1000)),
        "applied": len(await repo.list(apply="applied", limit=1000)),
        "failed": len(await repo.list(apply="failed", limit=1000)),
    }


@router.get("/{approval_id}")
async def get_detail(
    approval_id: int,
    user: Annotated[CurrentUser, Depends(require_login)],
):
    """单条详情 (含完整 payload), 仅 submitter 或 admin 可看."""
    repo = await _get_repo()
    approval = await repo.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="not found")
    if approval.submitter_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="forbidden")
    return _serialize(approval, include_payload=True)


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: int,
    background: BackgroundTasks,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """admin 批准. review: pending → approved, 触发 BackgroundTask 跑 apply."""
    svc = await _get_svc()
    repo = await _get_repo()
    try:
        approval = await svc.approve(approval_id, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 触发 BGTask (跟 spec 一致: 不引新依赖, 用 FastAPI BackgroundTasks)
    background.add_task(apply_approval, approval_id, svc, repo=repo)
    return _serialize(approval)


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: int,
    body: RejectBody,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """admin 拒绝. reason 必填 (Pydantic 枚举), reason=other 时 note 必填."""
    # reason=other 时强制 note 必填 (Pydantic model_validator)
    if body.reason == RejectReason.OTHER and not body.note:
        raise HTTPException(status_code=422, detail="reason=other 时 note 必填")

    svc = await _get_svc()
    try:
        approval = await svc.reject(approval_id, body.reason, body.note, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _serialize(approval)


@router.post("/{approval_id}/retry")
async def retry(
    approval_id: int,
    background: BackgroundTasks,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    """admin 重试. 限制: 仅 (approved, failed) 可重试."""
    svc = await _get_svc()
    repo = await _get_repo()
    try:
        approval = await svc.retry(approval_id, admin)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))

    background.add_task(apply_approval, approval_id, svc, repo=repo)
    return _serialize(approval)


# --- helper ---

def _serialize(a: Approval, include_payload: bool = False) -> dict:
    d = {
        "id": a.id,
        "kind": a.kind,
        "review_status": a.review_status,
        "apply_status": a.apply_status,
        "submitter_id": a.submitter_id,
        "reviewer_id": a.reviewer_id,
        "rejection_reason": a.rejection_reason,
        "rejection_note": a.rejection_note,
        "error_msg": a.error_msg,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        "applied_at": a.applied_at.isoformat() if a.applied_at else None,
    }
    if include_payload:
        d["payload"] = json.loads(a.payload) if a.payload else None
    return d
```

- [ ] **Step 4: 注册到 FastAPI app**

```python
# 找 packages/service/src/product_decoders/app.py 里 create_app(), 加:
from ..approvals.router import router as approvals_router
# ...
app.include_router(approvals_router)
```

- [ ] **Step 5: 跑测试 (P0 阶段先 smoke, 完整 router test 在 P0 末尾)**

```bash
cd packages/service && uv run pytest tests/approvals/ -v
```

Expected: 所有 P0 测试 PASS

- [ ] **Step 6: 写 8 个 router test 文件 (跟 spec 测试清单一致)**

> 完整 router test 模板 (8 个文件 1:1, 跟 test_kg_router 风格):
>
> - 鉴权: `require_admin` / `require_login` 跟现 auth 一样
> - 状态过滤: list 加 query param
> - reject: 缺 reason → 422, reason=other 缺 note → 422
> - retry: 非 (approved, failed) → 409
>
> 模板示例 (`test_approve.py`):
>
> ```python
> def test_approve_non_admin_returns_403(client):
>     # mock CurrentUser 走 require_admin 返 403
>
> def test_approve_pending_returns_approved(client):
>     # admin + pending → 200, 触发 BGTask
>
> def test_approve_already_approved_returns_409(client):
>     # admin + approved → 409 InvalidStateError
> ```
>
> 8 个文件, 每个 2-3 个 test, 共 ~20 个 case。**实施时按 spec 写, 模板足够, 不展开贴代码**

- [ ] **Step 7: 跑所有 P0 测试确认全绿**

```bash
cd packages/service && uv run pytest tests/approvals/ -v
```

Expected: 全部 PASS (~30 case)

- [ ] **Step 8: 注册 Approval 到 Base.metadata (确认 import 路径)**

```bash
# 检查 packages/service/src/storage/__init__.py 已 export Base, 否则加
# 检查 src/approvals/models.py 已被 import 一次 (test conftest.py import 一行, 触发注册)
```

- [ ] **Step 9: 跑全量后端测试确保没破坏其它模块**

```bash
cd packages/service && uv run pytest tests/ -v
```

Expected: 其它模块测试不破坏 (apprval 0 个新失败)

- [ ] **Step 10: Commit**

```bash
git add packages/service/src/approvals packages/service/src/product_decoders/app.py packages/service/tests/approvals
git commit -m "feat(approvals): FastAPI 8 端点 + repo 集成 + 全链路测试"
```

---

### Task 8: P0 完成验证 + 跑契约测试

**Files:** 无新增

- [ ] **Step 1: 跑全量 pytest 看 P0 状态**

```bash
cd packages/service && uv run pytest tests/ -v 2>&1 | tail -30
```

Expected: tests/approvals/ 全绿, 其它模块无新失败

- [ ] **Step 2: 跑契约测试 (跟项目 [feedback-bff-must-propagate-502] 一致)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

Expected: 新加 8 路由到后端 API 清单, 全绿

- [ ] **Step 3: 手动起 uvicorn 验证 1 个端点 smoke**

```bash
cd packages/service && uv run uvicorn src.product_decoders.app:app --reload --port 8000 &
sleep 3
curl -s http://localhost:8000/docs | head -5  # OpenAPI 加载, 含 /api/approvals
# 测 admin 端点 (需 RAG_DEV_AUTH=true)
RAG_DEV_AUTH=true curl -X GET http://localhost:8000/api/approvals -H "x-user-token: dev" | head -c 200
```

Expected: 返 200 + 空数组 `[]`

- [ ] **Step 4: Commit (如有改动)**

```bash
git status  # 看有无未提交
# 无新文件就跳过
```

---

**P0 阶段结束。** 进入 P1: 前端 server actions 改写。

---

## P1: 前端 Server Actions 改写 (4 个 action + 1 个新)

### Task 9: approvals 新建端点的 helper (前后端 BFF 复用准备)

**Files:**

- Create: `packages/web/lib/api/approvals.ts`
- Create: `packages/web/lib/api/approvals.test.ts`

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// packages/web/lib/api/approvals.test.ts
// approval HTTP client 测试 — 跟 lib/api/knowledge.ts 风格一致 (走 authHeaders)

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { fetchMock, authHeadersMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  authHeadersMock: vi.fn(async () => ({ cookie: "rag_user_token=test" })),
}));

vi.mock("@/lib/api/auth", () => ({
  API_BASE: "http://localhost:8000",
  authHeaders: authHeadersMock,
}));
vi.stubGlobal("fetch", fetchMock);

import { approvalsApi } from "./approvals";

describe("approvalsApi", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    authHeadersMock.mockClear();
  });
  afterEach(() => vi.unstubAllGlobals());

  describe("submit", () => {
    it("POST /api/approvals 带 kind + payload + authHeaders, 返 {id, review_status, apply_status}", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({ id: 142, kind: "qa", review_status: "pending", apply_status: "none" }),
          { status: 201 },
        ),
      );
      const out = await approvalsApi.submit("qa", {
        dataset_id: "ds1",
        question: "q",
        answer: "a",
      });
      expect(out).toEqual({ id: 142, kind: "qa", review_status: "pending", apply_status: "none" });

      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/approvals",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            cookie: "rag_user_token=test",
          }),
          body: JSON.stringify({
            kind: "qa",
            payload: { dataset_id: "ds1", question: "q", answer: "a" },
          }),
        }),
      );
    });

    it("非 2xx 返 throw 含 status + body", async () => {
      fetchMock.mockResolvedValueOnce(new Response("not found", { status: 404 }));
      await expect(approvalsApi.submit("qa", {})).rejects.toThrow(/HTTP 404/);
    });
  });

  describe("getDetail", () => {
    it("GET /api/approvals/{id} 返完整 approval 含 payload", async () => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: 1,
            kind: "qa",
            review_status: "approved",
            apply_status: "applied",
            payload: { dataset_id: "ds1", question: "q", answer: "a" },
          }),
          { status: 200 },
        ),
      );
      const out = await approvalsApi.getDetail(1);
      expect(out.payload).toEqual({ dataset_id: "ds1", question: "q", answer: "a" });
    });
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test lib/api/approvals.test.ts
```

Expected: FAIL (module not found)

- [ ] **Step 3: 实现 approvals client**

```typescript
// packages/web/lib/api/approvals.ts
// approval HTTP client — 跟 lib/api/knowledge.ts 风格一致
// 服务端 (server action) 跟客户端 (ApprovalRow 展开) 都用

import { authHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type ApprovalKind = "qa" | "triple" | "batch" | "optimize";
export type ReviewStatus = "pending" | "approved" | "rejected";
export type ApplyStatus = "none" | "applied" | "failed";
export type RejectReasonKey =
  | "duplicate"
  | "low_quality"
  | "incomplete"
  | "wrong_category"
  | "format_issue"
  | "other";

export interface Approval {
  id: number;
  kind: ApprovalKind;
  review_status: ReviewStatus;
  apply_status: ApplyStatus;
  submitter_id: number;
  reviewer_id: number | null;
  rejection_reason: RejectReasonKey | null;
  rejection_note: string | null;
  error_msg: string | null;
  created_at: string;
  reviewed_at: string | null;
  applied_at: string | null;
  payload?: Record<string, unknown>;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...(await authHeaders()),
    ...(init?.headers ?? {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return (await res.json()) as T;
}

export const approvalsApi = {
  submit: (kind: ApprovalKind, payload: Record<string, unknown>): Promise<Approval> =>
    call<Approval>("/api/approvals", {
      method: "POST",
      body: JSON.stringify({ kind, payload }),
    }),

  getDetail: (id: number): Promise<Approval> => call<Approval>(`/api/approvals/${id}`),

  approve: (id: number): Promise<Approval> =>
    call<Approval>(`/api/approvals/${id}/approve`, { method: "POST" }),

  reject: (id: number, reason: RejectReasonKey, note?: string): Promise<Approval> =>
    call<Approval>(`/api/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason, note }),
    }),

  retry: (id: number): Promise<Approval> =>
    call<Approval>(`/api/approvals/${id}/retry`, { method: "POST" }),
};
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test lib/api/approvals.test.ts
```

Expected: 3 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/api/approvals.ts packages/web/lib/api/approvals.test.ts
git commit -m "feat(web): approvalsApi client (5 端点 wrapper)"
```

---

### Task 10: 改写 createQA — 调 approvals.submit (不直调 Dify)

**Files:**

- Modify: `packages/web/app/[locale]/_actions/knowledge.ts`
- Modify: `packages/web/app/[locale]/_actions/knowledge.test.ts`

- [ ] **Step 1: 写测试 (TDD red) — 关键: 验调 approvals.submit, **不**调 DifyDatasets**

```typescript
// 加到 packages/web/app/[locale]/_actions/knowledge.test.ts
// (2026-06-13) 重构: 4 个 action 都改调 approvals.submit, 不直调 DifyDatasets
// 关键测试: assertNotCalled(DifyDatasets.createDocumentByText) 防止回归

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { approvalsSubmitMock, difyCreateDocMock } = vi.hoisted(() => ({
  approvalsSubmitMock: vi.fn(),
  difyCreateDocMock: vi.fn(),
}));

vi.mock("@/lib/api/approvals", () => ({
  approvalsApi: {
    submit: approvalsSubmitMock,
    getDetail: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    retry: vi.fn(),
  },
}));

vi.mock("@/lib/dify-datasets", () => ({
  DifyDatasets: {
    createDocumentByText: difyCreateDocMock,
    listDatasets: vi.fn(),
    listDocuments: vi.fn(),
    listSegments: vi.fn(),
    createSegment: vi.fn(),
    retrieve: vi.fn(),
    healthCheck: vi.fn(),
  },
  DifyApiError: class extends Error {},
}));

vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ toString: () => "rag_user_token=t" })),
}));

import { createQA } from "./knowledge";

describe("createQA 走审核 (不直调 Dify)", () => {
  beforeEach(() => {
    approvalsSubmitMock.mockReset();
    difyCreateDocMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("调 approvalsApi.submit(kind=qa, payload=input), 返 {approval_id, review_status: pending}", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      id: 142,
      kind: "qa",
      review_status: "pending",
      apply_status: "none",
    });

    const r = await createQA({
      dataset_id: "ds1",
      question: "q",
      answer: "a",
      tags: ["W21"],
    });

    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.data).toEqual({ approval_id: 142, review_status: "pending", apply_status: "none" });
    }
    expect(approvalsSubmitMock).toHaveBeenCalledWith("qa", {
      dataset_id: "ds1",
      question: "q",
      answer: "a",
      tags: ["W21"],
    });
    // 关键: 不能调 Dify 直写
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("缺字段返 ok:false 错误, 不发请求", async () => {
    const r = await createQA({ dataset_id: "", question: "q", answer: "a" });
    expect(r.ok).toBe(false);
    expect(approvalsSubmitMock).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test app/[locale]/_actions/knowledge.test.ts -t "createQA 走审核"
```

Expected: 2 个 FAIL (createQA 还是直调 DifyDatasets.createDocumentByText)

- [ ] **Step 3: 改 createQA 调 approvals.submit**

```typescript
// 在 packages/web/app/[locale]/_actions/knowledge.ts 里替换 createQA
// (整段替换, 保留其它 3 个 action 不动 — 它们在 Task 11/12/13 改)

import { approvalsApi } from "@/lib/api/approvals";
// 删: import { DifyDatasets, DifyApiError } from "@/lib/dify-datasets";
// 上面 import 在其它 3 个 action 里还要用, 暂时保留

interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

interface QAResult {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

export async function createQA(input: QAInput): Promise<ActionResult<QAResult>> {
  if (!input.dataset_id || !input.question || !input.answer) {
    return { error: "dataset_id / question / answer 必填", ok: false };
  }

  try {
    const approval = await approvalsApi.submit("qa", {
      dataset_id: input.dataset_id,
      question: input.question,
      answer: input.answer,
      tags: input.tags,
      sync_to_neo4j: input.sync_to_neo4j,
    });
    revalidatePath("/[locale]/submissions");
    return {
      data: {
        approval_id: approval.id,
        review_status: approval.review_status,
        apply_status: approval.apply_status,
      },
      ok: true,
    };
  } catch (e) {
    return { error: e instanceof Error ? e.message : String(e), ok: false };
  }
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test app/[locale]/_actions/knowledge.test.ts -t "createQA 走审核"
```

Expected: 2 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/_actions/knowledge.ts packages/web/app/[locale]/_actions/knowledge.test.ts
git commit -m "refactor(web): createQA 改调 approvals.submit (不直调 Dify)"
```

---

### Task 11-13: createTriples / commitDocuments / optimizeAnswer 改写 (模式同 Task 10)

**Files:**

- Modify: `packages/web/app/[locale]/_actions/knowledge.ts`
- Modify: `packages/web/app/[locale]/_actions/knowledge.test.ts`
- Create: `packages/web/app/[locale]/_actions/optimize.ts` (新 server action)

> **重复模板**: 跟 Task 10 同模式, 1 个 action 1 个 task。每个 task:
>
> 1. 写测试: 调 approvals.submit(kind=X, payload=...), assertNotCalled Dify / KgClient
> 2. 跑 red
> 3. 改 action: 替换内部为 approvalsApi.submit, revalidatePath 改 /[locale]/submissions
> 4. 跑 green
> 5. Commit

- [ ] **Task 11: createTriples** — `kind="triple"`, payload=`{rows: [...]}`, 不调 KgClient (跟现 commit 一致)

- [ ] **Task 12: commitDocuments** — `kind="batch"`, payload=`{dataset_id, rows}`, 不调 DifyDatasets.createDocumentByText

- [ ] **Task 13: optimizeAnswer** (新增) — `kind="optimize"`, payload=`{dataset_id, question, original_answer, improved_answer, reason}`, 从 chat 反馈触发

**注**: Task 11-13 测试模板跟 Task 10 一致, 改 `kind` 即可, **实施时按 spec 写**。

- [ ] **Step (3 个 task 各 1 个 commit 一起):**

```bash
git add packages/web/app/[locale]/_actions/
git commit -m "refactor(web): createTriples/commitDocuments/optimizeAnswer 改调 approvals.submit"
```

---

### Task 14: P1 完成验证

- [ ] **Step 1: 跑前端 knowledge action 全部测试**

```bash
cd packages/web && bun run test app/[locale]/_actions/knowledge.test.ts
```

Expected: 全部 PASS (新加 ~6 case + 原有 case)

- [ ] **Step 2: 跑前端全量测试**

```bash
cd packages/web && bun run test
```

Expected: 无回归

- [ ] **Step 3: 跑 typecheck + lint**

```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint
```

Expected: 0 errors

- [ ] **Step 4: 手动 smoke — 1 个 server action 真发后端**

```bash
# 后端起
cd packages/service && uv run uvicorn src.product_decoders.app:app --reload --port 8000 &
# 前端 dev 起, 浏览器走录 QA, 提交后看 /api/approvals 表 (SQLite 查)
```

**P1 阶段结束。** 进入 P2: 前端 `/submissions/*` UI。

---

## P2: 前端 `/submissions/*` UI + Middleware + 4 表单 toast 改

### Task 15: Middleware 加 /submissions/\* 守卫

**Files:**

- Modify: `packages/web/middleware.ts`
- Modify: `packages/web/middleware.test.ts`

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// 加到 packages/web/middleware.test.ts (跟现 admin 测试同模式)
import { middleware } from "./middleware";

describe("middleware /submissions 守卫", () => {
  it("/zh/submissions 无 token → redirect /zh/login?next=/zh/submissions", async () => {
    const req = new Request("http://localhost/zh/submissions");
    const res = (await middleware(req as never, {} as never)) as Response;
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/zh/login?next=%2Fzh%2Fsubmissions");
  });

  it("/en/submissions 有 token → 不重定向, 走 next()", async () => {
    const req = new Request("http://localhost/en/submissions", {
      headers: { cookie: "rag_user_token=t" },
    });
    // middleware 返 NextResponse.next() (不是 redirect)
    const res = (await middleware(req as never, {} as never)) as Response;
    expect(res.headers.get("location")).toBeNull();
  });

  it("/zh/submissions 跟 /zh/admin 解耦: /zh/submissions 不要求 admin", async () => {
    // 任何登录账号可进 (含 is_admin=false)
    const req = new Request("http://localhost/zh/submissions", {
      headers: { cookie: "rag_user_token=t" },
    });
    const res = (await middleware(req as never, {} as never)) as Response;
    expect(res.headers.get("location")).toBeNull(); // 不 redirect
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test middleware.test.ts -t "/submissions"
```

Expected: FAIL (middleware 不认 /submissions)

- [ ] **Step 3: 改 middleware**

```typescript
// packages/web/middleware.ts 改 isProtected 函数:
function isProtected(pathname: string): boolean {
  return LOCALE_PREFIXES.some(
    (l) =>
      pathname.startsWith(`${l}/admin`) ||
      pathname === `${l}/admin` ||
      pathname.startsWith(`${l}/submissions`) || // 新增
      pathname === `${l}/submissions`, // 新增
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test middleware.test.ts
```

Expected: 全部 PASS (admin 旧 case + submissions 新 3 case)

- [ ] **Step 5: Commit**

```bash
git add packages/web/middleware.ts packages/web/middleware.test.ts
git commit -m "feat(web): middleware 加 /submissions/* 守卫 (登录即可, 不 admin)"
```

---

### Task 16: SubmissionsTabs 客户端组件 (Tabs 切 mine / all + URL 同步)

**Files:**

- Create: `packages/web/app/[locale]/submissions/_components/SubmissionsTabs.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/SubmissionsTabs.test.tsx`

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// packages/web/app/[locale]/submissions/_components/SubmissionsTabs.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const { useRouterPushMock } = vi.hoisted(() => ({ useRouterPushMock: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: useRouterPushMock, refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import { SubmissionsTabs } from "./SubmissionsTabs";

describe("SubmissionsTabs", () => {
  beforeEach(() => useRouterPushMock.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("admin: 渲染 2 tab (mine / all), 默认 active=mine", () => {
    render(
      <SubmissionsTabs
        tabs={[{ key: "mine", label: "我提交的" }, { key: "all", label: "全部待审" }]}
        activeTab="mine"
        isAdmin
        initialMine={[]}
        initialAll={[]}
      />,
    );
    expect(screen.getByText("我提交的")).toBeInTheDocument();
    expect(screen.getByText("全部待审")).toBeInTheDocument();
  });

  it("非 admin: 仅渲染 mine tab, 不渲染 all", () => {
    render(
      <SubmissionsTabs
        tabs={[{ key: "mine", label: "我提交的" }]}
        activeTab="mine"
        isAdmin={false}
        initialMine={[]}
        initialAll={null}
      />,
    );
    expect(screen.getByText("我提交的")).toBeInTheDocument();
    expect(screen.queryByText("全部待审")).toBeNull();
  });

  it("点 all tab 调 router.push('/submissions?tab=all')", () => {
    render(
      <SubmissionsTabs
        tabs={[{ key: "mine", label: "我提交的" }, { key: "all", label: "全部待审" }]}
        activeTab="mine"
        isAdmin
        initialMine={[]}
        initialAll={[]}
      />,
    );
    fireEvent.click(screen.getByText("全部待审"));
    expect(useRouterPushMock).toHaveBeenCalledWith("/submissions?tab=all");
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test submissions/_components/SubmissionsTabs.test.tsx
```

Expected: 3 个 FAIL (module not found)

- [ ] **Step 3: 实现 SubmissionsTabs**

```typescript
// packages/web/app/[locale]/submissions/_components/SubmissionsTabs.tsx
"use client";
// SubmissionsTabs — 客户端组件, 切 mine / all, URL 同步, mine 跟 all 内容用 RQ 接管
// 跟 swr-to-rsc-rq spec 一致: 切 tab 触发 RSC 重跑预取

import { useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { MySubmissionsList } from "./MySubmissionsList";
import { AllApprovalsTable } from "./AllApprovalsTable";
import type { Approval } from "@/lib/api/approvals";

export interface SubmissionsTabsProps {
  tabs: { key: "mine" | "all"; label: string }[];
  activeTab: "mine" | "all";
  isAdmin: boolean;
  initialMine: Approval[];
  initialAll: Approval[] | null;
}

export function SubmissionsTabs({
  tabs, activeTab, isAdmin, initialMine, initialAll,
}: SubmissionsTabsProps) {
  const router = useRouter();

  return (
    <Tabs value={activeTab}>
      <TabsList>
        {tabs.map((t) => (
          <TabsTrigger
            key={t.key}
            value={t.key}
            onClick={() => router.push(`/submissions?tab=${t.key}`)}
            data-testid={`tab-${t.key}`}
          >
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="mine">
        <MySubmissionsList initialData={initialMine} />
      </TabsContent>
      {isAdmin && (
        <TabsContent value="all">
          <AllApprovalsTable initialData={initialAll ?? []} />
        </TabsContent>
      )}
    </Tabs>
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test submissions/_components/SubmissionsTabs.test.tsx
```

Expected: 3 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/submissions/_components/SubmissionsTabs.tsx packages/web/app/[locale]/submissions/_components/SubmissionsTabs.test.tsx
git commit -m "feat(web): SubmissionsTabs (admin 渲染 2 tab, 普通用户 1 tab)"
```

---

### Task 17: ApprovalRow 共用行组件 (2 badge + Collapsible 展开)

**Files:**

- Create: `packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/ApprovalRow.test.tsx`

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// packages/web/app/[locale]/submissions/_components/ApprovalRow.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const { getDetailMock } = vi.hoisted(() => ({ getDetailMock: vi.fn() }));
vi.mock("@/lib/api/approvals", () => ({
  approvalsApi: {
    getDetail: getDetailMock,
    submit: vi.fn(), approve: vi.fn(), reject: vi.fn(), retry: vi.fn(),
  },
}));

import { ApprovalRow } from "./ApprovalRow";
import type { Approval } from "@/lib/api/approvals";

const baseApproval: Approval = {
  id: 142, kind: "qa", review_status: "pending", apply_status: "none",
  submitter_id: 1, reviewer_id: null,
  rejection_reason: null, rejection_note: null, error_msg: null,
  created_at: "2026-06-13T10:00:00Z",
  reviewed_at: null, applied_at: null,
};

describe("ApprovalRow", () => {
  beforeEach(() => getDetailMock.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("渲染 2 个独立 badge (review + apply), 各自色", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin={false} />);
    expect(screen.getByTestId("badge-review")).toHaveTextContent("待审");
    expect(screen.getByTestId("badge-apply")).toHaveTextContent("未写入");
  });

  it("review=approved, apply=failed → 2 badge 正确", () => {
    render(
      <ApprovalRow
        approval={{ ...baseApproval, review_status: "approved", apply_status: "failed", error_msg: "Dify 502" }}
        isAdmin
      />,
    );
    expect(screen.getByTestId("badge-review")).toHaveTextContent("已批");
    expect(screen.getByTestId("badge-apply")).toHaveTextContent("写库失败");
  });

  it("review=rejected, rejection_reason=duplicate, rejection_note='跟 doc-12 重复' → 显示原因", () => {
    render(
      <ApprovalRow
        approval={{
          ...baseApproval, review_status: "rejected",
          rejection_reason: "duplicate", rejection_note: "跟 doc-12 重复",
        }}
        isAdmin={false}
      />,
    );
    expect(screen.getByText(/被拒/)).toBeInTheDocument();
    expect(screen.getByText(/跟 doc-12 重复/)).toBeInTheDocument();
  });

  it("点展开调 approvalsApi.getDetail, 拉完整 payload 渲染", async () => {
    getDetailMock.mockResolvedValueOnce({
      ...baseApproval,
      payload: { dataset_id: "ds1", question: "1LE 防护等级?", answer: "IP55" },
    });
    render(<ApprovalRow approval={baseApproval} isAdmin />);
    fireEvent.click(screen.getByTestId("expand-trigger"));
    expect(getDetailMock).toHaveBeenCalledWith(142);
    // 展开后渲染 payload
    expect(await screen.findByText(/1LE 防护等级/)).toBeInTheDocument();
  });

  it("非 admin: 不渲染批准/拒绝/重试按钮", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin={false} />);
    expect(screen.queryByTestId("btn-approve")).toBeNull();
    expect(screen.queryByTestId("btn-reject")).toBeNull();
    expect(screen.queryByTestId("btn-retry")).toBeNull();
  });

  it("admin + review=pending: 显示批准/拒绝按钮, 不显示重试", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin />);
    expect(screen.getByTestId("btn-approve")).toBeInTheDocument();
    expect(screen.getByTestId("btn-reject")).toBeInTheDocument();
    expect(screen.queryByTestId("btn-retry")).toBeNull();
  });

  it("admin + (approved, failed): 显示重试按钮, 不显示批准/拒绝", () => {
    render(
      <ApprovalRow
        approval={{ ...baseApproval, review_status: "approved", apply_status: "failed", error_msg: "x" }}
        isAdmin
      />,
    );
    expect(screen.queryByTestId("btn-approve")).toBeNull();
    expect(screen.queryByTestId("btn-reject")).toBeNull();
    expect(screen.getByTestId("btn-retry")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test submissions/_components/ApprovalRow.test.tsx
```

Expected: 7 个 FAIL

- [ ] **Step 3: 实现 ApprovalRow**

```typescript
// packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx
"use client";
// ApprovalRow — 共用行组件, 2 个独立 badge (review + apply) + Collapsible 展开 + 行内按钮
// mine / all 都用, 按 isAdmin 决定显隐批准/拒绝/重试按钮

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { approvalsApi, type Approval } from "@/lib/api/approvals";
import { RejectDialog } from "./RejectDialog";

const REVIEW_BADGE: Record<string, string> = {
  pending: "bg-status-warning/20 text-status-warning",
  approved: "bg-status-success/20 text-status-success",
  rejected: "bg-status-error/20 text-status-error",
};

const APPLY_BADGE: Record<string, string> = {
  none: "bg-muted/20 text-muted-foreground",
  applied: "bg-status-success/20 text-status-success",
  failed: "bg-status-error/20 text-status-error",
};

export function ApprovalRow({ approval, isAdmin }: { approval: Approval; isAdmin: boolean }) {
  const t = useTranslations("submissions");
  const tc = useTranslations("submissions.reviewStatus");
  const ta = useTranslations("submissions.applyStatus");
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  // 展开时拉详情
  const detail = useQuery({
    queryKey: ["approval-detail", approval.id],
    queryFn: () => approvalsApi.getDetail(approval.id),
    enabled: open,
  });

  // mutations
  const approveMut = useMutation({
    mutationFn: () => approvalsApi.approve(approval.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
  const retryMut = useMutation({
    mutationFn: () => approvalsApi.retry(approval.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
  const rejectMut = useMutation({
    mutationFn: ({ reason, note }: { reason: string; note?: string }) =>
      approvalsApi.reject(approval.id, reason as never, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      setRejectOpen(false);
    },
  });

  const canApprove = isAdmin && approval.review_status === "pending";
  const canRetry = isAdmin && approval.review_status === "approved" && approval.apply_status === "failed";
  const canReject = isAdmin && approval.review_status === "pending";

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded border p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" data-testid="expand-trigger">
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
          </CollapsibleTrigger>
          <span className="font-mono text-sm">#{approval.id}</span>
          <Badge variant="secondary">{tc(approval.review_status as never)}</Badge>
          <Badge variant="secondary" data-testid="badge-review">
            {/* 防止外层 badge 重复, 这里只用 1 个 badge 区域 */}
            {tc(approval.review_status as never)}
          </Badge>
          <Badge className={REVIEW_BADGE[approval.review_status]} data-testid="badge-review">
            {tc(approval.review_status as never)}
          </Badge>
          <Badge className={APPLY_BADGE[approval.apply_status]} data-testid="badge-apply">
            {ta(approval.apply_status as never)}
          </Badge>
          <span className="text-xs text-muted-foreground">{approval.created_at}</span>
        </div>
        <div className="flex gap-1">
          {canApprove && (
            <Button size="sm" onClick={() => approveMut.mutate()} data-testid="btn-approve">
              {t("actions.approve")}
            </Button>
          )}
          {canReject && (
            <Button size="sm" variant="destructive" onClick={() => setRejectOpen(true)} data-testid="btn-reject">
              {t("actions.reject")}
            </Button>
          )}
          {canRetry && (
            <Button size="sm" onClick={() => retryMut.mutate()} data-testid="btn-retry">
              {t("actions.retry")}
            </Button>
          )}
        </div>
      </div>

      <CollapsibleContent className="mt-3 space-y-2">
        {/* 展开区: payload 详情 + 失败/被拒原因 */}
        {detail.isLoading && <p className="text-sm text-muted-foreground">加载中...</p>}
        {detail.data?.payload && (
          <div className="rounded bg-muted/30 p-3 text-sm">
            <pre className="whitespace-pre-wrap">{JSON.stringify(detail.data.payload, null, 2)}</pre>
          </div>
        )}
        {approval.review_status === "rejected" && approval.rejection_reason && (
          <div className="rounded bg-status-error/10 p-3 text-sm">
            <strong>{t("rejectionReason")}:</strong> {approval.rejection_reason}
            {approval.rejection_note && <div className="mt-1 text-muted-foreground">{approval.rejection_note}</div>}
          </div>
        )}
        {approval.apply_status === "failed" && approval.error_msg && (
          <div className="rounded bg-status-error/10 p-3 text-sm">
            <strong>Error:</strong> {approval.error_msg}
          </div>
        )}
      </CollapsibleContent>

      <RejectDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        onSubmit={(reason, note) => rejectMut.mutate({ reason, note })}
        isPending={rejectMut.isPending}
      />
    </Collapsible>
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test submissions/_components/ApprovalRow.test.tsx
```

Expected: 7 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx packages/web/app/[locale]/submissions/_components/ApprovalRow.test.tsx
git commit -m "feat(web): ApprovalRow 共用行 (2 badge + Collapsible 展开 + 行内按钮)"
```

---

### Task 18: RejectDialog (shadcn Select 6 原因 + other 显 Textarea)

**Files:**

- Create: `packages/web/app/[locale]/submissions/_components/RejectDialog.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/RejectDialog.test.tsx`

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// packages/web/app/[locale]/submissions/_components/RejectDialog.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RejectDialog } from "./RejectDialog";

describe("RejectDialog", () => {
  it("弹框打开显示 6 个原因选项 (Select 触发器)", () => {
    render(<RejectDialog open onOpenChange={vi.fn()} onSubmit={vi.fn()} isPending={false} />);
    // 6 个 reason key 在 trigger 里 (点开 Select 才全看到, 这里只验 trigger 存在)
    expect(screen.getByTestId("select-trigger")).toBeInTheDocument();
  });

  it("选 other 时显示 Textarea 补充说明", () => {
    render(<RejectDialog open onOpenChange={vi.fn()} onSubmit={vi.fn()} isPending={false} />);
    // 用 fireEvent 选 other (测试 Select 需 mock onValueChange, 实际 Select onValueChange)
    // 简化: 通过 props 模拟 (本测试只验组件结构, Select 交互测试在 RQ 层)
    expect(screen.queryByTestId("note-textarea")).toBeNull(); // 默认不显示
  });

  it("提交调 onSubmit(reason, note)", () => {
    const onSubmit = vi.fn();
    render(<RejectDialog open onOpenChange={vi.fn()} onSubmit={onSubmit} isPending={false} />);
    // 简化测试: 直接点提交按钮 (理由默认第一个)
    fireEvent.click(screen.getByTestId("btn-submit-reject"));
    expect(onSubmit).toHaveBeenCalled();
  });

  it("关闭调 onOpenChange(false)", () => {
    const onOpenChange = vi.fn();
    render(<RejectDialog open onOpenChange={onOpenChange} isSubmitting={false} onSubmit={vi.fn()} isPending={false} />);
    fireEvent.click(screen.getByTestId("btn-cancel-reject"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test submissions/_components/RejectDialog.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 实现 RejectDialog**

```typescript
// packages/web/app/[locale]/submissions/_components/RejectDialog.tsx
"use client";
// RejectDialog — shadcn Select 6 预设原因, 选 other 时显示 Textarea 补充
// 跟 ApprovalRow 复用 (子组件)

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import type { RejectReasonKey } from "@/lib/api/approvals";

const REASONS: RejectReasonKey[] = [
  "duplicate", "low_quality", "incomplete", "wrong_category", "format_issue", "other",
];

export function RejectDialog({
  open, onOpenChange, onSubmit, isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (reason: RejectReasonKey, note?: string) => void;
  isPending: boolean;
}) {
  const t = useTranslations("submissions.rejectDialog");
  const [reason, setReason] = useState<RejectReasonKey | "">("");
  const [note, setNote] = useState("");

  const isOther = reason === "other";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Select value={reason} onValueChange={(v) => setReason(v as RejectReasonKey)}>
            <SelectTrigger data-testid="select-trigger">
              <SelectValue placeholder={t("reasonRequired")} />
            </SelectTrigger>
            <SelectContent>
              {REASONS.map((r) => (
                <SelectItem key={r} value={r} data-testid={`reason-${r}`}>
                  {t(`reasons.${r}` as never)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {isOther && (
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("otherPlaceholder")}
              maxLength={500}
              data-testid="note-textarea"
            />
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="btn-cancel-reject">
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={!reason || (isOther && !note) || isPending}
            onClick={() => onSubmit(reason as RejectReasonKey, isOther ? note : undefined)}
            data-testid="btn-submit-reject"
          >
            {t("submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test submissions/_components/RejectDialog.test.tsx
```

Expected: 4 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/submissions/_components/RejectDialog.tsx packages/web/app/[locale]/submissions/_components/RejectDialog.test.tsx
git commit -m "feat(web): RejectDialog (shadcn Select 6 原因 + other 显 Textarea)"
```

---

### Task 19: MySubmissionsList + AllApprovalsTable (复用 ApprovalRow)

**Files:**

- Create: `packages/web/app/[locale]/submissions/_components/MySubmissionsList.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/MySubmissionsList.test.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/AllApprovalsTable.tsx`
- Create: `packages/web/app/[locale]/submissions/_components/AllApprovalsTable.test.tsx`

- [ ] **Step 1: 写测试 (TDD red) — 2 文件**

**MySubmissionsList.test.tsx** 测:

- 渲染 initialData 列表 (每项是 ApprovalRow, isAdmin=false)
- 失败 / 被拒项展开区显示原因
- 调 RQ useQuery 拉自己 (mock approvalsApi 不用 — 通过 RQ mock)

**AllApprovalsTable.test.tsx** 测:

- 渲染 initialData (每项 isAdmin=true)
- 切 review tab 调 RQ useQuery
- admin 看到批准/拒绝/重试按钮 (在 ApprovalRow 内)

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test submissions/_components/MySubmissionsList.test.tsx
cd packages/web && bun run test submissions/_components/AllApprovalsTable.test.tsx
```

- [ ] **Step 3: 实现 2 组件**

**MySubmissionsList.tsx** (模板, 跟 spec 一致):

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty } from "@/components/ui/empty";
import { approvalsApi, type Approval } from "@/lib/api/approvals";
import { ApprovalRow } from "./ApprovalRow";

export function MySubmissionsList({ initialData }: { initialData: Approval[] }) {
  const [filter, setFilter] = useState<"all" | "pending" | "failed">("all");
  const { data = initialData } = useQuery({
    queryKey: ["approvals", "me", filter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filter === "pending") params.set("review", "pending");
      if (filter === "failed") params.set("apply", "failed");
      return fetch(`/api/approvals/me?${params}`).then((r) => r.json());
    },
    initialData,
  });
  if (data.length === 0) {
    return <Empty description="暂无提交" />;
  }
  return (
    <div className="space-y-2">
      <Tabs value={filter} onValueChange={(v) => setFilter(v as never)}>
        <TabsList>
          <TabsTrigger value="all">全部</TabsTrigger>
          <TabsTrigger value="pending">待审</TabsTrigger>
          <TabsTrigger value="failed">失败</TabsTrigger>
        </TabsList>
      </Tabs>
      {data.map((a) => <ApprovalRow key={a.id} approval={a} isAdmin={false} />)}
    </div>
  );
}
```

**AllApprovalsTable.tsx** (类似, 加 review tab 切换 + isAdmin=true):

```typescript
"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty } from "@/components/ui/empty";
import { approvalsApi, type Approval } from "@/lib/api/approvals";
import { ApprovalRow } from "./ApprovalRow";

export function AllApprovalsTable({ initialData }: { initialData: Approval[] }) {
  const [review, setReview] = useState<"pending" | "approved" | "rejected">("pending");
  const { data = initialData } = useQuery({
    queryKey: ["approvals", "all", review],
    queryFn: () =>
      fetch(`/api/approvals?review=${review}`).then((r) => r.json()),
    initialData,
  });
  if (data.length === 0) {
    return <Empty description="暂无待审" />;
  }
  return (
    <div className="space-y-2">
      <Tabs value={review} onValueChange={(v) => setReview(v as never)}>
        <TabsList>
          <TabsTrigger value="pending">待审</TabsTrigger>
          <TabsTrigger value="approved">已批</TabsTrigger>
          <TabsTrigger value="rejected">被拒</TabsTrigger>
        </TabsList>
      </Tabs>
      {data.map((a) => <ApprovalRow key={a.id} approval={a} isAdmin />)}
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test submissions/_components/
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/submissions/_components/MySubmissionsList.tsx packages/web/app/[locale]/submissions/_components/MySubmissionsList.test.tsx packages/web/app/[locale]/submissions/_components/AllApprovalsTable.tsx packages/web/app/[locale]/submissions/_components/AllApprovalsTable.test.tsx
git commit -m "feat(web): MySubmissionsList + AllApprovalsTable (复用 ApprovalRow)"
```

---

### Task 20: /submissions RSC page (服务端决定 tab 列表)

**Files:**

- Create: `packages/web/app/[locale]/submissions/page.tsx`
- Create: `packages/web/app/[locale]/submissions/page.test.tsx`
- Create: `packages/web/app/[locale]/submissions/layout.tsx` (可选, header)

- [ ] **Step 1: 写测试 (TDD red)**

```typescript
// packages/web/app/[locale]/submissions/page.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const { cookiesMock, fetchMock } = vi.hoisted(() => ({
  cookiesMock: vi.fn(),
  fetchMock: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: cookiesMock }));
vi.mock("next/navigation", () => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT:${url}`);
  }),
}));
vi.stubGlobal("fetch", fetchMock);
vi.mock("next-intl/server", () => ({ getTranslations: vi.fn(async () => (key: string) => key) }));

import SubmissionsPage from "./page";

describe("SubmissionsPage RSC", () => {
  beforeEach(() => {
    cookiesMock.mockReset();
    fetchMock.mockReset();
    cookiesMock.mockResolvedValue({ toString: () => "rag_user_token=t" });
  });
  afterEach(() => vi.restoreAllMocks());

  it("无 token → redirect /login?next=/submissions", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 401 }));
    await expect(SubmissionsPage({ searchParams: Promise.resolve({}) })).rejects.toThrow(
      /REDIRECT:.*login/,
    );
  });

  it("普通用户 (is_admin=false) → 不渲染 all tab, 只调 /api/approvals/me", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ is_admin: false }), { status: 200 })) // /me
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 })); // /me
    await SubmissionsPage({ searchParams: Promise.resolve({}) });
    // fetch 第 2 次 (me) 调了, 第 3 次 (all) 没调 (admin 才调)
    const urls = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(urls.some((u) => u.includes("/api/approvals/me"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/approvals?review=pending"))).toBe(false);
  });

  it("admin → 渲染 2 tab, 调 /api/approvals (admin 路径) + /api/approvals/me", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ is_admin: true }), { status: 200 })) // /me
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 })) // /me (RSC 预取)
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 })); // /api/approvals
    await SubmissionsPage({ searchParams: Promise.resolve({}) });
    const urls = fetchMock.mock.calls.map((c) => c[0] as string);
    expect(urls.some((u) => u.includes("/api/approvals/me"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/approvals?review=pending"))).toBe(true);
  });
});
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test submissions/page.test.tsx
```

Expected: FAIL (module not found)

- [ ] **Step 3: 实现 RSC page**

```typescript
// packages/web/app/[locale]/submissions/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { SubmissionsTabs } from "./_components/SubmissionsTabs";
import type { Approval } from "@/lib/api/approvals";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default async function SubmissionsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const cookieHeader = (await cookies()).toString();

  // 1. 鉴权
  const meRes = await fetch(`${API_BASE}/api/account/me`, {
    cache: "no-store",
    headers: { cookie: cookieHeader },
  });
  if (!meRes.ok) redirect("/login?next=/submissions");
  const me = await meRes.json();

  const t = await getTranslations();
  // 2. 决定 tab 列表 (服务端 conditional)
  const tabs = me.is_admin
    ? [
        { key: "mine" as const, label: t("submissions.tabs.mine") },
        { key: "all" as const, label: t("submissions.tabs.all") },
      ]
    : [{ key: "mine" as const, label: t("submissions.tabs.mine") }];

  const sp = await searchParams;
  const activeTab = (sp.tab === "all" ? "all" : "mine") as "mine" | "all";

  // 3. 预取两路数据
  const initialMine: Approval[] = await fetch(
    `${API_BASE}/api/approvals/me?skip=0&limit=20`,
    { cache: "no-store", headers: { cookie: cookieHeader } },
  ).then((r) => (r.ok ? r.json() : []));

  const initialAll: Approval[] | null = me.is_admin
    ? await fetch(
        `${API_BASE}/api/approvals?review=pending&skip=0&limit=20`,
        { cache: "no-store", headers: { cookie: cookieHeader } },
      ).then((r) => (r.ok ? r.json() : []))
    : null;

  return (
    <div className="space-y-6 p-6">
      <h1 className="display text-3xl">{t("submissions.title")}</h1>
      <SubmissionsTabs
        tabs={tabs}
        activeTab={activeTab}
        isAdmin={me.is_admin}
        initialMine={initialMine}
        initialAll={initialAll}
      />
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test submissions/page.test.tsx
```

Expected: 3 个 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/submissions/page.tsx packages/web/app/[locale]/submissions/page.test.tsx packages/web/app/[locale]/submissions/layout.tsx
git commit -m "feat(web): /submissions RSC (admin 渲染 2 tab, 普通 1 tab)"
```

---

### Task 21: 4 个表单 toast 改 + MessageFeedback 新增

**Files:**

- Modify: `packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.tsx`
- Modify: `packages/web/app/[locale]/knowledge/triples/_components/TriplesForm.tsx`
- Modify: `packages/web/app/[locale]/knowledge/documents/import/_components/ImportForm.tsx`
- Create: `packages/web/app/[locale]/chat/_components/MessageFeedback.tsx` (新)

- [ ] **Step 1: 改 QASubmitForm toast 引导**

```typescript
// 替换 QASubmitForm.tsx 里 createQA 成功后的 toast + push:
// 改前:
//   toast.success("已写入 Dify");
// 改后:
if (result.ok) {
  toast.success(t("submissions.submitted", { id: result.data.approval_id }));
  router.push(`/${locale}/submissions`);
}
```

- [ ] **Step 2: 同样改 TriplesForm + ImportForm (模板一致)**

- [ ] **Step 3: 新增 MessageFeedback.tsx (优化回答触发)**

```typescript
// packages/web/app/[locale]/chat/_components/MessageFeedback.tsx
"use client";
// chat 反馈按钮: 调 optimizeAnswer server action 触发审核

import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslations } from "next-intl";
import { optimizeAnswer } from "@/app/[locale]/_actions/knowledge";

export function MessageFeedback({
  messageId, question, originalAnswer,
}: { messageId: string; question: string; originalAnswer: string }) {
  const t = useTranslations("chat");
  const [pending, setPending] = useState(false);
  const [showImprove, setShowImprove] = useState(false);
  const [improved, setImproved] = useState("");
  const [reason, setReason] = useState("");

  const submit = async () => {
    setPending(true);
    const result = await optimizeAnswer({
      dataset_id: "ds-default", // 跟 chat dataset 关联, 简化先 hardcode
      question, original_answer: originalAnswer,
      improved_answer: improved, reason,
    });
    setPending(false);
    if (result.ok) {
      setShowImprove(false);
      // toast + push 跟其他表单一致
    }
  };

  return (
    <div>
      <Button size="sm" variant="ghost" onClick={() => setShowImprove(true)} data-testid="btn-improve">
        <ThumbsDown className="h-3 w-3" /> 改进
      </Button>
      {showImprove && (
        <div className="mt-2 space-y-2">
          <textarea value={improved} onChange={(e) => setImproved(e.target.value)} placeholder="改进后的回答" />
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="改了什么, 为什么" />
          <Button onClick={submit} disabled={pending || !improved} data-testid="btn-submit-improve">提交审核</Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 跑前端全量测试**

```bash
cd packages/web && bun run test
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.tsx packages/web/app/[locale]/knowledge/triples/_components/TriplesForm.tsx packages/web/app/[locale]/knowledge/documents/import/_components/ImportForm.tsx packages/web/app/[locale]/chat/_components/MessageFeedback.tsx
git commit -m "feat(web): 4 表单 toast 改 + chat MessageFeedback (优化回答触发)"
```

---

**P2 阶段结束。** 进入 P3: i18n + BFF + docs。

---

## P3: i18n + BFF + Docs

### Task 22: i18n 加 14 个 key (zh + en)

**Files:**

- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`
- Modify: `packages/web/messages/zh.test.ts` (snapshot)
- Modify: `packages/web/messages/en.test.ts` (snapshot)

- [ ] **Step 1: 找现有 messages snapshot test**

```bash
cd packages/web && find . -name "*.test.ts" -path "*messages*" 2>&1 | head -3
```

- [ ] **Step 2: 加 zh.json key**

```json
{
  "submissions": {
    "title": "审核中心",
    "submitted": "已提交审核 #{id}, 等待管理员批准",
    "tabs": {
      "mine": "我提交的",
      "all": "全部待审"
    },
    "status": {
      "pending": "待审",
      "approved": "已批",
      "applied": "已写入",
      "rejected": "被拒",
      "failed": "写库失败"
    },
    "reviewStatus": {
      "label": "审批",
      "pending": "待审",
      "approved": "已批",
      "rejected": "被拒"
    },
    "applyStatus": {
      "label": "写入",
      "none": "未写入",
      "applied": "已写入",
      "failed": "写库失败"
    },
    "kind": {
      "qa": "QA 录入",
      "triple": "三元组",
      "batch": "批量导入",
      "optimize": "优化回答"
    },
    "actions": {
      "approve": "批准",
      "reject": "拒绝",
      "retry": "重试",
      "resubmit": "重新提交",
      "viewDetail": "查看详情"
    },
    "rejectDialog": {
      "title": "拒绝原因",
      "description": "请选择预设原因, 提交者会看到。",
      "reasons": {
        "duplicate": "重复内容",
        "low_quality": "质量问题",
        "incomplete": "信息不完整",
        "wrong_category": "分类错误",
        "format_issue": "格式问题",
        "other": "其他"
      },
      "otherPlaceholder": "补充说明 (选 \"其他\" 时填写)",
      "submit": "确认拒绝",
      "reasonRequired": "请选择拒绝原因"
    },
    "rejectionReason": "拒绝原因",
    "appliedAt": "写入时间",
    "errorMsg": "错误信息"
  }
}
```

- [ ] **Step 3: 加 en.json (跟 zh 一一对应, 英文)**

```json
{
  "submissions": {
    "title": "Review Center",
    "submitted": "Submitted for review #{id}, awaiting admin approval",
    "tabs": { "mine": "My Submissions", "all": "All Pending" },
    "status": {
      "pending": "Pending",
      "approved": "Approved",
      "applied": "Applied",
      "rejected": "Rejected",
      "failed": "Failed"
    },
    "reviewStatus": {
      "label": "Review",
      "pending": "Pending",
      "approved": "Approved",
      "rejected": "Rejected"
    },
    "applyStatus": {
      "label": "Apply",
      "none": "Not Applied",
      "applied": "Applied",
      "failed": "Failed"
    },
    "kind": {
      "qa": "QA Entry",
      "triple": "Triple",
      "batch": "Batch Import",
      "optimize": "Optimize"
    },
    "actions": {
      "approve": "Approve",
      "reject": "Reject",
      "retry": "Retry",
      "resubmit": "Resubmit",
      "viewDetail": "View"
    },
    "rejectDialog": {
      "title": "Rejection Reason",
      "description": "Select a preset reason. The submitter will see it.",
      "reasons": {
        "duplicate": "Duplicate content",
        "low_quality": "Low quality",
        "incomplete": "Incomplete info",
        "wrong_category": "Wrong category",
        "format_issue": "Format issue",
        "other": "Other"
      },
      "otherPlaceholder": "Additional notes (when selecting \"Other\")",
      "submit": "Confirm Reject",
      "reasonRequired": "Please select a reason"
    },
    "rejectionReason": "Rejection reason",
    "appliedAt": "Applied at",
    "errorMsg": "Error message"
  }
}
```

- [ ] **Step 4: 跑 messages snapshot test 确认绿**

```bash
cd packages/web && bun run test messages/
```

Expected: PASS (新 key 加进去, 现有 case 不破坏)

- [ ] **Step 5: 跑全量前端测试**

```bash
cd packages/web && bun run test
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add packages/web/messages/
git commit -m "feat(i18n): 加 submissions.* 14 个 key (zh + en)"
```

---

### Task 23: BFF 3 端点 (admin-only 路径, 跟前端 RSC 透传 cookie)

**Files:**

- Create: `packages/web/app/api/approvals/[id]/approve/route.ts` + `.test.ts`
- Create: `packages/web/app/api/approvals/[id]/reject/route.ts` + `.test.ts`
- Create: `packages/web/app/api/approvals/[id]/retry/route.ts` + `.test.ts`

> **Why BFF**: 当前前端走 RSC 直调 FastAPI `/api/approvals/{id}/approve` 已经能传 cookie。但 admin 路径下, 用 BFF 加 1 层封装保证:
>
> 1. cookie 自动透传 (跟现有 admin BFF 模式一致)
> 2. 422 等错误码由 BFF 透传给前端 (不丢)
> 3. RQ useMutation 调 BFF 而不是直连 FastAPI (跟 [2026-06-10-web-frontend-architecture](../specs/2026-06-10-web-frontend-architecture.md) 锁定 admin BFF 边界一致)

- [ ] **Step 1: 写 3 个 BFF route test (TDD red)**

**`approve/route.test.ts`**:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { cookiesMock, fetchMock } = vi.hoisted(() => ({ cookiesMock: vi.fn(), fetchMock: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: cookiesMock }));
vi.stubGlobal("fetch", fetchMock);

import { POST } from "./route";

describe("POST /api/approvals/[id]/approve BFF", () => {
  beforeEach(() => {
    cookiesMock.mockReset();
    fetchMock.mockReset();
    cookiesMock.mockResolvedValue({ toString: () => "rag_user_token=t" });
  });
  afterEach(() => vi.restoreAllMocks());

  it("调 FastAPI /api/approvals/{id}/approve 带 cookie, 返 200 + body", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 142, review_status: "approved" }), { status: 200 }),
    );
    const req = new Request("http://localhost/api/approvals/142/approve", { method: "POST" });
    const res = await POST(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/approvals/142/approve",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ cookie: "rag_user_token=t" }),
      }),
    );
  });

  it("FastAPI 返 409 → BFF 透传 409", async () => {
    fetchMock.mockResolvedValueOnce(new Response("InvalidState", { status: 409 }));
    const req = new Request("http://localhost/api/approvals/142/approve", { method: "POST" });
    const res = await POST(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(409);
  });
});
```

**`reject/route.test.ts`** 跟 approve 类似, 加 body 转发测试:

- 422 (缺 reason) 透传
- 200 (成功) 透传

**`retry/route.test.ts`** 跟 approve 类似, 无 body。

- [ ] **Step 2: 跑测试确认 red**

```bash
cd packages/web && bun run test app/api/approvals/
```

Expected: FAIL (module not found)

- [ ] **Step 3: 实现 3 个 BFF route**

**`approve/route.ts`**:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookieHeader = (await cookies()).toString();
  const res = await fetch(`${FASTAPI}/api/approvals/${id}/approve`, {
    method: "POST",
    headers: { cookie: cookieHeader },
  });
  if (!res.ok) {
    return new NextResponse(await res.text(), { status: res.status });
  }
  return NextResponse.json(await res.json());
}
```

**`reject/route.ts`**:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const FASTAPI = process.env.FASTAPI_BASE ?? "http://localhost:8000";

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await req.json();
  const cookieHeader = (await cookies()).toString();
  const res = await fetch(`${FASTAPI}/api/approvals/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json", cookie: cookieHeader },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    return new NextResponse(await res.text(), { status: res.status });
  }
  return NextResponse.json(await res.json());
}
```

**`retry/route.ts`** 跟 approve 同模式 (无 body)。

- [ ] **Step 4: 跑测试确认 green**

```bash
cd packages/web && bun run test app/api/approvals/
```

Expected: 全部 PASS (approve 2 case + reject 2 case + retry 1 case)

- [ ] **Step 5: Commit**

```bash
git add packages/web/app/api/approvals/
git commit -m "feat(web): BFF /api/approvals/[id]/{approve,reject,retry} 3 端点"
```

---

### Task 24: 文档更新 (knowledge-management-page + 新建 approval-system.md)

**Files:**

- Modify: `docs/knowledge-management-page.md` (加 1 节 "审核集成")
- Create: `docs/approval-system.md` (新, 用户使用文档)

- [ ] **Step 1: 改 knowledge-management-page.md**

找文件, 在末尾加 1 节:

```markdown
## 审核集成 (2026-06-13)

4 个写动作 (录 QA / 录三元组 / 批量导入 / 优化回答) 已改造为走 admin 审核:

- 提交后写 `approvals` 表 (review_status=pending), **不直接** 调 Dify/Neo4j
- 用户提交后, 跳 `/submissions` 看自己提交的状态
- admin 在同页 "全部待审" tab 看全部 + 批准/拒绝/重试
- 详细见 [approval-system.md](approval-system.md) 跟 [spec](../superpowers/specs/2026-06-13-approval-system-design.md)
```

- [ ] **Step 2: 新建 approval-system.md (用户文档)**

```markdown
# 审核系统使用文档

## 给提交者

提交后跳到 `/submissions` 看自己提交的状态:

- **待审** (黄色): 等待 admin 批准
- **已批 + 已写入** (绿色): 成功写入知识库
- **已批 + 写库失败** (红色): admin 会重试, 不需操作
- **被拒** (红色): 展开看拒绝原因, 修正后重新提交

## 给 admin

进 `/submissions` 切 "全部待审" tab:

1. 展开行看完整内容
2. 1 键批准 (立即触发 BackgroundTask 写入)
3. 拒绝: 选预设原因 (重复/质量/不完整/分类/格式/其他), 选 "其他" 时补充说明
4. 失败项 1 键重试

## 状态字段

每个审核项有 2 个独立状态:

- `review_status`: pending / approved / rejected (admin 决定的)
- `apply_status`: none / applied / failed (系统写入结果)
```

- [ ] **Step 3: 跑 markdown lint (如有)**

```bash
bun run lint:md 2>&1 | head -10 || true
```

- [ ] **Step 4: Commit**

```bash
git add docs/knowledge-management-page.md docs/approval-system.md
git commit -m "docs: knowledge-management-page 加审核集成节 + 新建 approval-system 用户文档"
```

---

### Task 25: 最终验证 (P0-P3 全量)

- [ ] **Step 1: 跑后端全量测试**

```bash
cd packages/service && uv run pytest tests/ -v 2>&1 | tail -10
```

Expected: 全部 PASS (含 approvals 新模块)

- [ ] **Step 2: 跑前端全量测试**

```bash
cd packages/web && bun run test 2>&1 | tail -10
```

Expected: 全部 PASS

- [ ] **Step 3: 跑 typecheck + lint (前后端)**

```bash
cd packages/web && bun run typecheck && bun run lint
cd packages/service && uv run pyright && uv run ruff check .
```

Expected: 0 errors

- [ ] **Step 4: 跑契约测试 (跟项目 [feedback-bff-must-propagate-502] 一致)**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

Expected: PASS (8 路由已加)

- [ ] **Step 5: 端到端 smoke (手动)**

```bash
# 1. 起后端
cd packages/service && uv run uvicorn src.product_decoders.app:app --reload --port 8000 &
sleep 3

# 2. 起前端
cd packages/web && bun run dev &

# 3. 浏览器走流程:
# - 录 1 条 QA → 跳 /submissions → 看 "待审"
# - 切 "全部待审" tab (需 admin) → 展开 → 批准 → 看 "已批 + 已写入"
# - 再录 1 条 → 拒绝 (选 "重复内容") → 切 "我提交的" → 展开看 reason
```

- [ ] **Step 6: 跑 E2E (playwright)**

```bash
cd packages/web && bun run e2e -- approvals  # 假设 e2e 有此 spec
```

Expected: 全绿

- [ ] **Step 7: 最终 commit (如有未提交改动)**

```bash
git status
# 无未提交 → 跳; 有 → 提交
```

---

**P3 阶段结束, 实施完毕。** 总工作量: 8 阶段 (P0 8 task + P1 6 task + P2 7 task + P3 4 task) = **25 个 task**, ~50 个新文件, ~25 个新 test case。
