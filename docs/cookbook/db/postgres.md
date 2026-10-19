# PostgreSQL + pgvector 教程

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

PostgreSQL 是业界最强大的开源关系数据库，30+ 年持续发展，被 Apple、Instagram、Reddit、Discord 等公司用作主存储。**pgvector** 是 PostgreSQL 的官方扩展，提供向量数据类型 + 相似度搜索，让一个数据库同时承担结构化数据和向量检索两种角色。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **PostgreSQL + pgvector** | 关系 + 向量二合一 | 一库多用，少一个组件 |
| **PostgreSQL + 独立向量库（Milvus/Qdrant）** | 关系 + 专业向量 | 性能更好，但运维复杂 |
| **MySQL / MariaDB** | 关系数据库 | PG 的 JSONB / CTE / Window Function 更强 |
| **SQLite** | 嵌入式关系数据库 | 单机应用，不适合多服务 |
| **ClickHouse** | 列式 OLAP | 不支持事务，PG 用作主库 |

**PG + pgvector 解决的核心问题**：
- **关系数据持久化**：用户、订单、权限、审计日志
- **向量相似度搜索**：embedding 检索（RAG 核心）
- **避免多数据库**：把向量和元数据放一起，避免跨库 JOIN
- **强事务支持**：ACID、行级锁、MVCC

---

## 二、安装 & 启动

### 2.1 项目集成启动

`docker/docker-compose.yml:4-23` 用 `pgvector/pgvector:pg18` 镜像（PG 18 + pgvector 预装）：

```bash
cd docker/
docker compose up -d postgres
# 启动后 psql 验证
docker exec -it pgvector psql -U postgres -d rag -c "SELECT version();"
# 应返回 PostgreSQL 18.x + pgvector 0.x
```

### 2.2 独立 Docker 启动

```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=rag \
  -p 5432:5432 \
  -v $PWD/pg_data:/var/lib/postgresql \
  pgvector/pgvector:pg18
```

### 2.3 健康检查

```bash
# 用 pg_isready（项目 Dockerfile 内置）
docker exec pgvector pg_isready -U postgres -d rag

# 连接测试
docker exec -it pgvector psql -U postgres -d rag -c "SELECT 1"

# pgvector 扩展确认
docker exec -it pgvector psql -U postgres -d rag -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

---

## 三、核心概念

1. **Database / Schema / Table**：DB > Schema > Table 三层结构。`rag` 库下有 `public` schema。
2. **MVCC（多版本并发控制）**：PG 用"行版本"实现并发读不阻塞写，不用锁就能读到一致快照。
3. **Transaction（事务）**：BEGIN / COMMIT / ROLLBACK 包围，ACID 保证。
4. **JSONB**：二进制 JSON 字段，支持索引（GIN）、运算符（`@>`、`?`）。项目用 JSONB 存动态配置。
5. **Vector（pgvector）**：`vector(N)` 类型，存 N 维浮点向量。`CREATE EXTENSION vector;` 启用。
6. **HNSW / IVFFlat**：pgvector 的两种近似最近邻索引（ANN）。本项目用 HNSW（`docker/docker-compose.yml` 默认）。
7. **CTE（公用表表达式）**：`WITH ... AS ...` 子查询，提高复杂查询可读性。
8. **窗口函数**：`ROW_NUMBER() OVER (PARTITION BY ...)` 等，比 `GROUP BY` 更强大的分析函数。
9. **Alembic**：Python 生态的 SQLAlchemy 数据库迁移工具。项目用 alembic 管理 schema 变更。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker
docker start pgvector
docker stop pgvector
docker restart pgvector

# 服务端（Linux 直接安装）
sudo systemctl start postgresql
sudo systemctl stop postgresql
```

### 4.2 查询

