"""SafetyGuard 6 层防御测试 (2026-06-19 lookup spec §五, 模式 1 mock)

CLAUDE.md 规范: 测试禁止连真 PG / Redis.
- L1-L5 用 mock (查 lookup_cache._l1_data, 测 cache 同步 helper)
- L6 (rate_limit) mock rate_limiter.check_and_increment, 0 真实 Redis 依赖
- L4 (引用检查) mock session_scope, 0 真实 PG 依赖

测试矩阵 (8):
1. test_layer1_role_check_blocks_non_super_admin      — 非 super_admin → 403
2. test_layer2_env_readonly_blocks                    — DICTIONARY_READONLY=true → 403
3. test_layer2_dict_readonly_blocks                   — 字典 is_readonly → 403
4. test_layer3_delete_requires_confirm_token          — delete 无 token → 412
5. test_layer3_invalid_confirm_token_format           — token 格式错 → 412
6. test_layer4_delete_blocks_when_referenced          — 引用>0 → 409
7. test_layer5_version_mismatch                       — 版本不匹配 → 412
8. test_layer6_rate_limit_exceeded                    — rate_limit 触发 → 429
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.middleware.auth import CurrentUser


def _user(role: str = "super_admin", user_id: int = 42) -> CurrentUser:
    """构造 mock CurrentUser."""
    return CurrentUser(
        id=user_id,
        public_token="test-token",
        role=role,
        is_account=True,
        email=f"admin{user_id}@example.com",
    )


def _set_l1(readonly_flags: dict[str, bool] | None = None, versions: dict[str, int] | None = None):
    """设置 LookupCache L1 数据 (供 L2 / L5 测试用)."""
    from src.lookups.cache import lookup_cache

    lookup_cache._l1_data = {}
    if readonly_flags:
        for code, ro in readonly_flags.items():
            lookup_cache._l1_data[code] = {
                "label_zh": "测试",
                "label_en": "Test",
                "version": versions.get(code, 1) if versions else 1,
                "is_readonly": ro,
                "items": [],
            }
    elif versions:
        for code, v in versions.items():
            lookup_cache._l1_data[code] = {
                "label_zh": "测试",
                "label_en": "Test",
                "version": v,
                "is_readonly": False,
                "items": [],
            }


def _valid_confirm_token(user: CurrentUser) -> str:
    """生成当前小时的有效 confirm token (16 字符 hex, 跟 safety_guard._check_confirm_token 同步)."""
    now = datetime.now(UTC)
    secret = f"dict-admin-confirm:{user.id}"
    bucket = now.strftime("%Y%m%d%H")
    return hashlib.sha256(f"{secret}:{bucket}".encode()).hexdigest()[:16]


# ---- 第 1 层: 鉴权 ----


@pytest.mark.asyncio
async def test_layer1_role_check_blocks_non_super_admin():
    """非 super_admin 用户 → LookupSafetyError 403."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="user")  # 普通用户
    _set_l1()

    with pytest.raises(LookupSafetyError) as exc:
        await safety_guard.check_all(
            action="patch",
            dict_code="reject_reason",
            key="duplicate",
            user=user,
            confirm_token=None,
            payload={},
        )
    assert exc.value.http_status == 403
    assert "super_admin" in exc.value.detail


# ---- 第 2 层: 只读 ----


@pytest.mark.asyncio
async def test_layer2_env_readonly_blocks(monkeypatch):
    """env DICTIONARY_READONLY=true → 403 (env 优先于字典级)."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    monkeypatch.setenv("DICTIONARY_READONLY", "true")
    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": False})  # 字典级不是 readonly

    with pytest.raises(LookupSafetyError) as exc:
        await safety_guard.check_all(
            action="patch",
            dict_code="reject_reason",
            key="duplicate",
            user=user,
            confirm_token=None,
            payload={},
        )
    assert exc.value.http_status == 403
    assert "DICTIONARY_READONLY" in exc.value.detail


@pytest.mark.asyncio
async def test_layer2_dict_readonly_blocks(monkeypatch):
    """字典级 is_readonly=True → 403."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    monkeypatch.delenv("DICTIONARY_READONLY", raising=False)
    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": True})

    with pytest.raises(LookupSafetyError) as exc:
        await safety_guard.check_all(
            action="patch",
            dict_code="reject_reason",
            key="duplicate",
            user=user,
            confirm_token=None,
            payload={},
        )
    assert exc.value.http_status == 403
    assert "readonly" in exc.value.detail


