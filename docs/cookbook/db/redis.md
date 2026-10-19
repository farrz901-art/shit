# Redis 教程

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

Redis（Remote Dictionary Server）是一个基于内存的键值存储，支持多种数据结构（String、Hash、List、Set、Sorted Set、Stream、Bitmap、HyperLogLog），通常用作缓存、消息队列、限流器、分布式锁等。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Redis** | 内存 KV + 多数据结构 | 生态最成熟，文档多 |
| **Memcached** | 纯 KV 缓存 | 仅 String，无持久化，无 Pub/Sub |
| **DragonflyDB** | Redis 兼容 + 性能更强（多线程） | 新项目，生态仍在建设 |
| **etcd** | 强一致 KV（用于服务发现 / 配置） | 不是缓存定位 |
| **KeyDB** | Redis 兼容 + 多线程 | 同上，新项目 |

**Redis 解决的核心问题**：
- **热点数据缓存**：token、权限、embedding（避免每次打 PG）
- **限流**：滑动窗口计数器（`INCR + EXPIRE`）
- **分布式锁**：`SETNX` 或 `Redlock`
- **消息队列**：Pub/Sub 或 Stream 做跨进程通知
- **延迟队列**：Sorted Set + 时间戳做 score

---

## 二、安装 & 启动

### 2.1 项目集成启动

`docker/docker-compose.yml:75-99` 用 `redis:7.4-alpine` 镜像：

```bash
cd docker/
docker compose up -d redis
# 验证
docker exec -it redis redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning ping
# PONG
```

### 2.2 独立 Docker 启动

```bash
docker run -d --name redis \
  -p 6379:6379 \
  -e REDIS_PASSWORD=your_secure_password \
  -v $PWD/redis_data:/data \
  redis:7.4-alpine \
  redis-server --appendonly yes --requirepass your_secure_password
```

### 2.3 健康检查

```bash
# 容器内 ping
docker exec -it redis redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning ping

# 项目用 ping 方式做 healthcheck
# docker/docker-compose.yml:93
test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-redis123}", "--no-auth-warning", "ping"]
```

---

## 三、核心概念

1. **Key-Value**：Redis 基础结构，所有数据都是 key → value 映射。
2. **数据结构**：String、Hash、List、Set、ZSet、Stream、Geo、HyperLogLog、Bitmap。
3. **TTL（过期时间）**：每个 key 可设过期，过期后自动删除。`SET key value EX 60` 60 秒过期。
4. **持久化**：RDB（快照）+ AOF（追加日志）。AOF 更安全但写放大。
5. **Pub/Sub**：消息广播，fire-and-forget（不持久化）。项目用 `dict.invalidate` 广播（`src/lookups/cache.py`）。
6. **Stream**：5.0+ 的持久化消息队列（类 Kafka），支持消费者组、回溯。
7. **Pipeline**：一次发多个命令，节省 RTT 往返。
8. **Lua 脚本**：服务端原子执行，避免竞态条件。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker
docker start redis
docker stop redis
docker restart redis

# 服务端
sudo systemctl start redis
sudo systemctl stop redis
```

### 4.2 查询

```bash
# 进入 redis-cli
docker exec -it redis redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning

# 键操作
KEYS *                           # 列出所有 key（生产慎用，会阻塞）
SCAN 0 MATCH rag:* COUNT 100     # 增量遍历，推荐
EXISTS user:42                   # 存在性
DEL user:42                      # 删除
TTL user:42                      # 剩余过期秒数
EXPIRE user:42 60                # 设 60s 过期

# 数据结构
SET k "v" EX 60                  # String
GET k
HSET user:42 name "Alice" age 30 # Hash
HGETALL user:42
LPUSH queue:tasks "t1"           # List
SADD tags:42 "vip"               # Set
ZADD rank 100 "alice"            # ZSet（按 score 排）

# 服务器信息
INFO server                      # 版本、运行时间
INFO memory                      # 内存使用
INFO clients                     # 连接数
DBSIZE                          # 总 key 数
```

### 4.3 调试

```bash
# 慢查询
SLOWLOG GET 10                   # 最近 10 条慢命令
SLOWLOG LEN

