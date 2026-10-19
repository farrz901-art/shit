"""PreAnalysisTask ORM 字段验证 (mode 1 mock)

只验证 ORM 类定义存在 + 字段映射正确, 不连 PG (mock engine).
"""

from __future__ import annotations


def test_pre_analysis_task_table_name() -> None:
    """ORM 类 __tablename__ = pre_analysis_tasks"""
    from src.ingest.pre_analysis import PreAnalysisTask

    assert PreAnalysisTask.__tablename__ == "pre_analysis_tasks"


def test_pre_analysis_task_required_columns() -> None:
    """ORM 含所有字段"""
    from sqlalchemy import inspect

    from src.ingest.pre_analysis import PreAnalysisTask

    mapper = inspect(PreAnalysisTask)
    col_names = {c.key for c in mapper.columns}
    expected = {
        "id",
        "user_hash",
        "state",
        "pdf_filename",
        "pdf_uri",
        "started_at",
        "finished_at",
        "error",
        "output_files_json",
        "summary_json",
    }
    assert expected.issubset(col_names), f"缺字段: {expected - col_names}"


def test_pre_analysis_task_user_hash_not_user_id() -> None:
    """ORM 字段名是 user_hash (跟 ingest_tasks 一致)"""
    from sqlalchemy import inspect

    from src.ingest.pre_analysis import PreAnalysisTask

    mapper = inspect(PreAnalysisTask)
    col_names = {c.key for c in mapper.columns}
    assert "user_hash" in col_names
    assert "user_id" not in col_names


def test_pre_analysis_task_has_task_config_json_column() -> None:
    """(2026-07-06) 新增 task_config_json 列, Text NOT NULL, default='{}'."""
    from sqlalchemy import inspect

    from src.ingest.pre_analysis import PreAnalysisTask

    mapper = inspect(PreAnalysisTask)
    assert "task_config_json" in {c.key for c in mapper.columns}
    col = mapper.columns["task_config_json"]
    assert col.nullable is False
