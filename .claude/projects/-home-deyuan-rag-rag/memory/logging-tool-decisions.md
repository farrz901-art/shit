---
name: logging-tool-decisions
description: "Logging system tool decisions (2026-06-17) - loguru + PG, reserve Grafana hook, no UI"
metadata: 
  node_type: memory
  type: project
  originSessionId: 20df34db-3217-47b0-9511-2f09132e0f81
---

# 日志系统工具选型决策 (2026-06-17)

**当前 stack**:
- loguru (全量切, InterceptHandler 桥接 stdlib)
- Postgres 3 表 (app_logs / error_logs / audit_logs) + 月分区
- 控制台: dev 彩色 / prod JSON
- 全局异常 handler + PII scrub
- Audit decorator + 25 hook (P0+P1+P2+P3)

**预留 (本期不实现, spec 写明接入路径)**:
- Grafana: `GRAFANA_ENABLED=false`, 后期直接连 `RAG_DB_URL`, 1 天接好
- Sentry: `SENTRY_ENABLED=false`, SaaS DSN, 装 `sentry-sdk[fastapi]`
- Loki: `LOKI_ENABLED=false`, 日志量大或 K8s 时接

**不做**:
- ❌ 自建日志查看 UI (投入产出比差, 后期接 Grafana)
- ❌ Supabase Studio (没用 Supabase)
- ❌ Sentry 自部署 (太重, 24+ 容器)

**spec §12 必须写**:
1. 4 工具对比 (Loki / Grafana / Sentry / Supabase Studio) 表
2. Grafana 接入路线图 (3 步: 装 Grafana → datasource 配 PG → dashboard)
3. Sentry 接入路线图 (SaaS, 2 行代码)
4. 运维查询 SQL 示例 (5-10 条, 查错误 / 查 audit / 查危险操作)

**Why**: 用户 2026-06-17 在 brainstorming 中明确:
- "太重了" (Sentry 自部署)
- "加 1 个段: 运维查询示例 (5-10 条常用 SQL), 等真有 UI 需求, 接 Grafana"
- "你把四个工具的调研也写到 specs 或者别的文档里面方便后期接入"
- "预留接入 grafana 的位置, 并且文档说明一下"

**How to apply**: 写 spec 时把 4 工具调研作为 §12 段写明, env 留 3 个 ENABLED flag, doc 写运维 SQL.

**Related**: [[logging-decisions]] (整体决策), [[minio-plan-then-deepeval]] (项目队列)