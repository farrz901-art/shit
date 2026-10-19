"""测试 kg router SEC-003 修复: /stats + /health 端点鉴权.

模式 1 mock: 不连 PG, mock resolve_user 注入 fake user, 让 require_page 链路可测.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.kg import router as kg_router
from src.middleware.auth import CurrentUser


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(kg_router.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def fake_admin_user() -> CurrentUser:
    return CurrentUser(id=1, public_token="admin-token", role="super_admin", is_account=True)


@pytest.fixture
def fake_regular_user() -> CurrentUser:
    return CurrentUser(id=2, public_token="user-token", role="user", is_account=True)


def _override_resolve_user(user: CurrentUser):
    """构造 dependency_overrides[resolve_user] = lambda: user 的 closure.

    require_page 工厂内的 resolve_user import 来自 src.permissions.guards 命名空间,
    所以必须在两个命名空间都 override 才能完全旁路鉴权链.
    """
    from src.middleware import auth as auth_module
    from src.permissions import guards as guards_module

    return (
        (auth_module.resolve_user, lambda: user),
        (guards_module.resolve_user, lambda: user),
    )


class TestStatsAuth:
    def test_stats_requires_auth_dependency_wired(self, app):
        """verify /stats 端点已挂 require_page('kg') 守卫.

        通过 inspect endpoint signature 验证 Depends 注入存在, 防止回归 SEC-003.
        """
        stats_route = None
        for route in app.routes:
            if getattr(route, "path", None) == "/api/kg/stats" and "GET" in getattr(route, "methods", set()):
                stats_route = route
                break
        assert stats_route is not None, "/api/kg/stats 端点未注册"
        # 依赖列表里必须包含 require_page 工厂产生的闭包
        dep_names = [str(d) for d in stats_route.dependant.dependencies]
        assert any("require_page" in n for n in dep_names), f"/api/kg/stats 缺少 require_page 守卫, deps={dep_names}"

    def test_stats_anonymous_returns_401(self, app, client):
        """anon (无 token) 调 /stats 应该返 401 (resolve_user 拒绝).

        (2026-07-02 修) PR1 v3 后 resolve_user 走真 PG/Redis 链路, 不再是直接 401.
        用 app.dependency_overrides 注入一个永远抛 401 的 stub, 验 stats 透传 401 状态.
        之前的 "裸调" 写法会触发 PG conn timeout (因为 conftest 拿不到 mock).
        """
        from fastapi import HTTPException

        from src.middleware import auth as auth_module
        from src.permissions import guards as guards_module

        def reject_anonymous() -> CurrentUser:
            raise HTTPException(401, "missing x-user-token")

        app.dependency_overrides[auth_module.resolve_user] = reject_anonymous
        app.dependency_overrides[guards_module.resolve_user] = reject_anonymous

        res = client.get("/api/kg/stats")
        assert res.status_code == 401

    def test_stats_authenticated_user_returns_200(self, app, client, fake_admin_user, monkeypatch):
        """登录用户 (super_admin) 调 /stats 应该返 200.

        通过 override resolve_user 注入 fake admin (绕过真实 token 校验 + DB 查询),
        让 require_page 短路 super_admin 分支走完.
        """
        for dep, override in _override_resolve_user(fake_admin_user):
            app.dependency_overrides[dep] = override

        monkeypatch.delenv("DIFY_DATASET_API_KEY", raising=False)
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.counts.return_value = {"nodes": 10, "relations": 20}
            MockClient.return_value = instance

            res = client.get("/api/kg/stats")
            assert res.status_code == 200
            body = res.json()
            assert "neo4j" in body
            assert body["neo4j"]["nodes"] == 10

    def test_stats_regular_user_with_kg_permission_succeeds(self, app, client, fake_regular_user, monkeypatch):
        """普通 user 有 kg 权限 → 200.

        require_page 内部: role='user' 非 super_admin, 走 permission_cache.get('user', 'kg') 路径.
        conftest autouse mock 让 cache.get 永远返 True, 所以普通 user 也通过.
        """
        for dep, override in _override_resolve_user(fake_regular_user):
            app.dependency_overrides[dep] = override

        monkeypatch.delenv("DIFY_DATASET_API_KEY", raising=False)
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.counts.return_value = {"nodes": 5, "relations": 8}
            MockClient.return_value = instance

            res = client.get("/api/kg/stats")
            assert res.status_code == 200

    def test_stats_user_without_kg_permission_returns_403(self, app, client, fake_regular_user, monkeypatch):
        """普通 user 没 kg 权限 → 403 (permission_cache.get 返 False)."""
        for dep, override in _override_resolve_user(fake_regular_user):
            app.dependency_overrides[dep] = override

        # 覆盖 permission_cache.get 让 kg 页面对普通 user 返 False
        from src.permissions import cache as _cache

        monkeypatch.setattr(_cache.permission_cache, "get", lambda role, key: False)

        res = client.get("/api/kg/stats")
        assert res.status_code == 403


class TestHealthAuth:
    def test_health_requires_auth_dependency_wired(self, app):
        """verify /health 端点已挂 require_page('kg') 守卫."""
        health_route = None
        for route in app.routes:
            if getattr(route, "path", None) == "/api/kg/health" and "GET" in getattr(route, "methods", set()):
                health_route = route
                break
        assert health_route is not None, "/api/kg/health 端点未注册"
        dep_names = [str(d) for d in health_route.dependant.dependencies]
        assert any("require_page" in n for n in dep_names), f"/api/kg/health 缺少 require_page 守卫, deps={dep_names}"

    def test_health_anonymous_returns_401(self, app, client):
        """anon 调 /health 应该返 401.

        (2026-07-02 修) 跟 test_stats_anonymous_returns_401 同理, 用 dependency override
        注入一个永远抛 401 的 stub resolve_user.
        """
        from fastapi import HTTPException

        from src.middleware import auth as auth_module
        from src.permissions import guards as guards_module

        def reject_anonymous() -> CurrentUser:
            raise HTTPException(401, "missing x-user-token")

        app.dependency_overrides[auth_module.resolve_user] = reject_anonymous
        app.dependency_overrides[guards_module.resolve_user] = reject_anonymous

        res = client.get("/api/kg/health")
        assert res.status_code == 401

    def test_health_authenticated_succeeds(self, app, client, fake_admin_user):
        """登录用户 (admin) 调 /health 返 200 + {ok: bool}."""
        for dep, override in _override_resolve_user(fake_admin_user):
            app.dependency_overrides[dep] = override

        # 业务侧: DIFY_DATASET_API_KEY 缺失 → ok=False 但仍 200
        with patch.dict("os.environ", {"DIFY_DATASET_API_KEY": ""}, clear=False):
            res = client.get("/api/kg/health")
            assert res.status_code == 200
            assert "ok" in res.json()
            assert res.json()["ok"] is False


class TestExistingEndpointsRequireAuth:
    """(2026-07-02) PR1 v3 加 require_page 守卫的回归测试.

    这些端点在 PR1 v3 后已挂 require_page('kg') 鉴权 (跟 SEC-003 /stats /health 一致),
    不再是公开端点. 早期 SEC-003 留下的 'remain_unauthenticated' 测试假设已过时,
    改名为 'TestExistingEndpointsRequireAuth' 反映新行为.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/api/kg/nodes",
            "/api/kg/relationships",
            "/api/kg/products",
        ],
    )
    def test_other_endpoints_require_auth(self, app, path):
        """PR1 v3 后 /nodes|relationships|products 必须挂 require_page 守卫.

        防止回归: 后续误把守卫删了让端点变成公开访问.
        """
        route = None
        for r in app.routes:
            if getattr(r, "path", None) == path and "GET" in getattr(r, "methods", set()):
                route = r
                break
        assert route is not None, f"{path} 端点未注册"
        dep_names = [str(d) for d in route.dependant.dependencies]
        assert any("require_page" in n for n in dep_names), (
            f"{path} 缺 require_page 守卫 (PR1 v3 加的, 删了就 SEC-003 重复漏洞), deps={dep_names}"
        )


class TestOtherEndpointsRemainUnauthenticated:
    """回归测试: 真公开端点 (datasets/segments/schemas) 仍保持无鉴权.

    这些端点不涉及用户数据, SEC-003 不在范围.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/api/kg/datasets",
            "/api/kg/segments",
            "/api/kg/schemas",
        ],
    )
    def test_public_endpoints_remain_unauthenticated(self, app, path):
        """真公开端点仍保持无鉴权 — 不在 SEC-003 范围."""
        route = None
        for r in app.routes:
            if getattr(r, "path", None) == path and "GET" in getattr(r, "methods", set()):
                route = r
                break
        assert route is not None, f"{path} 端点未注册"
        dep_names = [str(d) for d in route.dependant.dependencies]
        assert not any("require_page" in n for n in dep_names), (
            f"{path} 不应挂 require_page (公开端点), deps={dep_names}"
        )
