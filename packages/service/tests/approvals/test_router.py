"""FastAPI router 测试 — 8 端点: 鉴权 + 状态过滤 + reject 校验 + retry 限制

- 用 app.dependency_overrides 注入 mock 鉴权 (避免触发真 DB 查 user)
- ApprovalService/Repo 全部 mock, 8 端点走真 router 路径
- lazy import src.middleware.auth (避免 src.auth.__init__ 循环, 跟 src/middleware/auth.py
  模块 docstring 一致)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# --- warm up src.auth 包 (避开 src.middleware.auth 顶层循环) ---
# src.middleware.auth 顶层 import src.auth.account_models → src.auth.__init__ →
# auth_account_router → src.middleware.auth (部分) → CRASH.
# 解决: 先 import 一个 src.auth 子模块, 让 src.middleware.auth 在子模块的 import 链里
# 被正常加载完. 之后再来 import src.middleware.auth 就只是查 sys.modules, 不再重跑顶层.
# 这里 import auth_account_router 是因为它是 src.auth/__init__ 第一个导入的, 等价于
# "走 register_routers 路径" 的最小子集.
import src.auth.auth_account_router  # noqa: F401  # 故意: 循环打破
from src.approvals import router as approvals_router
from src.approvals.models import (
    Approval,
)

# --- lazy auth (避免 src.auth/__init__ 循环) ---


def _get_auth_dep():
    """从 router 拿鉴权依赖 (resolve_user_dep 跟 router 内部注册的是同一函数对象)."""
    from src.approvals.router import resolve_user_dep

    return resolve_user_dep


def _make_user(id_: int, is_admin: bool):
    """懒构造 mock CurrentUser. is_admin → role 派生 ('admin' / 'user')."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        role="admin" if is_admin else "user",
        is_account=is_admin,
    )


@pytest.fixture
def anon_user():
    return _make_user(10, is_admin=False)


@pytest.fixture
def admin_user():
    return _make_user(1, is_admin=True)


# --- mock helpers ---


def _make_approval(
    id: int = 1,
    kind: str = "qa",
    review: str = "pending",
    apply: str = "none",
    submitter_id: int = 10,
) -> Approval:
    """构造 mock Approval (绕过 SQLAlchemy init)."""
    a = MagicMock(spec=Approval)
    a.id = id
    a.kind = kind
    a.payload = '{"dataset_id":"ds1","question":"Q","answer":"A"}'
    a.review_status = review
    a.apply_status = apply
    a.submitter_id = submitter_id
    a.reviewer_id = None
    a.rejection_reason = None
    a.rejection_note = None
    a.error_msg = None
    a.created_at = datetime(2026, 6, 12, 10, 0, 0)
    a.reviewed_at = None
    a.applied_at = None
    return a


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(approvals_router.router)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# --- POST /api/approvals (新建) ---


def test_post_approvals_creates_pending(client: TestClient, app: FastAPI, anon_user) -> None:
    """POST /api/approvals 任何登录用户可调, 返 review=pending."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user
    mock_approval = _make_approval(id=1, review="pending", apply="none")
    with patch("src.approvals.router.ApprovalService") as MockSvc:
        MockSvc.return_value.submit = AsyncMock(return_value=mock_approval)
        res = client.post(
            "/api/approvals",
            json={"kind": "qa", "payload": {"dataset_id": "ds1"}},
        )
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == 1
    assert body["review_status"] == "pending"
    assert body["apply_status"] == "none"


# --- GET /api/approvals (admin 列表) ---


def test_list_approvals_requires_login(client: TestClient) -> None:
    """无 token → resolve_user 抛 401 (走真依赖)."""
    res = client.get("/api/approvals")
    assert res.status_code in (401, 403)


def test_list_approvals_admin_returns_array(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """admin 列出返 list."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    with patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo:
        MockRepo.return_value.list = AsyncMock(return_value=[])
        res = client.get("/api/approvals")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# --- GET /api/approvals/me ---


def test_list_mine_returns_user_own(
    client: TestClient,
    app: FastAPI,
    anon_user,
) -> None:
    """GET /api/approvals/me 返当前用户自己提交的."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user
    with patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo:
        mock_list = AsyncMock(return_value=[])
        MockRepo.return_value.list = mock_list
        res = client.get("/api/approvals/me")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    # 验证传了 submitter_id=10
    _, kwargs = mock_list.call_args
    assert kwargs.get("submitter_id") == anon_user.id


# --- GET /api/approvals/stats ---


def test_stats_returns_counts(client: TestClient, app: FastAPI, admin_user) -> None:
    """GET /api/approvals/stats 返 {pending, applied, failed}."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user

    async def fake_list(*args: Any, **kwargs: Any) -> list[Approval]:
        if kwargs.get("review") == "pending":
            return [_make_approval(id=i) for i in range(3)]
        if kwargs.get("apply") == "applied":
            return [_make_approval(id=i, review="approved", apply="applied") for i in range(5)]
        if kwargs.get("apply") == "failed":
            return [_make_approval(id=i, review="approved", apply="failed") for i in range(2)]
        return []

    with patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo:
        MockRepo.return_value.list = fake_list
        res = client.get("/api/approvals/stats")
    assert res.status_code == 200
    body = res.json()
    assert body["pending"] == 3
    assert body["applied"] == 5
    assert body["failed"] == 2


