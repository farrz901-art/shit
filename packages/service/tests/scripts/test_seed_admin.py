"""seed_admin.py 脚本测试 — mock httpx 调 API"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_seed_admin_success(monkeypatch, capsys):
    monkeypatch.setenv("RAG_API_BASE", "http://api:8000")
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-tok")
    monkeypatch.setenv("RAG_SEED_ADMIN_EMAIL", "first@x.com")
    monkeypatch.setenv("RAG_SEED_ADMIN_PASSWORD", "longpassword")

    fake_response = MagicMock(status_code=200, json=lambda: {"account_id": 1, "email": "first@x.com"})
    with patch("httpx.post", return_value=fake_response) as m:
        from scripts.seed_admin import main

        main()
    out = capsys.readouterr().out
    assert "创 admin" in out
    assert m.called
    # 验 header 跟 body
    call_kwargs = m.call_args.kwargs
    assert call_kwargs["headers"]["x-admin-token"] == "env-tok"
    assert call_kwargs["json"]["email"] == "first@x.com"


def test_seed_admin_missing_env(monkeypatch, capsys):
    monkeypatch.delenv("RAG_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("RAG_SEED_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("RAG_SEED_ADMIN_PASSWORD", raising=False)
    with patch("httpx.post") as m:
        from scripts.seed_admin import main

        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    assert not m.called


def test_seed_admin_already_exists(monkeypatch, capsys):
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-tok")
    monkeypatch.setenv("RAG_SEED_ADMIN_EMAIL", "first@x.com")
    monkeypatch.setenv("RAG_SEED_ADMIN_PASSWORD", "longpassword")
    fake_response = MagicMock(status_code=409, text="admin already initialized")
    with patch("httpx.post", return_value=fake_response):
        from scripts.seed_admin import main

        main()  # 不应 raise
    out = capsys.readouterr().out
    assert "已存在" in out
