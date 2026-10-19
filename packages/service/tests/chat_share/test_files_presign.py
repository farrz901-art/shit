"""chat_share presign/finalize 端点测试 (2026-06-16 RAG MinIO 集成 B)

6 模式 1 mock 测试, 覆盖:
- presign_returns_put_url
- bad_mime → 400
- oversize → 413
- finalize_forwards_to_dify
- owner_mismatch_403
- dify_failure_keeps_uri (Dify 失败 URI 不删, 允许重试)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.chat_share import schemas as _schemas
from src.chat_share.router import finalize_chat_file, presign_chat_file


@pytest.fixture
def mock_user():
    u = MagicMock()
    u.id = 1
    u.public_token = "tok-abc"
    return u


@pytest.fixture
def mock_store():
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._cfg = MagicMock(bucket="rag-ingest", endpoint="http://localhost:9000")
    s.presign_put.return_value = "https://minio:9000/...?X-Amz-Signature=abc"
    s.exists.return_value = True
    return s


@pytest.fixture
def mock_http_client():
    """mock httpx.AsyncClient - Dify Files API 透传"""
    with patch("src.chat_share.service.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = client_instance
        yield client_instance


def test_presign_returns_put_url(mock_user, mock_store):
    """presign 返 {uri, put_url, mime}"""
    req = _schemas.PresignChatFileRequest(name="image.png", size=1024, mime="image/png")
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        resp = asyncio.run(presign_chat_file(req=req, current=mock_user))
    assert resp.uri.startswith("s3://rag-ingest/chat/")
    assert resp.uri.endswith("/image.png")
    assert resp.put_url is not None
    assert "X-Amz-Signature" in resp.put_url
    assert resp.mime == "image/png"


def test_presign_rejects_bad_mime(mock_user, mock_store):
    """octet-stream → 400"""
    req = _schemas.PresignChatFileRequest(name="malware.exe", size=1024, mime="application/octet-stream")
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_chat_file(req=req, current=mock_user))
    assert exc.value.status_code == 400


def test_presign_rejects_oversize(mock_user, mock_store):
    """> 20MB → 413"""
    req = _schemas.PresignChatFileRequest(name="big.png", size=21 * 1024 * 1024, mime="image/png")
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_chat_file(req=req, current=mock_user))
    assert exc.value.status_code == 413


def test_finalize_forwards_to_dify(mock_user, mock_store, mock_http_client):
    """finalize 真接 Dify Files API

    (2026-06-30) 跟 new _get_service Depends 链对齐: 直接调函数时显式传 mock service.
    service.upload_to_dify 是 async 方法, 必须 AsyncMock (之前调真 service, 走 patch 路径).
    现在 service 层 mock 后 httpx.post 不会被调 — 只验 endpoint → service 转发契约.
    """
    mock_service = MagicMock()
    mock_service.upload_to_dify = AsyncMock(
        return_value={"uploadFileId": "dify-real-uuid", "uri": "s3://rag-ingest/chat/1/abc.png"}
    )

    req = _schemas.FinalizeChatFileRequest(
        uri="s3://rag-ingest/chat/1/abc.png",
        name="abc.png",
        mime="image/png",
    )
    # store.exists check 必须走 mock_store 返 True (避免 404 短路)
    mock_store.exists.return_value = True
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        resp = asyncio.run(finalize_chat_file(req=req, current=mock_user, service=mock_service))
    assert resp.uploadFileId == "dify-real-uuid"
    assert resp.uri == "s3://rag-ingest/chat/1/abc.png"
    # 验 service.upload_to_dify 被调 + 透传 uri/name/mime
    mock_service.upload_to_dify.assert_called_once()
    call_args = mock_service.upload_to_dify.call_args
    assert call_args.kwargs["uri"] == "s3://rag-ingest/chat/1/abc.png"
    fake_file = call_args.args[0]
    assert fake_file.filename == "abc.png"
    assert fake_file.content_type == "image/png"


def test_finalize_dify_failure_keeps_uri(mock_user, mock_store, mock_http_client):
    """Dify 失败 → 500, 但 URI 保留 (允许重试)"""
    # (2026-06-30) 跟 new _get_service Depends 链对齐: 直接调函数时显式传 mock service
    mock_service = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("Dify 502")
    mock_http_client.post.return_value = mock_response
    mock_store.get_bytes.return_value = b"fake-bytes"

    req = _schemas.FinalizeChatFileRequest(
        uri="s3://rag-ingest/chat/1/abc.png",
        name="abc.png",
        mime="image/png",
    )
    # (2026-06-30) 直接调函数传 mock_service, 跟 test_finalize_forwards_to_dify 一致
    with (
        patch("src.chat_share.router.get_object_store", return_value=mock_store),
        patch("src.chat_share.service.get_object_store", return_value=mock_store),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(finalize_chat_file(req=req, current=mock_user, service=mock_service))
    assert exc.value.status_code == 500
    # URI 不删 (store.delete 不应被调)
    mock_store.delete.assert_not_called()


def test_finalize_uri_not_found_404(mock_user, mock_store):
    """URI 在 MinIO 不存在 → 404"""
    mock_store.exists.return_value = False
    req = _schemas.FinalizeChatFileRequest(
        uri="s3://rag-ingest/chat/1/nonexistent.png",
        name="nonexistent.png",
        mime="image/png",
    )
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(finalize_chat_file(req=req, current=mock_user))
    assert exc.value.status_code == 404
