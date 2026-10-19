"""SQLAlchemy 2.0 DeclarativeBase

所有业务 model (User / Conversation / Message / Evaluation / EvaluationSample) 都继承这个 Base。
metadata 在这里维护, Alembic autogenerate 拿这个生成 migration。
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """项目所有 SQLAlchemy model 的基类"""

    pass