```bash
# 进入 psql
docker exec -it pgvector psql -U postgres -d rag

# 常用元命令
\dt                          # 列出表
\d+ users                    # 表结构详情
\di                          # 列出索引
\dv                          # 列出视图
\df                          # 列出函数
\du                          # 列出用户 / 角色
\l                           # 列出所有数据库
\conninfo                    # 当前连接信息
\q                           # 退出

# 性能分析
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'alice@x.com';
```

### 4.3 调试

```bash
# 当前运行的查询
SELECT pid, query, state, age(clock_timestamp(), query_start) AS duration
FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;

# 杀死慢查询
SELECT pg_cancel_backend(pid);     # 软取消
SELECT pg_terminate_backend(pid);  # 硬终止

# 锁竞争
SELECT relation::regclass, mode, granted, pid FROM pg_locks WHERE NOT granted;

# 表膨胀
SELECT schemaname, relname, n_dead_tup, n_live_tup,
       round(n_dead_tup * 100.0 / GREATEST(n_live_tup, 1), 2) AS dead_pct
FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY dead_pct DESC;
```

### 4.4 排错

```bash
# 连接被拒
# 1. 密码错：检查 .env POSTGRES_PASSWORD
# 2. pg_hba.conf 限制：默认 trust（容器内）/ md5（远程）
# 3. 端口错：默认 5432

# 磁盘满
docker exec pgvector df -h /var/lib/postgresql
# 清理：VACUUM FULL;  （注意：会锁表）

# 启动失败（数据损坏）
docker logs pgvector
# 看 panic / inconsistent 关键字，对应 PGDATA 修复
```

---

## 五、项目集成点

### 5.1 项目当前使用 PostgreSQL + pgvector

`docker/docker-compose.yml:4-23` 是项目主存储。

### 5.2 业务配置

```bash
# packages/service/.env
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=replace-with-strong-password
PG_DATABASE=rag
```

后端通过 `src/common/db_url.py:17` 的 `get_rag_db_url()` 函数组装成 `postgresql+psycopg://user:pass@host:port/db` 形式。

### 5.3 pgvector 集成

`src/retrieval/vector_store.py:58-122` 是 `PGVectorStore` 封装：

- 用 `pgvector` 的 `PGVectorStore`（llama-index-vector-stores-postgres）
- 维度从 `EMBED_DIMENSIONS` env 派生（`src/retrieval/vector_store.py:222`）
- 索引类型可配 HNSW 或 IVFFlat（`PGVectorConfig:30-33`）

### 5.4 SQLAlchemy ORM

项目用 SQLAlchemy 2.x ORM（同步），定义在 `src/db/models.py` 等。

### 5.5 Alembic 迁移

```bash
# 项目迁移命令
cd packages/service
uv run alembic current
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add foo"
```

---

## 六、项目代码示例

### 6.1 Postgres 服务配置

`docker/docker-compose.yml:4-23`：

```yaml
postgres:
  image: pgvector/pgvector:pg18
  container_name: pgvector
  restart: unless-stopped
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
  ports:
    - "5432:5432"
  volumes:
    - ./volumes/pg_data:/var/lib/postgresql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
    interval: 5s
    timeout: 5s
    retries: 5
  networks:
    - app-network
```

### 6.2 URL 构造

`src/common/db_url.py:17`：

```python
def get_rag_db_url() -> str:
    """构造 RAG 项目的 PG 连接 URL.
    单一构造点, 跟 docker-compose env 字段对齐.
    """
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "")
    database = os.getenv("PG_DATABASE", "rag")
    # URL-encode 密码（防特殊字符）
    return f"postgresql+psycopg://{user}:{quote_plus(password)}@{host}:{port}/{database}"
```

### 6.3 pgvector 向量检索

`src/retrieval/vector_store.py:73-86`：

