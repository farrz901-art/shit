# Supabase 教程

> 📅 创建日期：2026-06-29
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python/TS 工程师
> ⚠️ **特殊状态：评估过，未采用。** 项目明确**不接 Supabase**（决策见 [docs/superpowers/specs/2026-06-17-logging-system-design.md §13.5](../superpowers/specs/2026-06-17-logging-system-design.md)）。本文档定位：**调研留档 + 未来触发条件**，不是接入指南。

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

**Supabase** 是开源的 Firebase 替代品，对外提供一整套 BaaS（Backend-as-a-Service）：

- **Postgres 数据库**（自带 pgvector / PostGIS / pg_cron 扩展）
- **Auth**（邮箱、OAuth、Phone、SSO、Passkey）
- **Storage**（S3 兼容对象存储）
- **Realtime**（Postgres CDC → WebSocket）
- **Edge Functions**（Deno 运行时）
- **Studio**（Web 管理面板，原生支持表编辑 + SQL + RLS 配置）

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Supabase** | 托管 PG + Auth + Storage + Realtime 一体化 | 功能全，但跟项目"自建 + 控细节"路线不符 |
| **Firebase (Google)** | NoSQL + Auth + Functions | Firestore 不是真关系型，RAG 的 SQL/JSONB 离不开 PG |
| **AppWrite** | 自部署 BaaS | 生态比 Supabase 小，无 pgvector 等价物 |
| **Neon / Supabase (PG-as-a-Service)** | 纯托管 PG | Supabase 的子集，只用 PG 时 Neon 更便宜 |
| **自建 (Postgres + FastAPI + Redis + MinIO + Neo4j)** | 当前项目架构 | 控每个组件，可换可调，**5 个容器全本地** |

**Supabase 解决的核心问题**：

- **快速启动**：5 分钟一个带 Auth + DB + Storage 的全栈应用
- **RLS 权限**：数据库层强制多租户隔离，不用在应用代码里写权限
- **实时推送**：表行变更直接推到前端，不用自建 WebSocket
- **TypeScript 优先**：`supabase-js` 类型自动生成

