"""kg.router FastAPI 路由测试 (httpx + mock)"""

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
    # 默认 super_admin 用户, 旁路 require_page 鉴权链 (override resolve_user 而非 require_page 工厂)
    fake_user = CurrentUser(id=1, public_token="test-token", role="super_admin", is_account=True)
    from src.middleware import auth as auth_module
    from src.permissions import guards as guards_module

    app.dependency_overrides[auth_module.resolve_user] = lambda: fake_user
    app.dependency_overrides[guards_module.resolve_user] = lambda: fake_user
    return TestClient(app)


class TestStats:
    def test_stats_returns_counts_per_label(self, client, monkeypatch):
        # 不设 DIFY_DATASET_API_KEY, 让 dify 段走 except 走空 default
        monkeypatch.delenv("DIFY_DATASET_API_KEY", raising=False)
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            # KgClient.counts() 返回扁平 (router 内部会包到 result["neo4j"])
            instance.counts.return_value = {"nodes": 57, "relations": 82}
            MockClient.return_value = instance
            res = client.get("/api/kg/stats")
            assert res.status_code == 200
            body = res.json()
            # /api/kg/stats?type=all 返回 {neo4j: {...}, dify: {...}}
            assert body["neo4j"] == {"nodes": 57, "relations": 82}


class TestNodes:
    def test_list_nodes_returns_array(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_nodes.return_value = [
                {"id": "1", "label": "产品系列", "props": {"name": "W21"}},
                {"id": "2", "label": "技术参数", "props": {"name": "机座号"}},
            ]
            MockClient.return_value = instance
            res = client.get("/api/kg/nodes")
            assert res.status_code == 200
            body = res.json()
            assert len(body) == 2
            assert body[0]["label"] == "产品系列"

    def test_list_nodes_passes_pagination(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_nodes.return_value = []
            MockClient.return_value = instance
            client.get("/api/kg/nodes?skip=10&limit=25")
            instance.list_nodes.assert_called_once_with(skip=10, limit=25)

    def test_list_nodes_neo4j_unavailable_returns_empty(self, client):
        """Neo4j 不可达 (e.g. 容器没起) 时, 返空 list + 200, 跟 /api/kg/stats 一致."""
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_nodes.side_effect = Exception("ServiceUnavailable")
            MockClient.return_value = instance
            res = client.get("/api/kg/nodes")
            assert res.status_code == 200
            assert res.json() == []


class TestRelationships:
    def test_list_relationships_returns_array(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_relationships.return_value = [
                {
                    "src": "1",
                    "src_label": "产品系列",
                    "type": "具有参数",
                    "dst": "2",
                    "dst_label": "技术参数",
                    "props": {},
                },
            ]
            MockClient.return_value = instance
            res = client.get("/api/kg/relationships")
            assert res.status_code == 200
            body = res.json()
            assert len(body) == 1
            assert body[0]["type"] == "具有参数"

    def test_list_relationships_passes_pagination(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_relationships.return_value = []
            MockClient.return_value = instance
            client.get("/api/kg/relationships?skip=5&limit=50")
            instance.list_relationships.assert_called_once_with(skip=5, limit=50)

    def test_list_relationships_neo4j_unavailable_returns_empty(self, client):
        """Neo4j 不可达时返空 list + 200, 跟 list_nodes 对齐."""
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.list_relationships.side_effect = Exception("ServiceUnavailable")
            MockClient.return_value = instance
            res = client.get("/api/kg/relationships")
            assert res.status_code == 200
            assert res.json() == []


class TestTriples:
    def test_post_empty_rows_returns_zero(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance.batch_upsert_triples.return_value = MagicMock(success=0, failed=0, errors=[])
            MockClient.return_value = instance
            res = client.post("/api/kg/triples", json={"rows": []})
            assert res.status_code == 200
            assert res.json()["success"] == 0

    def test_post_validates_required_fields(self, client):
        res = client.post("/api/kg/triples", json={"rows": [{"from_label": "Product"}]})
        assert res.status_code == 422  # Pydantic validation


class TestProducts:
    def test_get_products_returns_list(self, client):
        with patch.object(kg_router, "KgClient") as MockClient:
            instance = MagicMock()
            instance._store.execute_and_fetch.return_value = [{"id": "1", "model": "1LE0001", "name": "X"}]
            MockClient.return_value = instance
            res = client.get("/api/kg/products")
            assert res.status_code == 200
            body = res.json()
            assert len(body) == 1
            assert body[0]["model"] == "1LE0001"


class TestTasks:
    def test_get_task_status(self, client):
        with patch.object(kg_router, "_task_store") as mock_store:
            from src.kg.tasks import TaskStatus

            mock_store.get.return_value = TaskStatus(
                task_id="abc",
                kind="kg_batch",
                state="done",
                payload={},
                success=10,
                failed=0,
            )
            res = client.get("/api/kg/tasks/abc")
            assert res.status_code == 200
            assert res.json()["state"] == "done"

    def test_get_unknown_task_404(self, client):
        with patch.object(kg_router, "_task_store") as mock_store:
            from src.kg.exceptions import TaskNotFoundError

            mock_store.get.side_effect = TaskNotFoundError("nope")
            res = client.get("/api/kg/tasks/nope")
            assert res.status_code == 404


class TestBatch:
    def test_batch_submits_and_returns_task_id(self, client):
        with patch.object(kg_router, "KgClient") as MockClient, patch.object(kg_router, "_task_store") as mock_store:
            instance = MagicMock()
            MockClient.return_value = instance
            mock_store.submit.return_value = "task123"
            res = client.post("/api/kg/batch", json={"items": []})
            assert res.status_code == 200
            assert res.json()["task_id"] == "task123"


class TestHealth:
    def test_health_returns_ok_status(self, client):
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            res = client.get("/api/kg/health")
            assert res.status_code == 200
            assert "ok" in res.json()

    def test_health_without_api_key(self, client):
        with patch.dict("os.environ", {"DIFY_DATASET_API_KEY": ""}, clear=False):
            res = client.get("/api/kg/health")
            assert res.status_code == 200
            assert res.json()["ok"] is False


class TestDatasets:
    def test_datasets_returns_list(self, client):
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {"data": [{"id": "1", "name": "test"}]}
            res = client.get("/api/kg/datasets")
            assert res.status_code == 200
            assert "data" in res.json()


class TestSegments:
    def test_segments_returns_list(self, client):
        with patch("requests.get") as mock_get:
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {"data": [{"id": "s1", "content": "test"}]}
            res = client.get("/api/kg/segments?dataset_id=ds1&document_id=doc1")
            assert res.status_code == 200
            assert "data" in res.json()
