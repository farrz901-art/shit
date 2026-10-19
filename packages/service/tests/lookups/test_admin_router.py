"""admin_router 7 端点测试 (2026-06-19 lookup spec Task 6, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis. 此处:
- patch LookupService 静态方法 (业务)
- patch safety_guard.check_all 跳过 6 层防御 (auth/role 测除外, 那些测真实 raise)
- patch log_dict_change + lookup_cache.invalidate (旁路, 不连真 DB)
- patch session_scope (admin_router 里 create_dictionary 自己拼 insert, 需 mock)
- TestClient + dependency_overrides[require_super_admin] 模拟 super_admin 登录
- @audited decorator 内的 _persist_audit 永不抛, 无需 patch

测试矩阵 (15):
1. test_post_item_requires_super_admin          — 非 super_admin 403
2. test_post_item_creates_and_returns           — happy path 201
3. test_post_item_409_on_duplicate               — LookupSafetyError 409
4. test_patch_item_updates_label                 — happy path 200
5. test_patch_item_404_on_missing                — LookupNotFoundError 404
6. test_delete_item_soft_deletes_with_force      — confirm token + force=true 跳过引用
7. test_delete_item_requires_confirm_token       — 缺 X-Confirm-Token 412
8. test_delete_item_blocks_when_referenced       — 引用>0 → 409 (force=false)
9. test_post_dict_creates_new_dictionary         — POST /api/admin/dicts 201
10. test_patch_dict_updates_metadata             — PATCH /api/admin/dicts/{code} 200
11. test_get_audit_returns_entries               — 返 audit_logs 行
12. test_confirm_token_returns_16_char_hex        — 签发 token
13. test_confirm_token_requires_super_admin      — 403
14. test_post_dict_409_on_duplicate_code         — code 冲突 409
15. test_delete_item_invalid_token_format        — 格式错 412
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---- helpers ----


def _make_user(id_: int = 1, role: str = "super_admin") -> Any:
    """构造 mock CurrentUser (id_/role 决定 super_admin 守卫)."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        is_account=True,
        role=role,
        email=f"admin{id_}@x.com",
    )


def _valid_confirm_token(user_id: int) -> str:
    """生成当前小时有效 confirm token (16 字符 hex, 跟 safety_guard 一致)."""
    now = datetime.now(UTC)
    secret = f"dict-admin-confirm:{user_id}"
    bucket = now.strftime("%Y%m%d%H")
    return hashlib.sha256(f"{secret}:{bucket}".encode()).hexdigest()[:16]


def _build_app_with_user(user_id: int = 1, role: str = "super_admin") -> tuple[TestClient, Any]:
    """构造 FastAPI app + TestClient + mock super_admin 注入, 返 (client, mock_user)."""
    from src.lookups.admin_router import router as admin_router
    from src.permissions.guards import require_super_admin

    mock_user = _make_user(id_=user_id, role=role)
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[require_super_admin] = lambda: mock_user
    return TestClient(app), mock_user


# ---- mock safety_guard 装饰器 (用上下文 manager 让 router 跳过 6 层) ----


def _patch_safety_guard_pass():
    """让 safety_guard.check_all 走 no-op (跳过 6 层, 业务函数单独测)."""
    return patch(
        "src.lookups.admin_router.safety_guard.check_all",
        new=AsyncMock(return_value=None),
    )


def _patch_safety_guard_raise(http_status: int, detail: str):
    """让 safety_guard.check_all raise LookupSafetyError, 模拟任一层失败."""

    async def _raise(**kwargs):
        from src.lookups.exceptions import LookupSafetyError

        raise LookupSafetyError(http_status, detail)

    return patch("src.lookups.admin_router.safety_guard.check_all", side_effect=_raise)


def _patch_session_scope_noop():
    """mock session_scope, 让 create_dictionary 走通 (不连 PG)."""
    noop = MagicMock()
    noop.flush = MagicMock()
    noop.add = MagicMock()

    @contextmanager
    def _cm():
        # 第一次 (查重): 返 None (字典不存在 → 走 insert 路径)
        # 用 side_effect 顺序处理
        yield noop

    return patch("src.lookups.admin_router.session_scope", _cm)


# ==================== POST item (3 测) ====================


