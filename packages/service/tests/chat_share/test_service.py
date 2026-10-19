"""ChatShareService 单元测试 (2026-06-16)

覆盖 4 个 service 方法:
- create_share: 生成短 ID + URL + TTL + 存消息 JSON
- get_share: 反序列化 + 不泄漏 user_id + 404 抛异常
- revoke_share: 所有者校验 + 统一 404 防 ID 探测
- upload_to_dify: 占位 (Task 2 透传, 测 mock 注入)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

# ---- create_share ----


def test_create_share_generates_short_id_and_url():
    """create_share 生成 12 字符 share_id, url 拼接 /chat/s/{share_id}"""
    from src.chat_share.service import ChatShareService

    svc = ChatShareService(repo=MagicMock())
    result = svc.create_share(conv_id="conv-1", user_id=42, title="标题")
    assert len(result["share_id"]) == 12
    assert result["url"].endswith(f"/chat/s/{result['share_id']}")


def test_create_share_uses_explicit_title():
    """用户传 title 优先; 不传 → None (前端可编辑, 不强求自动生成)"""
    from src.chat_share.service import ChatShareService

    svc = ChatShareService(repo=MagicMock())
    # 显式 title
    r1 = svc.create_share(conv_id="c", user_id=1, title="我的对话")
    assert r1["title"] == "我的对话"
    # 缺 title 时不崩, 返 None
    r2 = svc.create_share(conv_id="c", user_id=1, title=None)
    assert r2["title"] is None


def test_create_share_sets_default_ttl_7_days():
    """默认 expires_at = now + 7d (timezone-aware UTC)"""
    from src.chat_share.service import ChatShareService

    svc = ChatShareService(repo=MagicMock())
    before = datetime.now(UTC)
    result = svc.create_share(conv_id="c", user_id=1, title="t")
    after = datetime.now(UTC)

    assert result["expires_at"] is not None
    # 距 before/after 应在 6-8 天之间 (允许 clock skew)
    delta_from_before = result["expires_at"] - before
    delta_from_after = result["expires_at"] - after
    assert timedelta(days=6) < delta_from_before < timedelta(days=8)
    assert timedelta(days=6) < delta_from_after < timedelta(days=8)


def test_create_share_messages_snapshot_stored_as_json():
    """messages 序列化为 JSON 字符串存 repo.messages_json"""
    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    svc = ChatShareService(repo=repo)
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    svc.create_share(conv_id="c", user_id=1, title="t", messages=msgs)

    # 验证 repo.save 收到的 messages_json 字段
    call_kwargs = repo.save.call_args.kwargs
    parsed = json.loads(call_kwargs["messages_json"])
    assert len(parsed) == 2
    assert parsed[0]["role"] == "user"
    assert parsed[1]["content"] == "hello"


# ---- get_share (公开, anon) ----


def test_get_share_returns_messages_deserialized():
    """get_share 把 messages_json 反序列化成 list"""
    from src.chat_share.service import ChatShareService

    msgs = [{"role": "user", "content": "hi"}]
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(
        share_id="abc123",
        title="t",
        messages_json=json.dumps(msgs),
        model="gpt-4o-mini",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
    )
    svc = ChatShareService(repo=repo)
    result = svc.get_share("abc123")

    assert result["messages"] == msgs
    assert result["share_id"] == "abc123"
    assert result["model"] == "gpt-4o-mini"


def test_get_share_raises_share_not_found_for_unknown():
    """share_id 不存在 → 抛 ShareNotFound (router 翻译 404)"""
    from src.chat_share.service import ChatShareService, ShareNotFound

    repo = MagicMock()
    repo.get_by_id.return_value = None
    svc = ChatShareService(repo=repo)

    with pytest.raises(ShareNotFound):
        svc.get_share("nope")


def test_get_share_excludes_sensitive_fields():
    """get_share 返 SharedConversationResponse, 不含 user_id / share_password / token"""
    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(
        share_id="x",
        title="t",
        messages_json="[]",
        model="gpt-4o-mini",
        created_at=datetime(2026, 6, 16, tzinfo=UTC),
        user_id="42",  # **不应泄漏**
    )
    svc = ChatShareService(repo=repo)
    result = svc.get_share("x")

    assert "user_id" not in result


# ---- revoke_share ----


def test_revoke_share_only_owner():
    """非所有者撤销 → 抛 ShareNotFound (统一 404 防 ID 探测)"""
    from src.chat_share.service import ChatShareService, ShareNotFound

    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(user_id="99")  # 别人的
    svc = ChatShareService(repo=repo)

    with pytest.raises(ShareNotFound):
        svc.revoke_share("x", current_user_id=42)


def test_revoke_share_owner_succeeds():
    """所有者撤销 → repo.delete 调用"""
    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(user_id=42)  # 自己的, 跟 current_user_id 一致
    svc = ChatShareService(repo=repo)

    svc.revoke_share("x", current_user_id=42)
    repo.delete.assert_called_once_with("x")


# ---- list_shares (登录, 按 conv + user) ----


def test_list_shares_filters_by_user_id_and_conv_id():
    """list_shares(conv_id, user_id) 只返当前用户对应该 conv 的 share, 按 created_at DESC"""
    from datetime import UTC, datetime

    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    share_row = MagicMock()
    share_row.share_id = "abc123"
    share_row.title = "t"
    share_row.expires_at = None
    share_row.created_at = datetime(2026, 6, 30, tzinfo=UTC)
    repo.list_by_conv_and_user = MagicMock(return_value=[share_row])

    svc_inst = ChatShareService(repo=repo, locale="zh")
    result = svc_inst.list_shares(conv_id="c1", user_id=42)

    repo.list_by_conv_and_user.assert_called_once_with(conv_id="c1", user_id=42, limit=20)
    assert len(result) == 1
    assert result[0]["share_id"] == "abc123"
    assert result[0]["url"].endswith("/zh/chat/s/abc123")