```python
def _build_vector_store(self) -> BaseVectorStore:
    from llama_index.vector_stores.postgres.base import PGVectorStore

    cfg = self.config
    # 索引参数全塞 hnsw_kwargs（新版没单独的 hnsw_m / hnsw_ef_construction）
    hnsw_kwargs: dict[str, Any] | None = None
    if cfg.index_type == "hnsw":
        hnsw_kwargs = {"hnsw_m": cfg.hnsw_m, "hnsw_ef_construction": cfg.hnsw_ef_construction}
    return PGVectorStore(
        connection_string=cfg.connection_string,
        embed_dim=cfg.vector_dim or _get_embed_dim(),
        hnsw_kwargs=hnsw_kwargs,
    )
```

### 6.4 业务 SQL 模式

项目典型 session_scope 模式（`src/storage/session.py`）：

```python
from src.storage.session import session_scope

def get_user_by_email(email: str) -> User | None:
    with session_scope() as session:
        return session.query(User).filter_by(email=email).first()

def create_user(email: str, password_hash: str) -> User:
    with session_scope() as session:
        user = User(email=email, password_hash=password_hash)
        session.add(user)
        session.flush()  # 拿 id，不 commit
        return user
    # 退出 with 时自动 commit / rollback
```

---

## 七、项目没用到的能力

以下 PostgreSQL / pgvector 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Logical Replication** | 主从同步、零停机迁移 | 单机够用，多实例时启用 |
| **Connection Pooling (PgBouncer)** | 高并发场景下减少连接开销 | 单后端进程够用，多 worker 时启用 |
| **Partitioning（表分区）** | 大表按时间/范围分片 | `app_logs` / `error_logs` 表 > 1 亿行时启用 |
| **Row-Level Security (RLS)** | 数据库层强制权限隔离 | 多租户场景使用 |
| **LISTEN / NOTIFY** | 进程间异步通知 | 字典失效通知当前用 Redis pub/sub（`src/lookups/cache.py`） |
| **Full-Text Search (tsvector)** | 全文搜索 | 项目用 embedding 搜索，全文用 ES |
| **pgvector IVFFlat** | 备选向量索引 | HNSW 已用，IVFFlat 适合极大数据量 |
| **Materialized View** | 预计算聚合 | 复杂报表场景考虑 |

**建议关注**：Connection Pooling。当并发请求 > 50 时，PG 默认 100 连接很快耗尽，引入 PgBouncer 复用连接。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **备份策略**：每日 `pg_dump`，保留 7 天 / 4 周 / 12 月三档
2. **监控指标**：连接数、TPS、慢查询、复制延迟、表膨胀率
3. **vacuum 配置**：`autovacuum_vacuum_scale_factor=0.05` 提前清理，避免长事务后大表膨胀
4. **WAL 归档**：`wal_level=replica` + 定期归档到 MinIO（项目已用 S3 兼容）
5. **版本升级**：大版本（PG 16→17）必须先 `pg_dumpall` + 新实例恢复，不能直接覆盖

### 常见坑

1. **密码含特殊字符**：`POSTGRES_PASSWORD=ab#cd` 在 docker-compose 里要把 `#` 转义，URL 也必须 encode（项目 `get_rag_db_url()` 已处理）
2. **docker compose down -v 删数据**：`v` 删 `pg_data` volume，所有数据全丢
3. **大表 `VACUUM FULL`**：锁表 10+ 分钟，必须在维护窗口执行
4. **pgvector 维度不匹配**：插入 1024 维向量到 768 维列 → 报错。每次改 `EMBED_DIMENSIONS` 必须重建索引
5. **transaction 长持有**：`session_scope` 内做网络 IO（HTTP 调用、LLM 调用）会长时间持有连接，导致连接池耗尽。LLM 调用要在 `session_scope` 之外

---

## 📚 参考

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/18/index.html)
- [pgvector 官方仓库](https://github.com/pgvector/pgvector)
- [pgvector + Python 教程](https://github.com/pgvector/pgvector-python)
- [llama-index-vector-stores-postgres](https://docs.llamaindex.ai/en/stable/examples/vector_stores/postgres.html)
- [PG 性能调优](https://www.postgresql.org/docs/18/performance-tips.html)
- [Alembic 迁移工具](https://alembic.sqlalchemy.org/en/latest/)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
