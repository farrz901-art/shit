"""audit_logs SQLAlchemy model (2026-06-17 logging spec §4.3)"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    actor_id = Column(BigInteger, nullable=False)
    actor_type = Column(Text, nullable=False, default="user")
    action = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Text, nullable=False)
    ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    result = Column(Text, nullable=False, default="success")
    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    meta = Column("metadata", JSONB, nullable=False, default={})
