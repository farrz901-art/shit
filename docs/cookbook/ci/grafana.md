# Grafana 教程

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

Grafana 是一款开源的数据可视化与监控仪表盘工具。它从各种数据源（Prometheus、PostgreSQL、Elasticsearch、Loki 等）拉取指标数据，通过灵活的图表、表格、告警规则呈现给用户。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Grafana** | 通用可视化 + 告警 | 支持 50+ 数据源，能同时接 PG / Prometheus / Loki |
| **Prometheus** | 指标收集 + 告警（自带简单图表） | Grafana 通常与 Prometheus 配合：Prometheus 采集，Grafana 展示 |
| **Kibana** | Elasticsearch 配套仪表盘 | 强绑定 ES，不适合本项目多源数据场景 |
| **Metabase** | 业务数据可视化（SQL-first） | 对时序指标和系统监控不友好 |

**Grafana 解决的核心问题**：把分散在不同系统（DB 性能、应用日志、容器资源、业务 SQL）的指标统一到一个 Web 仪表盘上，让开发者 / 运维一眼看清系统健康。

---

## 二、安装 & 启动

### 2.1 本地 docker 启动

Grafana 官方提供了 `grafana/grafana` 镜像，启动一个测试实例：

```bash
# 临时启动（数据不持久化）
docker run -d -p 3000:3000 --name=grafana grafana/grafana

# 持久化数据启动
mkdir -p $PWD/grafana_data
docker run -d -p 3000:3000 \
  -v $PWD/grafana_data:/var/lib/grafana \
  --name=grafana grafana/grafana
```

访问 http://localhost:3000，默认账号 `admin` / `admin`，首次登录会要求改密码。

### 2.2 添加到本项目 docker-compose（待评估）

当前项目 `docker/docker-compose.yml` 未集成 Grafana（项目仍用 `app_logs` / `error_logs` 表 + 后台 in-memory 监控做健康检查）。**待评估**集成方案见 §7。

### 2.3 健康检查

```bash
# Grafana 容器内健康检查
docker inspect --format='{{.State.Health.Status}}' grafana
# 返回 "healthy" / "starting" / "unhealthy"

# 直接访问 health endpoint
curl -f http://localhost:3000/api/health
# 返回 {"database":"ok","version":"11.x.x"}
```

---

## 三、核心概念

1. **Data Source（数据源）**：Grafana 拉数据的"接口适配器"。配置一次后可被所有面板复用。本项目推荐用 PostgreSQL 数据源直接跑 SQL。
2. **Dashboard（仪表盘）**：一组面板的集合，类似 Excel 里的"工作表"。可以 JSON 导入导出，便于团队共享。
3. **Panel（面板）**：单个图表（折线图、柱状图、表格、Stat 等）。每个面板有独立查询。
4. **Query（查询）**：面板从数据源拉数据的语句（SQL / PromQL / LogQL）。在面板编辑器下方实时预览结果。
5. **Alert Rule（告警规则）**：基于查询结果设置阈值（如 `error_count > 100/5min`），触发后通过 Email / Slack / Webhook 通知。
6. **Variables（变量）**：Dashboard 级参数（`$datasource`、`$interval`），实现一个 Dashboard 适配多环境。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# 启动 / 停止 / 重启（已配 docker）
docker start grafana
docker stop grafana
docker restart grafana

# 查看日志（容器内）
docker logs -f grafana
# 等价容器内命令：tail -f /var/log/grafana/grafana.log
```

### 4.2 查询 / 导入

```bash
# 列出已安装的 Grafana 实例（多容器时）
docker ps | grep grafana

# 通过 API 查询（认证用 Basic Auth + API key）
curl -u admin:password http://localhost:3000/api/dashboards/home

# 导入预制 dashboard（从 grafana.com 或本地 JSON）
curl -X POST -H "Content-Type: application/json" \
  -d @dashboard.json \
  -u admin:password \
  http://localhost:3000/api/dashboards/import
```

### 4.3 调试

```bash
# 启用 debug 日志（容器内）
docker exec -it grafana bash
# 编辑 /etc/grafana/grafana.ini
# [log]
# level = debug
# 然后重启

# 测试数据源连接（在 UI 左侧 Data Sources → Edit → Save & Test）
# SQL 调试（直接 psql 进库跑同一条 SQL 验证）
docker exec -it pgvector psql -U postgres -d rag -c "SELECT count(*) FROM app_logs;"
```

### 4.4 排错

```bash
# 容器内查看完整日志（含 panic）
docker logs --tail=100 grafana 2>&1 | grep -i "error\|panic"

# 端口冲突：本地已有服务占 3000
netstat -ano | grep :3000
# 改映射端口：docker run -p 3030:3000 grafana/grafana

