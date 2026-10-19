"""ingest read_task_file / download_zip / upload fallback 走 ABC 测试 (2026-06-16)

4 模式 1 mock 测试.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from src.ingest.pdf_processing.router import read_task_file, upload
from src.storage.object_store import ObjectMeta


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
    s.presign_get.return_value = "https://minio:9000/...?X-Amz-Signature=read"
    return s


def test_read_task_file_returns_presigned_url(mock_user, mock_store):
    """read_task_file 返 {name, url, size, mime}, 不再 read_text."""
    with (
        patch("src.ingest.pdf_processing.router._resolve_task") as mock_resolve,
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
    ):
        t = MagicMock()
        t.work_dir = "s3://rag-ingest/inputs/abc/"
        mock_resolve.return_value = t
        mock_store.list_prefix.return_value = [
            ObjectMeta(uri="s3://rag-ingest/inputs/abc/output/foo.md", size=500, mime=None)
        ]
        resp = read_task_file(task_id="abc", name="foo.md", user=mock_user)
    assert resp["name"] == "foo.md"
    assert resp["url"] is not None
    assert "X-Amz-Signature" in resp["url"]
    assert resp["size"] == 500
    assert resp["mime"] == "text/markdown"
    assert "content" not in resp


def test_read_task_file_not_found_404(mock_user, mock_store):
    """name 不在 outputs/ → 404"""
    with (
        patch("src.ingest.pdf_processing.router._resolve_task") as mock_resolve,
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
    ):
        t = MagicMock()
        t.work_dir = "s3://rag-ingest/inputs/abc/"
        mock_resolve.return_value = t
        mock_store.list_prefix.return_value = []
        with pytest.raises(HTTPException) as exc:
            read_task_file(task_id="abc", name="nonexistent.md", user=mock_user)
    assert exc.value.status_code == 404


def test_read_task_file_rejects_traversal(mock_user, mock_store):
    """name 含 '..' → 400"""
    with (
        patch("src.ingest.pdf_processing.router._resolve_task") as mock_resolve,
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
    ):
        t = MagicMock()
        t.work_dir = "s3://rag-ingest/inputs/abc/"
        mock_resolve.return_value = t
        with pytest.raises(HTTPException) as exc:
            read_task_file(task_id="abc", name="../../etc/passwd", user=mock_user)
    assert exc.value.status_code == 400


def test_upload_fallback_writes_via_abc(mock_user, mock_store):
    """POST /upload (multipart fallback) 走 store.put_stream, 不写本地 FS."""
    f = MagicMock(spec=UploadFile)
    f.filename = "test.pdf"
    f.content_type = "application/pdf"
    f.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])
    f.size = 12

    background = MagicMock()
    with (
        patch("src.ingest.pdf_processing.router.get_object_store", return_value=mock_store),
        patch("src.ingest.pdf_processing.router._save"),
    ):
        resp = asyncio.run(upload(background=background, user=mock_user, files=[f]))
    mock_store.put_stream.assert_called_once()
    assert resp["task_id"]
    assert resp["state"] == "queued"
    assert resp["total_files"] == 1
