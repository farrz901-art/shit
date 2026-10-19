# Neo4j 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python/TS 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

Neo4j 是一款高性能的原生图数据库，用节点（Node）、关系（Relationship）、属性（Property）三元组存储数据，并提供声明式查询语言 **Cypher** 进行图遍历。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Neo4j** | 商业级原生图数据库 | 生态最成熟，Cypher 是事实标准 |
| **Memgraph** | 兼容 Cypher 的内存图数据库 | 速度更快但生态小 |
| **Amazon Neptune** | 云托管图数据库 | 锁定 AWS |
| **ArangoDB** | 多模型（文档 + 图 + KV） | 通用但图查询能力弱于 Neo4j |
| **PostgreSQL + pgvector** | 关系数据库 + 向量扩展 | 关系查询够用但图遍历性能差 |

**Neo4j 解决的核心问题**：
- **关系密集型查询**：社交网络、知识图谱、推荐系统的"二度人脉""共同好友"
- **RAG 中的实体关系**：把文档中的实体（人/产品/概念）及其关系结构化存储，支持"刘德华主演的电影"这类查询
- **路径查找**：找两个节点之间的最短路径 / 全部路径

---

## 二、安装 & 启动

### 2.1 项目集成启动

`docker/docker-compose.yml:26-51` 定义 Neo4j 服务：

```bash
cd docker/
docker compose up -d neo4j
# 启动后访问：
# Browser UI:  http://localhost:7474 (neo4j / 315009 默认密码)
# Bolt 协议:    bolt://localhost:7687
```

### 2.2 独立 Docker 启动

```bash
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v $PWD/neo4j_data:/data \
  --name neo4j \
  neo4j:2026.05.0
```

### 2.3 健康检查

```bash
# HTTP 探活
curl -f http://localhost:7474
# 返回 "Neo4j Browser" HTML

# 容器内 cypher-shell（需安装 client）
docker exec -it neo4j cypher-shell -u neo4j -p 315009 "RETURN 1"
```

---

## 三、核心概念

1. **Node（节点）**：图中的实体（人、产品、概念）。用 `CREATE (n:Person {name: "Alice"})` 创建。
2. **Relationship（关系）**：连接两个节点的有向边，有类型（type）和方向。`(:Person)-[:KNOWS]->(:Person)`。
3. **Property（属性）**：节点 / 关系上的键值对，类似表的列。
4. **Label（标签）**：节点的类型（`:Person`、`:Movie`），一个节点可有多个标签。
5. **Pattern（模式）**：Cypher 的核心查询结构 `(a:Person)-[r:KNOWS]->(b:Person)`，可以 MATCH 任意模式。
6. **Index（索引）**：按属性查的快速入口。`CREATE INDEX FOR (n:Person) ON (n.name)`。
7. **Constraint（约束）**：唯一性 / 存在性约束，如 `CREATE CONSTRAINT FOR (n:Person) REQUIRE n.email IS UNIQUE`。
8. **APOC 插件**：Neo4j 生态的"瑞士军刀"，提供 500+ 实用函数（数据导入、图算法、JSON 处理）。
9. **Cypher**：类 SQL 的图查询语言，`MATCH ... WHERE ... RETURN ...` 结构。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker
docker start neo4j
docker stop neo4j

# 服务端（Linux 直接安装）
sudo systemctl start neo4j
sudo systemctl stop neo4j
```

### 4.2 查询 / 数据操作

```cypher
-- 列出所有节点
MATCH (n) RETURN n LIMIT 25;

-- 按类型统计
MATCH (n) RETURN labels(n)[0] AS type, count(n) AS cnt ORDER BY cnt DESC;

-- 查路径
MATCH p=shortestPath((a:Person {name:"Alice"})-[:KNOWS*]-(b:Person {name:"Bob"}))
RETURN p;

-- 2 跳邻居
MATCH (n:Person {name:"Alice"})-[:KNOWS]-(friend)-[:KNOWS]-(foaf)
RETURN foaf.name;
```

### 4.3 调试 / 监控

```bash
# 容器内查看日志
docker logs -f neo4j

