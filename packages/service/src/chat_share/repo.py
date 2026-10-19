"""ChatShare ORM CRUD helpers (2026-06-16)

4 个方法: save / get_by_id / delete / list_by_conv_and_user.
service 层依赖 repo 接口 (便于单测时 mock repo), 跟 approvals/repo.py 风格一致.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import ChatShare


class ChatShareRepo(Protocol):
    """repo 接口契约 — service 层接受任何实现此 Protocol 的对象 (测试用 MagicMock)."""

    def save(
        self,
        share_id: str,
        conv_id: str,
        user_id: int,
        title: str | None,
        messages_json: str,
        model: str | None,
        expires_at: datetime | None,
    ) -> None:
        """写入新 share. 调用方负责生成 share_id / expires_at."""
        ...

    def get_by_id(self, share_id: str) -> ChatShare | None:
        """按 share_id 查; 不存在 → None."""
        ...

    def delete(self, share_id: str) -> None:
        """按 share_id 删; 不存在也无副作用."""
        ...

    def list_by_conv_and_user(
        self,
        conv_id: str,
        user_id: int,
        limit: int = 20,
    ) -> list[ChatShare]:
        """按 (conv_id, user_id) 查 share 列表, 按 created_at DESC, 分页.

        Returns:
            list[ChatShare]: 空时返 [], 顺序最新在前
        """
        ...


class SqlAlchemyChatShareRepo:
    """SQLAlchemy sync session 实现 — 跟 approvals/repo.py 不同, chat_share 同步即可 (无 BGTask)."""

    def __init__(self, session):
        self._session = session

    def save(
        self,
        share_id: str,
        conv_id: str,
        user_id: int,
        title: str | None,
        messages_json: str,
        model: str | None,
        expires_at: datetime | None,
    ) -> None:
        """INSERT 一条 ChatShare."""
        share = ChatShare(
            share_id=share_id,
            conv_id=conv_id,
            user_id=user_id,
            title=title,
            messages_json=messages_json,
            model=model,
            expires_at=expires_at,
        )
        self._session.add(share)
        self._session.commit()
        self._session.refresh(share)

    def get_by_id(self, share_id: str) -> ChatShare | None:
        """SELECT 一条; 不存在 → None."""
        return self._session.query(ChatShare).filter_by(share_id=share_id).first()

    def delete(self, share_id: str) -> None:
        """DELETE 一条; 不存在 → noop."""
        share = self._session.query(ChatShare).filter_by(share_id=share_id).first()
        if share is not None:
            self._session.delete(share)
            self._session.commit()

    def list_by_conv_and_user(
        self,
        conv_id: str,
        user_id: int,
        limit: int = 20,
    ) -> list[ChatShare]:
        """按 (conv_id, user_id) 查 share 列表, 走 ix_chat_shares_conv_id_user_id 复合索引."""
        return (
            self._session.query(ChatShare)
            .filter_by(conv_id=conv_id, user_id=user_id)
            .order_by(ChatShare.created_at.desc())
            .limit(limit)
            .all()
        )
