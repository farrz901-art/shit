"""IngestTask ORM model 单元测试 (无 DB, 纯字段断言)"""

from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, Table, Text


class TestIngestTaskTable:
    """IngestTask 表结构断言"""

    def test_tablename(self):
        from src.ingest.pdf_processing.models import IngestTask

        assert IngestTask.__tablename__ == "ingest_tasks"

    def test_columns_present(self):
        from src.ingest.pdf_processing.models import IngestTask

        cols = {c.name for c in IngestTask.__table__.columns}
        expected = {
            "id",
            "user_hash",
            "state",
            "total_files",
            "processed",
            "failed",
            "started_at",
            "finished_at",
            "error",
            "work_dir",
            "input_files_json",
            "output_files_json",
        }
        assert expected.issubset(cols), f"缺列: {expected - cols}"

    def test_id_is_string_pk(self):
        from src.ingest.pdf_processing.models import IngestTask

        col = IngestTask.__table__.columns.id
        assert isinstance(col.type, String)
        assert col.primary_key is True
        assert col.nullable is False

    def test_user_hash_indexed(self):
        from src.ingest.pdf_processing.models import IngestTask

        col = IngestTask.__table__.columns.user_hash
        assert col.nullable is False
        assert col.index is True

    def test_state_not_null(self):
        from src.ingest.pdf_processing.models import IngestTask

        col = IngestTask.__table__.columns.state
        assert col.nullable is False
        assert isinstance(col.type, String)

    def test_counts_are_int(self):
        from src.ingest.pdf_processing.models import IngestTask

        for c in ["total_files", "processed", "failed"]:
            col = IngestTask.__table__.columns[c]
            assert isinstance(col.type, Integer), f"{c} 应为 Integer"
            assert col.nullable is False

    def test_timestamps_are_datetime(self):
        from src.ingest.pdf_processing.models import IngestTask

        assert isinstance(IngestTask.__table__.columns.started_at.type, DateTime)
        assert IngestTask.__table__.columns.started_at.nullable is False
        assert IngestTask.__table__.columns.finished_at.nullable is True

    def test_json_columns_are_text(self):
        """input_files_json / output_files_json 存 JSON 字符串, 用 Text (跟原 SQLite 一致)"""
        from src.ingest.pdf_processing.models import IngestTask

        for c in ["input_files_json", "output_files_json"]:
            col = IngestTask.__table__.columns[c]
            assert isinstance(col.type, Text)
            assert col.nullable is False

    def test_composite_index(self):
        """(user_hash, started_at) 复合索引加速按用户查询"""
        from src.ingest.pdf_processing.models import IngestTask

        # __table__ 静态类型是 FromClause, .indexes 仅在 Table 上声明; runtime OK
        table: Table = IngestTask.__table__  # type: ignore[assignment]
        idx_names = {i.name for i in table.indexes}
        assert "ix_ingest_tasks_user_started" in idx_names
