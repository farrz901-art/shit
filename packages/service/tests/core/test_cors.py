"""测试 CORS ENV 隔离.

SEC-005: production 环境禁止 localhost 跨域.
模式 1 mock, 用 TestClient 发 OPTIONS 请求验 CORS header.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_test_client():
    """在 patch 的 env 下创建 app 并返回 TestClient"""
    from src.core.app_factory import create_app

    app = create_app()
    return TestClient(app)


class TestCorsDevelopment:
    """development 环境 — 默认放行 localhost"""

    def test_dev_allows_localhost_3000(self):
        with patch.dict("os.environ", {"ENV": "development"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_dev_allows_localhost_8000(self):
        with patch.dict("os.environ", {"ENV": "development"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://localhost:8000",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_dev_allows_127_0_0_1(self):
        with patch.dict("os.environ", {"ENV": "development"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://127.0.0.1:3000",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"

    def test_dev_rejects_evil_site(self):
        with patch.dict("os.environ", {"ENV": "development"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "https://evil.com",
                    "access-control-request-method": "GET",
                },
            )
            # preflight 不匹配 = 400, 且无 CORS header
            assert resp.status_code == 400


class TestCorsProduction:
    """production 环境 — 只从 CORS_ALLOW_ORIGINS 白名单读"""

    def test_prod_rejects_localhost_by_default(self):
        """ENV=production 且没配 CORS_ALLOW_ORIGINS, localhost 拒绝."""
        with patch.dict("os.environ", {"ENV": "production"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET",
                },
            )
            # preflight 不匹配 = 400, 且无 CORS header
            assert resp.status_code == 400

    def test_prod_rejects_localhost_when_whitelist_set(self):
        """production 配了白名单, localhost 不在内则拒绝."""
        with patch.dict(
            "os.environ",
            {"ENV": "production", "CORS_ALLOW_ORIGINS": "https://app.example.com"},
            clear=False,
        ):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET",
                },
            )
            # preflight 不匹配 = 400, 且无 CORS header
            assert resp.status_code == 400

    def test_prod_allows_whitelisted_origin(self):
        """production 白名单内的 origin 允许."""
        with patch.dict(
            "os.environ",
            {"ENV": "production", "CORS_ALLOW_ORIGINS": "https://app.example.com"},
            clear=False,
        ):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "https://app.example.com",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"

    def test_prod_allows_multiple_whitelisted_origins(self):
        """production 白名单多 origin, 逗号分隔."""
        with patch.dict(
            "os.environ",
            {
                "ENV": "production",
                "CORS_ALLOW_ORIGINS": "https://app.example.com,https://admin.example.com",
            },
            clear=False,
        ):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "https://admin.example.com",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "https://admin.example.com"

    def test_prod_empty_cors_allow_origins_no_cors(self):
        """CORS_ALLOW_ORIGINS 空字符串 -> 无 CORS header 发出."""
        with patch.dict(
            "os.environ",
            {"ENV": "production", "CORS_ALLOW_ORIGINS": ""},
            clear=False,
        ):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "https://app.example.com",
                    "access-control-request-method": "GET",
                },
            )
            # preflight 不匹配 (空列表) = 400
            assert resp.status_code == 400


class TestCorsUnsetEnv:
    """ENV 未设置 — 默认走 development 行为"""

    def test_unset_env_defaults_to_dev(self):
        """ENV 不设时, 默认 development, localhost 放行."""
        with patch.dict("os.environ", {"ENV": "development"}, clear=False):
            client = _make_test_client()
            resp = client.options(
                "/api/v1/health",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET",
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
