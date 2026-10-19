"""neo4j.py 测试 (2026-06-09 从 tests/rag/knowledge_graph/test_neo4j_client.py 迁来)"""

from unittest.mock import MagicMock, patch

import pytest


def test_neo4j_config_default():
    from src.kg.neo4j import Neo4jConfig

    cfg = Neo4jConfig()
    assert cfg.uri == "bolt://localhost:7687"
    assert cfg.username == "neo4j"
    assert cfg.password == "neo4j"


def test_neo4j_config_custom():
    from src.kg.neo4j import Neo4jConfig

    cfg = Neo4jConfig(uri="bolt://host:7687", username="u", password="p", database="d")
    assert cfg.uri == "bolt://host:7687"
    assert cfg.username == "u"


def test_neo4j_store_init():
    from src.kg.neo4j import Neo4jStore

    store = Neo4jStore()
    assert store._config is not None
    assert store._driver is None


def test_neo4j_store_close_no_driver():
    from src.kg.neo4j import Neo4jStore

    store = Neo4jStore()
    store.close()  # 不应抛错


def test_context_manager():
    from src.kg.neo4j import Neo4jStore

    store = Neo4jStore()
    mock_driver = MagicMock()
    store._driver = mock_driver
    with store as s:
        assert s is store
    mock_driver.close.assert_called_once()


class TestNeo4jConfigFromEnv:
    """_config_from_env 读 NEO4J_USER (不是 NEO4J_USERNAME)"""

    def test_config_from_env_uses_user_key(self, monkeypatch):
        """env 用 NEO4J_USER (跟 scripts/neo4j_import.py + .env.example 一致)"""
        from src.kg.neo4j import Neo4jStore

        monkeypatch.setenv("NEO4J_URI", "neo4j+s://x.databases.neo4j.io")
        monkeypatch.setenv("NEO4J_USER", "alice")
        monkeypatch.setenv("NEO4J_PASSWORD", "pw")
        monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
        store = Neo4jStore()
        assert store._config.uri == "neo4j+s://x.databases.neo4j.io"
        assert store._config.username == "alice"
        assert store._config.password == "pw"
        assert store._config.database == "neo4j"

    def test_config_from_env_falls_back_to_default(self, monkeypatch):
        """env 全没设时, 默认走 bolt://localhost:7687 / neo4j / neo4j / neo4j"""
        for k in ["NEO4J_URI", "NEO4J_USER", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"]:
            monkeypatch.delenv(k, raising=False)
        from src.kg.neo4j import Neo4jStore

        store = Neo4jStore()
        assert store._config.uri == "bolt://localhost:7687"
        assert store._config.username == "neo4j"
        assert store._config.password == "neo4j"
        assert store._config.database == "neo4j"


class TestNeo4jStoreDriverTimeout:
    """(2026-06-26 ERR-002) driver 创建必须传连接超时, 防止 Neo4j 不可达时挂 30s"""

    def test_driver_uses_short_connection_timeout(self, monkeypatch):
        """Neo4jStore.driver 触发 GraphDatabase.driver() 必须传 connection_timeout=5
        (与 Redis facade 2s 超时对齐, 量级略宽因 Neo4j 握手更重)."""
        from src.kg.neo4j import Neo4jStore

        with patch("neo4j.GraphDatabase.driver") as mock_driver:
            store = Neo4jStore()
            _ = store.driver
        kwargs = mock_driver.call_args.kwargs
        # 关键: 必须显式传超时, 不允许依赖默认 (默认 30s)
        assert "connection_timeout" in kwargs
        assert kwargs["connection_timeout"] <= 10
        assert "connection_acquisition_timeout" in kwargs
        assert kwargs["connection_acquisition_timeout"] <= 30

    def test_driver_uses_max_connection_lifetime(self, monkeypatch):
        """Neo4jStore.driver 必须传 max_connection_lifetime, 防止连接过期"""
        from src.kg.neo4j import Neo4jStore

        with patch("neo4j.GraphDatabase.driver") as mock_driver:
            store = Neo4jStore()
            _ = store.driver
        kwargs = mock_driver.call_args.kwargs
        assert "max_connection_lifetime" in kwargs
        assert kwargs["max_connection_lifetime"] > 0


class TestNeo4jCircuitBreaker:
    """(2026-06-26 ERR-004) Neo4j 熔断器: 宕机时短路所有请求, 不 spam socket 连接."""

    def _reset_circuit(self):
        """测试间重置熔断状态, 避免互相污染."""
        from src.kg import neo4j as neo4j_mod

        neo4j_mod._circuit_open_until = 0.0
        neo4j_mod._circuit_first_failure_logged = False

    def test_circuit_starts_closed(self):
        """初始状态: 熔断关闭, 业务侧正常调用 driver"""
        from src.kg import neo4j as neo4j_mod
        from src.kg.neo4j import Neo4jStore

        self._reset_circuit()
        store = Neo4jStore()
        assert neo4j_mod._is_circuit_open() is False
        store.close()

    def test_circuit_trips_on_driver_error(self, monkeypatch):
        """driver 构造抛错 → _trip_circuit 打开熔断 _CIRCUIT_OPEN_SECONDS 秒.
        第二次访问 .driver 直接抛 Neo4jCircuitOpen 异常, 不再尝试 GraphDatabase.driver()."""
        from src.kg import neo4j as neo4j_mod
        from src.kg.neo4j import Neo4jCircuitOpen, Neo4jStore

        self._reset_circuit()
        # 第一次: GraphDatabase.driver() 抛 ServiceUnavailable
        with patch("neo4j.GraphDatabase.driver", side_effect=Exception("bolt unreachable")):
            store = Neo4jStore()
            with pytest.raises(Exception, match="bolt unreachable"):
                _ = store.driver
        # 熔断应已 trip
        assert neo4j_mod._is_circuit_open() is True

        # 第二次: 即使 mock 改成正常, 熔断仍开启, 直接抛 Neo4jCircuitOpen
        with patch("neo4j.GraphDatabase.driver") as mock_driver:
            store2 = Neo4jStore()
            with pytest.raises(Neo4jCircuitOpen):
                _ = store2.driver
            # 关键: 熔断开启时 GraphDatabase.driver 不应被调用 (避免 spam)
            mock_driver.assert_not_called()

    def test_circuit_logs_first_failure_only(self, monkeypatch):
        """熔断开启期间首次失败 log WARNING, 后续失败静默 (避免 spam 日志)."""
        from src.kg import neo4j as neo4j_mod

        self._reset_circuit()
        neo4j_mod._trip_circuit(Exception("first"))
        assert neo4j_mod._circuit_first_failure_logged is True
        # 第二次 _trip_circuit 不应改 _circuit_first_failure_logged 状态 (无新 log)
        neo4j_mod._trip_circuit(Exception("second"))
        assert neo4j_mod._circuit_first_failure_logged is True

    def test_circuit_resets_after_window(self, monkeypatch):
        """熔断到期 → 重置, 下次调用可重试."""
        from src.kg import neo4j as neo4j_mod

        self._reset_circuit()
        # 缩短窗口方便测试
        monkeypatch.setattr(neo4j_mod, "_CIRCUIT_OPEN_SECONDS", 0.1)
        neo4j_mod._trip_circuit(Exception("boom"))
        assert neo4j_mod._is_circuit_open() is True
        import time

        time.sleep(0.2)
        assert neo4j_mod._is_circuit_open() is False
        neo4j_mod._reset_circuit_if_due()  # 显式重置
        assert neo4j_mod._circuit_first_failure_logged is False
