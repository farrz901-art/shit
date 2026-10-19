"""测试 chat_share presign_chat_file path traversal 防护 (SEC-002).

模式 1 mock: 不连 PG/Redis, mock store + CurrentUser.
覆盖:
- name 含 ../ → schema 拒绝 (Pydantic ValidationError)
- name 含 / → schema 拒绝
- 合法 name → 接受
- router 用 Path.name 兜底防 schema 漏
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.chat_share import schemas as _schemas
from src.chat_share.router import presign_chat_file


@pytest.fixture
def mock_user():
    """当前登录用户 fixture."""
    u = MagicMock()
    u.id = 42
    u.public_token = "tok-abc"
    u.is_admin = False
    return u


@pytest.fixture
def mock_store():
    """mock 对象存储 fixture (local 后端)."""
    s = MagicMock()
    s.backend_name.return_value = "local"
    s.presign_put.return_value = "http://localhost:9000/put?X-Amz-Signature=abc"
    return s


def test_name_with_path_traversal_rejected_by_schema():
    """name 含 ../ → Pydantic ValidationError (FastAPI 翻译成 422)."""
    with pytest.raises(ValidationError) as exc_info:
        _schemas.PresignChatFileRequest(name="../999/x.png", size=1024, mime="image/png")
    # 错误信息应提到 pattern 不匹配
    msg = str(exc_info.value).lower()
    assert "pattern" in msg or "string does not match" in msg


def test_name_with_forward_slash_rejected_by_schema():
    """name 含 / → Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        _schemas.PresignChatFileRequest(name="subdir/x.png", size=1024, mime="image/png")


def test_name_with_backslash_rejected_by_schema():
    """name 含 \\ → Pydantic ValidationError (Windows 路径分隔符也防)."""
    with pytest.raises(ValidationError):
        _schemas.PresignChatFileRequest(name="subdir\\x.png", size=1024, mime="image/png")


def test_name_with_null_byte_rejected_by_schema():
    """name 含 \\0 → Pydantic ValidationError (防 null byte injection)."""
    with pytest.raises(ValidationError):
        _schemas.PresignChatFileRequest(name="image.png\0.exe", size=1024, mime="image/png")


def test_valid_name_accepted_by_schema():
    """合法 name (字母数字._-) → 接受."""
    for name in ["image.png", "doc_v2.pdf", "report-2026.docx", "abc", "a.b.c.d"]:
        req = _schemas.PresignChatFileRequest(name=name, size=1024, mime="image/png")
        assert req.name == name


def test_name_too_long_rejected_by_schema():
    """name > 255 字符 → ValidationError."""
    with pytest.raises(ValidationError):
        _schemas.PresignChatFileRequest(name="a" * 256, size=1024, mime="image/png")


def test_router_path_traversal_fallback(mock_user, mock_store):
    """即便 schema pattern 失效, router 用 Path.name 兜底防 ../.

    模拟 schema 被绕过 (用 construct 跳过校验), 直接传含 ../ 的 name.
    期望: Path("evil/../../../999/x.png").name = "x.png", 落到当前 user (42) 目录,
    不出现 "999" (其他用户 ID).
    """
    req = _schemas.PresignChatFileRequest.model_construct(name="evil/../../../999/x.png", size=1024, mime="image/png")
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        resp = asyncio.run(presign_chat_file(req=req, current=mock_user))

    # 兜底: URI 路径里不应包含其他 user id "999"
    assert "999" not in resp.uri, f"path traversal 没被拦: uri={resp.uri}"
    # 落到当前 user (42) 目录, 文件名是 Path.name 截后的 "x.png"
    assert "42" in resp.uri
    assert resp.uri.endswith("/x.png")
    # URI 应是 local backend 格式
    assert resp.uri.startswith("local://chat/42/")


def test_router_dot_dot_only_fallback(mock_user, mock_store):
    """name 仅 ".." → Path.name = "..", 兜底 422."""
    req = _schemas.PresignChatFileRequest.model_construct(name="..", size=1024, mime="image/png")
    from fastapi import HTTPException

    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(presign_chat_file(req=req, current=mock_user))
    assert exc.value.status_code == 422
    assert "invalid filename" in exc.value.detail


def test_router_minio_backend_uses_safe_name(mock_user, mock_store):
    """minio 后端同样用 safe_name 拼 URI."""
    mock_store.backend_name.return_value = "minio"
    req = _schemas.PresignChatFileRequest.model_construct(name="../../etc/passwd.png", size=1024, mime="image/png")
    with patch("src.chat_share.router.get_object_store", return_value=mock_store):
        resp = asyncio.run(presign_chat_file(req=req, current=mock_user))

    # safe_name = Path("../../etc/passwd.png").name = "passwd.png"
    assert "etc" not in resp.uri
    assert "42" in resp.uri
    assert resp.uri.endswith("/passwd.png")
    assert resp.uri.startswith("s3://rag-ingest/chat/42/")
