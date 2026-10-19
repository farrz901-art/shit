"""/api/evaluate/* 路由测试 (2026-06-16 重写 100% mock, 11 tests)

覆盖 src/eval/router.py 的 5 个端点:
- GET    /api/evaluate/template
- GET    /api/evaluate/runs
- POST   /api/evaluate/runs
- GET    /api/evaluate/runs/{id}
- POST   /api/evaluate/runs/{id}/cancel

100% mock 模式:
- dependency_overrides[resolve_user] 注入 CurrentUser
- dependency_overrides[get_session] 注入 mock Session
- patch src.eval.router.session_scope 替 mock (upload 用 session_scope 直调)
- monkeypatch runner.run_evaluation + asyncio.create_task 不真跑后台

0 真实 DB 连接, 0 dev DB writes.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.models import User
from src.eval.models import Evaluation, EvaluationSample
from src.eval.router import router as eval_router
from src.middleware.auth import CurrentUser, resolve_user
from src.storage.session import get_session
from src.utils.timezone import HKT

# ---------------- helpers ----------------


def _make_user_row(
    id: int = 1,
    public_token: str = "tok-1",
    account_id: int | None = None,
) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = id
    u.public_token = public_token
    u.account_id = account_id
    return u


def _make_eval_row(
    id: int = 1,
    user_id: int = 1,
    status: str = "completed",
    dataset_name: str = "x.csv",
    total_samples: int = 1,
    successful: int = 1,
    failed: int = 0,
    avg_metrics: dict[str, Any] | None = None,
    duration_seconds: float = 1.0,
    concurrency: int = 5,
    error_message: str | None = None,
    finished_at: datetime | None = None,
) -> MagicMock:
    e = MagicMock(spec=Evaluation)
    e.id = id
    e.user_id = user_id
    e.status = status
    e.dataset_name = dataset_name
    e.dataset_path = None
    e.total_samples = total_samples
    e.successful = successful
    e.failed = failed
    e.concurrency = concurrency
    e.avg_metrics = avg_metrics or {}
    e.duration_seconds = duration_seconds
    e.error_message = error_message
    e.created_at = datetime.now(HKT)
    e.finished_at = finished_at
    e.samples = []
    return e


def _current_user(id: int = 1, is_admin: bool = False, email: str | None = None) -> CurrentUser:
    return CurrentUser(
        id=id,
        public_token=f"tok-{id}",
        role="admin" if is_admin else "user",  # is_admin 是 property, 从 role 派生
        is_account=True,
        account_id=id,
        email=email or f"u{id}@x.com",
        is_active=True,
    )


@contextmanager
def _patch_router_session_scope(mock_session: MagicMock):
    with patch("src.eval.router.session_scope") as p:
        p.return_value.__enter__.return_value = mock_session
        p.return_value.__exit__.return_value = False
        yield mock_session


def _make_app(current_user: CurrentUser, mock_session: MagicMock) -> FastAPI:
    """FastAPI app + 注入 mock 当前用户 + mock session"""
    app = FastAPI()
    app.include_router(eval_router)
    app.dependency_overrides[resolve_user] = lambda: current_user
    app.dependency_overrides[get_session] = lambda: mock_session
    return app


def _client(current_user: CurrentUser, mock_session: MagicMock) -> TestClient:
    return TestClient(_make_app(current_user, mock_session))


# ---------------- template ----------------


def test_template_endpoint_no_auth():
    """GET /template 不需要鉴权, 内容是 CSV header + 至少 1 行"""
    mock_session = MagicMock()  # get_session override 用, 实际 template 不查 DB
    client = _client(_current_user(), mock_session)
    r = client.get("/api/evaluate/template")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.startswith("question,ground_truth")


# ---------------- list runs ----------------


def test_list_runs_requires_auth():
    """没 override resolve_user → 真实链路 → 401 (no token)"""
    app = FastAPI()
    app.include_router(eval_router)
    client = TestClient(app)
    r = client.get("/api/evaluate/runs")
    assert r.status_code == 401


def test_list_runs_returns_empty_for_new_user():
    """新用户没评估 → 空列表"""
    mock_session = MagicMock()
    mock_session.query.return_value.order_by.return_value.all.return_value = []
    client = _client(_current_user(id=1), mock_session)
    r = client.get("/api/evaluate/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_list_runs_admin_returns_all():
    """admin 列表不按 user_id 过滤 (覆盖 admin 分支)"""
    eval_alice = _make_eval_row(id=10, user_id=2, dataset_name="b.csv")
    mock_session = MagicMock()
    mock_session.query.return_value.order_by.return_value.all.return_value = [eval_alice]
    client = _client(_current_user(id=1, is_admin=True), mock_session)
    r = client.get("/api/evaluate/runs")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------------- upload (POST /runs) ----------------


def test_upload_creates_pending_evaluation(monkeypatch):
    """上传 CSV → 落 pending + 返 id (mock 后台, 不真跑)"""
    import asyncio

    from src.eval import runner

    # 后台任务改成同步空跑 (避免 schedule 真跑)
    async def fake_run(**_):
        return None

    monkeypatch.setattr(runner, "run_evaluation", fake_run)

    # 阻止真后台 create_task: 关掉 coroutine (避免 RuntimeWarning) + 不调度
    def _discard_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", _discard_task)

    # session_scope mock: add(eval) + flush → setattr id
    mock_session = MagicMock()

    def _fake_flush():
        # session.add() 拿最后 add 的对象设 id
        if mock_session.add.called:
            added = mock_session.add.call_args[0][0]
            if hasattr(added, "id") and added.id is None or added.id == 0:
                added.id = 42

    mock_session.flush.side_effect = _fake_flush

    client = _client(_current_user(id=1), mock_session)
    csv_bytes = b"question,ground_truth\nQ1,A1\nQ2,A2\n"
    with _patch_router_session_scope(mock_session):
        r = client.post(
            "/api/evaluate/runs",
            files={"file": ("t.csv", csv_bytes, "text/csv")},
            data={"concurrency": "3"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 42
    assert body["status"] == "pending"
    # session.add 被调 (创 Evaluation 行)
    assert mock_session.add.called
    added = mock_session.add.call_args[0][0]
    assert added.user_id == 1
    assert added.dataset_name == "t.csv"
    assert added.concurrency == 3
    assert added.total_samples == 2


def test_upload_rejects_oversize():
    """> 5MB → 400"""
    mock_session = MagicMock()
    client = _client(_current_user(id=1), mock_session)
    big = b"question,ground_truth\n" + b"x," * (3 * 1024 * 1024) + b"\n"
    r = client.post(
        "/api/evaluate/runs",
        files={"file": ("big.csv", big, "text/csv")},
        data={"concurrency": "3"},
    )
    assert r.status_code == 400
    assert "5MB" in r.json()["detail"]


# ---------------- GET /runs/{id} ----------------


def test_get_run_returns_with_samples():
    """GET /runs/{id} 返 evaluation + samples (按 index 排序)"""
    s0 = MagicMock(spec=EvaluationSample)
    s0.id = 100
    s0.index = 0
    s0.question = "Q1"
    s0.answer = "A1"
    s0.ground_truth = "g1"
    s0.contexts = ["c"]
    s0.sources = None
    s0.metrics = {"faithfulness": 0.9}
    s0.error = None
    s0.duration_ms = 100
    s1 = MagicMock(spec=EvaluationSample)
    s1.id = 101
    s1.index = 1
    s1.question = "Q2"
    s1.answer = "A2"
    s1.ground_truth = "g2"
    s1.contexts = ["c2"]
    s1.sources = None
    s1.metrics = {"faithfulness": 0.8}
    s1.error = None
    s1.duration_ms = 200

    eval_row = _make_eval_row(
        id=42,
        user_id=1,
        status="completed",
        avg_metrics={"faithfulness": 0.9},
    )
    eval_row.samples = [s1, s0]  # 乱序, 验证 router 按 index 排序

    mock_session = MagicMock()
    mock_session.get.return_value = eval_row
    client = _client(_current_user(id=1), mock_session)

    r = client.get("/api/evaluate/runs/42")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 42
    assert body["status"] == "completed"
    assert len(body["samples"]) == 2
    # 验证按 index 排序: 0, 1
    assert body["samples"][0]["index"] == 0
    assert body["samples"][1]["index"] == 1


def test_get_run_404_for_other_user():
    """别人的 evaluation → 404 (避免泄露存在性)"""
    eval_other = _make_eval_row(id=42, user_id=2)
    mock_session = MagicMock()
    mock_session.get.return_value = eval_other
    client = _client(_current_user(id=1), mock_session)

    r = client.get("/api/evaluate/runs/42")
    assert r.status_code == 404


def test_get_run_admin_sees_all():
    """admin 能看任何用户的 evaluation"""
    eval_alice = _make_eval_row(id=42, user_id=2)
    mock_session = MagicMock()
    mock_session.get.return_value = eval_alice
    client = _client(_current_user(id=1, is_admin=True), mock_session)

    r = client.get("/api/evaluate/runs/42")
    assert r.status_code == 200
    assert r.json()["id"] == 42


# ---------------- cancel ----------------


def test_cancel_returns_true_when_registered():
    """已注册的 evaluation → cancel 触发 event.set → True.

    (2026-07-09) request_cancel 内部 session_scope 持久化, 测试必须 mock,
    否则连真 PG → 'too many clients already' (CLAUDE.md 强制测试 100% mock).
    """
    import asyncio

    from src.eval import runner_registry

    runner_registry.register_cancel_event(123, asyncio.Event())
    mock_session = MagicMock()
    mock_session.get.return_value = None  # 不查 DB 也行, 取消不依赖行存在
    client = _client(_current_user(id=1), mock_session)
    # (2026-07-09) runner_registry.request_cancel 调 session_scope 写 cancel_requested_at,
    # mock 掉防连真 PG
    rr_session = MagicMock()
    rr_session.get.return_value = None
    rr_ctx = MagicMock()
    rr_ctx.__enter__.return_value = rr_session
    rr_ctx.__exit__.return_value = False
    with patch("src.eval.runner_registry.session_scope", return_value=rr_ctx):
        r = client.post("/api/evaluate/runs/123/cancel")
    assert r.status_code == 200
    assert r.json() == {"cancelled": True}
    runner_registry.unregister_cancel_event(123)


def test_cancel_returns_false_when_not_registered():
    """未注册的 → False (已结束 / 从未注册). request_cancel 走 else 分支不调 session_scope, 无需 mock."""
    mock_session = MagicMock()
    mock_session.get.return_value = None
    client = _client(_current_user(id=1), mock_session)

    r = client.post("/api/evaluate/runs/99999/cancel")
    assert r.status_code == 200
    assert r.json() == {"cancelled": False}


# ---------------- dev auth ----------------


def test_no_token_dev_mode_returns_200(monkeypatch):
    """RAG_DEV_AUTH=true 时无 token 走 dev user 鉴权, 能访问列表"""
    monkeypatch.setenv("RAG_DEV_AUTH", "true")
    mock_session = MagicMock()
    mock_session.query.return_value.order_by.return_value.all.return_value = []
    # _ensure_dev_user() 调 session_scope 创 dev user, 需要 mock 掉
    mw_ctx = MagicMock()
    mw_ctx.__enter__.return_value = mock_session
    mw_ctx.__exit__.return_value = False
    app = FastAPI()
    app.include_router(eval_router)
    app.dependency_overrides[get_session] = lambda: mock_session
    with patch("src.middleware.auth.session_scope", return_value=mw_ctx):
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/evaluate/runs")
    assert r.status_code == 200
    assert r.json() == []