**项目为什么不用**（[docs/superpowers/specs/2026-06-17-logging-system-design.md:923](../superpowers/specs/2026-06-17-logging-system-design.md#L923)）：

> **Supabase Studio**: 不接. **项目不用 Supabase**. 跟 Grafana 功能有重叠（都能查 PG），但 Grafana 更通用。

3 条核心理由：

1. **已自建等价组件**：项目有 PG + pgvector（`docker/docker-compose.yml:4-23`）+ Redis + MinIO + Neo4j + FastAPI Auth（[src/middleware/auth.py](../../packages/service/src/middleware/auth.py)），全栈本地自跑，接 Supabase 等于 **删一半自建 + 加 1 个 SaaS 依赖**
2. **RLS 不在路线图**：项目多租户隔离在应用层（`users.id` 强外键 + 业务代码 `current_user.id` 过滤），不上数据库 RLS。Supabase 强项之一用不上
3. **锁定风险**：Supabase 用 GoTrue + Realtime + 自家 fork 的 PG，**不是上游 PG**。迁回自建 PG 时 schema / 函数 / RLS 策略需要重写

---

## 二、安装 & 启动

### 2.1 SaaS（推荐试用）

```bash
# 1. 去 https://supabase.com 注册
# 2. 新建 Project，选 region（建议 Singapore/Tokyo，离中国大陆近）
# 3. 拿 3 个 env（Project Settings → API）：
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # 后端用, 前端不暴露
```

免费档：500 MB 数据库 + 1 GB Storage + 50k MAU。

### 2.2 自部署（Docker）

```bash
# 官方仓库：https://github.com/supabase/supabase
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
# 编辑 .env：POSTGRES_PASSWORD、JWT_SECRET、ANON_KEY、SERVICE_ROLE_KEY
docker compose up -d
# Studio 在 http://localhost:54323
# Postgres 在 localhost:54322
# Kong API Gateway 在 localhost:8000
```

自部署磁盘占用 ~5 GB（含 Studio / GoTrue / Realtime / Storage / PostgREST / Functions 6 个服务）。

### 2.3 健康检查

```bash
# 自部署
docker compose ps                # 看 11+ 个容器全 up
curl -f http://localhost:8000/rest/v1/ -H "apikey: $SUPABASE_ANON_KEY"  # PostgREST
curl -f http://localhost:8000/auth/v1/health                                # GoTrue
curl -f http://localhost:9000/minio/health/live                             # Storage (底层是 MinIO)

# SaaS
curl -f https://xxx.supabase.co/rest/v1/ -H "apikey: $SUPABASE_ANON_KEY"
```

---

## 三、核心概念

1. **Project**：一个 Supabase 项目 = 1 套独立 PG + Auth + Storage + Realtime。生产建议 1 项目 = 1 环境（dev / staging / prod 各自独立 project）。
2. **PostgREST**：自动把 PG 表 / 视图 / 函数转成 REST API（`/rest/v1/<table>`），免写后端 CRUD。
3. **GoTrue**：Auth 服务，签发 JWT（access + refresh），支持 30+ OAuth provider。
4. **Realtime**：监听 PG logical replication slot，把行变更推 WebSocket 客户端。
5. **RLS（Row Level Security）**：PG 的行级安全策略，Supabase 强制启用，是多租户隔离的"数据库层"防线。
6. **Studio**：Web 管理面板，类 pgAdmin + Auth 用户管理 + RLS 可视化 + SQL 编辑器。
7. **Edge Functions**：Deno 运行时写的 TS 函数，部署到 Supabase 边缘节点（不是 Cloudflare Workers，是 Supabase 自家节点）。

---

## 四、常用命令 & 用法速查

> 项目不用 Supabase，命令区只列**自部署运维**和**SDK 调用**两类，方便以后真要接入时复用。

### 4.1 自部署启停

```bash
# 启停
cd supabase/docker
docker compose up -d
docker compose down          # 停服务，保留 volume
docker compose down -v       # ⚠️ 删所有数据, 不可逆

# 升级
docker compose pull && docker compose up -d
# 升级前必须读 https://github.com/supabase/supabase/releases 的 breaking changes

# 进入 PG
docker compose exec db psql -U postgres -d postgres
```

### 4.2 SQL / 数据查询

```sql
-- 列出所有表
\dt

-- 查 RLS 策略
SELECT schemaname, tablename, policyname, cmd, qual
FROM pg_policies WHERE schemaname = 'public';

-- 查当前角色
SELECT current_user, session_user;

-- 切到 service_role（绕过 RLS，慎用）
SET LOCAL ROLE service_role;
```

### 4.3 调试

```bash
# 实时看 DB 日志
docker compose logs -f db

# 实时看 GoTrue (Auth) 日志
docker compose logs -f auth

# 重置 Auth（清所有用户）
docker compose exec auth psql -U postgres -d postgres -c "TRUNCATE auth.users CASCADE;"

# 重新生成 anon / service_role JWT（密钥改了之后）
# https://supabase.com/docs/guides/auth/auth-helpers
```

### 4.4 排错

```bash
# "permission denied for table xxx"
# → 缺 RLS 策略。表上 ENABLE RLS 但没建 policy，所有行都不可见

# "invalid api key"
# → SUPABASE_ANON_KEY 跟 project 不匹配；去 dashboard 重新复制

# 实时订阅收不到消息
# → Realtime 必须在表上开 publication：
#   ALTER PUBLICATION supabase_realtime ADD TABLE public.orders;

# 升级后 Studio 502
# → 跟 PostgREST 时区不一致；设 TZ=Asia/Shanghai 后重启
```

---

## 五、项目集成点

### 5.1 项目当前**不**使用 Supabase

`docker/docker-compose.yml` 全文件（[docker/docker-compose.yml](../../docker/docker-compose.yml)）列出的服务是：postgres + pgvector、redis、minio、neo4j。**没有 `supabase` 服务**。

### 5.2 决策记录

- [docs/superpowers/specs/2026-06-17-logging-system-design.md:920-923](../superpowers/specs/2026-06-17-logging-system-design.md#L920) — "Supabase Studio: 不接. 项目不用 Supabase."
- [docs/superpowers/specs/2026-06-17-logging-system-design.md:996](../superpowers/specs/2026-06-17-logging-system-design.md#L996) — "✅ 不接 Grafana / Loki / Supabase (本期不接, §13.5 写明)"

### 5.3 如果将来接入，env 配置（**未启用**，留个格式参考）

```bash
# packages/service/.env (未来可能新增, 当前不写)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # 后端专用, 不下到前端
SUPABASE_JWT_SECRET=super-secret-jwt-secret
```

后端入口用 `supabase-py`（[supabase/supabase-py](https://github.com/supabase/supabase-py)）：

```python
from supabase import create_client, Client

client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
resp = client.table("orders").select("*").eq("user_id", user_id).execute()
```

前端入口用 `supabase-js`（[supabase/supabase-js](https://github.com/supabase/supabase-js)）：

```typescript
import { createClient } from "@supabase/supabase-js";
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);
```

### 5.4 触发再评估的 3 个条件

1. **新项目起 MVP**：5 分钟要一个 Auth + DB + Storage 全栈 demo，2 周内不上 production
2. **多人协作 + RLS 需求**：3+ 个非技术协作者需要直接看 DB 数据，自己用 Studio 比装 pgAdmin 顺
3. **真要换 SaaS 减运维**：PG + Redis + MinIO + Neo4j 自维护成本 > Supabase Pro $25/月

3 个条件都满足时，**先开新 Project 试用 1 个月，验证 schema / 迁移工具 / RLS 跟现有业务兼容**，再决定切换。

---

## 六、项目代码示例

> 项目代码里**没有任何 Supabase 调用**（[Grep supabase 命中 0](../../) 业务代码）。下面是**通用 SDK 模式**作为参考，不是项目源码。

### 6.1 后端：supabase-py CRUD

```python
# 通用模式（不是项目代码）
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# 查
resp = supabase.table("orders").select("id, total, status").eq("user_id", uid).execute()
orders = resp.data

# 插
resp = supabase.table("orders").insert({"user_id": uid, "total": 99.0}).execute()
new_id = resp.data[0]["id"]

# 改
supabase.table("orders").update({"status": "paid"}).eq("id", new_id).execute()

# 删
supabase.table("orders").delete().eq("id", new_id).execute()
```

### 6.2 后端：Auth 集成

```python
# 通用模式
# 1. 客户端发 access_token (GoTrue JWT) 到后端
# 2. 后端用 SUPABASE_JWT_SECRET 解码
import jwt

def verify_supabase_jwt(token: str) -> dict:
    payload = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
    )
    return {"user_id": payload["sub"], "email": payload["email"]}
```

### 6.3 前端：supabase-js + RLS

```typescript
// 通用模式
const { data, error } = await supabase
  .from("orders")
  .select("*")
  .eq("status", "pending")
  .order("created_at", { ascending: false })
  .limit(10);

// Realtime 订阅
const channel = supabase
  .channel("orders-changes")
  .on("postgres_changes",
    { event: "INSERT", schema: "public", table: "orders" },
    (payload) => console.log("新订单:", payload.new),
  )
  .subscribe();
```

### 6.4 RLS 策略示例

```sql
-- 多租户隔离（Supabase 标配）
CREATE POLICY "用户只看自己订单" ON orders
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "用户只能改自己订单" ON orders
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- 管理员可看全部
CREATE POLICY "admin 看全部" ON orders
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
```

### 6.5 项目自建方案对照

| 场景 | Supabase | 项目自建 |
|------|----------|----------|
| Auth 登录 | GoTrue + JWT | FastAPI + [src/middleware/auth.py:87-159](../../packages/service/src/middleware/auth.py) (opaque token + Redis) |
| DB 迁移 | `supabase db push` (内嵌 migration 文件) | [Alembic](../../packages/service/alembic/) |
| 文件存储 | Supabase Storage (S3 兼容) | [MinIO](../../docker/docker-compose.yml) + S3 SDK |
| 实时推送 | Realtime (WebSocket) | 当前不用，未来可上 SSE |
| 多租户隔离 | RLS 策略 | 应用层 `current_user.id` 过滤（[feedback-multi-tenant-isolation-required](../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-multi-tenant-isolation-required.md)） |

---

## 七、项目没用到的能力

以下 Supabase 能力**项目当前未使用，且暂无启用计划**（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **PostgREST 自动 REST API** | 免写后端 CRUD | 项目用 FastAPI 自定义路由，需要复杂业务逻辑时 PostgREST 不够灵活 |
| **GoTrue Auth** | 邮箱/OAuth/SSO 一体化 | 自建 [src/middleware/auth.py](../../packages/service/src/middleware/auth.py) 满足当前需求 |
| **Realtime (CDC → WebSocket)** | 表行变更推送 | 业务无强实时需求，后期 SSE/长轮询就够 |
| **RLS（数据库层多租户）** | 强制行级隔离 | 项目在应用层隔离，RLS 增加调试复杂度 |
| **Edge Functions (Deno)** | 边缘函数 | 项目无 serverless 需求，单 FastAPI 跑全栈 |
| **Storage** | 对象存储 | MinIO 已覆盖，自建可控 |
| **pgvector in Supabase** | 托管 PG 自带向量扩展 | 项目用自建 PG + pgvector，扩展版本可锁 |
| **Studio (Web UI)** | pgAdmin 替代 | psql + 自写 [docs/superpowers/specs/2026-06-17-logging-system-design.md §12 运维 SQL](../superpowers/specs/2026-06-17-logging-system-design.md) 够用 |
| **Supabase Branching** | DB 跟 Git branch 联动 | 单环境够用，CI/CD 走 Alembic |
| **Logflare / 日志** | SaaS 日志聚合 | 项目用 loguru + [Grafana 预留 hook](../superpowers/specs/2026-06-17-logging-system-design.md#L863) |

**建议关注**：

- **Realtime** — 业务做 chat / 协作时是个加速器，免自建 WebSocket
- **Supabase Branching** — 团队扩大、previews 环境需要 1:1 DB 时再考虑

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单（**仅自部署 Supabase 适用**）

1. **备份**：每日 `pg_dump`（Supabase 自带 PITR 7 天），定期 dump 到 MinIO
2. **监控**：Studio 内置仪表盘 + 自接 Grafana（用 [supabase-admin-api](https://supabase.com/docs/reference/api) 拉 metrics）
3. **升级**：先在 staging 跑 `docker compose pull && up -d`，看 release notes 的 breaking changes，重点关注 GoTrue / PostgREST / Realtime 的 schema 变更
4. **资源**：Studio 用 1 GB RAM，PostgREST + GoTrue + Realtime 各 256 MB，自部署至少 4 GB RAM
5. **磁盘**：WAL 跟 `db/data` 是大头，至少留 30% 空闲；logical replication slot 不消费会撑爆

### 常见坑

1. **RLS 没建 policy = 全部拒绝访问**：表 `ENABLE RLS` 后**默认拒绝所有**（包括 service_role 之外的 anon）。新表加完要立刻建 SELECT / INSERT / UPDATE / DELETE 4 个 policy
2. **service_role JWT 落到前端 = 数据库裸奔**：service_role 绕过 RLS，前端**只能用 anon key**。CI/服务端用 service_role，浏览器只暴露 anon
3. **Realtime 必须开 publication**：默认只监听 `supabase_realtime` publication 里的表，新表 `ALTER PUBLICATION supabase_realtime ADD TABLE xxx;` 才能订阅
4. **Realtime + 高频写入会撑爆**：每秒 >100 行变更时，logical replication slot 跟不上，需要调 `wal_sender_timeout` + 客户端节流
5. **升级后 migration 文件夹结构变了**：Supabase 1.x 跟 2.x migration 目录从 `supabase/migrations/` 变 `supabase/db/migrations/`，升大版本必须读 migration guide
6. **JWT secret 改了 = 所有用户被踢下线**：改 `JWT_SECRET` 后所有 token 失效。生产改前要先灰度
7. **SaaS 项目的 region 一旦选了就改不了**：dev 跟 prod 必须用同 region，跨 region 延迟 100+ ms
8. **逻辑复制 slot 累积 WAL**：如果 Realtime 客户端断连不重连，slot 不消费 → WAL 涨 → 磁盘满。加 `max_slot_wal_keep_size` 兜底

### 真要切换时的迁移步骤（**未来路线图**）

1. **数据迁移**：`pg_dump` 自建 PG → `psql` 灌入 Supabase PG（schema 必须 100% 兼容，注意 Supabase 用 `postgres` 库不是 `rag`）
2. **Auth 迁移**：用户密码 hash 格式可能不兼容，需要"重置密码"邮件流；OAuth 联邦用户走 Supabase Auth 后台手工绑定
3. **代码改造**：`session_scope` (SQLAlchemy) → `supabase-py` 调用；所有 RLS 缺失的查询要补 policy
4. **Storage 迁移**：MinIO 对象 → Supabase Storage（`supabase-storage-api` 有迁移脚本）
5. **运维切流量**：先 10% 流量灰度，验证延迟 / 错误率，再全量
6. **回滚预案**：保留原 PG 7 天，期间出任何问题立即切回

**预估工时**：2-3 周（含测试）。**只有触发"5.4"列的 3 个条件时再启动**。

---

## 📚 参考

- [Supabase 官方文档](https://supabase.com/docs)
- [supabase-js SDK](https://github.com/supabase/supabase-js)
- [supabase-py SDK](https://github.com/supabase/supabase-py)
- [Supabase 自部署 Docker](https://github.com/supabase/supabase/tree/master/docker)
- [RLS 性能调优](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Realtime 架构](https://supabase.com/docs/guides/realtime/architecture)
- 项目决策记录：[docs/superpowers/specs/2026-06-17-logging-system-design.md §13.5](../superpowers/specs/2026-06-17-logging-system-design.md#L920)

---

**状态：** ✅ 已完成（**调研留档**，非接入指南）

**最后更新：** 2026-06-29