def test_post_item_requires_super_admin():
    """非 super_admin → 403 (走 require_super_admin 守卫, SafetyGuard 不跑)."""
    from src.lookups.admin_router import router as admin_router

    app = FastAPI()
    app.include_router(admin_router)
    # 不设置 dependency_overrides[require_super_admin], 用普通 user 走守卫
    normal_user = _make_user(id_=2, role="user")
    from src.permissions.guards import require_super_admin

    app.dependency_overrides[require_super_admin] = lambda: normal_user

    client = TestClient(app)
    resp = client.post(
        "/api/admin/dicts/reject_reason/items",
        json={"key": "test", "label_zh": "测试", "label_en": "Test"},
    )

    assert resp.status_code == 403
    assert "super_admin" in resp.json()["detail"].lower()


def test_post_item_creates_and_returns():
    """happy path: POST item → 201 + 返新 item."""
    from src.lookups import service as svc

    expected = {
        "key": "qa_refine",
        "label_zh": "QA 精修",
        "label_en": "QA Refine",
        "sort": 6,
        "is_active": True,
        "description": None,
        "metadata_json": {"color": "blue"},
    }

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "create_item", return_value=expected) as mock_create,
    ):
        client, _ = _build_app_with_user()
        resp = client.post(
            "/api/admin/dicts/approval_kind/items",
            json={
                "key": "qa_refine",
                "label_zh": "QA 精修",
                "label_en": "QA Refine",
                "sort": 6,
                "metadata_json": {"color": "blue"},
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["key"] == "qa_refine"
    assert data["label_zh"] == "QA 精修"
    assert data["label_en"] == "QA Refine"
    assert data["metadata_json"] == {"color": "blue"}
    # 验证 LookupService.create_item 被调, dict_code 透传, actor_id=1
    assert mock_create.call_args.args[0] == "approval_kind"
    assert mock_create.call_args.kwargs["actor_id"] == 1
    assert mock_create.call_args.kwargs["actor"] == "admin1@x.com"


def test_post_item_409_on_duplicate():
    """key 已存在 → LookupSafetyError 409 (router 翻译成 HTTPException)."""
    from src.lookups import service as svc
    from src.lookups.exceptions import LookupSafetyError

    async def _raise(*args, **kwargs):
        raise LookupSafetyError(409, "item 'approval_kind:qa_refine' already exists")

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "create_item", side_effect=_raise),
    ):
        client, _ = _build_app_with_user()
        resp = client.post(
            "/api/admin/dicts/approval_kind/items",
            json={"key": "qa_refine", "label_zh": "QA 精修", "label_en": "QA Refine"},
        )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


# ==================== PATCH item (2 测) ====================


