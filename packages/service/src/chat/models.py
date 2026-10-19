"""Conversation + Message models: 聊天会话/消息"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..storage import Base
from ..utils.timezone import HKT


class Conversation(Base):
    """聊天会话

    - id 用 UUID 字符串, 跟前端 crypto.randomUUID() 兼容
    - message_count 冗余, 减少 COUNT(*)
    - (user_id, updated_at DESC) 复合索引, 列表查询"最近对话"

    (2026-06-19 chat spec §3) 软删:
    - deleted_at: NULL = 活跃, 非空 = 软删时间戳
    - cron 30d 后 hard_delete 真删 (GDPR right to erasure)
    - 业务查询必带 WHERE deleted_at IS NULL
    """

    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # (2026-06-24 DATA-003) FK 加 ondelete=CASCADE, 跟 messages.conversation_id 一致,
    # 删 user 自动级联删 conversations (避免孤儿行 + 配合 GDPR right to erasure).
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT), index=True
    )
    # (2026-06-19) 软删时间戳; NULL=活跃; cron 30d 后 hard_delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r}>"


class Message(Base):
    """单条聊天消息

    - role: user / assistant / system
    - meta: token 用量 / 模型名 / 工具调用 (JSON, 后续可加)
    - (conversation_id, created_at) 复合索引, 按时间正序拉

    (2026-06-19 chat spec §3) 软删:
    - deleted_at: NULL=活跃; 跟 Conversation 软删时间不强制一致 (单独软删场景暂未支持)
    """

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 列类型 jsonb (2026-06-26 migration), psycopg3 读直接返 dict
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )
    # (2026-06-19) 软删时间戳; NULL=活跃
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conv={self.conversation_id} role={self.role}>"
