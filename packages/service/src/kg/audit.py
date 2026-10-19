"""知识图谱审计日志 (ORM 重写, 2026-06-15).

替原 sqlite3 raw 实现. 走 SQLAlchemy ORM (src.kg.audit_models.KgAudit) +
session_scope() 事务. 现有 AuditStore.record / list_recent 接口签名 1:1 保留.

构造函数保留 db_path 参数 (向后兼容 src/kg/router.py:25), 但忽略.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import select

from ..storage import session_scope
from .audit_models import KgAudit


class AuditStore:
    """薄壳: 保持旧 record/list_recent 接口, 内部走 session_scope."""

    def __init__(self, db_path: Path | str | None = None):  # noqa: ARG001  # 保留参数兼容调用方
        """db_path 参数已废弃 (旧 SQLite 路径), 保留只为向后兼容.

        实际数据走 PG (PG_* 5 env, get_rag_db_url() 拼 URL), 跟 src.kg.audit_models.KgAudit 一致.
        """
        pass

    def record(
        self,
        *,
        action: str,
        actor: str | None,
        target: str | None,
        result: str,
        detail: dict,
    ) -> None:
        """写一条审计日志."""
        with session_scope() as s:
            s.add(
                KgAudit(
                    ts=time.time(),
                    action=action,
                    actor=actor,
                    target=target,
                    result=result,
                    detail=json.dumps(detail, ensure_ascii=False),
                )
            )

    def list_recent(self, limit: int = 50) -> list[dict]:
        """查最近 N 条, 按 ts DESC.

        返回结构跟原 sqlite3 list_recent 一致:
          [{"id": int, "ts": float, "action": str, "actor": str|None,
            "target": str|None, "result": str, "detail": dict}, ...]
        """
        with session_scope() as s:
            rows = s.execute(select(KgAudit).order_by(KgAudit.ts.desc()).limit(limit)).scalars().all()
            return [
                {
                    "id": r.id,
                    "ts": r.ts,
                    "action": r.action,
                    "actor": r.actor,
                    "target": r.target,
                    "result": r.result,
                    "detail": json.loads(r.detail),
                }
                for r in rows
            ]


__all__ = ["AuditStore"]
