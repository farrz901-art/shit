# Redis 运维查询 (2026-06-18 redis spec §8)

> 项目用 redis 7.4-alpine 容器, 跟 PG / MinIO / Neo4j 同 docker-compose.
> 6 个 use case 共享: perm / auth token / rate limit / mem0 ready / dify query / embed.

## 连接信息

```bash
# 容器内 (docker compose exec)
docker compose exec redis redis-cli -a $REDIS_PASSWORD --no-auth-warning PING

# 宿主机 (端口 6379 暴露)
redis-cli -h localhost -p 6379 -a $REDIS_PASSWORD --no-auth-warning PING
```

## 实时 key 列表

```bash
# 所有 rag: 前缀 key
redis-cli -a $REDIS_PASSWORD --no-auth-warning KEYS "rag:*"

# 按域分桶 (生产用 SCAN, 不用 KEYS 阻塞)
for prefix in perm auth rl mem0 dify embed; do
  count=$(redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:${prefix}:*" | wc -l)
  echo "$prefix: $count keys"
done
```

## 命中率监控

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO stats | grep keyspace
# keyspace_hits:12345  keyspace_misses:678
# hit_rate = 12345 / (12345 + 678) = 94.8%
# 命中率 <80% → 调 TTL / 检查 key 设计
```

## TTL 倒计时

```bash
# 单个 key 剩余秒数
redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL "rag:auth:tok:abc123..."

# 大批 key TTL (e.g. embed 缓存)
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:embed:*" | \
  head -100 | xargs -I {} redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL {}
```

## 内存监控

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning INFO memory | grep -E "used_memory_human|maxmemory_human"
# used_memory_human:24.5M  maxmemory_human:512M
# 满时触发 allkeys-lru 淘汰 (docker-compose.yml:89 已配)
```

## 限流检查 (某 IP 当前计数)

```bash
redis-cli -a $REDIS_PASSWORD --no-auth-warning GET "rag:rl:login:1.2.3.4"
redis-cli -a $REDIS_PASSWORD --no-auth-warning TTL "rag:rl:login:1.2.3.4"
# 返 int 计数 + 剩余秒数, 超过 5 则 login 端点返 429
```

## 手动失效 (临时, 不在 spec 范围)

```bash
# 踢某 token (强制重新登录)
redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL "rag:auth:tok:abc123..."

# 踢所有 Dify query 缓存 (知识库大改后)
redis-cli -a $REDIS_PASSWORD --no-auth-warning --scan --pattern "rag:dify:q:*" | \
  xargs redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL

# 踢所有 permission cache (角色权限调整后)
redis-cli -a $REDIS_PASSWORD --no-auth-warning DEL "rag:perm:matrix"
# 也可由代码 permission_cache.invalidate() 触发
```

## 模拟 Redis 挂 (测试 fail-open)

```bash
# 停 Redis
docker compose stop redis

# 观察服务是否仍可用
curl http://localhost:8000/api/health  # 应 200
# log 应该有 "redis GET/SET 失败" CRITICAL 记录

# 重启
docker compose start redis
```

## 配置文件位置

- 服务端: docker-compose.yml:74-99 (Redis 容器, AOF + LRU + 密码)
- 客户端: packages/service/src/core/redis_client.py
- 应用 env: packages/service/.env.example (REDIS_*, RL_*, *_CACHE_TTL)
- 监控接入: health check 已就位 (check_redis)

## 已知限制 (handoff 记)

1. **单 Redis 实例, 无 Sentinel/Cluster**: 当前 512mb 够用, 后期 K8s 多 pod 需 Sentinel
2. **AOF 写盘每 1s**: appendfsync everysec 已配, 最多丢 1s 数据
3. **没跨 Redis 实例 sync**: 6 use case 全在单 Redis, 不分库
4. **不主动 evict Dify query on ingest**: 10min TTL 纯过期, ingest 后最多 10min 旧结果
5. **没 quota 限额 (按 user)**: 仅 IP 限流, 业务用户配额本期不做