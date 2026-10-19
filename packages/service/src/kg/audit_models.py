"""kg (知识图谱) 子包 ORM model (2026-06-15).

替原 src/kg/audit.py 里的 sqlite3 raw table. 字段跟旧 schema 1:1 对齐,
保证 AuditStore.record / list_recent 行为不变.
"""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class KgAudit(Base):
    """知识图谱审计日志.

    字段顺序 + 类型跟原 data/kg_audit.db schema 一致:
    - id: DB 自增 PK
    - ts: Unix 时间戳 (float, 秒), 原 SQLite schema 用 REAL
    - action: 操作类型 (e.g. "create_triple", "update_node")
    - actor: 操作者标识 (current user id 字符串)
    - target: 操作目标 (triple id / node id 等)
    - result: ok / error
    - detail: 详细信息 JSON 字符串 (跟原 SQLite 一致)
    """

    __tablename__ = "kg_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ts 字段索引由 __table_args__ 显式定义 (避免 column 级 index=True 跟显式 Index 重复创建索引名)
    ts: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_kg_audit_ts", "ts"),)

    def __repr__(self) -> str:
        return f"<KgAudit id={self.id} action={self.action} result={self.result}>"
