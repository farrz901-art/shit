# 日志运维查询 SQL (2026-06-17 logging spec §12)

> 项目用 loguru + PG 3 表存日志, 后期接 Grafana 直接查这些表.
> 当前阶段没 UI, 用 psql / pgAdmin / DBeaver 跑下面 SQL 排错.

## 表结构速览

| 表 | 用途 | 保留 |
|---|---|---|
| `app_logs` | 应用生命周期 (INFO/WARN/ERROR/CRITICAL) | 7-30 天, 月分区 |
| `error_logs` | 5xx 异常 + stacktrace | 90 天, 月分区 |
| `audit_logs` | 危险操作审计 (append-only) | 1-7 年, 月分区 |

每表有 `request_id` (UUID4) 关联同一请求的多条记录, `user_id` (审计用), `context` JSONB (业务字段).

## 常用查询

### 1. 最近 1 小时 ERROR/WARNING

```sql
SELECT ts, level, logger, message, request_id, user_id
FROM app_logs
WHERE ts > NOW() - INTERVAL '1 hour'
  AND level IN ('WARNING', 'ERROR', 'CRITICAL')
ORDER BY ts DESC
LIMIT 100;
```

### 2. 某用户最近 7 天操作

```sql
SELECT ts, level, message, request_id
FROM app_logs
WHERE user_id = $1
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 200;
```

### 3. 危险操作审计 (按 action 分桶, 30 天)

```sql
SELECT action, COUNT(*) AS cnt, MAX(ts) AS last_at
FROM audit_logs
WHERE ts > NOW() - INTERVAL '30 days'
GROUP BY action
ORDER BY cnt DESC;
```

### 4. 某用户的 audit 轨迹 (合规查询)

```sql
SELECT ts, action, target_type, target_id, result, ip
FROM audit_logs
WHERE actor_id = $1
ORDER BY ts DESC
LIMIT 100;
```

### 5. 失败的危险操作

```sql
SELECT ts, actor_id, action, target_id, metadata->>'error' AS error
FROM audit_logs
WHERE result = 'failure'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC;
```

### 6. 按小时分桶 ERROR 数 (找异常高峰)

```sql
SELECT date_trunc('hour', ts) AS hour, COUNT(*) AS err_cnt
FROM app_logs
WHERE level = 'ERROR'
  AND ts > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
```

### 7. 某异常类型最近 7 天

```sql
SELECT ts, exception_type, exception_msg, path, user_id
FROM error_logs
WHERE exception_type = 'ValueError'
  AND ts > NOW() - INTERVAL '7 days'
ORDER BY ts DESC
LIMIT 50;
```

### 8. GIN 索引查 context JSONB

```sql
SELECT ts, level, message
FROM app_logs
WHERE context @> '{"action": "presign_upload"}'
  AND ts > NOW() - INTERVAL '1 day'
ORDER BY ts DESC;
```

### 9. 跨用户访问检测

```sql
SELECT ts, actor_id, target_id, ip, metadata
FROM audit_logs
WHERE action = 'cross_user.read'
ORDER BY ts DESC
LIMIT 100;
```

### 10. 删除类操作全表

```sql
SELECT ts, actor_id, action, target_id, target_type
FROM audit_logs
WHERE action LIKE '%delete%' OR action LIKE '%purge%'
ORDER BY ts DESC
LIMIT 200;
```

## Grafana 接入路线图

当前阶段没 UI. 后期接 Grafana 1 天接好:

```bash
# 1. 装 Grafana (docker compose 加一段, 或单独跑)
docker run -d -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana:latest

# 2. 浏览器开 http://localhost:3000 → Configuration → Data sources → Add → PostgreSQL
#    填: host=postgres port=5432 db=rag user=postgres password=...
#    Save & Test

# 3. Create dashboard → Import dashboard JSON
#    (本仓库后期提供 app_logs / error_logs / audit_logs 仪表盘 JSON)
```

接入后, env 设 `GRAFANA_ENABLED=true` (core/logging.py 留 hook).

## Sentry 接入路线图 (本期不接)

```bash
# 1. 注册 sentry.io → 创 project → 拿 DSN
# 2. 装包
uv add 'sentry-sdk[fastapi]'

# 3. main.py 加 2 行
import sentry_sdk
sentry_sdk.init(dsn=os.getenv('SENTRY_DSN'), traces_sample_rate=0.1)

# 4. core/errors.py 全局异常 handler 加 sentry_sdk.capture_exception(exc)
```

## 分区维护 (后期 cron)

`packages/service/scripts/log_partition_cron.py` (本 spec 不实现):
- 每天 0:00 续建下月分区 (`CREATE TABLE app_logs_YYYY_MM PARTITION OF ...`)
- 删过期分区:
  - app_logs: 30 天前
  - error_logs: 90 天前
  - audit_logs: 1 年前 (导 Parquet 到 MinIO 后再删)
