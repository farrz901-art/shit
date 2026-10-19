"""error_logs SQLAlchemy model (2026-06-17 logging spec §4.2)"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ErrorLog(Base):
    __tablename__ = "error_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    level = Column(Text, nullable=False)
    exception_type = Column(Text, nullable=False)
    exception_msg = Column(Text, nullable=False)
    stacktrace = Column(Text, nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    path = Column(Text, nullable=True)
    method = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    context = Column(JSONB, nullable=False, default={})
