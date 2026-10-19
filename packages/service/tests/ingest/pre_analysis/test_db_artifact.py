"""append_artifact 测试 (mode 1 mock, 2026-07-09).

由 conftest::mock_all_db_connections 自动 mock session_scope, 不需手动 patch.
本文件用显式 patch 验证行为契约 (因为 conftest autouse 是为其他 stage 测试兜底).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from unittest.mock import MagicMock


def _patch_session_scope(task: MagicMock | None) -> None:
    """把 db_artifact.session_scope 替换成返指定 task 的 fake context manager."""
    s = MagicMock()
    s.get.return_value = task

    @contextmanager
    def fake_session_scope():
        yield s

    import src.ingest.pre_analysis.db_artifact as mod

    mod.session_scope = fake_session_scope


def test_append_artifact_happy_path() -> None:
    """happy path: 追加 1 项到 output_files_json."""
    from src.ingest.pre_analysis.db_artifact import append_artifact
    from src.ingest.pre_analysis.models import PreAnalysisTask

    task = MagicMock(spec=PreAnalysisTask)
    task.output_files_json = "[]"
    _patch_session_scope(task)

    append_artifact("t1", "chapter_structure", "chapter_structure.json", "local://x", 1024)

    files = json.loads(task.output_files_json)
    assert len(files) == 1
    assert files[0]["kind"] == "chapter_structure"
    assert files[0]["size_bytes"] == 1024
    assert files[0]["uri"] == "local://x"
    assert files[0]["filename"] == "chapter_structure.json"


def test_append_artifact_task_none_silently_skip() -> None:
    """task 不存在 → 静默返回, 不抛."""
    from src.ingest.pre_analysis.db_artifact import append_artifact

    _patch_session_scope(None)
    # 不抛
    append_artifact("missing", "table", "x.csv", "local://x", 0)


def test_append_artifact_existing_json_preserved() -> None:
    """已有 output_files_json 保留, 追加 1 项."""
    from src.ingest.pre_analysis.db_artifact import append_artifact
    from src.ingest.pre_analysis.models import PreAnalysisTask

    existing = [{"kind": "table", "filename": "t1.csv", "uri": "local://t1", "size_bytes": 100}]
    task = MagicMock(spec=PreAnalysisTask)
    task.output_files_json = json.dumps(existing)
    _patch_session_scope(task)

    append_artifact("t1", "index", "index.json", "local://i", 50)

    files = json.loads(task.output_files_json)
    assert len(files) == 2
    assert files[1]["kind"] == "index"
    assert files[1]["size_bytes"] == 50
