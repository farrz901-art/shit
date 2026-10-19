---
name: project-neo4j-uri-host-vs-localhost
description: "NEO4J_URI 在宿主机跑 service 时必须用 neo4j://localhost:7687, 绝对别用 host.docker.internal (2026-06-15 实测慢 10 倍)"
metadata:
  node_type: memory
  type: project
  originSessionId: neo4j-uri-fix-2026-06-15
---

`packages/service/.env.local` 里 `NEO4J_URI` 的选型, 2026-06-15 实测:

| URI | 延迟 | 推荐场景 |
|---|---|---|
| `neo4j://host.docker.internal:7687` | **1352ms** | ❌ 宿主机跑 service 时**绝对别用** |
| `neo4j://localhost:7687` | **128ms** | ✅ 宿主机 uv run main.py |
| `bolt://localhost:7687` | **63ms** | 可用但 neo4j 5+ 推荐 neo4j:// (routing) |

**Why:** `host.docker.internal` 是 Docker Desktop 在 Windows 上为**容器内**进程访问宿主机而设的特殊 DNS 别名（写到 hosts 文件，指向 127.0.0.1）。宿主机上的进程用这个 host 名时，会先走 hosts 文件解析 + DockerNAT 桥接转换，多一层 NAT 转发开销。在 docker 容器里跑 service 时它才是正确选择（service 跟 neo4j 不在一个 docker network）。

本项目现状: `docker-compose.yml` 只起了 postgres / pgadmin / neo4j, **没有把 service 容器化**, service 是宿主机 `uv run python main.py` 跑。所以 `.env.local` 必须用 `localhost`。

**How to apply:**
- 改 NEO4J_URI 前先 `docker ps --format "table {{.Names}}"` 确认 service 在不在容器里
- 宿主机跑 → `neo4j://localhost:7687`
- 容器跑 → `neo4j://host.docker.internal:7687`（或同 docker network 内的服务名 `neo4j://neo4j:7687`）
- Aura 云 → `neo4j+s://<id>.databases.neo4j.io:7687`（在 `.env.example` 里）
- 不要为了"通用"在 .env.example 里留 placeholder, 写明 3 种环境怎么填
