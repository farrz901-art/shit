# Docker / Docker Compose 教程

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python/TS 工程师，需要理解本项目为什么这样用、能怎么扩展

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

Docker 是一个容器化运行时，能将应用及其依赖打包成轻量、可移植的镜像，在任意 Linux 主机上一致运行。Docker Compose 是它的多容器编排工具，用一个 `docker-compose.yml` 声明式地定义多个服务（数据库、缓存、对象存储等）的启动、网络、依赖关系。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| Docker Compose | 单机多容器编排 | 开发环境足矣，零额外成本 |
| Kubernetes (K8s) | 生产级容器编排（集群、自动扩缩） | 本项目无高可用需求，K8s 太重 |
| Podman Compose | 无 daemon 的容器编排 | Docker 社区更成熟，文档更多 |

**为什么要用 Docker Compose 而不用裸 `apt install postgresql`？**
- 版本隔离：不同项目需要不同版本的 Postgres/Redis，宿主机装一个就冲突
- 环境一致：团队新成员 `docker compose up -d` 5 秒拉起全套基础服务，不用花 1 小时配 DB
- 可复现：`docker-compose.yml` 锁定镜像 tag，`docker compose up` 在任何机器产出相同环境

---

## 二、安装 & 启动

### 2.1 安装 Docker Desktop

Windows 推荐用 Docker Desktop（自带 Docker Compose v2）：

```bash
# 1. 去 https://docs.docker.com/desktop/ 下载 Docker Desktop
# 2. 安装后启动 Docker Desktop，确认 WSL 2 backend 已启用
# 3. 验证安装
docker --version          # 需要 ≥ 24.0
docker compose version    # 需要 ≥ 2.27
```

> ⚠️ Windows 用户务必用 **Docker Desktop + WSL 2 backend**，不要用 Hyper-V backend（性能差）。Docker Desktop 设置里确保 "Use WSL 2 based engine" 已勾选。

### 2.2 启动项目基础服务

```bash
# 进入项目 docker 目录
cd docker/

# 复制环境变量（首次运行）
cp .env.example .env
# 编辑 .env 里的 POSTGRES_PASSWORD 等字段

# 启动全部服务（后台）
docker compose up -d
```

第一次启动会拉取镜像（~2 GB），后续秒级启动。

### 2.3 健康检查

```bash
# 检查所有服务状态
docker compose ps

# 检查单个服务健康状态
docker compose exec postgres pg_isready -U postgres -d rag
docker compose exec redis redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning ping
curl -f http://localhost:9000/minio/health/live
```

---

## 三、核心概念

1. **镜像（Image）**：容器的只读模板，类似 VM 的 ISO。项目基于 `pgvector/pgvector:pg18`、`neo4j:2026.05.0` 等官方镜像。
2. **容器（Container）**：镜像的运行实例，每个容器各有独立文件系统、网络、进程空间。`docker compose up -d` 后 4 个容器同时运行。
3. **卷（Volume）**：持久化存储，容器删除后数据保留。项目用 `bind mount`（`./volumes/pg_data:/var/lib/postgresql`）将数据挂到宿主机目录，方便备份和查看。
4. **网络（Network）**：容器间的隔离通信层。项目定义 `app-network`，4 个服务都在此网络上，服务名即 hostname（代码里无需写 IP）。
5. **健康检查（Healthcheck）**：Docker 定期在容器内执行命令判断服务是否就绪。Postgres 用 `pg_isready`，Redis 用 `redis-cli ping`，Neo4j 用 HTTP `wget`。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# 启动全部服务（后台）
cd docker/
docker compose up -d

# 启动单个服务
docker compose up -d postgres

# 查看启动日志（首次排查用）
docker compose logs -f

# 停止全部（不删除卷，数据保留）
docker compose stop

# 停止并删除容器（卷保留）
docker compose down

# 停止并删除容器+卷（数据全清）
docker compose down -v
```

### 4.2 查询

```bash
# 列出运行中的容器
docker compose ps

# 查看容器资源占用
docker stats

# 查看容器内运行的进程
docker compose top

# 检查容器 IP（在 app-network 上）
docker inspect pgvector --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

### 4.3 调试

```bash
# 进入容器内部（bash）
docker compose exec postgres bash

# 执行 SQL 查询
docker compose exec -T postgres psql -U postgres -d rag -c "SELECT count(*) FROM users;"

# 查看容器日志（最后 50 行 + 持续追踪）
docker compose logs --tail=50 -f neo4j

# 复制文件出容器
docker compose cp neo4j:/logs/debug.log ./debug.log
```

### 4.4 排错

```bash
# 端口冲突检测
netstat -ano | grep -E "5432|6379|9000|7474"

# 容器启动后马上退出（看 exit code）
docker compose logs postgres --tail=50

# 重建容器（清缓存，不删卷）
docker compose up -d --force-recreate

# 查看容器内环境变量
docker compose exec postgres env | grep POSTGRES

# Docker Desktop 资源不足（WSL 2 内存不够）
# 设置文件：%USERPROFILE%\.wslconfig
# [wsl2]
# memory=8GB
# processors=4
```

