"""output_api 走 ABC 测试 (2026-06-16 D 集成)

4-5 模式 1 mock 测试, 覆盖:
- list_files 调 store.list_prefix(outputs/), 返 {name, size, mtime}
- list_files 按 mtime 倒序
- list_files 跳 .md/.json 之外的扩展名
- read_file 返 {name, url, size, mime}, 走 presigned GET
- read_file 不存在 → 404
- read_file 非法 name → 400
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.product_decoders import output_api
from src.storage.object_store import ObjectMeta


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._cfg = MagicMock(bucket="rag-ingest", endpoint="http://localhost:9000")
    s.list_prefix.return_value = [
        ObjectMeta(uri="s3://rag-ingest/outputs/foo.md", size=100, last_modified=1700000000.0),
        ObjectMeta(uri="s3://rag-ingest/outputs/bar.json", size=200, last_modified=1700000100.0),
    ]
    s.presign_get.return_value = "https://minio:9000/...?X-Amz-Signature=read"
    return s


def test_list_files_uses_abc(mock_store):
    """list_files 调 store.list_prefix(_outputs_prefix())"""
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        resp = output_api.list_files()
    assert "files" in resp
    assert len(resp["files"]) == 2
    # bar.json mtime 更大, 按 mtime 倒序排在前面
    assert resp["files"][0]["name"] == "bar.json"
    assert resp["files"][0]["size"] == 200
    assert resp["files"][1]["name"] == "foo.md"
    assert resp["files"][1]["size"] == 100
    mock_store.list_prefix.assert_called_once()


def test_list_files_filters_non_md_json(mock_store):
    """.svg 等不在白名单的扩展名被过滤"""
    mock_store.list_prefix.return_value = [
        ObjectMeta(uri="s3://rag-ingest/outputs/foo.md", size=100, last_modified=1.0),
        ObjectMeta(uri="s3://rag-ingest/outputs/x.svg", size=200, last_modified=2.0),
        ObjectMeta(uri="s3://rag-ingest/outputs/bar.json", size=300, last_modified=3.0),
    ]
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        resp = output_api.list_files()
    names = [f["name"] for f in resp["files"]]
    assert "x.svg" not in names
    assert "foo.md" in names
    assert "bar.json" in names


def test_list_files_sorted_by_mtime_desc(mock_store):
    """按 mtime 倒序"""
    mock_store.list_prefix.return_value = [
        ObjectMeta(uri="s3://rag-ingest/outputs/old.md", size=100, last_modified=1000.0),
        ObjectMeta(uri="s3://rag-ingest/outputs/new.md", size=200, last_modified=2000.0),
    ]
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        resp = output_api.list_files()
    assert resp["files"][0]["name"] == "new.md"
    assert resp["files"][1]["name"] == "old.md"


def test_read_file_returns_presigned_url(mock_store):
    """read_file 返 {name, url, size, mime}, 走 presigned GET, 不再 read_text"""
    mock_store.list_prefix.return_value = [
        ObjectMeta(uri="s3://rag-ingest/outputs/foo.md", size=500, last_modified=1.0)
    ]
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        resp = output_api.read_file(name="foo.md")
    assert resp["name"] == "foo.md"
    assert resp["url"] is not None
    assert "X-Amz-Signature" in resp["url"]
    assert resp["size"] == 500
    assert resp["mime"] == "text/markdown"
    assert "content" not in resp  # 关键: 不再有 content 字段


def test_read_file_not_found_404(mock_store):
    mock_store.list_prefix.return_value = []
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            output_api.read_file(name="nonexistent.md")
    assert exc.value.status_code == 404


def test_read_file_rejects_unsafe_name(mock_store):
    """含 .. 路径穿越 → 400"""
    with patch("src.product_decoders.output_api.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            output_api.read_file(name="../../etc/passwd")
    assert exc.value.status_code == 400