# 数据源连接失败：检查网络（容器间需在同一个 docker network）
docker network ls
docker network connect app-network grafana
```

---

## 五、项目集成点

### 5.1 项目当前不使用 Grafana

**项目当前未集成 Grafana**。`docker/docker-compose.yml` 中没有 `grafana` 服务，`.env.example` 中仅 `GRAFANA_ENABLED=false` 一个开关占位（`packages/service/.env.example:67`）。

### 5.2 项目健康检查现状

项目自建 `src/health/router.py:18-37` + 后台 `start_health_loop`（5s 轮询 7 项指标）实现监控：

- DB（Postgres）连接
- MinIO 连接
- Dify API 可达性
- LLM 响应
- Mem0 状态
- 字典子系统
- 调度器状态

指标由 `src/health/cache.py` 维护内存缓存，通过 `GET /api/health/system`（`src/health/router.py:18-37`）返回。

### 5.3 潜在数据源配置

如果集成 Grafana，可以配置以下数据源：

| 数据源 | URL | 用途 |
|--------|-----|------|
| PostgreSQL | `localhost:5432` (db: `rag`) | 查 `app_logs` / `error_logs` / `users` |
| Prometheus | `host.docker.internal:9090` | 容器 / 进程资源 |
| Loki | `host.docker.internal:3100` | 日志聚合（需要额外加 Loki 容器） |

---

## 六、项目代码示例

### 6.1 项目的健康检查输出

`src/health/cache.py` 维护一个内存中的健康检查快照，被 Grafana 风格的"面板"读取：

```python
# 项目当前做法：后台 5s 轮询 + cache
# src/health/router.py:18-37
@router.get(
    "/system",
    summary="查询系统监控状态",
    description=(
        "## 用途\n\n"
        "返回系统 5 类核心组件的聚合监控状态 (DB / MinIO / Dify / LLM / Mem0)"
    ),
)
def health_system(_user: CurrentUser = Depends(require_super_admin)):
    return _cache.get_cached_health()
```

返回的 JSON 结构与 Grafana 数据源响应格式不同，但包含相似信息（如 `db.ok`、`minio.ok`、时间戳等）。

### 6.2 Grafana 数据源配置示例（假设集成后）

如果将来加 Grafana + PostgreSQL 数据源，可以用同一条 SQL 渲染指标：

```sql
-- 错误日志 5 分钟分桶
SELECT
  date_trunc('minute', created_at) AS time,
  count(*) AS error_count
FROM error_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY time
ORDER BY time;
```

把这条 SQL 放到 Grafana 的 PostgreSQL 数据源 Panel 里，就能得到错误日志时序图。

### 6.3 Grafana 仪表盘 JSON 片段

Grafana 仪表盘可导出为 JSON，存入 `docker/volumes/grafana_data/provisioning/dashboards/` 自动加载：

```json
{
  "title": "RAG Project Health",
  "uid": "rag-health",
  "panels": [
    {
      "title": "Errors per Minute",
      "type": "graph",
      "datasource": "PostgreSQL",
      "targets": [{
        "rawSql": "SELECT date_trunc('minute', created_at), count(*) FROM error_logs ..."
      }]
    }
  ]
}
```

---

## 七、项目没用到的能力

以下 Grafana 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Alert 告警** | 配置阈值自动 Email / Slack 通知 | 当前用 `src/health/router.py` 5s 轮询替代 |
| **Provisioning（自动加载）** | 用 YAML / JSON 自动创建数据源和仪表盘 | 适合 CI 环境，无需手动点击 UI |
| **Variables 变量** | Dashboard 顶部下拉切换时间范围 / 数据源 | 单环境用不到，多环境有价值 |
| **Templating** | Dashboard 模板化（一次开发多实例复用） | 仅在多项目共用仪表盘时有用 |
| **Grafana Tempo（链路追踪）** | 与 Langfuse 配合显示 trace | 已有 Langfuse（见 `cookbook/rag/langfuse.md`）做追踪 |
| **Unified Alerting** | 跨数据源统一告警 | 简单场景不需要，复杂时再启用 |

**建议关注**：如果日志量持续增长（日均 > 10 万条 `app_logs`），建议引入 Grafana + Loki，PostgreSQL 承担长期审计，Grafana 承担实时可视化。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **数据持久化**：Grafana 仪表盘存在内置 SQLite（`/var/lib/grafana/grafana.db`），必须挂载到宿主机 volume，否则容器删除后仪表盘全丢。
2. **备份策略**：备份 `grafana_data/` 目录足够；导出关键仪表盘为 JSON 多一份异地备份。
3. **认证管理**：生产环境用 OAuth / LDAP / SAML，不要用默认 admin 密码。
4. **数据源只读账号**：为 Grafana 创建专用的 PostgreSQL 只读账号（`GRANT SELECT ON ALL TABLES`），不要给 superuser。
5. **版本锁定**：用具体 tag（如 `grafana/grafana:11.4.0`）而非 `:latest`，避免升级破坏仪表盘。

### 常见坑

1. **首次登录后必须改密码**：Grafana 11.x 默认要求改 admin 密码，否则无法进入 UI。
2. **PostgreSQL 数据源连接失败**：容器内 localhost 是容器自己的 localhost，不是宿主机。用 `host.docker.internal:5432`（Mac/Windows）或宿主 IP（Linux）。
3. **SQL 时间区间参数**：Grafana 用 `__timeFilter(column)` 而不是 SQL `WHERE`，避免硬编码时间窗口。
4. **Variables 引用必须带 `$`**：`$datasource` 和 `${datasource}` 都能解析，但 `datasource` 不会。
5. **Panel 预览 SQL 报错**：检查 SQL 是否在 pgadmin / psql 里能跑通，Grafana 不会改写你的 SQL。

---

## 📚 参考

- [Grafana 官方文档](https://grafana.com/docs/grafana/latest/)
- [Grafana Docker 部署](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)
- [PostgreSQL 数据源](https://grafana.com/docs/grafana/latest/datasources/postgres/)
- [Grafana 仪表盘 JSON 规范](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