# --- GET /api/approvals/{id} ---


def test_get_detail_returns_404_if_not_found(
    client: TestClient,
    app: FastAPI,
    anon_user,
) -> None:
    """不存在的 id → 404."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user
    with patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo:
        MockRepo.return_value.get = AsyncMock(return_value=None)
        res = client.get("/api/approvals/999")
    assert res.status_code == 404


def test_get_detail_returns_403_if_not_owner_and_not_admin(
    client: TestClient,
    app: FastAPI,
    anon_user,
) -> None:
    """非 submitter 且非 admin → 403."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user  # id=10
    approval = _make_approval(submitter_id=999)  # 别人提交的
    with patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo:
        MockRepo.return_value.get = AsyncMock(return_value=approval)
        res = client.get("/api/approvals/1")
    assert res.status_code == 403


# --- POST /api/approvals/{id}/approve ---


def test_approve_requires_admin(
    client: TestClient,
    app: FastAPI,
    anon_user,
) -> None:
    """approve 端点需 admin, 非 admin → 403."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user
    res = client.post("/api/approvals/1/approve")
    assert res.status_code == 403


def test_approve_returns_200_with_approval(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """admin + pending → 200 + 触发 BGTask."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    approved = _make_approval(id=1, review="approved", apply="none", submitter_id=10)
    with (
        patch("src.approvals.router.ApprovalService") as MockSvc,
        patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo,
        patch("src.approvals.router.apply_approval") as mock_apply,
    ):
        MockSvc.return_value.approve = AsyncMock(return_value=approved)
        MockRepo.return_value = MagicMock()
        res = client.post("/api/approvals/1/approve")
    assert res.status_code == 200
    assert res.json()["review_status"] == "approved"
    # BGTask 触发 (TestClient 同步跑完所有 background)
    assert mock_apply.called


# --- POST /api/approvals/{id}/reject ---


def test_reject_missing_reason_returns_422(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """reject 缺 reason → 422 (Pydantic 校验)."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    res = client.post("/api/approvals/1/reject", json={})
    assert res.status_code == 422


def test_reject_other_without_note_returns_422(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """reason=other 但缺 note → 422 (业务校验)."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    res = client.post("/api/approvals/1/reject", json={"reason": "other"})
    assert res.status_code == 422


def test_reject_returns_200_with_approval(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """admin + 合法 reason → 200 + rejected 终态."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    rejected = _make_approval(id=1, review="rejected", apply="none", submitter_id=10)
    with patch("src.approvals.router.ApprovalService") as MockSvc:
        MockSvc.return_value.reject = AsyncMock(return_value=rejected)
        res = client.post(
            "/api/approvals/1/reject",
            json={"reason": "duplicate", "note": "已存在"},
        )
    assert res.status_code == 200
    assert res.json()["review_status"] == "rejected"


# --- POST /api/approvals/{id}/retry ---


def test_retry_requires_admin(
    client: TestClient,
    app: FastAPI,
    anon_user,
) -> None:
    """retry 端点需 admin, 非 admin → 403."""
    app.dependency_overrides[_get_auth_dep()] = lambda: anon_user
    res = client.post("/api/approvals/1/retry")
    assert res.status_code == 403


def test_retry_returns_200_with_approval(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """admin + (approved, failed) → 200 + 触发 BGTask."""
    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    retried = _make_approval(id=1, review="approved", apply="none", submitter_id=10)
    with (
        patch("src.approvals.router.ApprovalService") as MockSvc,
        patch("src.approvals.router.SqlAlchemyApprovalRepo") as MockRepo,
        patch("src.approvals.router.apply_approval") as mock_apply,
    ):
        MockSvc.return_value.retry = AsyncMock(return_value=retried)
        MockRepo.return_value = MagicMock()
        res = client.post("/api/approvals/1/retry")
    assert res.status_code == 200
    assert res.json()["apply_status"] == "none"
    assert mock_apply.called


def test_retry_invalid_state_returns_409(
    client: TestClient,
    app: FastAPI,
    admin_user,
) -> None:
    """retry 状态不合法 (非 approved+failed) → 409."""
    from src.approvals.service import InvalidStateError

    app.dependency_overrides[_get_auth_dep()] = lambda: admin_user
    with patch("src.approvals.router.ApprovalService") as MockSvc:
        MockSvc.return_value.retry = AsyncMock(
            side_effect=InvalidStateError("not in (approved, failed)"),
        )
        res = client.post("/api/approvals/1/retry")
    assert res.status_code == 409


# --- 真集成测试 (无 dependency_overrides, 走真 RAG_DEV_AUTH pipeline) ---
#
# 目的: 防 [feedback-tdd-test-real-behavior] 教训 — 上面 13 个 unit test 全用
# app.dependency_overrides 跳过真 _resolve_user, 跑 39 测试全绿, 但生产 smoke 时
# 8 端点全 AttributeError (因为 _resolve_user 返函数本身, 不返 CurrentUser).
# 下面测试用 RAG_DEV_AUTH=true + 真 create_app() + 不 override, 验真实 wiring.
# (2026-06-29) 删除: 历史 bug 早已修, 真集成场景在 dev mode E2E 覆盖. 跟项目 100% mock 规约不一致.
