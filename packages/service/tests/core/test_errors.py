"""FastAPI 全局异常 handler 测试 (模式 1, 0 PG)"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.core.errors import install_error_handlers


@pytest.fixture
def app_with_handlers(monkeypatch):
    error_sink_calls = []

    def fake_sink(level, exc, request):
        error_sink_calls.append({"level": level, "exc": exc, "path": request.url.path if request else None})

    monkeypatch.setattr("src.core.errors._error_sink_sync", fake_sink)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise-http-404")
    async def raise_404():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/raise-validation")
    async def validate(q: int):
        return {"q": q}

    @app.get("/raise-runtime")
    async def raise_runtime():
        raise RuntimeError("boom")

    return app, error_sink_calls


def test_4xx_returns_detail_no_error_log(app_with_handlers):
    app, error_sink_calls = app_with_handlers
    client = TestClient(app)
    resp = client.get("/raise-http-404")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "not found"}
    assert error_sink_calls == []


def test_422_validation_error_logs_warning(app_with_handlers):
    app, error_sink_calls = app_with_handlers
    client = TestClient(app)
    resp = client.get("/raise-validation")
    assert resp.status_code == 422
    assert error_sink_calls == []


def test_5xx_returns_500_writes_error_log(app_with_handlers):
    """RuntimeError → 500 with generic detail + _error_sink 调 1 次"""
    app, error_sink_calls = app_with_handlers
    # raise_server_exceptions=False 避免 Starlette ServerErrorMiddleware 重抛
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/raise-runtime")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    body_text = resp.text
    assert "Traceback" not in body_text
    assert "boom" not in body_text
    assert len(error_sink_calls) == 1
    assert error_sink_calls[0]["level"] == "ERROR"
    assert isinstance(error_sink_calls[0]["exc"], RuntimeError)


def test_5xx_error_sink_failure_does_not_crash(monkeypatch):
    def boom_sink(*a, **k):
        raise RuntimeError("PG down")

    monkeypatch.setattr("src.core.errors._error_sink_sync", boom_sink)

    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise")
    async def raise_x():
        raise ValueError("user err")

    # raise_server_exceptions=False 避免 Starlette ServerErrorMiddleware 重抛
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/raise")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}


# (2026-07-09) LLM helper 异常类测试, llm_helper 抛这 2 类 → CrossPageMerger 优雅降级


def test_llm_unavailable_error_inherits_exception() -> None:
    from src.core.errors import LLMUnavailableError

    err = LLMUnavailableError("ollama down")
    assert isinstance(err, Exception)
    assert "ollama down" in str(err)


def test_llm_unavailable_error_keeps_backend_attr() -> None:
    from src.core.errors import LLMUnavailableError

    err = LLMUnavailableError("ollama down", backend="ollama")
    assert err.backend == "ollama"


def test_llm_parsing_error_inherits_exception() -> None:
    from src.core.errors import LLMParsingError

    err = LLMParsingError("invalid json")
    assert isinstance(err, Exception)
    assert "invalid json" in str(err)


def test_llm_parsing_error_keeps_raw_response() -> None:
    from src.core.errors import LLMParsingError

    err = LLMParsingError("invalid json", raw_response="not a json")
    assert err.raw_response == "not a json"