def test_patch_item_updates_label():
    """happy path: PATCH item label/sort → 200 + 返更新后 item."""
    from src.lookups import service as svc

    expected = {
        "key": "duplicate",
        "label_zh": "完全重复",
        "label_en": "Full Duplicate",
        "sort": 1,
        "is_active": True,
        "description": None,
        "metadata_json": None,
    }

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "patch_item", return_value=expected) as mock_patch,
    ):
        client, _ = _build_app_with_user()
        resp = client.patch(
            "/api/admin/dicts/reject_reason/items/duplicate",
            json={"label_zh": "完全重复", "label_en": "Full Duplicate", "sort": 1},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "duplicate"
    assert data["label_zh"] == "完全重复"
    # 验证 router 透传 (dict_code, key, payload) 给 service
    assert mock_patch.call_args.args[:2] == ("reject_reason", "duplicate")
    assert mock_patch.call_args.kwargs["actor_id"] == 1


def test_patch_item_404_on_missing():
    """item 不存在 → LookupNotFoundError 404."""
    from src.lookups import service as svc
    from src.lookups.exceptions import LookupNotFoundError

    async def _raise(*args, **kwargs):
        raise LookupNotFoundError("item 'reject_reason:nonexistent' not found")

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "patch_item", side_effect=_raise),
    ):
        client, _ = _build_app_with_user()
        resp = client.patch(
            "/api/admin/dicts/reject_reason/items/nonexistent",
            json={"label_zh": "X"},
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ==================== DELETE item (4 测) ====================


def test_delete_item_soft_deletes_with_force():
    """DELETE item + X-Confirm-Token + ?force=true → 200 (跳过引用检查)."""
    from src.lookups import service as svc

    expected = {
        "key": "duplicate",
        "is_active": False,
        "deprecated_at": datetime(2026, 6, 19, 10, 0, 0, tzinfo=UTC),
        "forced": True,
    }

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "soft_delete_item", return_value=expected) as mock_del,
    ):
        client, mock_user = _build_app_with_user(user_id=42)
        token = _valid_confirm_token(42)
        resp = client.delete(
            "/api/admin/dicts/reject_reason/items/duplicate?force=true",
            headers={"X-Confirm-Token": token},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "duplicate"
    assert data["is_active"] is False
    assert data["forced"] is True
    # 验证 force=True 透传给 service
    assert mock_del.call_args.kwargs["force"] is True
    assert mock_del.call_args.args[:2] == ("reject_reason", "duplicate")


def test_delete_item_requires_confirm_token():
    """缺 X-Confirm-Token → SafetyGuard 第 3 层 raise 412."""
    with _patch_safety_guard_raise(412, "confirm token required for delete"):
        client, _ = _build_app_with_user()
        resp = client.delete("/api/admin/dicts/reject_reason/items/duplicate")

    assert resp.status_code == 412
    assert "confirm token" in resp.json()["detail"].lower()


def test_delete_item_blocks_when_referenced():
    """force=false 时引用>0 → SafetyGuard 第 4 层 raise 409."""
    with _patch_safety_guard_raise(
        409,
        "item 'reject_reason:duplicate' still referenced by 12 rows; soft-delete refused.",
    ):
        client, mock_user = _build_app_with_user(user_id=42)
        token = _valid_confirm_token(42)
        resp = client.delete(
            "/api/admin/dicts/reject_reason/items/duplicate",
            headers={"X-Confirm-Token": token},
        )

    assert resp.status_code == 409
    assert "still referenced" in resp.json()["detail"]


def test_delete_item_invalid_token_format():
    """token 格式错 (非 16 hex) → 412 (SafetyGuard raise 模拟)."""
    with _patch_safety_guard_raise(412, "invalid confirm token format (must be 16 hex chars)"):
        client, _ = _build_app_with_user()
        resp = client.delete(
            "/api/admin/dicts/reject_reason/items/duplicate",
            headers={"X-Confirm-Token": "NOT_HEX_TOO_SHORT"},
        )

    assert resp.status_code == 412


# ==================== POST / PATCH dict (3 测) ====================


def test_post_dict_creates_new_dictionary():
    """POST /api/admin/dicts → 201 + 返新字典 (含 version=1, is_active=True)."""

    # mock session_scope 返回 mock session, 查重返 None (字典不存在) → 走 insert
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None  # 不存在

    @contextmanager
    def _cm():
        yield mock_session

    with (
        _patch_safety_guard_pass(),
        patch("src.lookups.admin_router.session_scope", _cm),
        patch("src.lookups.admin_router.log_dict_change"),
        patch("src.lookups.admin_router.lookup_cache.invalidate", new=AsyncMock()),
    ):
        client, _ = _build_app_with_user()
        resp = client.post(
            "/api/admin/dicts",
            json={
                "code": "new_dict",
                "label_zh": "新字典",
                "label_en": "New Dict",
                "description": "测试字典",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "new_dict"
    assert data["label_zh"] == "新字典"
    assert data["version"] == 1
    assert data["is_active"] is True
    assert data["is_readonly"] is False


def test_post_dict_409_on_duplicate_code():
    """code 已存在 → 409 (查重返 Dictionary, router raise LookupSafetyError 409)."""
    from src.lookups.models import Dictionary

    existing_dict = MagicMock(spec=Dictionary)
    existing_dict.code = "old_dict"

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing_dict  # 已存在

    @contextmanager
    def _cm():
        yield mock_session

    with (
        _patch_safety_guard_pass(),
        patch("src.lookups.admin_router.session_scope", _cm),
    ):
        client, _ = _build_app_with_user()
        resp = client.post(
            "/api/admin/dicts",
            json={"code": "old_dict", "label_zh": "X", "label_en": "Y"},
        )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_patch_dict_updates_metadata():
    """PATCH /api/admin/dicts/{code} → 200 + 返更新后字典."""
    from src.lookups import service as svc

    expected = {
        "code": "reject_reason",
        "label_zh": "拒绝原因 v2",
        "label_en": "Reject Reason v2",
        "description": "新说明",
        "version": 2,
        "is_active": True,
        "is_readonly": False,
    }

    with (
        _patch_safety_guard_pass(),
        patch.object(svc.LookupService, "patch_dict", return_value=expected) as mock_patch,
    ):
        client, _ = _build_app_with_user()
        resp = client.patch(
            "/api/admin/dicts/reject_reason",
            json={"label_zh": "拒绝原因 v2", "label_en": "Reject Reason v2"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "reject_reason"
    assert data["label_zh"] == "拒绝原因 v2"
    assert data["version"] == 2
    # 验证 router 透传 (dict_code, payload)
    assert mock_patch.call_args.args[0] == "reject_reason"
    assert "label_zh" in mock_patch.call_args.args[1]


# ==================== Audit / Token (3 测) ====================


def test_get_audit_returns_entries():
    """GET /api/admin/dicts/{code}/audit 返 audit_logs 行."""
    from datetime import UTC, datetime

    from src.db.models.audit_log import AuditLog

    now = datetime.now(UTC)
    mock_row_1 = MagicMock(spec=AuditLog)
    mock_row_1.id = 1
    mock_row_1.ts = now
    mock_row_1.actor_id = 1
    mock_row_1.action = "dictionary.item.create"
    mock_row_1.target_id = "reject_reason:duplicate"
    mock_row_1.before = None
    mock_row_1.after = {"key": "duplicate", "label_zh": "重复"}
    mock_row_1.ip = "127.0.0.1"
    mock_row_1.meta = {"actor_display": "admin@x.com"}

    mock_row_2 = MagicMock(spec=AuditLog)
    mock_row_2.id = 2
    mock_row_2.ts = now
    mock_row_2.actor_id = 1
    mock_row_2.action = "dictionary.item.patch"
    mock_row_2.target_id = "reject_reason:duplicate"
    mock_row_2.before = {"label_zh": "重复"}
    mock_row_2.after = {"label_zh": "完全重复"}
    mock_row_2.ip = "127.0.0.1"
    mock_row_2.meta = {"actor_display": "admin@x.com"}

    mock_session = MagicMock()
    mock_session.execute.return_value.scalars.return_value.all.return_value = [
        mock_row_1,
        mock_row_2,
    ]

    @contextmanager
    def _cm():
        yield mock_session

    with patch("src.lookups.admin_router.session_scope", _cm):
        client, _ = _build_app_with_user()
        resp = client.get("/api/admin/dicts/reject_reason/audit")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["entries"]) == 2
    assert data["entries"][0]["action"] == "dictionary.item.create"
    assert data["entries"][0]["target_id"] == "reject_reason:duplicate"
    assert data["entries"][0]["actor_display"] == "admin@x.com"
    assert data["entries"][1]["action"] == "dictionary.item.patch"


def test_confirm_token_returns_16_char_hex():
    """POST /api/admin/dicts/confirm-token 返 16 字符 hex token + valid_until."""
    client, mock_user = _build_app_with_user(user_id=42)
    resp = client.post("/api/admin/dicts/confirm-token")

    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert len(data["token"]) == 16
    # 验证 token 跟 sha256(secret:bucket)[:16] 一致
    now = datetime.now(UTC)
    secret = f"dict-admin-confirm:{mock_user.id}"
    bucket = now.strftime("%Y%m%d%H")
    expected = hashlib.sha256(f"{secret}:{bucket}".encode()).hexdigest()[:16]
    assert data["token"] == expected
    # 验证 valid_until 是 ISO 格式
    assert "valid_until" in data
    # 验证 ISO 字符串能 parse
    datetime.fromisoformat(data["valid_until"])


def test_confirm_token_requires_super_admin():
    """非 super_admin 调 confirm-token → 403 (require_super_admin 守卫).

    不 override require_super_admin (否则会替换掉守卫逻辑), 只 override
    resolve_user, 让 require_super_admin 走真实检查.
    """
    from src.lookups.admin_router import router as admin_router
    from src.middleware.auth import resolve_user

    normal_user = _make_user(id_=2, role="user")

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[resolve_user] = lambda: normal_user

    client = TestClient(app)
    resp = client.post("/api/admin/dicts/confirm-token")

    assert resp.status_code == 403
    assert "super_admin" in resp.json()["detail"].lower()
