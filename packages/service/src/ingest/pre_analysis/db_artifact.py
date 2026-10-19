# packages/service/src/ingest/pre_analysis/db_artifact.py
"""DB output_files_json 公共 append 函数 (2026-07-09).

4 个 stage 共享, 改输出 JSON 格式只改这里. 测试由 conftest::mock_all_db_connections
自动覆盖 session_scope, 单元测试可手动 patch (见 test_db_artifact.py).
"""

from __future__ import annotations

import json

from ...storage import session_scope
from .models import PreAnalysisTask


def append_artifact(
    task_id: str,
    kind: str,
    filename: str,
    uri: str,
    size_bytes: int,
) -> None:
    """DB output_files_json append 1 项.

    Args:
        task_id: PreAnalysisTask.id
        kind: chapter_structure / table / flagged_paragraphs / index
        filename: 相对路径 (e.g. 'tables/page-3-table-1.csv')
        uri: ObjectStore URI
        size_bytes: 字节数

    Note:
        task 不存在时静默跳过 (跟原 runner._append_artifact 行为一致).
    """
    with session_scope() as s:
        task = s.get(PreAnalysisTask, task_id)
        if task is None:
            return
        current = json.loads(task.output_files_json or "[]")
        current.append(
            {
                "kind": kind,
                "filename": filename,
                "uri": uri,
                "size_bytes": size_bytes,
            }
        )
        task.output_files_json = json.dumps(current, ensure_ascii=False)


__all__ = ["append_artifact"]
