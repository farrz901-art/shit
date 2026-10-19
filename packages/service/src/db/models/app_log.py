"""app_logs SQLAlchemy model (2026-06-17 logging spec §4.1)"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AppLog(Base):
    __tablename__ = "app_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    level = Column(Text, nullable=False)
    logger = Column(Text, nullable=False)
    message = Column(Text, nullable=False)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    trace_id = Column(CHAR(32), nullable=True)
    context = Column(JSONB, nullable=False, default={})