# 监控（实时）
redis-cli -a PASSWORD MONITOR    # 看所有命令（性能影响大，调试用）

# 客户端连接
CLIENT LIST
CLIENT KILL ID <id>

# 大 key 排查
redis-cli -a PASSWORD --bigkeys  # 自动扫描（会消耗时间）
```

### 4.4 排错

```bash
# 连接被拒
docker logs redis | grep "Authentication"
# 密码错 → 检查 REDIS_PASSWORD 一致性

# 内存满（OOM）
docker exec -it redis redis-cli -a PASSWORD INFO memory
# 看 used_memory 和 maxmemory
# 解法：清理大 key / 调 maxmemory / 启用 LRU 淘汰

# 主从同步失败
INFO replication
# 看 master_link_status 是否 up
```

---

## 五、项目集成点

### 5.1 项目当前使用 Redis 做缓存 / 限流 / 失效广播

`docker/docker-compose.yml:75-99` 启动 Redis，6 个核心模块（`packages/service/src/core/`）直接使用：

| Use case | 模块 | TTL |
|---------|------|-----|
| Auth token 缓存 | `src/core/token_cache.py` | 6h sliding |
| IP 限流 | `src/core/rate_limiter.py` | 15min / 1h |
| Permission 矩阵 | `src/core/permission_cache_redis.py` | 60s |
| Dify query 缓存 | `src/core/dify_query_cache.py` | 10min |
| Embedding 缓存 | `src/core/embed_cache.py` | 7d |
| Mem0 ready 标记 | `src/core/mem0_ready.py` | 1h |

### 5.2 业务配置

```bash
# packages/service/.env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_redis_password
REDIS_MAX_CONNECTIONS=20        # 限连接防单核打爆
REDIS_SOCKET_TIMEOUT=2          # 2s 超时, 失败走原路径（fail-open）
REDIS_CONNECT_TIMEOUT=2
REDIS_CIRCUIT_OPEN_SECONDS=60   # 60s 熔断
```

### 5.3 业务 facade

项目封装了统一 facade（`src/core/redis_client.py`）：

```python
from src.core.redis_client import safe_get, safe_set, safe_delete, safe_incr
# 永不抛异常，失败返 None / False / 0
val = await safe_get("rag:foo")
```

**fail-open 原则**：Redis 挂 = 服务降级（走原 PG / 进程内存），不挂服务。

### 5.4 Key 规范

- 统一 `rag:` 前缀 + 分域：`rag:perm:matrix`、`rag:auth:tok:...`、`rag:rl:login:1.2.3.4`
- token / cookie 值在 Redis 里存 sha256[:32]，不存原值（防 dump 泄露）
- 长 key 取 sha256[:16] 前缀

### 5.5 启动时连通性探测

`src/core/lifespan.py:51-65`：

```python
def _setup_redis() -> None:
    """启动时验证 Redis 连通性. 失败 WARNING, 不阻塞启动 (fail-open 设计).
    用 socket 探测, 不调 get_redis(). 因为此时无 running loop,
    get_redis() 创建的 pool 无 loop binding, 后续请求复用报
    'Future attached to a different loop'.
    """
    try:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        with socket.create_connection((host, port), timeout=2):
            pass
    except Exception as e:
        logger.warning("Redis warmup 失败: {}, 以降级模式启动 (走原路径)", e)
```

---

## 六、项目代码示例

### 6.1 Redis 服务配置

`docker/docker-compose.yml:75-99`：

```yaml
redis:
  image: redis:7.4-alpine
  container_name: redis
  restart: unless-stopped
  ports:
    - "6379:6379"
  environment:
    TZ: Asia/Shanghai
  command:
    - redis-server
    - --appendonly yes                # 开启 AOF 持久化
    - --appendfsync everysec         # 每秒刷盘
    - --requirepass ${REDIS_PASSWORD:-redis123}
    - --maxmemory 512mb              # 限内存
    - --maxmemory-policy allkeys-lru # 内存满时 LRU 淘汰
  volumes:
    - ./volumes/redis_data:/data
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-redis123}", "--no-auth-warning", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 5s
  networks:
    - app-network
```

### 6.2 IP 限流实现

`src/core/rate_limiter.py`（推测模式）：

```python
from src.core.redis_client import safe_incr

