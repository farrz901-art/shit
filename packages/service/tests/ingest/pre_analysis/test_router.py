"""pre_analysis router 单文件下载端点测试 (2026-07-06, 模式 1 mock).

测试 /api/pre-analysis/tasks/{id}/files/{filename}:
- 鉴权: 非 super_admin → 403
- task 不存在 → 404
- filename 不在 output_files → 404 (防 path traversal)
- 正常: 返二进制流 + Content-Disposition
- store.get_bytes 抛错 → 404

@audited → _persist_audit 走 session_scope 写 audit_logs, autouse 屏蔽.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_user(id_: int = 1, role: str = "super_admin") -> Any:
    """构造 mock CurrentUser."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        is_account=True,
        role=role,
        email=f"u{id_}@x.com",
    )


def _make_task(
    task_id: str = "pa-abc",
    state: str = "completed",
    output_files: list[dict] | None = None,
) -> dict[str, Any]:
    """构造 mock task dict (router 期望的格式)."""
    if output_files is None:
        output_files = [
            {
                "kind": "chapter_structure",
                "filename": "chapters.json",
                "uri": "s3://bucket/pa-abc/chapters.json",
                "size_bytes": 12,
            },
            {
                "kind": "table",
                "filename": "table_p1.json",
                "uri": "s3://bucket/pa-abc/table_p1.json",
                "size_bytes": 24,
            },
        ]
    return {
        "id": task_id,
        "state": state,
        "user_hash": "h",
        "pdf_filename": "D81.pdf",
        "pdf_uri": "s3://bucket/input/D81.pdf",
        "started_at": "2026-07-06T10:00:00Z",
        "finished_at": "2026-07-06T10:01:00Z",
        "current_stage": "done",
        "output_files": output_files,
        "summary": {
            "total_chapters": 1,
            "total_tables": 1,
            "total_flagged_paragraphs": 0,
            "elapsed_ms": 1000,
            "cross_page_candidates": 0,
        },
        "error": None,
    }


@pytest.fixture(autouse=True)
def _patch_audit_persist():
    """autouse: 屏蔽 @audited decorator 的 audit_logs 写入."""
    noop_session = MagicMock()

    @contextmanager
    def _cm():
        yield noop_session

    def _fake_session_scope():
        return _cm()

    with patch("src.storage.session.session_scope", _fake_session_scope):
        yield


@pytest.fixture
def client() -> tuple[TestClient, Any]:
    """构造 TestClient + 暴露 mock 容器, 调用方可在 patch 内填入."""
    from src.ingest.pre_analysis.router import pre_analysis_router
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(pre_analysis_router)
    app.dependency_overrides[resolve_user] = lambda: _make_user()
    return TestClient(app), app


def test_download_file_success(client: tuple[TestClient, Any]) -> None:
    """正常下载: 返 200 + bytes + Content-Disposition."""
    from src.ingest.pre_analysis.router import pa_load_task

    cli, _ = client
    fake_task = _make_task()
    fake_bytes = b'{"chapters": []}'

    with (
        patch.object(pa_load_task, "__defaults__", (None,)),
        patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task),
        patch(
            "src.ingest.pre_analysis.router.get_object_store",
            return_value=MagicMock(get_bytes=MagicMock(return_value=fake_bytes)),
        ),
    ):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/files/chapters.json")

    assert resp.status_code == 200
    assert resp.content == fake_bytes
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "chapters.json" in resp.headers.get("content-disposition", "")


def test_download_file_task_not_found(client: tuple[TestClient, Any]) -> None:
    """task 不存在 → 404."""

    cli, _ = client
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=None):
        resp = cli.get("/api/pre-analysis/tasks/missing/files/chapters.json")
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


def test_download_file_not_in_output_files(client: tuple[TestClient, Any]) -> None:
    """filename 不在 output_files → 404 (防 path traversal, 只取清单内真实 uri)."""

    cli, _ = client
    fake_task = _make_task()  # 只有 chapters.json / table_p1.json
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/files/../../etc/passwd")
    assert resp.status_code == 404


def test_download_file_store_get_bytes_failure(client: tuple[TestClient, Any]) -> None:
    """ObjectStore get_bytes 抛错 → 404."""

    cli, _ = client
    fake_task = _make_task()
    failing_store = MagicMock(get_bytes=MagicMock(side_effect=FileNotFoundError("missing")))
    with (
        patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task),
        patch("src.ingest.pre_analysis.router.get_object_store", return_value=failing_store),
    ):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/files/chapters.json")
    assert resp.status_code == 404
    assert "读取失败" in resp.json()["detail"]


