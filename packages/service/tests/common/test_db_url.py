"""get_rag_db_url() 单测 (TDD, 2026-06-18 PG env 统一)."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest


@pytest.fixture(autouse=True)
def _clean_pg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试清空 PG_* env, 避免外部 .env.local 污染."""
    for k in ("PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_DATABASE"):
        monkeypatch.delenv(k, raising=False)


def test_default_when_no_env() -> None:
    """无 PG_* env → 走 defaults.py 默认值."""
    from src.common.db_url import get_rag_db_url

    url = get_rag_db_url()
    assert url == "postgresql+psycopg://postgres:postgres@localhost:5432/rag"


def test_uses_pg_env_overrides() -> None:
    """5 env 全设 → URL 含新值."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_HOST"] = "pg.prod"
    os.environ["PG_PORT"] = "6432"
    os.environ["PG_USER"] = "alice"
    os.environ["PG_PASSWORD"] = "s3cret"
    os.environ["PG_DATABASE"] = "prod_rag"

    url = get_rag_db_url()
    assert url == "postgresql+psycopg://alice:s3cret@pg.prod:6432/prod_rag"


def test_url_encodes_password_with_at_sign() -> None:
    """密码含 @ 必须 URL-encode 成 %40, 否则 urlparse 把 @ 后面当 host."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p@ss@word"
    url = get_rag_db_url()
    assert url == "postgresql+psycopg://postgres:p%40ss%40word@localhost:5432/rag"
    p = urlparse(url)
    assert p.hostname == "localhost"
    assert p.port == 5432
    from urllib.parse import unquote

    assert unquote(p.password or "") == "p@ss@word"


def test_url_encodes_password_with_colon() -> None:
    """密码含 : 必须 %3A, 否则 urlparse 把 : 当 host:port 分隔."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p:ss"
    url = get_rag_db_url()
    assert ":p%3Ass@" in url


def test_url_encodes_password_with_slash() -> None:
    """密码含 / 必须 %2F, 否则跟 path 串了."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p/ss"
    url = get_rag_db_url()
    assert ":p%2Fss@" in url


def test_url_encodes_password_with_space() -> None:
    """密码含空格 必须 %20."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "hello world"
    url = get_rag_db_url()
    assert ":hello%20world@" in url


def test_url_encodes_user_with_special() -> None:
    """user 含 @ 也要 encode."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_USER"] = "ad@min"
    url = get_rag_db_url()
    assert "://ad%40min:" in url


def test_url_encodes_database_with_special() -> None:
    """database 含空格 也要 encode."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_DATABASE"] = "my db"
    url = get_rag_db_url()
    assert url.endswith("/my%20db")


def test_port_cast_from_string_env() -> None:
    """env 里 PG_PORT 是 str, 必须 int() 转."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PORT"] = "6543"
    url = get_rag_db_url()
    assert ":6543/" in url


def test_special_chars_round_trip() -> None:
    """综合: 5 env 全设 + 各种特殊字符, urlparse 拆回字段跟原值相等."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_HOST"] = "pg.test"
    os.environ["PG_PORT"] = "5432"
    os.environ["PG_USER"] = "ad@min"
    os.environ["PG_PASSWORD"] = "p@ss:wo/rd !"
    os.environ["PG_DATABASE"] = "db 1"

    url = get_rag_db_url()
    from urllib.parse import unquote

    p = urlparse(url)
    assert p.hostname == "pg.test"
    assert p.port == 5432
    assert unquote(p.username or "") == "ad@min"
    assert unquote(p.password or "") == "p@ss:wo/rd !"
    assert unquote((p.path or "").lstrip("/")) == "db 1"