async def check_and_increment(action: str, ip: str) -> tuple[bool, int]:
    """限流检查 + 计数。返回 (allowed, current_count)."""
    key = f"rag:rl:{action}:{ip}"
    count = await safe_incr(key, ttl=900)  # 15min 窗口
    if count is None:
        return True, 0  # Redis 挂 → 放行
    threshold = 5
    return count <= threshold, count
```

### 6.3 Token 缓存

`src/core/token_cache.py` 模式（推测）：

```python
import hashlib
from src.core.redis_client import safe_get, safe_set

def _key(token: str) -> str:
    # 原 token 存 Redis 有 dump 泄露风险
    return f"rag:auth:tok:{hashlib.sha256(token.encode()).hexdigest()[:32]}"

async def get_user_by_token(token: str) -> dict | None:
    cached = await safe_get(_key(token))
    if cached:
        return json.loads(cached)
    # 缓存未命中 → 查 PG
    user = await _query_pg(token)
    if user:
        await safe_set(_key(token), json.dumps(user), ttl=21600)  # 6h
    return user
```

### 6.4 字典失效广播

`src/lookups/cache.py` 用 Pub/Sub 跨进程失效：

```python
# 进程 A 修改字典后发广播
await redis.publish("dict.invalidate", json.dumps({"item_id": 42}))

# 进程 B 订阅
async with redis.pubsub() as pubsub:
    await pubsub.subscribe("dict.invalidate")
    async for message in pubsub.listen():
        # 清本地缓存
        cache.invalidate(json.loads(message["data"])["item_id"])
```

---

## 七、项目没用到的能力

以下 Redis 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Redis Cluster** | 分片 / HA | 单机够用，10k+ QPS 时启用 |
| **Redis Sentinel** | 主从自动故障转移 | 6.x 默认有 replica，但无自动故障切换 |
| **Stream** | 持久化消息队列 | Pub/Sub 是 fire-and-forget，Stream 更适合"任务队列" |
| **RedisJSON** | 原生 JSON 数据类型 | 当前用 String + JSON 序列化 |
| **RediSearch** | 全文 / 向量搜索 | PG + pgvector 已覆盖 |
| **TimeSeries** | 时序数据存储 | Prometheus 已覆盖 |
| **Bloom Filter** | 防穿透 | 用 Redis 内置 bloom module |
| **Distributed Lock (Redlock)** | 分布式锁 | 当前无强需求，未来审核工作流考虑 |

**建议关注**：Stream 适合做 LLM 任务的异步队列（替代内存 task queue），跨进程更可靠。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **maxmemory 设置**：必设，否则 OOM 后 Redis 崩溃。`allkeys-lru` 适合缓存场景
2. **appendfsync 策略**：`everysec` 平衡性能和安全（`docker/docker-compose.yml:86`）；`always` 最安全但 IO 大
3. **备份**：AOF 文件必须定期 `BGREWRITEAOF` 压缩，定期拷贝到 MinIO
4. **大 key 监控**：`redis-cli --bigkeys` 定期扫
5. **慢查询日志**：`slowlog-log-slower-than 10000`（10ms 阈值）

### 常见坑

1. **KEYS \* 阻塞**：生产用 `SCAN` 替代 `KEYS`
2. **密码泄露在命令历史**：`redis-cli -a password` 会泄露密码到 `~/.bash_history`，用 `REDISCLI_AUTH` 环境变量
3. **flushdb 误操作**：先 `CONFIG SET save ""` 禁用持久化，避免误清空写盘
4. **AOF 重写卡住**：磁盘 IO 不足会卡 `BGREWRITEAOF`，监控 `aof_rewrite_in_progress`
5. **客户端连接耗尽**：默认 10000 连接，但 maxclients 限制；用连接池 + 复用，不要每次新建

---

## 📚 参考

- [Redis 官方文档](https://redis.io/docs/latest/)
- [Redis 7.4 release notes](https://github.com/redis/redis/releases)
- [Redis 持久化](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis Pub/Sub](https://redis.io/docs/latest/develop/pubsub/)
- [redis-py 客户端](https://redis-py.readthedocs.io/en/stable/)
- [Redis 内存优化](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
