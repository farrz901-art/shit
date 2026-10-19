"""User model: 客户端匿名 token + Mem0 关联"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base
from ..utils.timezone import HKT


class User(Base):
    """客户端匿名用户

    - public_token: 32 字节 hex, 客户端存的; 首次访问 /api/auth/anon 后端生成 + 落库
    - last_seen_at: 清理冷用户的依据 (后续脚本扫描)
    - display_name: 后续用户填昵称 (本 spec 不用)
    - account_id: 账号体系上线后, 匿名 user 跟 Account 1:1 关联; 老匿名 user 留空
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT), index=True
    )

    # 2026-06-13: 账号体系上线, user 关联到 Account; 老匿名 user 留空
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} token={self.public_token[:8]}…>"