---

## 五、项目集成点

### 5.1 环境变量配置

项目后端（FastAPI）通过环境变量连接这些服务（`docker/.env` → `packages/service/.env`）：

| 服务 | 连接字符串示例 | 项目配置位置 |
|------|----------------|-------------|
| PostgreSQL | `postgresql+psycopg://postgres:deyuan888@localhost:5432/rag` | `PG_HOST`/`PG_PORT`/`PG_USER`/`PG_PASSWORD`/`PG_DATABASE`（`src/config/settings.py` 内 `get_rag_db_url()` 拼接） |
| Redis | `redis://:redis123@localhost:6379/0` | `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` |
| Neo4j | `bolt://localhost:7687` | `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` |
| MinIO | `http://minioadmin:minioadmin@localhost:9000` | `OBJECT_STORE_S3_ENDPOINT`/`OBJECT_STORE_S3_ACCESS_KEY`/`OBJECT_STORE_S3_SECRET_KEY`/`OBJECT_STORE_S3_BUCKET` |

### 5.2 被引用的模块

- **Postgres**：所有数据持久化（用户、知识图谱、对话历史、审计日志）
- **Redis**：认证 token 缓存（6h）、IP 限流（15min）、权限矩阵（60s）、embedding 缓存（7d）
- **Neo4j**：知识图谱三元组存储
- **MinIO**：对象存储（文档上传、处理结果、聊天附件），全部走 presigned URL

### 5.3 网络拓扑

```
宿主机
 ├─ :5432 ─── pgvector (PostgreSQL + pgvector)
 ├─ :7474 ─── neo4j (Browser UI)
 ├─ :7687 ─── neo4j (Bolt 协议)
 ├─ :6379 ─── redis (缓存)
 ├─ :9000 ─── minio (S3 API)
 └─ :9001 ─── minio (Web Console)
```

---

## 六、项目代码示例

### 6.1 多阶段构建后端镜像

`packages/service/Dockerfile:10-74` 使用典型的 Python 多阶段构建：独立的 builder 阶段安装依赖，runner 阶段仅复制 .venv 和源码，最终镜像只有运行时需要的文件。

```dockerfile
# 阶段 1：依赖构建
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY main.py alembic.ini pyproject.toml ./

# 阶段 2：运行时
FROM python:3.14-slim AS runner
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/main.py /app/main.py
CMD ["python", "main.py"]
```

`docker/docker-compose.yml:4-23` 定义了 Postgres 服务及其 healthcheck：

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

`docker/docker-compose.yml:54-73` 展示了 MinIO 对象存储的配置，包含健康检查和 CORS 相关的 command 参数：

```yaml
minio:
  image: minio/minio:latest
  container_name: minio
  ports:
    - "9000:9000"   # S3 API 端口
    - "9001:9001"   # Web 控制台端口
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  volumes:
    - ./volumes/minio_data:/data
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
```

### 6.2 多阶段构建前端镜像

`packages/web/Dockerfile:11-59` 使用了三层构建：deps 阶段安装依赖 → builder 阶段构建产物 → runner 阶段仅保留 `standalone` 输出：

```dockerfile
FROM oven/bun:1-alpine AS deps
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

FROM oven/bun:1-alpine AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build

FROM oven/bun:1-alpine AS runner
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
CMD ["bun", "server.js"]
```

### 6.3 容器化基础服务一键启动

项目 `docker/docker-compose.yml:102-104` 定义了 `app-network`：

```yaml
networks:
  app-network:
    name: app-network
```

4 个服务——PostgreSQL、Neo4j、MinIO、Redis——全部在同一个 `app-network` 上，互相通过服务名访问。每个服务都配置了：
- `restart: unless-stopped` —— 机器重启后自动拉起
- `healthcheck` —— 确保依赖就绪才接受连接
- volumes —— 数据持久化到 `docker/volumes/` 目录

---

## 七、项目没用到的能力

以下为 Docker Compose 官方支持、但项目当前未用的能力（**待评估**）：

| 特性 | 用途 | 为什么不加 |
|------|------|-----------|
| **Multi-stage build（项目已用，但 Compose 里没编排）** | `docker compose build` 能编排镜像构建流程 | 当前 CI 中分别 build 两个 Dockerfile，不依赖 Compose |
| **`depends_on` + 条件等待** | 控制服务启动顺序（如 Postgres 就绪后再起后端） | 项目在应用层做重试，不依赖 Compose 级编排 |
| **Profiles** | 区分 dev/staging/prod 的 service 集合 | 当前所有服务一起起，未区分环境 |
| **BuildKit secrets (`--secret`)** | 构建时不把 SSH 密钥等写入镜像层 | 本地构建无密钥需求，CI 用 GitHub Actions secrets |
| **Docker Compose 扩展字段 (`x-`)** | YAML 锚点去重，适合多环境 Compose | 项目只有一个 `docker-compose.yml`，重复尚可控 |

