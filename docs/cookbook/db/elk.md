# ELK Stack 教程

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

ELK Stack 是 Elasticsearch + Logstash + Kibana 三个开源工具的组合，是业界最流行的日志聚合与分析方案：

- **Elasticsearch**：分布式搜索 + 存储引擎（基于 Lucene）
- **Logstash**：日志收集 + 解析 + 转发管道
- **Kibana**：Elasticsearch 的 Web 可视化界面

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **ELK Stack** | 集中式日志平台 | 完整生态，但重 |
| **Loki + Grafana** | 轻量日志聚合（Grafana 生态） | 资源占用小，但查询能力弱于 ES |
| **ClickHouse** | 列式 OLAP 数据库 | 自建日志分析时用，运维成本高 |
| **CloudWatch / Loki SaaS** | 云厂商日志服务 | 仅云环境适用 |

**ELK 解决的核心问题**：
- 多服务日志统一收集（FastAPI、Next.js、MinIO、Postgres 错误日志）
- 全文搜索 + 聚合（"过去 1 小时所有 /api/health 5xx 错误"）
- 长保留期（日志存 1 年以上，PG 表只能存几个月）
- 可视化 + 告警（Kibana dashboards）

---

## 二、安装 & 启动

### 2.1 Docker Compose 一键启动

社区维护的 `elastic-stack` docker-compose：

```bash
# 创建项目目录
mkdir -p elk && cd elk

# 下载官方示例
curl -L -O https://raw.githubusercontent.com/elastic/stack-docker/8.13/docker-compose.yml

# 启动
docker compose up -d

# 健康检查
curl -f http://localhost:9200    # Elasticsearch
curl -f http://localhost:5601    # Kibana
```

### 2.2 单机简化版（仅 ES + Kibana）

本项目可能用不到 Logstash 复杂管道，先用 Filebeat 直接送 ES：

```yaml
# docker-compose.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports: ["9200:9200"]
    volumes: ["es_data:/usr/share/elasticsearch/data"]

  kibana:
    image: docker.elastic.co/kibana/kibana:8.13.0
    depends_on: [elasticsearch]
    ports: ["5601:5601"]
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200

volumes:
  es_data:
```

### 2.3 健康检查

```bash
# ES 健康
curl http://localhost:9200/_cluster/health
# 返回 {"status":"green"|"yellow"|"red", ...}

# Kibana 健康
curl http://localhost:5601/api/status

# 节点列表
curl http://localhost:9200/_cat/nodes
```

---

## 三、核心概念

1. **Index（索引）**：ES 的"数据库"概念。每个索引有 mapping（schema）+ settings（分片、副本）。
2. **Document（文档）**：ES 的"行"概念，JSON 格式。
3. **Shard（分片）**：索引分片，分布式存储的基本单位。生产索引一般 3-5 个 primary shard + 1 个 replica。
4. **Mapping（映射）**：文档字段的类型定义。提前建好 mapping 比 dynamic mapping 性能好。
5. **Ingest Pipeline（摄取管道）**：Logstash / ES 内置的字段解析 + 转换 + 富化能力。
6. **Index Pattern（索引模式）**：Kibana 中用 `logs-*` 通配符匹配一组索引，配置时间字段后即可做时序分析。
7. **DSL Query**：ES 的查询语言（JSON 格式），比 SQL 更强大（nested、percolator、script_score）。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker Compose
docker compose up -d              # 启动
docker compose down               # 停止（保留数据）
docker compose down -v            # 停止 + 删卷

# 单服务（生产环境）
sudo systemctl start elasticsearch
sudo systemctl start kibana
sudo systemctl start logstash
```

### 4.2 查询

```bash
# 查看所有索引
curl http://localhost:9200/_cat/indices?v

# 搜索文档
curl -X GET "http://localhost:9200/logs-*/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"match": {"message": "error"}}, "size": 10}'

# 聚合统计
curl -X GET "http://localhost:9200/logs-*/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"size": 0, "aggs": {"by_level": {"terms": {"field": "level.keyword"}}}}'
```

### 4.3 调试

```bash
# 集群健康详情
curl http://localhost:9200/_cluster/health?level=indices

# 节点资源
curl http://localhost:9200/_cat/nodes?h=heap.percent,ram.percent,cpu,load_1m

# 慢查询（启用慢日志后）
# 在 elasticsearch.yml 设：index.search.slowlog.threshold.query.warn: 10s
# 慢查询会进 logs/elasticsearch_index_search_slowlog.log

# Kibana Dev Tools（F12 → Console）
GET _cat/indices
GET logs-*/_search {"query": {"match_all": {}}}
```

### 4.4 排错

```bash
# 集群红色（red）
# 通常是 primary shard 不可用
curl http://localhost:9200/_cluster/allocation/explain?pretty

# 磁盘满（ES 默认 85% 后禁写）
df -h
# 清理旧索引：curl -X DELETE http://localhost:9200/logs-2024.*