# 查看运行查询
docker exec -it neo4j cypher-shell -u neo4j -p 315009 \
  "CALL dbms.listQueries() YIELD query, status, runtime"

# 终止慢查询
CALL dbms.killQuery(queryId)

# EXPLAIN / PROFILE 优化
EXPLAIN MATCH (n:Person) WHERE n.name = "Alice" RETURN n;
PROFILE MATCH (n:Person) WHERE n.name = "Alice" RETURN n;
```

### 4.4 排错

```bash
# 端口冲突
netstat -ano | grep -E ":7474|:7687"
# 改 -p 端口映射

# 启动失败（OOM）
docker logs neo4j | grep -i "memory\|heap"
# Neo4j 默认 heap 512MB，容器资源不足时启动失败
# 调：-e NEO4J_dbms_memory_heap_max__size=2G

# 认证失败
# NEO4J_AUTH=neo4j/PASSWORD 格式
# 改完必须重启容器（第一次设后写入 data/databases/）

# 性能差
# 1. 加索引：CREATE INDEX FOR (n:Label) ON (n.prop)
# 2. PROFILE 看是否走索引
# 3. 加内存 -e NEO4J_dbms_memory_heap_max__size=4G
```

---

## 五、项目集成点

### 5.1 项目当前使用 Neo4j 做知识图谱

`docker/docker-compose.yml:26-51` 启动 Neo4j，`packages/service/src/kg/` 模块管理图数据。

### 5.2 业务配置

```python
# packages/service/.env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=replace-with-your-password
NEO4J_DATABASE=neo4j
```

注意 `NEO4J_URI` 不在 URI 内嵌认证，跟 PG/Redis 风格一致（用户密码分开存 env）。

### 5.3 APOC 插件

`docker/docker-compose.yml:35-38` 启用 APOC（Awesome Procedures On Cypher）：

```yaml
NEO4J_PLUGINS: '["apoc"]'
NEO4J_apoc_export_file_enabled: "true"
NEO4J_apoc_import_file_enabled: "true"
NEO4J_apoc_import_file_use__neo4j__config: "true"
```

APOC 用于：JSON 导入导出、图算法、批量导入。

### 5.4 业务模块

`src/kg/router.py:11` 导入 APIRouter，提供知识图谱 CRUD 端点。

---

## 六、项目代码示例

### 6.1 Neo4j 服务配置

`docker/docker-compose.yml:26-51`：

```yaml
neo4j:
  image: neo4j:2026.05.0
  container_name: neo4j
  restart: unless-stopped
  ports:
    - "7474:7474"   # Browser UI
    - "7687:7687"   # Bolt 协议
  environment:
    NEO4J_AUTH: ${NEO4J_AUTH:-neo4j/315009}
    NEO4J_PLUGINS: '["apoc"]'
    NEO4J_apoc_export_file_enabled: "true"
    NEO4J_apoc_import_file_enabled: "true"
    NEO4J_apoc_import_file_use__neo4j__config: "true"
  volumes:
    - ./volumes/neo4j/neo4j_logs:/logs
    - ./volumes/neo4j/neo4j_conf:/conf
    - ./volumes/neo4j/neo4j_data:/data
    - ./volumes/neo4j/neo4j_plugins:/plugins
  healthcheck:
    test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
    start_period: 30s
  networks:
    - app-network
```

### 6.2 Python 驱动连接

`packages/service/src/kg/neo4j.py:33-35`（推测）从 env 读连接配置：

```python
import os
from neo4j import GraphDatabase

# 项目典型做法：lazy init driver
_driver = None

def get_neo4j_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", ""),
            ),
        )
    return _driver
```

### 6.3 基本 CRUD（Cypher）

知识图谱三元组（subject-predicate-object）操作示例：

```cypher
-- 创建实体和关系
CREATE (alice:Person {name: "Alice", age: 30})
CREATE (bob:Person {name: "Bob", age: 32})
CREATE (alice)-[:KNOWS {since: 2020}]->(bob);

