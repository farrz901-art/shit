"""chat_share/repo.py mock 单元测试 (mode 1, 不连 PG)"""

from datetime import UTC
from unittest.mock import MagicMock

import pytest

from src.chat_share.models import ChatShare


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session


# ============================================================
# save
# ============================================================


def test_save_calls_session_add_and_commit_and_refresh(mock_session):
    """save 后应 add + commit + refresh (验证 refresh 被调)"""
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.save("s1", "c1", 1, "标题", "[]", "gpt-4", None)
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


def test_save_with_all_fields(mock_session):
    """所有非空参数正确传递"""
    from datetime import datetime

    from src.chat_share.repo import SqlAlchemyChatShareRepo

    expires = datetime(2026, 7, 1, tzinfo=UTC)
    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.save("s2", "c2", 2, "标题", '[{"role": "user"}]', "gpt-4", expires)

    # 验证 add 被调, 且 ChatShare 正确构造
    call_args = mock_session.add.call_args[0][0]
    assert isinstance(call_args, ChatShare)
    assert call_args.share_id == "s2"
    assert call_args.conv_id == "c2"
    assert call_args.user_id == 2
    assert call_args.title == "标题"
    assert call_args.messages_json == '[{"role": "user"}]'
    assert call_args.model == "gpt-4"
    assert call_args.expires_at == expires


def test_save_with_none_fields(mock_session):
    """title / model / expires_at 可 None"""
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.save("s3", "c3", 3, None, "[]", None, None)

    call_args = mock_session.add.call_args[0][0]
    assert call_args.title is None
    assert call_args.model is None
    assert call_args.expires_at is None


# ============================================================
# get_by_id
# ============================================================


def test_get_by_id_returns_share(mock_session):
    share = MagicMock(spec=ChatShare)
    share.share_id = "s1"
    mock_session.query.return_value.filter_by.return_value.first.return_value = share
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    result = repo.get_by_id("s1")
    assert result is not None
    assert result.share_id == "s1"


def test_get_by_id_returns_none(mock_session):
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    result = repo.get_by_id("nonexistent")
    assert result is None


# ============================================================
# delete
# ============================================================


def test_delete_calls_session_delete(mock_session):
    share = MagicMock(spec=ChatShare)
    mock_session.query.return_value.filter_by.return_value.first.return_value = share
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.delete("s1")
    mock_session.delete.assert_called_once_with(share)
    mock_session.commit.assert_called_once()


def test_delete_nonexistent_noop(mock_session):
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.delete("nonexistent")
    mock_session.delete.assert_not_called()


def test_delete_called_twice_noop_on_second(mock_session):
    """第二次 delete 同 share_id 应 noop (share 已被删)"""
    share = MagicMock(spec=ChatShare)
    # 第一次找到, 第二次 None (已删)
    mock_session.query.return_value.filter_by.return_value.first.side_effect = [share, None]
    from src.chat_share.repo import SqlAlchemyChatShareRepo

    repo = SqlAlchemyChatShareRepo(mock_session)
    repo.delete("s1")  # 第一次: 找到并删
    assert mock_session.delete.call_count == 1
    assert mock_session.commit.call_count == 1

    repo.delete("s1")  # 第二次: 找不到, noop
    assert mock_session.delete.call_count == 1  # 不变
    assert mock_session.commit.call_count == 1  # 不变
