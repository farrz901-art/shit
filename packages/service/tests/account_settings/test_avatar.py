"""模式 1 纯单测: 验 process_avatar_upload (PIL) + store_avatar (ObjectStore)"""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.auth.account_settings_service import delete_avatar, process_avatar_upload, store_avatar


def _make_png_bytes(width: int = 300, height: int = 300, color: str = "red") -> bytes:
    """生成测试 PNG bytes"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_process_avatar_upload_returns_webp():
    png = _make_png_bytes()
    result = process_avatar_upload(png)
    assert isinstance(result, bytes)
    # 验证输出是 WebP (magic bytes: "RIFF" + size + "WEBP")
    assert result[:4] == b"RIFF"
    assert b"WEBP" in result[:12]


def test_process_avatar_upload_resizes_to_256():
    png = _make_png_bytes(width=800, height=600)
    result = process_avatar_upload(png)
    # 重新打开验证
    img = Image.open(io.BytesIO(result))
    assert img.size == (256, 256)


def test_process_avatar_upload_rejects_too_large():
    # 3MB fake bytes (超过 2MB 上限)
    big = b"x" * (3 * 1024 * 1024)
    with pytest.raises(ValueError, match="too large"):
        process_avatar_upload(big)


def test_process_avatar_upload_rejects_invalid_image():
    with pytest.raises(ValueError, match="invalid image"):
        process_avatar_upload(b"not an image")


def test_store_avatar_saves_to_object_store_and_sets_url():
    mock_account = MagicMock(id=42, avatar_url=None)
    mock_session = MagicMock()
    png = _make_png_bytes()

    with patch("src.auth.account_settings_service.get_object_store") as mock_get_store:
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        uri = store_avatar(mock_session, mock_account, png)

    assert "42" in uri  # 包含 account id
    assert uri.startswith(("s3://", "local://"))
    mock_store.put_bytes.assert_called_once()
    assert mock_account.avatar_url == uri
    mock_session.flush.assert_called_once()


def test_pick_avatar_uri_minio_backend():
    from src.auth.account_settings_service import _pick_avatar_uri

    uri = _pick_avatar_uri("minio", 7, "abc123")
    assert uri.startswith("s3://")
    assert "7" in uri
    assert "abc123" in uri


def test_pick_avatar_uri_local_backend():
    from src.auth.account_settings_service import _pick_avatar_uri

    uri = _pick_avatar_uri("local", 7, "abc123")
    assert uri.startswith("local://")
    assert "7" in uri
    assert "abc123" in uri


def test_store_avatar_uses_s3_scheme_for_minio_backend():
    mock_account = MagicMock(id=42, avatar_url=None)
    mock_session = MagicMock()
    png = _make_png_bytes()

    with patch("src.auth.account_settings_service.get_object_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.backend_name.return_value = "minio"
        mock_get_store.return_value = mock_store
        uri = store_avatar(mock_session, mock_account, png)

    assert uri.startswith("s3://")
    assert "rag-avatars" in uri or "avatars" in uri
    assert "42" in uri


def test_delete_avatar_clears_url():
    mock_account = MagicMock(avatar_url="s3://x/y")
    mock_session = MagicMock()
    delete_avatar(mock_session, mock_account)
    assert mock_account.avatar_url is None
    mock_session.flush.assert_called_once()