-- 查询
MATCH (a:Person {name: "Alice"})-[:KNOWS]->(b:Person)
RETURN a.name, b.name, b.age;

-- 添加索引
CREATE INDEX person_name IF NOT EXISTS FOR (n:Person) ON (n.name);

-- 唯一性约束
CREATE CONSTRAINT person_email_unique IF NOT EXISTS
FOR (n:Person) REQUIRE n.email IS UNIQUE;
```

### 6.4 业务代码：知识图谱查询

`src/kg/router.py:11` 引入 APIRouter，知识图谱查询端点（推测）：

```python
from fastapi import APIRouter, Depends
from neo4j import Session

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])

@router.get("/graph/{entity}")
def get_related_entities(entity: str, session = Depends(get_neo4j_session)):
    # 2 跳邻居查询
    result = session.run(
        """
        MATCH (e {name: $name})-[r*1..2]-(neighbor)
        RETURN DISTINCT neighbor.name AS name,
               labels(neighbor) AS type,
               length(r) AS distance
        """,
        name=entity,
    )
    return [{"name": r["name"], "type": r["type"][0], "distance": r["distance"]} for r in result]
```

---

## 七、项目没用到的能力

以下 Neo4j 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Neo4j Bloom** | 图形化探索 UI | 业务侧用 Browser 已够，营销展示时再上 |
| **Graph Data Science (GDS) 库** | 图算法（Pagerank、社区发现） | 知识图谱不需要，未来推荐系统时考虑 |
| **Multi-database** | 多个独立 graph | 单业务不需要，多租户时有用 |
| **Causal Cluster** | HA 集群（≥3 节点） | 单机够用，SLA 要求高时上 |
| **Change Data Capture (CDC)** | 监听图变更 | 当前用应用层同步，未来 Kafka 集成时再上 |
| **向量索引（Neo4j 5+）** | 图内嵌向量搜索 | 用 LlamaIndex + pgvector 已覆盖 |
| **全文索引（Full-text）** | 节点属性全文搜索 | 用 ES / PG 全文索引更专业 |

**建议关注**：GDS 库值得评估（如知识图谱做"领域专家发现""核心实体识别"）。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **内存规划**：Neo4j 默认 heap 512MB 不够用，调到 2-4GB（`NEO4J_dbms_memory_heap_max__size=4G`）
2. **磁盘空间**：定期 `CALL dbms.listTransactions()` + `db.stats.retrieve` 看增长
3. **备份**：用 `neo4j-admin dump` / `neo4j-admin backup` 做全量 + 增量备份
4. **慢查询监控**：开启 `dbms.logs.query.enabled=DEBUG` 记录慢 Cypher
5. **APOC 升级**：APOC 版本必须严格匹配 Neo4j major.minor 版本，否则报 `NoClassDefFound`

### 常见坑

1. **NEO4J_AUTH 格式**：必须是 `username/password` 一个变量值，**不能**拆成 NEO4J_USER + NEO4J_PASSWORD（容器内变量名约定）
2. **首次启动慢**：Neo4j 首次启动会建索引 + 加载 APOC 插件，`start_period: 30s` 留不够就误判 unhealthy
3. **4GB 内存上限**：Neo4j 不允许 heap 超过 31GB（JVM pointer 限制），大实例用 page cache 而不是 heap
4. **Cypher 注入**：跟 SQL 注入一样，`MATCH (n {name: $name})` 一定要用参数化，不要字符串拼接
5. **APOC 路径导入**：APOC `apoc.import.file.enabled` 默认 false，必须显式开，且要重启容器

---

## 📚 参考

- [Neo4j 官方文档](https://neo4j.com/docs/)
- [Cypher 查询语言](https://neo4j.com/docs/cypher-manual/current/)
- [Neo4j Docker 部署](https://neo4j.com/docs/operations-manual/current/installation/docker/)
- [APOC 用户指南](https://neo4j.com/docs/apoc/current/)
- [Neo4j Python 驱动](https://neo4j.com/docs/python-manual/current/)
- [Neo4j Browser 用户指南](https://neo4j.com/docs/browser-manual/current/)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
