"""RequestID middleware 测试 (模式 1, 0 PG)"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.logging_context import current_request_id, current_user_id
from src.core.middleware import RequestIDMiddleware, bind_user_id


@pytest.fixture
def app_with_middleware():
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo():
        return {
            "request_id": current_request_id.get(),
            "user_id": current_user_id.get(),
        }

    return app


def test_middleware_generates_uuid_when_no_header(app_with_middleware):
    client = TestClient(app_with_middleware)
    resp = client.get("/echo")
    assert resp.status_code == 200
    body = resp.json()
    rid = body["request_id"]
    assert uuid.UUID(rid).version == 4
    assert resp.headers["x-request-id"] == rid


def test_middleware_uses_provided_header(app_with_middleware):
    client = TestClient(app_with_middleware)
    resp = client.get("/echo", headers={"X-Request-ID": "custom-req-123"})
    assert resp.status_code == 200
    assert resp.json()["request_id"] == "custom-req-123"
    assert resp.headers["x-request-id"] == "custom-req-123"


def test_middleware_resets_contextvar_after_request(app_with_middleware):
    client = TestClient(app_with_middleware)
    client.get("/echo", headers={"X-Request-ID": "req-1"})
    assert current_request_id.get() is None


def test_bind_user_id_sets_contextvar():
    token = current_user_id.set(None)
    try:
        bind_user_id(42)
        assert current_user_id.get() == 42
    finally:
        current_user_id.reset(token)


def test_bind_user_id_none_clears():
    token = current_user_id.set(99)
    try:
        bind_user_id(None)
        assert current_user_id.get() is None
    finally:
        current_user_id.reset(token)
