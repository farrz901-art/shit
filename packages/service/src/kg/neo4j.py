"""Neo4j 驱动封装 (2026-06-09 从 src/rag/knowledge_graph/ 合并)

提供通用 CRUD: execute / execute_and_fetch / upsert_node / find_nodes /
upsert_relationship / get_neighbors / delete_node / upsert_entity_knowledge。
知识图谱业务 API 在 client.py (KgClient), 跟驱动层分离。

(2026-06-26 ERR-004) 加熔断器: Neo4j 不可达时, 短期短路所有 driver() 调用,
避免每秒数十个请求 spam socket 连接. 模式参考 src/core/redis_client.py
的 _is_circuit_open / _trip_circuit / _reset_circuit_if_due.
"""

import os
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..common import defaults


@dataclass
class Neo4jConfig:
    uri: str = field(default_factory=lambda: defaults.DEFAULT_NEO4J_URI)
    username: str = field(default_factory=lambda: defaults.DEFAULT_NEO4J_USER)
    password: str = field(default_factory=lambda: defaults.DEFAULT_NEO4J_PASSWORD)
    database: str = field(default_factory=lambda: defaults.DEFAULT_NEO4J_DATABASE)


# (2026-06-26 ERR-004) 熔断状态: 模块级单例, 进程内全局共享.
# Neo4jStore 实例可多个, 但熔断窗口统一, 避免一个 store 失败后其他 store 还在 spam.
_CIRCUIT_OPEN_SECONDS: int = defaults.DEFAULT_NEO4J_CIRCUIT_OPEN_SECONDS
_circuit_open_until: float = 0.0  # unix timestamp, 0 表示 closed
_circuit_first_failure_logged: bool = False  # 单次失败期内只 log 一次


class Neo4jCircuitOpen(Exception):
    """Neo4j 熔断开启, 业务侧应 catch 走降级路径 (返空/默认值).

    跟一般 Neo4j 异常区分, 方便业务侧只对熔断做特殊处理.
    """


def _is_circuit_open() -> bool:
    """熔断中 → True, Neo4jStore.driver() 直接抛 Neo4jCircuitOpen."""
    return time.monotonic() < _circuit_open_until


def _trip_circuit(err: BaseException) -> None:
    """记录失败, 打开熔断 _CIRCUIT_OPEN_SECONDS 秒. 首次失败 log WARNING, 后续静默."""
    global _circuit_open_until, _circuit_first_failure_logged
    _circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS
    if not _circuit_first_failure_logged:
        logger.warning(
            "neo4j 不可达, 打开熔断 {}s (期间 driver() 静默短路, 不再 spam GraphDatabase.driver()): {}",
            _CIRCUIT_OPEN_SECONDS,
            err,
        )
        _circuit_first_failure_logged = True


def _reset_circuit_if_due() -> None:
    """熔断到期 → 重置. 下次 Neo4jStore.driver() 调 GraphDatabase.driver() 尝试恢复."""
    global _circuit_open_until, _circuit_first_failure_logged
    if _circuit_open_until != 0.0 and time.monotonic() >= _circuit_open_until:
        _circuit_open_until = 0.0
        _circuit_first_failure_logged = False
        logger.info("neo4j 熔断到期, 下次访问 driver() 尝试恢复连接")