# Kibana 连不上 ES
# 检查 network.host / discovery 配置
# 容器内 localhost ≠ 宿主机 localhost
```

---

## 五、项目集成点

### 5.1 项目当前不使用 ELK

**项目当前未集成 ELK Stack**。日志处理走自建方案：

- `app_logs` / `error_logs` 表 + loguru + 后台 worker 写 PG（`src/core/logging.py`）
- `.env` 中 `LOKI_ENABLED=false` 占位（`packages/service/.env.example:69`），未启用
- 容器日志通过 `docker logs <container>` 直接看

### 5.2 项目日志结构

`src/core/logging.py` 写入的 `app_logs` 表结构（`app_logs.created_at` + `level` + `message` + `context` JSONB），如果迁到 ELK：

```json
{
  "@timestamp": "2026-06-25T10:00:00Z",
  "level": "ERROR",
  "service": "rag-service",
  "logger": "src.core.errors",
  "message": "unhandled_exception path=/api/foo method=POST",
  "exception": "Traceback (most recent call last)...",
  "request_id": "abc-123",
  "user_id": 42,
  "ip": "1.2.3.4"
}
```

### 5.3 未来集成方案

| 阶段 | 方案 | 复杂度 |
|------|------|--------|
| 短期 | Filebeat 读 `docker logs`，送 ES | 低 |
| 中期 | 项目代码改用 `logstash-async` SDK 直送 | 中 |
| 长期 | 替换 PG `app_logs` 表，全部走 ES | 高 |

**建议**：日志量 < 100/分钟时，PG 表够用；当错误日志超过 10k/天或需要复杂全文搜索时，再上 ELK。

---

## 六、项目代码示例

### 6.1 项目当前日志实现

`src/core/errors.py:47-61` 是项目典型的错误日志写法：

```python
@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    logger.opt(exception=True).error(
        "unhandled_exception path={} method={}",
        request.url.path,
        request.method,
    )
    try:
        _error_sink_sync(level="ERROR", exc=exc, request=request)
    except Exception as write_exc:
        logger.critical("error_logs write failed: {}", write_exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

`_error_sink_sync` 把异常详情写入 `error_logs` 表（见 `src/core/logging.py`）。

### 6.2 loguru → ES 的最小代码

如果想加 ELK，loguru 配置 `sink` 直接送 ES 索引：

```python
# src/core/logging.py（示意）
import loguru
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

def es_sink(message):
    record = message.record
    es.index(index="app-logs", document={
        "@timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "extra": record["extra"],
    })

logger.add(es_sink, level="ERROR", serialize=True)  # serialize=True 输出 JSON
```

### 6.3 Filebeat 配置片段

部署期用 Filebeat 更省事。`filebeat.yml`：

```yaml
filebeat.inputs:
  - type: container
    paths:
      - /var/lib/docker/containers/*/*.log

processors:
  - add_docker_metadata: ~
  - drop_fields:
      fields: ["agent.ephemeral_id", "agent.id"]

output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  index: "app-logs-%{+yyyy.MM.dd}"

setup.template.name: "app-logs"
setup.template.pattern: "app-logs-*"
```

---

## 七、项目没用到的能力

以下 ELK 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Logstash** | 复杂日志解析管道 | 用 Filebeat 替代更轻量 |
| **Beats 家族（Filebeat/Metricbeat/Packetbeat）** | 多源采集 | 单服务用不上，全栈监控时上 |
| **Watcher 告警** | 基于查询阈值告警 | Kibana 自带 Alerting 即可 |
| **Graph API** | 数据关系图查询 | 知识图谱用 Neo4j 更专业 |
| **Machine Learning 异常检测** | 自动发现异常模式 | ES 商业功能（X-Pack），自建 ML 用不到 |
| **Cross-cluster Replication** | 跨集群同步 | 单机房项目不需要 |
| **Index Lifecycle Management (ILM)** | 自动归档/删除 | MinIO 5 prefix 规则已实现类似功能（`docker/scripts/minio_init.sh`） |

**建议关注**：ILM（自动清理老索引）值得评估。`error_logs` 表的 30d 保留策略可改为 ILM 自动归档到 S3/MinIO。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **磁盘规划**：ES 索引占用大（1 GB 日志 ≈ 200 MB ES 索引），预留 5x 容量
2. **分片数规划**：单分片 10-50 GB 为佳，过多分片反而慢
3. **JVM heap**：不超过物理内存 50%，最大 32 GB
4. **备份**：用 `elasticsearch-repository-s3` 插件快照到 MinIO
5. **版本升级**：升级 ES 必须 major → minor → patch 顺序，不可跳级

### 常见坑

1. **内存设置**：容器内设 `ES_JAVA_OPTS=-Xms2g -Xmx2g`（默认 1GB 不够），否则 OOM 频繁
2. **mmapfs 限制**：Linux 默认 `vm.max_map_count=65530` 太小，ES 启动会报 max_map_count 错误，调到 262144
3. **dynamic mapping 爆炸**：没配 mapping 就灌日志，ES 自动建几百个字段，索引查询慢
4. **深分页**：ES 默认 `from + size` ≤ 10000，否则 OOM。用 `search_after` 替代
5. **时间字段名**：Kibana 时间序列必须配 `@timestamp` 字段（默认），别用自定义 `created_at` 不配 mapping

---

## 📚 参考

- [Elasticsearch 官方文档](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Kibana 官方文档](https://www.elastic.co/guide/en/kibana/current/index.html)
- [Logstash 官方文档](https://www.elastic.co/guide/en/logstash/current/index.html)
- [ELK Docker 部署](https://www.elastic.co/guide/en/elastic-stack-get-started/current/get-started-docker.html)
- [Filebeat 官方文档](https://www.elastic.co/guide/en/beats/filebeat/current/index.html)
- [ELK 性能调优最佳实践](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-search-speed.html)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