**建议关注**：如果将来需要"开发时排除 MinIO / Neo4j 以节省资源"，可以引入 Compose profiles：`docker compose --profile minimal up -d` 只起 Postgres + Redis。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **日志轮转**：Docker 默认 `--log-opt max-size=10m --log-opt max-file=3` 应加到 `docker-compose.yml` 的每个服务下，否则容器日志会无限积累撑满磁盘。
2. **定期备份**：Postgres 数据在 `docker/volumes/pg_data/`，这个目录要加到备份策略中。Redis AOF 文件同理在 `docker/volumes/redis_data/`。
3. **磁盘监控**：定期 `docker system df` 查看 Docker 占用的磁盘，`docker system prune -a --volumes` 清理未使用的镜像/容器/卷（慎用）。
4. **版本锁定**：`docker-compose.yml` 里所有镜像都指定了 tag（如 `pgvector/pgvector:pg18`），不要用 `:latest`（MinIO 除外，因为其 API 向后兼容）。

### 常见坑

1. **端口冲突**：本地已装 Postgres（5432）或 Redis（6379）时，Docker 容器端口映射失败。解法：停本地服务，或改 `docker-compose.yml` 的 host port（如 `"5433:5432"`）。
2. **WSL 2 内存吃满**：Docker Desktop 默认用 WSL 2，内存上限与宿主机共享。`.wslconfig` 设 `memory=8GB` 可限制内存占用（重启 WSL 生效）。
3. **`docker compose down -v` 误删数据**：`-v` 会删除 volumes 里的数据，新手常误操作。关键操作前确认 `docker compose ps` 没有业务数据卷挂载。
4. **MinIO 首次使用需初始化**：`docker compose up -d` 后需执行 `bash docker/scripts/minio_init.sh` 创建 bucket 和 CORS 规则，否则浏览器直传会 403。

---

## 九、Docker Compose 写作技巧

> 本 docker.md 是工具类唯一特例（见 spec），需额外覆盖 Compose 文件编写技巧。

### 9.1 YAML 缩进规则

Docker Compose 是 YAML 格式，缩进决定层级：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18     # 两级缩进：services → postgres → image
    restart: unless-stopped           # 同级键值对齐
    environment:                      # 值可以是 mapping 或 array 两种写法
      POSTGRES_USER: ${POSTGRES_USER} # mapping 写法（推荐，类型明确）
    ports:
      - "5432:5432"                   # array 写法
```

常见错误：`services` 和 `postgres` 之间少缩进、`environment` 下用 `=` 赋值（那是 `.env` 的语法）。

### 9.2 environment 与 env_file 区别

```yaml
# 方式 1：直接写键值对（优先，显式可读）
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

# 方式 2：引用 .env 文件（docker-compose.yml 同目录的 .env 自动读取）
# .env 内容：POSTGRES_PASSWORD=deyuan888
# Compose 会展开 ${POSTGRES_PASSWORD}

# 方式 3：env_file（多个环境时用）
env_file:
  - ./dev.env
  - ./common.env
```

优先级（高→低）：shell 环境变量 > 同目录 `.env` 文件 > `env_file` > compose 内硬编码。

### 9.3 depends_on 条件等待

```yaml
# 不加条件：仅保证启动顺序，不保证服务就绪
depends_on:
  - postgres

# 加条件（Compose v2.27+）：等待 healthcheck 通过
depends_on:
  postgres:
    condition: service_healthy
```

项目当前未配置 `depends_on` 条件（服务启动后在应用层做重试），但在依赖链复杂时推荐加上。

### 9.4 YAML 扩展字段与锚点

```yaml
# 扩展字段（以 x- 开头）：可被 services 引用
x-logging: &logging
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"

services:
  postgres:
    image: pgvector/pgvector:pg18
    <<: *logging    # 引用上面的 logging 配置
  redis:
    image: redis:7.4-alpine
    <<: *logging    # 复用同一个 logging 配置
```

这在多服务复用日志/健康检查/重启策略时非常有用，避免 5 个服务重复写 15 行相同配置。

---

## 📚 参考

- [Docker Compose 官方文档](https://docs.docker.com/compose/compose-file/)
- [Docker 多阶段构建](https://docs.docker.com/build/building/multi-stage/)
- [pgvector 镜像](https://hub.docker.com/r/pgvector/pgvector)
- [Neo4j Docker 部署](https://neo4j.com/docs/operations-manual/current/installation/docker/)
- [MinIO Docker 部署](https://min.io/docs/minio/container/index.html)
- [Redis Docker 部署](https://redis.io/docs/latest/operate/orchestration/docker/)

---

**状态：** 🚧 样例

**最后更新：** 2026-06-19