class Neo4jStore:
    def __init__(self, config: Neo4jConfig | None = None):
        self._config = config or self._config_from_env()
        self._driver: Any = None

    def _config_from_env(self) -> Neo4jConfig:
        # 重依赖 lazy: defaults 模块加载读 env (side-effect), Neo4jStore 初始化可被推迟
        from ..common import defaults  # noqa: E402

        return Neo4jConfig(
            uri=os.getenv("NEO4J_URI", defaults.DEFAULT_NEO4J_URI),
            username=os.getenv("NEO4J_USER", defaults.DEFAULT_NEO4J_USER),
            password=os.getenv("NEO4J_PASSWORD", defaults.DEFAULT_NEO4J_PASSWORD),
            database=os.getenv("NEO4J_DATABASE", defaults.DEFAULT_NEO4J_DATABASE),
        )

    @property
    def driver(self) -> Any:
        # (2026-06-26 ERR-004) 熔断开启 → 直接抛 Neo4jCircuitOpen, 不尝试
        # GraphDatabase.driver() 创建连接. 避免 Neo4j 宕机时 spam socket.
        if _is_circuit_open():
            raise Neo4jCircuitOpen("neo4j 熔断开启, 静默短路, 待到期重试")
        if self._driver is None:
            # 重依赖 lazy: neo4j driver 启动慢 (~500ms), 仅在 Neo4jStore 首次用时需要
            import neo4j  # noqa: E402

            # (2026-06-26 ERR-002) 必须显式传连接超时, 不允许依赖默认 30s.
            # 量级: connection_timeout=5s (与 Redis 2s 对齐略宽), acquisition=30s
            # (给连接池重试留余地), max_lifetime=30min 防止 stale 连接.
            try:
                self._driver = neo4j.GraphDatabase.driver(
                    self._config.uri,
                    auth=(self._config.username, self._config.password),
                    connection_timeout=defaults.DEFAULT_NEO4J_CONNECTION_TIMEOUT,
                    connection_acquisition_timeout=defaults.DEFAULT_NEO4J_CONNECTION_ACQUISITION_TIMEOUT,
                    max_connection_lifetime=defaults.DEFAULT_NEO4J_MAX_CONNECTION_LIFETIME,
                )
            except Exception as e:
                # (2026-06-26 ERR-004) driver() 失败 (Neo4j 宕机) → 打开熔断.
                # 业务侧 catch Neo4jCircuitOpen 走降级, 后续请求短路.
                _trip_circuit(e)
                raise
            _reset_circuit_if_due()  # 成功 → 重置熔断标记
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self.driver.close()

    def verify_connectivity(self) -> None:
        """监控检查: 跑一条最便宜的 RETURN 1, 验证 driver 实际能通信

        Neo4j Python driver 在创建时不连接, 必须 session().run() 一次才真连.
        """
        with self.driver.session() as session:
            session.run("RETURN 1").consume()
            self._driver = None

    def execute(self, cypher: str, params: dict | None = None, database: str | None = None) -> list[dict]:
        params = params or {}
        database = database or self._config.database
        with self.driver.session(database=database) as session:
            result = session.run(cypher, params)
            result.consume()
            return [{"type": "ok"}]

    def execute_and_fetch(self, cypher: str, params: dict | None = None, database: str | None = None) -> list[dict]:
        params = params or {}
        database = database or self._config.database
        with self.driver.session(database=database) as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]

    def upsert_node(self, label: str, properties: dict, match_keys: dict | None = None) -> str | None:
        if match_keys:
            where_clause = " AND ".join(f"n.`{k}` = ${k}" for k in match_keys)
            cypher = f"MATCH (n:{label}) WHERE {where_clause} SET n += $properties RETURN id(n) AS node_id"
            params = {**match_keys, "properties": properties}
        else:
            key = list(properties.keys())[0]
            cypher = f"MERGE (n:{label} {{{key}: ${key}}}) SET n += $extra RETURN id(n) AS node_id"
            params = {key: properties[key], "extra": {k: v for k, v in properties.items() if k != key}}
        results = self.execute_and_fetch(cypher, params)
        return results[0]["node_id"] if results else None

    def find_nodes(self, label: str, where: dict | None = None, limit: int = 100) -> list[dict]:
        if where:
            where_clause = " AND ".join(f"n.`{k}` = ${k}" for k in where)
            cypher = f"MATCH (n:{label}) WHERE {where_clause} RETURN id(n) AS node_id, n AS properties LIMIT $limit"
            params = {**where, "limit": limit}
        else:
            cypher = f"MATCH (n:{label}) RETURN id(n) AS node_id, n AS properties LIMIT $limit"
            params = {"limit": limit}
        return self.execute_and_fetch(cypher, params)

    def delete_node(self, node_id: int) -> None:
        self.execute("MATCH (n) WHERE id(n) = $node_id DETACH DELETE n", {"node_id": node_id})

    def upsert_relationship(
        self, from_node_id: int, to_node_id: int, rel_type: str, properties: dict | None = None
    ) -> None:
        properties = properties or {}
        cypher = f"""
            MATCH (a), (b) WHERE id(a) = $from_id AND id(b) = $to_id
            MERGE (a)-[r:{rel_type}]->(b) SET r += $properties
        """
        self.execute(cypher, {"from_id": from_node_id, "to_id": to_node_id, "properties": properties})

    def get_neighbors(
        self, node_id: int, rel_type: str | None = None, direction: str = "both", depth: int = 1, limit: int = 100
    ) -> list[dict]:
        arrow = "->" if direction == "outgoing" else "<-" if direction == "incoming" else "-"
        rel_clause = f":{rel_type}" if rel_type else ""
        cypher = f"""
            MATCH (n){arrow}[r{rel_clause}*1..{depth}]{arrow}(neighbor)
            WHERE id(n) = $node_id AND id(neighbor) <> $node_id
            RETURN id(neighbor) AS node_id, neighbor AS properties, count(r) AS distance
            ORDER BY distance LIMIT $limit
        """
        return self.execute_and_fetch(cypher, {"node_id": node_id, "limit": limit})

    def upsert_entity_knowledge(self, triplets: Iterable[tuple[str, str, str]]) -> None:
        for subject, predicate, obj in triplets:
            self.upsert_node("Entity", {"name": subject}, match_keys={"name": subject})
            self.upsert_node("Entity", {"name": obj}, match_keys={"name": obj})
            from_id = self.find_nodes("Entity", where={"name": subject}, limit=1)
            to_id = self.find_nodes("Entity", where={"name": obj}, limit=1)
            if from_id and to_id:
                self.upsert_relationship(int(from_id[0]["node_id"]), int(to_id[0]["node_id"]), predicate)

    def __enter__(self) -> Neo4jStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def get_neo4j_store(config: Neo4jConfig | None = None) -> Neo4jStore:
    return Neo4jStore(config)
