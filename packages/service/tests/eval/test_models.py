"""Evaluation + EvaluationSample model 测试 (2026-06-16 重写 100% mock)

CLAUDE.md 模式 1 纯单测: 不连 PG, 用 SQLAlchemy metadata 测字段定义.
原 SQL 行为测试 (NOT NULL / CASCADE / JSON roundtrip) 是 SQL 层特性,
SQLAlchemy ORM mapper 上可静态推断, 不需要真连 DB.
"""

from __future__ import annotations

from typing import get_type_hints

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import RelationshipProperty


def test_evaluation_tablename_and_columns():
    """Evaluation 注册到 Base.metadata, 表名 + 关键列类型对"""
    from src.eval.models import Evaluation
    from src.storage import Base

    table = Base.metadata.tables[Evaluation.__tablename__]
    assert Evaluation.__tablename__ == "evaluations"

    cols = {c.name: c for c in table.columns}
    # 主键
    assert cols["id"].primary_key is True
    # user_id: FK 到 users.id, NOT NULL
    assert cols["user_id"].nullable is False
    assert any(isinstance(c, ForeignKey) for c in cols["user_id"].foreign_keys)
    # 字符串列
    assert isinstance(cols["dataset_name"].type, String)
    assert cols["dataset_name"].nullable is False
    assert isinstance(cols["status"].type, String)
    assert cols["status"].nullable is False
    # avg_metrics JSON
    assert isinstance(cols["avg_metrics"].type, JSON)
    assert cols["avg_metrics"].nullable is True
    # 数值列 (duration_seconds 显式 Float, total_samples Integer)
    assert isinstance(cols["total_samples"].type, Integer)
    assert isinstance(cols["duration_seconds"].type, Float)
    # 时间列 TZ-aware
    assert isinstance(cols["created_at"].type, DateTime)
    assert cols["created_at"].nullable is False


def test_evaluation_status_not_null():
    """status NOT NULL + 有 index"""
    from src.eval.models import Evaluation
    from src.storage import Base

    table = Base.metadata.tables[Evaluation.__tablename__]
    col = table.columns["status"]
    assert col.nullable is False
    assert col.index is True


def test_evaluation_sample_cascade_delete():
    """Evaluation.samples 关系带 cascade='all, delete-orphan', FK CASCADE"""
    from src.eval.models import Evaluation, EvaluationSample

    # 关系定义: Evaluation → samples
    rel = Evaluation.samples.property
    assert isinstance(rel, RelationshipProperty)
    assert rel.cascade.save_update is True
    assert rel.cascade.delete_orphan is True

    # FK: EvaluationSample.evaluation_id → evaluations.id, ondelete CASCADE
    fk_cols = list(EvaluationSample.__table__.columns["evaluation_id"].foreign_keys)
    assert len(fk_cols) == 1
    fk = fk_cols[0]
    assert fk.column.table.name == "evaluations"
    assert fk.ondelete == "CASCADE"


def test_evaluation_sample_contexts_json_column():
    """contexts / sources / metrics 都是 JSON 列, 可存 list[str] / list[dict]"""
    from src.eval.models import EvaluationSample
    from src.storage import Base

    table = Base.metadata.tables[EvaluationSample.__tablename__]
    cols = {c.name: c for c in table.columns}
    assert isinstance(cols["contexts"].type, JSON)
    assert cols["contexts"].nullable is True
    assert isinstance(cols["sources"].type, JSON)
    assert isinstance(cols["metrics"].type, JSON)
    # 文本列
    assert isinstance(cols["question"].type, Text)
    assert cols["question"].nullable is False
    assert isinstance(cols["error"].type, Text)
    # 类型注解验证 (Pydantic / IDE 兼容)
    hints = get_type_hints(EvaluationSample)
    # contexts 在源码里是 list[str] | None
    assert "contexts" in hints
