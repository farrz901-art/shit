"""chat_share files upload 测试 (2026-06-16)

用例: 上传 200 / 超大 413 / 禁用类型 400 / 无鉴权 401 / 真 Dify 透传.

- 鉴权走 dependency_overrides (跟 approvals / memory router 测试一致)
- service.upload_to_dify 是 async 方法, 测试用 AsyncMock 返回
- 大小 + 类型校验在 router 层 (_validate_upload), 失败 → 4xx
- (2026-06-16) 新增 test_upload_to_dify_real_dify_api: 验证 service 层真接 Dify Files API
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_user(id_: int = 1) -> Any:
    """构造 mock CurrentUser."""
    from src.middleware.auth import CurrentUser

    return CurrentUser(
        id=id_,
        public_token=f"tok-{id_}",
        role="user",  # is_admin 是 property, 从 role 派生
        is_account=False,
    )


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.upload_to_dify = AsyncMock(return_value={"uploadFileId": "file-abc-123", "uri": ""})
    return svc


@pytest.fixture
def app_with_chat_share(mock_service):
    """构造 FastAPI app + 鉴权覆盖, 挂上 chat_share_router.

    (2026-06-30) 改 app.dependency_overrides 模式, 跟 test_router.py / approvals 测试一致 —
    之前 router_mod._get_service = lambda: mock_service 在 Depends 改成 generator 后失效.
    """
    from src.chat_share import router as router_mod
    from src.middleware.auth import resolve_user

    app = FastAPI()
    app.include_router(router_mod.router)
    # 覆盖 service: 直接返 mock 实例 (避开 SqlAlchemy repo 真 DB 调用)
    app.dependency_overrides[router_mod._get_service] = lambda: mock_service
    app.dependency_overrides[resolve_user] = lambda: _make_user(id_=1)
    return app


@pytest.fixture
def client(app_with_chat_share):
    return TestClient(app_with_chat_share)


def test_upload_file_200_returns_upload_file_id(client, mock_service):
    """上传有效文件 → 200 + {uploadFileId: ...}"""
    resp = client.post(
        "/api/chat/files",
        files={"file": ("test.png", b"fake-png-bytes", "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["uploadFileId"] == "file-abc-123"


def test_upload_file_oversize_413(client, mock_service):
    """>20MB → 413"""
    # 上传 21MB 文件
    big_content = b"x" * (21 * 1024 * 1024)
    resp = client.post(
        "/api/chat/files",
        files={"file": ("big.pdf", big_content, "application/pdf")},
    )
    assert resp.status_code == 413


def test_upload_file_disallowed_type_400(client, mock_service):
    """.exe / application/octet-stream → 400 (禁用类型)"""
    resp = client.post(
        "/api/chat/files",
        files={"file": ("hack.exe", b"MZ\x00\x00", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_upload_file_401_without_auth(mock_service):
    """非 dev mode + 无 cookie → 401 — 单独构造一个无 overrides 的 app"""
    from src.chat_share import router as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    no_auth_client = TestClient(app)

    os.environ.pop("RAG_DEV_AUTH", None)
    resp = no_auth_client.post(
        "/api/chat/files",
        files={"file": ("test.png", b"x", "image/png")},
    )
    assert resp.status_code == 401


# (2026-06-16) B 集成: 验证 service.upload_to_dify 真接 Dify Files API
# 走真 service 实例 (不 mock service), 用 patch 替换 store + httpx, 验 httpx post
# 调用 + Dify response 透传 + uri 字段
def test_upload_to_dify_real_dify_api():
    """service.upload_to_dify 真调 Dify /files/upload + 透传 id.

    流程:
    - 真实 ChatShareService(repo=MagicMock()) 实例
    - mock ObjectStore.get_bytes 返 b"fake-bytes"
    - mock httpx.AsyncClient.post 返 {"id": "dify-real-uuid"}
    - 断言: post URL 含 /files/upload, response.uploadFileId == "dify-real-uuid"
    """
    from src.chat_share.service import ChatShareService

    # mock store.get_bytes
    mock_store = MagicMock()
    mock_store.get_bytes.return_value = b"fake-bytes"

    # mock httpx AsyncClient
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "dify-real-uuid"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    svc = ChatShareService(repo=MagicMock())
    fake_file = MagicMock()
    fake_file.filename = "test.png"
    fake_file.content_type = "image/png"

    with (
        patch("src.chat_share.service.get_object_store", return_value=mock_store),
        patch("src.chat_share.service.httpx.AsyncClient", return_value=mock_client),
        patch.dict(
            os.environ,
            {"DIFY_BASE_URL": "http://dify.test", "DIFY_DATASET_API_KEY": "key-xyz"},
        ),
    ):
        result = asyncio.run(svc.upload_to_dify(fake_file, uri="s3://rag-ingest/chat/1/test.png"))

    assert result["uploadFileId"] == "dify-real-uuid"
    assert result["uri"] == "s3://rag-ingest/chat/1/test.png"

    # 验 httpx post 被调 + URL 含 /files/upload
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "/files/upload" in call_args[0][0]
    assert "Bearer key-xyz" in call_args.kwargs.get("headers", {}).get("Authorization", "")
    # 验 store.get_bytes 被调
    mock_store.get_bytes.assert_called_once_with("s3://rag-ingest/chat/1/test.png")