# ---- 第 3 层: 二次确认 ----


@pytest.mark.asyncio
async def test_layer3_delete_requires_confirm_token():
    """delete 缺 confirm_token → 412."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": False})

    # patch _check_business_references 避免 DB, 让 token 检查先触发
    with (
        patch.object(safety_guard, "_check_business_references", new=AsyncMock()),
        patch("src.lookups.safety_guard.check_and_increment", new=AsyncMock(return_value=(True, 1))),
    ):
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="delete",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token=None,  # 缺 token
                payload={},
            )
    assert exc.value.http_status == 412
    assert "confirm token required" in exc.value.detail


@pytest.mark.asyncio
async def test_layer3_invalid_confirm_token_format():
    """token 长度/字符错 → 412."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": False})

    with (
        patch.object(safety_guard, "_check_business_references", new=AsyncMock()),
        patch("src.lookups.safety_guard.check_and_increment", new=AsyncMock(return_value=(True, 1))),
    ):
        # 长度错 (15 chars)
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="delete",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token="0123456789abcde",  # 15 chars
                payload={},
            )
        assert exc.value.http_status == 412
        assert "16 hex chars" in exc.value.detail

        # 字符错 (含非 hex)
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="delete",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token="ZZZZZZZZZZZZZZZZ",  # 16 chars but 非 hex
                payload={},
            )
        assert exc.value.http_status == 412


# ---- 第 4 层: 引用检查 ----


@pytest.mark.asyncio
async def test_layer4_delete_blocks_when_referenced():
    """delete 时引用>0 → 409 (force=False)."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": False})

    # mock session.execute scalar() → 12 (mock 引用行数)
    mock_session = MagicMock()

    @contextmanager
    def _cm():
        yield mock_session

    mock_execute_result = MagicMock()
    mock_execute_result.scalar.return_value = 12  # 12 个 approvals 引用
    mock_session.execute.return_value = mock_execute_result

    valid_token = _valid_confirm_token(user)

    with (
        patch("src.lookups.safety_guard.session_scope", lambda: _cm()),
        patch(
            "src.lookups.safety_guard.check_and_increment",
            new=AsyncMock(return_value=(True, 1)),
        ),
    ):
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="delete",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token=valid_token,
                payload={},
                force=False,  # 不绕过 → 触发引用检查
            )
    assert exc.value.http_status == 409
    assert "still referenced by 12" in exc.value.detail


# ---- 第 5 层: 版本 ----


@pytest.mark.asyncio
async def test_layer5_version_mismatch():
    """payload.expected_version 不匹配 → 412."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="super_admin")
    # L1 里 reject_reason version=1, 但 payload 期望 999 → 不匹配
    _set_l1(readonly_flags={"reject_reason": False}, versions={"reject_reason": 1})

    with patch("src.lookups.safety_guard.check_and_increment", new=AsyncMock(return_value=(True, 1))):
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="patch",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token=None,
                payload={"expected_version": 999},
            )
    assert exc.value.http_status == 412
    assert "version mismatch" in exc.value.detail
    assert "expected=999" in exc.value.detail
    assert "current=1" in exc.value.detail


# ---- 第 6 层: rate limit ----


@pytest.mark.asyncio
async def test_layer6_rate_limit_exceeded():
    """rate_limiter 返 (False, count) → 429."""
    from src.lookups.exceptions import LookupSafetyError
    from src.lookups.safety_guard import safety_guard

    user = _user(role="super_admin")
    _set_l1(readonly_flags={"reject_reason": False})

    with patch(
        "src.lookups.safety_guard.check_and_increment",
        new=AsyncMock(return_value=(False, 61)),  # 第 61 次超阈值
    ):
        with pytest.raises(LookupSafetyError) as exc:
            await safety_guard.check_all(
                action="patch",
                dict_code="reject_reason",
                key="duplicate",
                user=user,
                confirm_token=None,
                payload={},
            )
    assert exc.value.http_status == 429
    assert "rate limit" in exc.value.detail
