"""KgAudit ORM model 单元测试"""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text


class TestKgAuditTable:
    """KgAudit 表结构断言"""

    def test_tablename(self):
        from src.kg.audit_models import KgAudit

        assert KgAudit.__tablename__ == "kg_audit"

    def test_columns_present(self):
        from src.kg.audit_models import KgAudit

        cols = {c.name for c in KgAudit.__table__.columns}
        expected = {"id", "ts", "action", "actor", "target", "result", "detail"}
        assert expected.issubset(cols)

    def test_id_is_autoincrement_pk(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.id
        assert isinstance(col.type, Integer)
        assert col.primary_key is True
        assert col.autoincrement is True

    def test_ts_is_float_indexed(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.ts
        assert isinstance(col.type, Float)
        assert col.nullable is False
        # 索引由 __table_args__ 的 Index("ix_kg_audit_ts", "ts") 显式定义
        # (避免 column 级 index=True 跟显式 Index 重复创建索引名)
        # pyright 不识别 SA Table.indexes, 走 __table_args__ 元组断言
        table_args = KgAudit.__table_args__
        assert "ix_kg_audit_ts" in {ix.name for ix in table_args}

    def test_action_not_null(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.action
        assert col.nullable is False
        assert isinstance(col.type, String)

    def test_actor_target_nullable(self):
        from src.kg.audit_models import KgAudit

        assert KgAudit.__table__.columns.actor.nullable is True
        assert KgAudit.__table__.columns.target.nullable is True

    def test_result_not_null(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.result
        assert col.nullable is False

    def test_detail_is_text_json_string(self):
        from src.kg.audit_models import KgAudit

        col = KgAudit.__table__.columns.detail
        assert isinstance(col.type, Text)
        assert col.nullable is False
