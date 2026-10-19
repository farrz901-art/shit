"""auth/router.py mock 单元测试"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.router import router


@patch("src.auth.router.session_scope")
def test_create_anon_token_returns_token(mock_scope_cls):
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post("/api/auth/anon")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert len(data["token"]) == 64  # 32 bytes hex


@patch("src.auth.router.session_scope")
def test_migrate_valid_token(mock_scope_cls):
    mock_session = MagicMock()
    user = MagicMock()
    user.public_token = "valid_token_here"
    mock_session.query.return_value.filter_by.return_value.first.return_value = user
    mock_scope_cls.return_value.__enter__.return_value = mock_session

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post("/api/auth/migrate", json={"token": "valid_token_here"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@patch("src.auth.router.session_scope")
def test_migrate_invalid_token(mock_scope_cls):
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    mock_scope_cls.return_value.__enter__.return_value = mock_session

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post("/api/auth/migrate", json={"token": "bad_token"})
    assert resp.status_code == 400
