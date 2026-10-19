# Dify Docker Compose 全景深度分析

> 📅 文档版本：基于 `docker/docker-compose.yaml` 1.14.0 版本生成
> 📁 源文件：[docker/docker-compose.yaml](docker/docker-compose.yaml)
> 🔧 配套文件：[docker-compose-template.yaml](docker/docker-compose-template.yaml)（源模板）、[docker-compose.middleware.yaml](docker/docker-compose.middleware.yaml)（开发中间件）

---

## 目录

- [一、文件总览](#一文件总览)
- [二、整体架构拓扑](#二整体架构拓扑)
- [三、Dify 自研镜像（4 个）](#三dify-自研镜像4-个)
- [四、关系型数据库（2 个主选 + 4 个备选）](#四关系型数据库2-个主选--4-个备选)
- [五、缓存与消息队列（1 个）](#五缓存与消息队列1-个)
- [六、向量数据库（14 个）](#六向量数据库14-个)
- [七、安全与代理组件（3 个）](#七安全与代理组件3-个)
- [八、反向代理与证书（2 个）](#八反向代理与证书2-个)
- [九、辅助工具（3 个）](#九辅助工具3-个)
- [十、网络与存储设计](#十网络与存储设计)
- [十一、Profile 按需启动机制](#十一profile-按需启动机制)
- [十二、安全设计总结](#十二安全设计总结)
- [十三、常用启动命令](#十三常用启动命令)
- [十四、生产环境建议](#十四生产环境建议)

---

## 一、文件总览

| 维度 | 数值 |
|------|------|
| 文件大小 | ~50 KB，1175 行 |
| 服务数量 | **32 个**（含 1 个本地构建） |
| 独立镜像数 | **33 个**（含 couchbase-server 本地构建） |
| 公共网络 | 3 个 |
| 命名卷 | 2 个 |
| Dify 镜像版本 | 1.14.0 |

### 服务的功能分层

```
┌──────────────────────────────────────────────────────┐
│ ① 核心服务层（Dify 自研）    ② 反向代理 / 证书        │
│ ③ 关系型数据库             ④ 缓存层                  │
│ ⑤ 向量数据库（14 种）       ⑥ 安全 / 代理            │
│ ⑦ 辅助工具（ETL、Init）                              │
└──────────────────────────────────────────────────────┘
```

---

## 二、整体架构拓扑

```
                   ┌──────────────┐
   用户 ────HTTP─▶ │   nginx      │ :80/:443
                   └──────┬───────┘
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
        ┌──────────────┐    ┌──────────────┐
        │  dify-web    │    │   dify-api   │
        │  (Next.js)   │    │  (Flask)     │
        └──────────────┘    └──────┬───────┘
                                   │
            ┌──────────────────────┼──────────────────┐
            ▼                      ▼                  ▼
       ┌────────┐          ┌────────────┐      ┌──────────┐
       │ redis  │          │ db_postgres│      │  vector  │ (weaviate/milvus/...)
       │        │          │  /mysql    │      │  store   │
       └────────┘          └────────────┘      └──────────┘
            ▲
            │ 消息队列
       ┌────┴───────┐
       │  dify-api  │ (MODE=worker)  ──▶ Celery 队列
       │  worker    │
       └────────────┘
            ▲
       ┌────┴───────┐
       │ worker_beat│ (MODE=beat)  ──▶ 周期任务
       └────────────┘

  ┌────────────────────────────────────────────────┐
  │  ssrf_proxy_network（隔离内网）                 │
  │   ┌──────────┐    ┌──────────┐                 │
  │   │  api     │ ◀─▶│ sandbox  │ ────▶ ssrf_proxy ──▶ 外网
  │   └──────────┘    └──────────┘                 │
  │   ┌──────────────────┐                         │
  │   │  plugin_daemon   │                         │
  │   └──────────────────┘                         │
  └────────────────────────────────────────────────┘
```

---

## 三、Dify 自研镜像（4 个）

> 💡 全部由 `langgenius` 组织发布于 Docker Hub，是 Dify 团队自主构建的官方镜像。

### 3.1 `langgenius/dify-api:1.14.0`

| 属性 | 值 |
|------|-----|
| 出品 | Dify.AI 官方 |
| 基础镜像（推测） | `python:3.11-slim` |
| 部署形态 | 多模式（api / worker / beat）通过 `MODE` 环境变量切换 |
| 镜像大小 | ~1.5 GB（包含机器学习依赖） |
| 暴露端口 | `5001`（API 端口） |

**关键角色**：Dify 的核心后端，承担 3 种运行模式：

- **`MODE=api`**：HTTP API 服务（Flask + Gunicorn，gevent worker），对外提供 RESTful 接口
- **`MODE=worker`**：Celery Worker，处理所有异步任务（dataset、workflow、mail、mail_clean 等队列）
- **`MODE=beat`**：Celery Beat 调度器，触发周期任务（如清理过期数据、TIDB Serverless 状态更新）

**关键配置**（来自 `envs/core-services/api.env.example`）：

| 环境变量 | 默认值 | 作用 |
|---------|--------|------|
| `SENTRY_DSN` | 空 | 错误监控（SaaS） |
| `PLUGIN_MAX_PACKAGE_SIZE` | `52428800` (50MB) | 插件包大小上限 |
| `PLUGIN_DAEMON_TIMEOUT` | `600.0` | 插件守护进程超时 |
| `INNER_API_KEY_FOR_PLUGIN` | 内置密钥 | API 与 plugin_daemon 的内网鉴权 |

**健康检查**：
```yaml
test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
interval: 30s
```

---

### 3.2 `langgenius/dify-web:1.14.0`

| 属性 | 值 |
|------|-----|
| 出品 | Dify.AI 官方 |
| 技术栈 | Next.js + React + TypeScript |
| 部署形态 | 纯静态前端 + SSR 容器 |
| 镜像大小 | ~300 MB |

**关键角色**：Dify 的 Web 前端应用，对应 `web/` 目录源码。

**支持的功能开关**（节选自 env 配置）：

| 变量 | 用途 |
|------|------|
| `EXPERIMENTAL_ENABLE_VINEXT` | 实验性 Vue/Next 混合栈（默认 `false`） |
| `NEXT_TELEMETRY_DISABLED` | 关闭 Next.js 埋点 |
| `LOOP_NODE_MAX_COUNT` | 工作流循环节点最大次数（默认 100） |
| `MAX_ITERATIONS_NUM` | Agent 最大迭代次数（默认 99） |
| `MAX_TREE_DEPTH` | 工作流树最大深度（默认 50） |
| `ENABLE_WEBSITE_JINAREADER/FIRECRAWL/WATERCRAWL` | 网页抓取插件 |

**外部依赖配置**：
```yaml
MARKETPLACE_API_URL: https://marketplace.dify.ai  # 插件市场 API
MARKETPLACE_URL:     https://marketplace.dify.ai  # 插件市场 UI
```

---

### 3.3 `langgenius/dify-sandbox:0.2.15`

| 属性 | 值 |
|------|-----|
| 出品 | Dify.AI 官方 |
| 技术栈 | Go + Gin |
| 暴露端口 | `8194` |
| 镜像大小 | ~200 MB（精简 Linux 运行时） |

**关键角色**：**代码沙箱**——执行工作流中"代码节点"的用户 Python 代码。

**安全设计**：

- **网络隔离**：仅加入 `ssrf_proxy_network`（内网），所有出站请求**强制走 SSRF 代理**：
  ```yaml
  HTTP_PROXY:  http://ssrf_proxy:3128
  HTTPS_PROXY: http://ssrf_proxy:3128
  ```
- **资源限制**：
  ```yaml
  WORKER_TIMEOUT: 15          # 每次执行最大 15 秒
  ENABLE_NETWORK: true        # 可关闭外网
  ```
- **依赖管理**：通过 `volumes/sandbox/dependencies` 挂载预装 Python 包，避免运行时下载
- **配置**：通过 `volumes/sandbox/conf` 挂载配置目录（含 `config.yaml`）

**API 鉴权**：
```yaml
API_KEY: ${SANDBOX_API_KEY:-dify-sandbox}  # ⚠️ 生产必须修改
```

---

### 3.4 `langgenius/dify-plugin-daemon:0.6.0-local`

| 属性 | 值 |
|------|-----|
| 出品 | Dify.AI 官方 |
| 技术栈 | Go |
| 暴露端口 | `5002`（服务）+ `5003`（远程调试） |
| 镜像大小 | ~400 MB |

**关键角色**：**插件守护进程**，独立于主 API 运行，原因有二：

1. **隔离性**：插件可以动态加载第三方代码，单独容器防止污染主进程
2. **安全性**：配合 `FORCE_VERIFYING_SIGNATURE` 强制校验插件签名

**支持的对象存储后端**（7+ 种）：

| 类型 | 环境变量前缀 |
|------|-------------|
| 本地 | `PLUGIN_STORAGE_TYPE=local` |
| AWS S3 | `PLUGIN_S3_*` |
| 阿里云 OSS | `PLUGIN_ALIYUN_OSS_*` |
| 腾讯云 COS | `PLUGIN_TENCENT_COS_*` |
| 火山引擎 TOS | `PLUGIN_VOLCENGINE_TOS_*` |
| Azure Blob | `PLUGIN_AZURE_BLOB_*` |
| AWS Managed IAM | `PLUGIN_S3_USE_AWS_MANAGED_IAM` |

**插件签名验证**：
```yaml
FORCE_VERIFYING_SIGNATURE: true  # 强制签名校验
PYTHON_ENV_INIT_TIMEOUT: 120     # Python venv 初始化超时
PLUGIN_MAX_EXECUTION_TIMEOUT: 600  # 插件单次执行最大 10 分钟
```

---

### 3.5 `langgenius/qdrant:v1.8.3`（Dify 定制的 Qdrant 镜像）

> ⚠️ 严格说这并非纯上游 Qdrant，docker hub 上的 `langgenius/qdrant` 是 Dify 团队打包的版本。

| 属性 | 值 |
|------|-----|
| 出品 | Dify.AI 官方定制 |
| 基础镜像 | Qdrant v1.8.3 |
| 镜像大小 | ~150 MB |

**关键角色**：Dify 向量库的可选后端之一，对应 `profiles: qdrant`。

**配置极简**：
```yaml
QDRANT_API_KEY: ${QDRANT_API_KEY:-difyai123456}
volumes:
  - ./volumes/qdrant:/qdrant/storage
```

---

## 四、关系型数据库（2 个主选 + 4 个备选）

### 4.1 主选数据库（互斥使用 profiles）

#### `postgres:15-alpine`（推荐默认）

| 属性 | 值 |
|------|-----|
| Profile | `postgresql` |
| 镜像大小 | ~240 MB |
| 调优 | `max_connections=100`、`shared_buffers=128MB` |

**作用**：Dify 的**主关系型数据库**，存储租户、应用、对话、知识库元数据、工作流执行记录等。

**关键参数**（可通过环境变量覆盖）：

| 参数 | 默认值 | 调优建议 |
|------|--------|---------|
| `max_connections` | 100 | 按 worker 数量估算 |
| `shared_buffers` | 128MB | 推荐为宿主机内存的 25% |
| `work_mem` | 4MB | 复杂查询可上调 |
| `effective_cache_size` | 4096MB | 推荐为宿主机内存的 75% |
| `statement_timeout` | 0 | 生产建议设置（如 60s） |

#### `mysql:8.0`

| 属性 | 值 |
|------|-----|
| Profile | `mysql` |
| 镜像大小 | ~550 MB |
| 调优 | `max_connections=1000`、`innodb_buffer_pool_size=512M` |

**作用**：PostgreSQL 的替代选项，配置 `.env` 中 `DB_TYPE=mysql` 时启用。

**注意**：Dify 1.x 已**默认推荐 PostgreSQL**，MySQL 路径的测试覆盖相对较少。

---

### 4.2 备选数据库（也可作为向量库的特殊数据库）

#### `oceanbase/oceanbase-ce:4.3.5-lts`（分布式数据库 + 向量）

| 属性 | 值 |
|------|-----|
| 出品 | 蚂蚁集团 |
| Profile | `oceanbase` |
| 镜像大小 | ~1.5 GB |
| 默认内存 | 6 GB（`OB_MEMORY_LIMIT`） |

**作用**：**国产分布式数据库**，可同时作为关系数据库和向量数据库（结合 HNSW 索引）。  
适合超大规模（>1 亿向量）的国产化场景。

**健康检查**：通过 `obclient` 真实查询验证：
```yaml
test: 'obclient -h127.0.0.1 -P2881 -uroot@test -p... -e "SELECT 1;"'
```

#### `oceanbase/seekdb:latest`（OceanBase 精简版）

| 属性 | 值 |
|------|-----|
| 出品 | 蚂蚁集团 |
| Profile | `seekdb` |
| 默认内存 | 2 GB（轻量） |

**作用**：OceanBase 的轻量分支，更适合**开发和中小规模生产**。

#### `opengauss/opengauss:7.0.0-RC1`（华为 openGauss）

| 属性 | 值 |
|------|-----|
| 出品 | 华为 |
| Profile | `opengauss` |
| 需要 | `privileged: true`（特殊权限） |
| 端口 | 6600 |

**作用**：**国产开源数据库**，源自 PostgreSQL 9.2.4，内置向量能力。

**注意**：使用 `netstat` 做健康检查（启动较慢，需更多重试）。

#### `container-registry.oracle.com/database/free:latest`（Oracle 23c Free）

| 属性 | 值 |
|------|-----|
| 出品 | Oracle |
| Profile | `oracle` |
| 字符集 | AL32UTF8 |
| 命名卷 | `oradata` |

**作用**：Oracle 数据库的免费版本（**首次发布即支持向量数据类型**）。

#### `matrixorigin/matrixone:2.1.1`（MatrixOne）

| 属性 | 值 |
|------|-----|
| 出品 | 矩阵起源 |
| Profile | `matrixone` |
| 端口 | 6001 |

**作用**：**云原生超融合数据库**，支持 HTAP。

---

## 五、缓存与消息队列（1 个）

### 5.1 `redis:6-alpine`（默认启动，无 profile）

| 属性 | 值 |
|------|-----|
| 镜像大小 | ~30 MB |
| 密码 | 必填（启动时通过 `requirepass` 强制） |
| 用途 | Celery 消息队列 + 缓存 + 会话存储 + Socket.IO |

**关键配置**：
```yaml
command: redis-server --requirepass ${REDIS_PASSWORD:-difyai123456}
REDISCLI_AUTH: ${REDIS_PASSWORD:-difyai123456}
```

**健康检查**：
```yaml
test: ["CMD-SHELL", "redis-cli -a ${REDIS_PASSWORD} ping | grep -q PONG"]
```

> 💡 实际上 `redis-cli` 输出 `PONG` 时，`AUTH` 阶段的错误也会回显到 stderr，因此 `grep -q PONG` 仍然能通过——这是 Dify 故意采用的"宽容"健康检查。

---

## 六、向量数据库（14 个）

> Dify 是市面上**支持向量库最广泛**的 LLM 平台之一，覆盖 PostgreSQL 系、独立向量系、搜索系三大流派。

### 6.1 PostgreSQL 流派（4 个）

#### `pgvector/pgvector:pg16`（推荐轻量方案）

| 属性 | 值 |
|------|-----|
| Profile | `pgvector` |
| 镜像大小 | ~250 MB |
| 扩展 | `vector`、`pg_bigm`（可选全文检索） |

**特点**：把向量数据存入 PostgreSQL，适合**中小规模 + 已有 PG 运维经验**的团队。

#### `tensorchord/pgvecto-rs:pg16-v0.3.0`

| 属性 | 值 |
|------|-----|
| Profile | `pgvecto-rs` |
| 出品 | TensorChord |
| 实现 | Rust（性能比 pgvector 更高） |

**特点**：基于 Rust 实现的 PG 向量扩展，对**IVF、HNSW 索引**有更深优化。

#### `vastdata/vastbase-vector`（海量 Vastbase）

| 属性 | 值 |
|------|-----|
| Profile | `vastbase` |
| 出品 | 海量数据 |
| 端口 | 5434（避开默认 5432） |
| 认证 | `VB_DBCOMPATIBILITY=PG`（PG 兼容模式） |

**特点**：国产数据库，内置向量检索。

#### `couchbase-server`（本地构建）

> ⚠️ 唯一**本地构建**的镜像，Dockerfile 在 [docker/couchbase-server/](docker/couchbase-server/)。

| 属性 | 值 |
|------|-----|
| Profile | `couchbase` |
| 构建 | `build: ./couchbase-server` |
| 桶 RAM | 512 MB（`COUCHBASE_BUCKET_RAMSIZE`） |

**特点**：支持混合搜索（向量 + 全文），但资源占用较大。

---

### 6.2 独立向量库（5 个）

#### `semitechnologies/weaviate:1.27.0`（**官方推荐默认**）

| 属性 | 值 |
|------|-----|
| 出品 | Weaviate B.V. |
| Profile | `weaviate`（**`docker-compose.middleware.yaml` 默认启动**） |
| 镜像大小 | ~300 MB |
| 通信端口 | 8080（HTTP）+ 50051（gRPC） |

**特点**：
- **模块化架构**：可通过 `DEFAULT_VECTORIZER_MODULE` 启用内置向量化模型
- **多语言分词器**：`ENABLE_TOKENIZER_GSE/KAGOME_JA/KAGOME_KR`
- **认证体系**：API Key + Admin List 双重保护

**安全配置**：
```yaml
AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: false  # 禁止匿名
AUTHENTICATION_APIKEY_ENABLED: true
AUTHORIZATION_ADMINLIST_ENABLED: true
```

#### `milvusdb/milvus:v2.6.3`（**性能最强**）

| 属性 | 值 |
|------|-----|
| Profile | `milvus`（**需要 3 个容器组合启动**） |
| 镜像大小 | ~1.5 GB |
| 通信端口 | 19530（gRPC）+ 9091（健康） |

**特点**：专为**十亿级向量**设计的分布式向量数据库。

**依赖 3 个子容器**：

| 子服务 | 镜像 | 作用 |
|--------|------|------|
| `etcd` | `quay.io/coreos/etcd:v3.5.5` | 元数据存储（K/V） |
| `minio` | `minio/minio:RELEASE.2023-03-20T20-16-18Z` | 对象存储（存放向量原始数据） |
| `milvus-standalone` | `milvusdb/milvus:v2.6.3` | 主服务 |

**Milvus 依赖镜像详解**：

##### `quay.io/coreos/etcd:v3.5.5`

| 属性 | 值 |
|------|-----|
| 出品 | CoreOS（被 Red Hat 收购） |
| 作用 | 分布式 K/V 存储，Milvus 用其存储 schema、index 等元数据 |
| 端口 | 2379（client）+ 2380（peer） |

##### `minio/minio:RELEASE.2023-03-20T20-16-18Z`

| 属性 | 值 |
|------|-----|
| 作用 | 兼容 S3 协议的对象存储，Milvus 用其存放**向量原始数据和索引文件** |
| 端口 | 9000（API）+ 9001（Console） |

> ⚠️ 这个 MinIO 版本是**专门为 Milvus 锁定**的，单独用作 Dify 的存储不合适。

#### `langgenius/qdrant:v1.8.3`（已在前文 Dify 自研镜像中详述）

#### `ghcr.io/chroma-core/chroma:0.5.20`（最易用）

| 属性 | 值 |
|------|-----|
| Profile | `chroma` |
| 出品 | Chroma |
| 镜像大小 | ~400 MB |

**特点**：
- 专注 **Python 生态**，API 极简
- 默认开启 token 鉴权 + 持久化存储

#### `myscale/myscaledb:1.6.4`（ClickHouse 变体）

| 属性 | 值 |
|------|-----|
| Profile | `myscale` |
| 基础 | ClickHouse 21.x |
| 端口 | 8123（HTTP） |

**特点**：ClickHouse 的向量增强版，适合**大规模 SQL + 向量混合查询**。

---

### 6.3 搜索系 / 多模型数据库（5 个）

#### `docker.elastic.co/elasticsearch/elasticsearch:8.14.3`

| 属性 | 值 |
|------|-----|
| Profile | `elasticsearch` / `elasticsearch-ja` |
| 镜像大小 | ~1.5 GB |
| 资源限制 | 内存硬限 2 GB（`deploy.resources.limits.memory`） |
| 端口 | 9200 |

**特点**：
- 强大的**全文 + 向量混合搜索**（`knn` 查询）
- 自带 `pg_bigm` 中文分词替代品 `analysis-ik`/`analysis-smartcn`

**安全配置**（自签 basic 证书）：
```yaml
xpack.security.enabled: "true"
xpack.security.enrollment.enabled: "false"
xpack.security.http.ssl.enabled: "false"
ELASTIC_PASSWORD: elastic  # ⚠️ 生产必须修改
```

#### `docker.elastic.co/kibana/kibana:8.14.3`

| 属性 | 值 |
|------|-----|
| Profile | `elasticsearch`（随 ES 启动） |
| 端口 | 5601（默认） |
| 本地化 | `I18N_LOCALE: zh-CN` |

**作用**：Elasticsearch 的可视化控制台，方便调试 ES 集群。

#### `opensearchproject/opensearch:latest`

| 属性 | 值 |
|------|-----|
| Profile | `opensearch` |
| 镜像大小 | ~1.5 GB |
| 内存 | 默认 512MB-1GB（`OPENSEARCH_JAVA_OPTS`） |

**特点**：Elasticsearch 的**开源分支**（由 AWS 主导），协议更宽松。

**资源限制（关键）**：
```yaml
ulimits:
  memlock: { soft: -1, hard: -1 }   # 必须，否则性能暴跌
  nofile:  { soft: 65536, hard: 65536 }
```

#### `opensearchproject/opensearch-dashboards:latest`

| 属性 | 值 |
|------|-----|
| Profile | `opensearch` |
| 作用 | OpenSearch 的可视化（对应 Kibana） |
| 网络 | 内部 `opensearch-net`（无外网） |

**注意**：配置中写死走 HTTPS：
```yaml
OPENSEARCH_HOSTS: '["https://opensearch:9200"]'
```
但实际 ES 的 `xpack.security.http.ssl.enabled: "false"`，**这是配置不一致**，可能需要用户额外配置证书。

#### `containers.intersystems.com/intersystems/iris-community:2025.3`

| 属性 | 值 |
|------|-----|
| Profile | `iris` |
| 出品 | InterSystems |
| 镜像大小 | ~2 GB |
| 端口 | 1972（Super Server）+ 52773（Web 管理） |

**特点**：**多模型数据库**（关系 + 对象 + 向量 + 文档），医疗行业常用。

**特殊配置**：
```yaml
init: true                       # 启用 init 进程
tty: true                        # 分配 TTY
ISC_DATA_DIRECTORY: /durable/iris  # 持久化
```

---

## 七、安全与代理组件（3 个）

### 7.1 `ubuntu/squid:latest`（SSRF 防护代理）

| 属性 | 值 |
|------|-----|
| Profile | 默认启动 |
| 端口 | 3128（HTTP 代理） |
| 镜像大小 | ~200 MB |

**关键角色**：**SSRF（Server-Side Request Forgery）防护**——Dify 的 LLM 工具在执行用户配置的 HTTP 请求时，所有出站流量**强制走 Squid 代理**，从而：

1. **审计日志**：所有外网请求可在 Squid 中审计
2. **域名/IP 黑名单**：通过 Squid 规则阻止访问内网（如 `169.254.169.254` AWS metadata）
3. **统一出口**：便于企业内网代理配置

**架构关键**：
```yaml
networks:
  ssrf_proxy_network:
    driver: bridge
    internal: true  # ← 关键：禁止该网络直连外网
```

- `api`、`worker`、`worker_beat`、`plugin_daemon`、`sandbox` 同时加入 `ssrf_proxy_network` 和 `default` 两个网络
- 出口流量必须经 Squid 中转到 `default` 网络才能访问外网

**反向代理**：
```yaml
REVERSE_PROXY_PORT: 8194
SANDBOX_HOST: sandbox
SANDBOX_PORT: 8194
```
Squid 还被配置为**反向代理 sandbox**，确保 sandbox 也走同一出口。

---

### 7.2 `certbot/certbot`（Let's Encrypt 证书）

| 属性 | 值 |
|------|-----|
| Profile | `certbot`（**需手动启动**） |
| 启动命令 | `docker compose --profile certbot up -d` |

**作用**：自动申请和续期 Let's Encrypt 免费证书。

**挂载点**（多个）：
```yaml
- ./volumes/certbot/conf:/etc/letsencrypt        # 配置
- ./volumes/certbot/www:/var/www/html            # HTTP-01 验证
- ./volumes/certbot/logs:/var/log/letsencrypt    # 日志
- ./volumes/certbot/conf/live:/etc/letsencrypt/live  # 证书链
- ./certbot/update-cert.template.txt             # 续期脚本模板
- ./certbot/docker-entrypoint.sh                 # 自定义入口
```

**与 nginx 配合**：nginx 通过共享卷 `volumes/certbot/conf/live` 读取证书。

---

### 7.3 `busybox:latest`（一次性权限修复）

| 属性 | 值 |
|------|-----|
| 启动策略 | `restart: "no"`（一次性） |
| 镜像大小 | ~5 MB |

**作用**：**仅在首次启动时**修正 `volumes/app/storage` 目录的权限（改为 UID 1001，对应 api 容器的运行用户）。

**幂等设计**：
```bash
FLAG_FILE="/app/api/storage/.init_permissions"
if [ -f "${FLAG_FILE}" ]; then
  echo "Permissions already initialized. Exiting."
  exit 0
fi
chown -R 1001:1001 /app/api/storage && touch "${FLAG_FILE}"
```

---

## 八、反向代理与证书（2 个）

### 8.1 `nginx:latest`（统一入口）

| 属性 | 值 |
|------|-----|
| 镜像大小 | ~150 MB |
| 暴露端口 | 80 / 443 |

**关键作用**：唯一对外暴露的入口，路由到 web 和 api。

**挂载 4 个模板**：
```yaml
- ./nginx/nginx.conf.template         # 主配置
- ./nginx/proxy.conf.template        # 反向代理通用配置
- ./nginx/https.conf.template         # HTTPS 配置
- ./nginx/conf.d:/etc/nginx/conf.d    # 站点配置目录
- ./nginx/ssl:/etc/ssl               # 传统 SSL 证书目录
- ./volumes/certbot/conf/live:/etc/letsencrypt/live  # certbot 证书
```

**关键环境变量**：
| 变量 | 默认 | 说明 |
|------|------|------|
| `NGINX_CLIENT_MAX_BODY_SIZE` | 100M | 客户端请求体上限（影响文件上传） |
| `NGINX_PROXY_READ_TIMEOUT` | 3600s | 长连接超时（适配 LLM 流式输出） |
| `NGINX_PROXY_SEND_TIMEOUT` | 3600s | 同上 |
| `NGINX_ENABLE_CERTBOT_CHALLENGE` | false | 是否启用 HTTP-01 验证 |

**依赖**：`depends_on: api, web`（不等待健康状态，需注意启动顺序）。

---

## 九、辅助工具（3 个）

### 9.1 `downloads.unstructured.io/unstructured-io/unstructured-api:latest`

| 属性 | 值 |
|------|-----|
| Profile | `unstructured` |
| 作用 | 高级文档解析 ETL |

**触发条件**：`.env` 中设置 `ETL_TYPE=Unstructured` 启用，替代 Dify 内置的简单文档解析器。

**支持的格式**：PDF（OCR）、Word、Excel、PPT、HTML、EPUB 等。

**数据卷**：`./volumes/unstructured:/app/data`（缓存解析中间结果）。

---

### 9.2 `couchbase-server`（本地构建，已在向量库部分详述）

---

### 9.3 `certbot/certbot`（已在安全组件部分详述）

---

## 十、网络与存储设计

### 10.1 网络架构

| 网络 | driver | internal | 用途 |
|------|--------|----------|------|
| `ssrf_proxy_network` | bridge | ✅ **是** | api/worker/sandbox/plugin_daemon 之间的隔离内网 |
| `default` | bridge | ❌ 否 | 默认网络，可访问外网 |
| `milvus` | bridge | ❌ 否 | Milvus 集群专用（etcd + minio + milvus-standalone） |
| `opensearch-net` | bridge | ✅ **是** | OpenSearch 内部网络 |

**网络拓扑示意**：

```
┌─────────────── default network (可访问外网) ───────────────┐
│                                                            │
│  [nginx] [web] [api] [worker] [worker_beat] [plugin_daemon]│
│       │           │                                        │
│       │      ┌────┴────┐                                   │
│       │      │  redis  │ [db_postgres/mysql]              │
│       │      └─────────┘                                  │
│       ▼                                                    │
│  [vector store: weaviate/milvus/...]                       │
│       │                                                    │
│       │  ssrf_proxy 也连 default                          │
│       ▼                                                    │
│  [ssrf_proxy] ─────▶ 外网                                  │
└────────────────────────────────────────────────────────────┘
            │                              ▲
            │ ssrf_proxy_network (隔离)     │
            │                              │
   ┌────────┴────────┐                     │
   │  api/worker     │ ── 出站请求 ────▶ ssrf_proxy
   │  sandbox        │
   │  plugin_daemon  │
   └─────────────────┘
```

### 10.2 命名卷

```yaml
volumes:
  oradata:        # Oracle 数据
  dify_es01_data: # Elasticsearch 数据
```

其余数据均通过**绑定挂载**到 `./volumes/` 目录（便于备份和迁移）。

---

## 十一、Profile 按需启动机制

Dify 通过 Compose Profile 实现**模块化部署**，避免资源浪费。

### 11.1 Profile 分类总览

| Profile | 启用的服务 | 资源需求 |
|---------|-----------|---------|
| （无） | api, worker, worker_beat, web, redis, sandbox, plugin_daemon, ssrf_proxy, nginx, init_permissions | 基础 |
| `postgresql` | + db_postgres | +250MB |
| `mysql` | + db_mysql | +550MB |
| `weaviate` | + weaviate | +300MB |
| `milvus` | + etcd + minio + milvus-standalone | +2GB |
| `qdrant` | + qdrant | +150MB |
| `chroma` | + chroma | +400MB |
| `pgvector` | + pgvector | +250MB |
| `pgvecto-rs` | + pgvecto-rs | +250MB |
| `vastbase` | + vastbase | +500MB |
| `couchbase` | + couchbase-server | +1GB |
| `iris` | + iris | +2GB |
| `oracle` | + oracle | +1.5GB |
| `opengauss` | + opengauss | +500MB |
| `myscale` | + myscale | +500MB |
| `matrixone` | + matrixone | +500MB |
| `elasticsearch` | + elasticsearch + kibana | +3GB |
| `elasticsearch-ja` | 同上（仅切换镜像） | +3GB |
| `opensearch` | + opensearch + opensearch-dashboards | +2GB |
| `oceanbase` | + oceanbase | +1.5GB |
| `seekdb` | + seekdb | +500MB |
| `certbot` | + certbot | +100MB |
| `unstructured` | + unstructured | +1GB |

### 11.2 默认启动组合

通过 `.env` 中的 `COMPOSE_PROFILES` 控制：
```bash
COMPOSE_PROFILES=${VECTOR_STORE:-weaviate},${DB_TYPE:-postgresql}
```

- 默认：`postgresql` + `weaviate`
- 修改示例：`DB_TYPE=mysql VECTOR_STORE=milvus docker compose up -d`

---

## 十二、安全设计总结

### 12.1 三层防御体系

```
┌─────────────────────────────────────────────┐
│ Layer 1: 网络隔离                            │
│   - ssrf_proxy_network (internal: true)     │
│   - 禁止直接外联                            │
└─────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│ Layer 2: 出口代理                            │
│   - Squid 审计所有外网请求                   │
│   - 可配置域名/IP 黑名单                     │
└─────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│ Layer 3: 代码执行隔离                        │
│   - sandbox 独立容器                        │
│   - WORKER_TIMEOUT 强制超时                 │
│   - 强制走 SSRF 代理                        │
└─────────────────────────────────────────────┘
```

### 12.2 鉴权机制

| 鉴权点 | 机制 | 强度 |
|--------|------|------|
| API ↔ plugin_daemon | `INNER_API_KEY_FOR_PLUGIN` | 中（需修改默认密钥） |
| API ↔ sandbox | `SANDBOX_API_KEY` | 中（需修改默认密钥） |
| plugin_daemon ↔ API | `DIFY_INNER_API_KEY` | 中（需修改默认密钥） |
| 插件签名 | `FORCE_VERIFYING_SIGNATURE: true` | 高 |
| 内部 API → API | `SECRET_KEY` | 高（用于 Flask session） |
| Weaviate | API Key + Admin List | 中 |
| Elasticsearch | Basic Auth (`elastic`) | 中 |
| OpenSearch | Basic Auth | 中 |

### 12.3 ⚠️ 默认密码清单（生产必须修改）

```
DB_PASSWORD=difyai123456
REDIS_PASSWORD=difyai123456
SANDBOX_API_KEY=dify-sandbox
SECRET_KEY=sk-9f73s3ljTXVcMT3Blb3ljTqtsKiGHXVcMT3BlbkFJLK7U
INNER_API_KEY_FOR_PLUGIN=QaHbTe77CtuXmsfyhR7+vRjI/+XbV1AaFy691iy+kGDv2Jvy0/eAh8Y1
PLUGIN_DIFY_INNER_API_KEY=QaHbTe77CtuXmsfyhR7+vRjI/+XbV1AaFy691iy+kGDv2Jvy0/eAh8Y1
PLUGIN_DAEMON_KEY=lYkiYYT6owG+71oLerGzA7GXCgOT++6ovaezWAjpCjf+Sjc3ZtU+qUEi
WEAVIATE_API_KEY=WVF5YThaHlkYwhGUSmCRgsX3tD5ngdN8pkih
QDRANT_API_KEY=difyai123456
ELASTICSEARCH_PASSWORD=elastic
OPENSEARCH_INITIAL_ADMIN_PASSWORD=Qazwsxedc!@#123
OCEANBASE_VECTOR_PASSWORD=difyai123456
```

**生成强密钥的方法**：
```bash
openssl rand -base64 42
```

---

## 十三、常用启动命令

```bash
# 1. 准备环境
cd docker
cp .env.example .env
# 编辑 .env，至少修改 SECRET_KEY、DB_PASSWORD、REDIS_PASSWORD

# 2. 默认启动（PostgreSQL + Weaviate）
docker compose up -d

# 3. 切换数据库
DB_TYPE=mysql docker compose up -d

# 4. 切换向量库
VECTOR_STORE=milvus docker compose --profile milvus up -d

# 5. 启用 HTTPS（Let's Encrypt）
docker compose --profile certbot up -d

# 6. 启用高级 ETL
docker compose --profile unstructured up -d

# 7. 查看日志
docker compose logs -f api
docker compose logs -f worker

# 8. 健康检查
docker compose ps
curl http://localhost/health
curl http://localhost:5001/health  # 绕过 nginx 直接看 API

# 9. 备份数据
tar czf dify-backup-$(date +%Y%m%d).tar.gz volumes/

# 10. 完全重置（⚠️ 销毁数据）
docker compose down -v
```

---

## 十四、生产环境建议

### 14.1 必须修改的事项

1. **所有默认密码**（见 12.3 节）
2. **`SECRET_KEY`**：用于加密 Flask session，必须使用 `openssl rand -base64 42` 生成
3. **HTTPS**：启用 `certbot` profile 或自备证书
4. **`NGINX_SERVER_NAME`**：从 `_` 改为实际域名
5. **数据库连接池**：根据并发量调优 PostgreSQL `max_connections`

### 14.2 推荐优化

| 优化项 | 建议 |
|--------|------|
| 向量库选择 | 中小规模用 **pgvector**（最少运维）；大规模用 **Milvus** 或 **Weaviate** |
| 文件上传 | 提升 `NGINX_CLIENT_MAX_BODY_SIZE` 到 100M+ |
| 大模型流式输出 | `NGINX_PROXY_READ/SEND_TIMEOUT=3600s`（已默认） |
| Worker 数量 | `CELERY_WORKER_AMOUNT=核数 × 2` |
| 资源限制 | 在 `docker-compose.yaml` 添加 `deploy.resources.limits` |
| 监控 | 启用 `ENABLE_OTEL=true`，对接 Prometheus/Jaeger |
| 日志 | 配置集中日志收集（Loki/ELK） |

### 14.3 不要做的事

- ❌ **不要直接修改 `docker-compose.yaml`**：它是 `generate_docker_compose` 工具自动生成的，修改会丢失。应改 `docker-compose-template.yaml` 后重新生成。
- ❌ **不要在公网直接暴露 5001、5002、5003 端口**：仅 nginx 应通过 80/443 对外服务。
- ❌ **不要使用 `latest` 镜像**（除了 busybox、nginx、certbot、opensearch、oracle、unstructured）：这些是开发镜像，生产应锁版本。
- ❌ **不要删除 `init_permissions` 服务**：否则 API 容器会因权限问题无法写入 `storage` 目录。

---

## 附录：镜像汇总速查表

| 分类 | 镜像 | Profile | 端口 | 镜像大小 |
|------|------|---------|------|---------|
| **Dify 自研** | `langgenius/dify-api:1.14.0` | - | 5001 | ~1.5GB |
| | `langgenius/dify-web:1.14.0` | - | 3000 | ~300MB |
| | `langgenius/dify-sandbox:0.2.15` | - | 8194 | ~200MB |
| | `langgenius/dify-plugin-daemon:0.6.0-local` | - | 5002/5003 | ~400MB |
| | `langgenius/qdrant:v1.8.3` | qdrant | 6333/6334 | ~150MB |
| **数据库** | `postgres:15-alpine` | postgresql | 5432 | ~240MB |
| | `mysql:8.0` | mysql | 3306 | ~550MB |
| | `redis:6-alpine` | - | 6379 | ~30MB |
| **国产 DB** | `oceanbase/oceanbase-ce:4.3.5-lts` | oceanbase | 2881 | ~1.5GB |
| | `oceanbase/seekdb:latest` | seekdb | 2881 | ~500MB |
| | `opengauss/opengauss:7.0.0-RC1` | opengauss | 6600 | ~500MB |
| | `vastdata/vastbase-vector` | vastbase | 5432→5434 | ~500MB |
| | `container-registry.oracle.com/database/free:latest` | oracle | 1521 | ~1.5GB |
| **多模型** | `containers.intersystems.com/intersystems/iris-community:2025.3` | iris | 1972/52773 | ~2GB |
| **向量库** | `pgvector/pgvector:pg16` | pgvector | 5432 | ~250MB |
| | `tensorchord/pgvecto-rs:pg16-v0.3.0` | pgvecto-rs | 5432 | ~250MB |
| | `semitechnologies/weaviate:1.27.0` | weaviate | 8080/50051 | ~300MB |
| | `ghcr.io/chroma-core/chroma:0.5.20` | chroma | 8000 | ~400MB |
| | `myscale/myscaledb:1.6.4` | myscale | 8123 | ~500MB |
| | `matrixorigin/matrixone:2.1.1` | matrixone | 6001 | ~500MB |
| | `couchbase-server` (本地构建) | couchbase | 8091-8094 | ~1GB |
| **搜索系** | `docker.elastic.co/elasticsearch/elasticsearch:8.14.3` | elasticsearch | 9200 | ~1.5GB |
| | `docker.elastic.co/kibana/kibana:8.14.3` | elasticsearch | 5601 | ~1GB |
| | `opensearchproject/opensearch:latest` | opensearch | 9200 | ~1.5GB |
| | `opensearchproject/opensearch-dashboards:latest` | opensearch | 5601 | ~800MB |
| **Milvus 依赖** | `quay.io/coreos/etcd:v3.5.5` | milvus | 2379/2380 | ~50MB |
| | `minio/minio:RELEASE.2023-03-20T20-16-18Z` | milvus | 9000/9001 | ~250MB |
| | `milvusdb/milvus:v2.6.3` | milvus | 19530/9091 | ~1.5GB |
| **代理 / 入口** | `nginx:latest` | - | 80/443 | ~150MB |
| | `ubuntu/squid:latest` | - | 3128/8194 | ~200MB |
| | `certbot/certbot` | certbot | - | ~200MB |
| **辅助** | `busybox:latest` | - | - | ~5MB |
| | `downloads.unstructured.io/unstructured-io/unstructured-api:latest` | unstructured | - | ~1GB |

---

> 📚 **延伸阅读**：
> - [Dify 官方文档](https://docs.dify.ai)
> - [SSRF 防护 FAQ](https://docs.dify.ai/learn-more/faq/install-faq#18-why-is-ssrf-proxy-needed%3F)
> - [docker/README.md](docker/README.md) - 部署指南
> - [docker/envs/*.env.example](docker/envs/) - 完整配置参考