def test_download_file_running_state_allowed(client: tuple[TestClient, Any]) -> None:
    """running 状态也可下载 (阶段化产物已落 ObjectStore)."""

    cli, _ = client
    fake_task = _make_task(state="running")
    fake_bytes = b'{"partial": true}'
    with (
        patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task),
        patch(
            "src.ingest.pre_analysis.router.get_object_store",
            return_value=MagicMock(get_bytes=MagicMock(return_value=fake_bytes)),
        ),
    ):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/files/table_p1.json")
    assert resp.status_code == 200
    assert resp.content == fake_bytes


def test_list_table_pages_success(client: tuple[TestClient, Any]) -> None:
    """正常: 返回 {pages: [...], total: N}."""

    cli, _ = client
    fake_task = _make_task(
        output_files=[
            {"kind": "table", "filename": "tables/page-3-table-1.csv", "uri": "s3://x", "size_bytes": 50},
            {"kind": "table", "filename": "tables/page-9-table-1.csv", "uri": "s3://x", "size_bytes": 100},
            {"kind": "table", "filename": "tables/page-9-table-2.csv", "uri": "s3://x", "size_bytes": 200},
            {"kind": "table", "filename": "tables/page-21-table-1.csv", "uri": "s3://x", "size_bytes": 150},
            {"kind": "chapter_structure", "filename": "chapters.json", "uri": "s3://x", "size_bytes": 1000},
        ],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"pages": [3, 9, 21], "total": 4}


def test_list_table_pages_task_not_found(client: tuple[TestClient, Any]) -> None:
    """task 不存在 → 404."""
    cli, _ = client
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=None):
        resp = cli.get("/api/pre-analysis/tasks/missing/tables/pages")
    assert resp.status_code == 404


def test_list_table_pages_non_super_admin_403(client: tuple[TestClient, Any]) -> None:
    """非 super_admin → 403."""
    from src.middleware.auth import resolve_user

    app = client[1]
    app.dependency_overrides[resolve_user] = lambda: _make_user(role="user")
    cli = client[0]
    resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 403


def test_list_table_pages_empty(client: tuple[TestClient, Any]) -> None:
    """无表格 → {pages: [], total: 0}."""

    cli, _ = client
    fake_task = _make_task(
        output_files=[{"kind": "chapter_structure", "filename": "chapters.json", "uri": "s3://x", "size_bytes": 1000}],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 200
    assert resp.json() == {"pages": [], "total": 0}


def test_get_table_page_success(client: tuple[TestClient, Any]) -> None:
    """正常: 返回 {page, tables} 含 CSV 解析 JSON."""

    cli, _ = client
    fake_task = _make_task(
        output_files=[
            {
                "kind": "table",
                "filename": "tables/page-9-table-1.csv",
                "uri": "s3://x/tables/page-9-table-1.csv",
                "size_bytes": 50,
            },
            {
                "kind": "table",
                "filename": "tables/page-9-table-2.csv",
                "uri": "s3://x/tables/page-9-table-2.csv",
                "size_bytes": 100,
            },
            {
                "kind": "table",
                "filename": "tables/page-3-table-1.csv",  # 其它页
                "uri": "s3://x/tables/page-3-table-1.csv",
                "size_bytes": 80,
            },
        ],
    )
    csv_1 = b"col_a,col_b\nv1,v2\nv3,v4\n"
    csv_2 = b"col_x\nfoo\nbar\n"

    fake_store = MagicMock(
        get_bytes=MagicMock(
            side_effect=lambda uri: {
                "s3://x/tables/page-9-table-1.csv": csv_1,
                "s3://x/tables/page-9-table-2.csv": csv_2,
            }.get(uri, b"")
        )
    )

    with (
        patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task),
        patch("src.ingest.pre_analysis.router.get_object_store", return_value=fake_store),
    ):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/9")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 9
    assert len(body["tables"]) == 2
    # 按 table_index 升序
    assert body["tables"][0]["table_index"] == 1
    assert body["tables"][0]["filename"] == "tables/page-9-table-1.csv"
    assert body["tables"][0]["columns"] == ["col_a", "col_b"]
    assert body["tables"][0]["rows"] == [
        {"col_a": "v1", "col_b": "v2"},
        {"col_a": "v3", "col_b": "v4"},
    ]
    assert body["tables"][0]["size_bytes"] == 50


