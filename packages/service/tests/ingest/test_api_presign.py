"""ingest presign/finalize 端点测试 (2026-06-16 RAG MinIO 集成)

7 模式 1 mock 测试, 覆盖:
- presign_upload 返 {task_id, uploads: [{name, uri, put_url, mime}]}
- presign_upload 不支持的扩展名 → 400
- presign_upload 文件超 50MB → 413
- presign_upload 任务总超 200MB → 413
- finalize_upload state != queued → 409
- finalize_upload 启动 BackgroundTask
- _collect_output_files 走 ABC list_prefix
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.ingest.pdf_processing.router import (
    _collect_output_files,
    _run_ingest,
    finalize_upload,
    presign_upload,
)
from src.ingest.pdf_processing.schemas_presign import FinalizeUploadRequest, PresignFileItem, PresignUploadRequest


@pytest.fixture
def mock_user():
    u = MagicMock()
    u.public_token = "tok-abc"
    u.id = 1
    return u


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.backend_name.return_value = "local"
    s.presign_put.return_value = "https://minio:9000/...?X-Amz-Signature=abc"
    return s


def _patched_presign(req, mock_user, mock_store):
    """patch get_object_store + _save (避免 PG 写)"""
    with (
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
        patch("src.ingest.pdf_processing.router._save"),
    ):
        return asyncio.run(presign_upload(req=req, current=mock_user))


def test_presign_upload_returns_put_url(mock_user, mock_store):
    """presign 返 {task_id, uploads: [{name, uri, put_url, mime}]}"""
    req = PresignUploadRequest(files=[PresignFileItem(name="foo.pdf", size=1024, mime="application/pdf")])
    resp = _patched_presign(req, mock_user, mock_store)
    assert resp.task_id
    assert len(resp.uploads) == 1
    item = resp.uploads[0]
    assert item.name == "foo.pdf"
    assert item.uri.startswith("local://inputs/")  # backend 是 local
    assert item.put_url is not None


def test_presign_upload_rejects_bad_ext(mock_user, mock_store):
    """.exe 等不支持扩展名 → 400"""
    req = PresignUploadRequest(files=[PresignFileItem(name="virus.exe", size=1024, mime="application/octet-stream")])
    with (
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
        patch("src.ingest.pdf_processing.router._save"),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_upload(req=req, current=mock_user))
    assert exc.value.status_code == 400
    assert "不支持的格式" in str(exc.value.detail)


def test_presign_upload_rejects_oversize_file(mock_user, mock_store):
    """单文件 > 50MB → 413"""
    req = PresignUploadRequest(files=[PresignFileItem(name="big.pdf", size=60 * 1024 * 1024, mime="application/pdf")])
    with (
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
        patch("src.ingest.pdf_processing.router._save"),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_upload(req=req, current=mock_user))
    assert exc.value.status_code == 413


def test_presign_upload_rejects_oversize_total(mock_user, mock_store):
    """总大小 > 200MB → 413"""
    files = [PresignFileItem(name=f"f{i}.pdf", size=50 * 1024 * 1024, mime="application/pdf") for i in range(5)]
    req = PresignUploadRequest(files=files)
    with (
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
        patch("src.ingest.pdf_processing.router._save"),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_upload(req=req, current=mock_user))
    assert exc.value.status_code == 413


def test_finalize_upload_rejects_wrong_state(mock_user, mock_store):
    """task state != queued → 409"""
    req1 = PresignUploadRequest(files=[PresignFileItem(name="foo.pdf", size=1024, mime="application/pdf")])
    resp1 = _patched_presign(req1, mock_user, mock_store)

    # finalize_upload 用 session_scope + execute(...).with_for_update().scalar_one_or_none()
    # mock 链: session_scope() → s.execute(...) → .scalar_one_or_none() → mock_task
    mock_task = MagicMock()
    mock_task.state = "running"
    mock_task.id = "task-abc"
    mock_task.work_dir = "s3://rag-ingest/inputs/abc/"
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_task
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    with patch("src.ingest.pdf_processing.router.session_scope", return_value=mock_scope):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(finalize_upload(req=FinalizeUploadRequest(task_id=resp1.task_id), current=mock_user))
    assert exc.value.status_code == 409


def test_finalize_upload_starts_background_task(mock_user, mock_store):
    """finalize 调 background.add_task(_run_ingest, task_id, workdir_uri)"""
    req1 = PresignUploadRequest(files=[PresignFileItem(name="foo.pdf", size=1024, mime="application/pdf")])
    resp1 = _patched_presign(req1, mock_user, mock_store)
    background = MagicMock()

    mock_task = MagicMock()
    mock_task.state = "queued"
    mock_task.work_dir = "s3://rag-ingest/inputs/abc/"
    mock_task.id = "task-abc"
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_task
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    with patch("src.ingest.pdf_processing.router.session_scope", return_value=mock_scope):
        resp2 = asyncio.run(
            finalize_upload(
                req=FinalizeUploadRequest(task_id=resp1.task_id),
                current=mock_user,
                background=background,
            )
        )
    assert resp2.state == "running"
    background.add_task.assert_called_once()
    args = background.add_task.call_args
    assert args[0][0] == _run_ingest
    assert args[0][1] == "task-abc"
    assert args[0][2] == "s3://rag-ingest/inputs/abc/"


def test_collect_output_files_uses_abc_list_prefix(mock_store):
    """_collect_output_files 调 store.list_prefix(workdir_uri + 'output/')"""
    from src.storage.object_store import ObjectMeta

    mock_store.list_prefix.return_value = [
        ObjectMeta(uri="s3://rag-ingest/inputs/abc/output/foo.md", size=100, mime=None),
        ObjectMeta(uri="s3://rag-ingest/inputs/abc/output/bar.svg", size=200, mime=None),
    ]
    out = _collect_output_files("s3://rag-ingest/inputs/abc/", mock_store)
    assert len(out) == 2
    assert out[0].name == "foo.md"
    assert out[1].name == "bar.svg"
    mock_store.list_prefix.assert_called_once_with("s3://rag-ingest/inputs/abc/output/")
