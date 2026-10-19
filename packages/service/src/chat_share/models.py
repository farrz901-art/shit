"""ChatShare ORM 模型 (2026-06-24 DATA-007)

1 张表: chat_shares (短 share_id 主键 + conv/user FK + JSON 消息快照).
跟 alembic migration 20260624_170000 字段 1:1 对齐.
conv_id → String(36) + FK conversations.id, user_id → Integer + FK users.id.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base
from ..utils.timezone import HKT


class ChatShare(Base):
    """chat 对话分享快照 — anon 公开读, 所有者撤销"""

    __tablename__ = "chat_shares"

    share_id: Mapped[str] = mapped_column(String(12), primary_key=True)  # nanoid 12 字符
    conv_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )  # 所有者
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    messages_json: Mapped[str] = mapped_column(Text, nullable=False)  # 快照 JSON
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(HKT),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_chat_shares_conv_id", "conv_id"),
        Index("ix_chat_shares_user_id", "user_id"),
        Index("ix_chat_shares_conv_id_user_id", "conv_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatShare share_id={self.share_id} conv_id={self.conv_id} user_id={self.user_id}>"