def test_get_table_page_not_found(client: tuple[TestClient, Any]) -> None:
    """指定页没表格 → 404 'page not found'."""

    cli, _ = client
    fake_task = _make_task(
        output_files=[{"kind": "table", "filename": "tables/page-3-table-1.csv", "uri": "s3://x", "size_bytes": 50}],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/999")
    assert resp.status_code == 404
    assert "page" in resp.json()["detail"].lower() or "999" in resp.json()["detail"]


def test_get_table_page_task_not_found(client: tuple[TestClient, Any]) -> None:
    """task 不存在 → 404."""
    cli, _ = client
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=None):
        resp = cli.get("/api/pre-analysis/tasks/missing/tables/page/9")
    assert resp.status_code == 404


def test_get_table_page_non_super_admin_403(client: tuple[TestClient, Any]) -> None:
    """非 super_admin → 403."""
    from src.middleware.auth import resolve_user

    app = client[1]
    app.dependency_overrides[resolve_user] = lambda: _make_user(role="user")
    cli = client[0]
    resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/9")
    assert resp.status_code == 403


class TestChapterConfigForm:
    """(2026-07-09 PDF 章节树状化) chapter_config_json form 字段测试.

    用直接 patch + 调用 _run_pre_analysis 跳过 multipart 复杂度.
    """

    def test_run_pre_analysis_extracts_chapter_config(self) -> None:
        """_run_pre_analysis 从 task_config 提取 chapter_config 并传 runner."""
        from src.ingest.pre_analysis import router as r

        captured: dict = {}

        class FakeRunner:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def run(  # noqa: PLR0913  # 跟 runner.run 同 shape 接收 4 参数
                self,
                task_id: str,
                pdf_uri: str,
                table_extraction_config: dict | None = None,
                chapter_config: Any = None,
            ) -> None:
                captured["task_id"] = task_id
                captured["table"] = table_extraction_config
                captured["chapter_max_level"] = chapter_config.chapter_max_level_for_display if chapter_config else None
                captured["llm_enabled"] = chapter_config.enable_llm_refinement if chapter_config else None

        fake_task = {
            "id": "t1",
            "state": "pending",
            "pdf_uri": "local://x.pdf",
        }
        task_config = {
            "table_backend": "camelot",
            "table_params": {"foo": "bar"},
            "chapter": {"chapter_max_level_for_display": 5, "enable_llm_refinement": True},
        }
        with (
            patch.object(r, "pa_load_task", return_value=fake_task),
            patch("src.ingest.pre_analysis.runner.PreAnalysisRunner", FakeRunner),
            patch.object(r, "get_object_store"),
            patch.object(r, "PreAnalysisTaskStore"),
            patch.object(r, "PreAnalysisStageStore"),
        ):
            r._run_pre_analysis("t1", task_config)

        assert captured["task_id"] == "t1"
        assert captured["table"] == {"table_backend": "camelot", "table_params": {"foo": "bar"}}
        assert captured["chapter_max_level"] == 5
        assert captured["llm_enabled"] is True

    def test_run_pre_analysis_default_chapter_when_missing(self) -> None:
        """老 task 只有 table 字段, 缺 chapter → 走默认 (从 {} parse)."""
        from src.ingest.pre_analysis import router as r

        captured: dict = {}

        class FakeRunner:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def run(  # noqa: PLR0913
                self,
                task_id: str,
                pdf_uri: str,
                table_extraction_config: dict | None = None,
                chapter_config: Any = None,
            ) -> None:
                captured["chapter_max_level"] = chapter_config.chapter_max_level_for_display
                captured["llm"] = chapter_config.enable_llm_refinement

        fake_task = {"id": "t1", "state": "pending", "pdf_uri": "local://x.pdf"}
        task_config = {"table_backend": "pymupdf", "table_params": {}}
        with (
            patch.object(r, "pa_load_task", return_value=fake_task),
            patch("src.ingest.pre_analysis.runner.PreAnalysisRunner", FakeRunner),
            patch.object(r, "get_object_store"),
            patch.object(r, "PreAnalysisTaskStore"),
            patch.object(r, "PreAnalysisStageStore"),
        ):
            r._run_pre_analysis("t1", task_config)

        assert captured["chapter_max_level"] == 3  # DEFAULT_CHAPTER_MAX_LEVEL
        assert captured["llm"] is False

    def test_from_form_rejects_invalid_json_in_router(self) -> None:
        """chapter_config_json 非法 JSON → ChapterExtractionConfig.from_form 抛 ValueError (router 端映射 400)."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        with pytest.raises(ValueError, match="chapter_config_json JSON 非法"):
            ChapterExtractionConfig.from_form("{not valid}")
