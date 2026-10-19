# RAG 项目


## 快速上手 (TLDR)

```bash
# 1. 启本地依赖 (PG + Neo4j + pgAdmin)
cd docker && docker compose up -d && cd ..
#    等 30s, docker compose ps 看到 postgres/neo4j 都是 Up (healthy) 再继续

# 2. 装 Python 依赖 + 跑 migration 建表
cd packages/service
uv sync
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run alembic upgrade head

# 3. (可选) 创首个 admin
uv run python scripts/seed_admin.py

# 4. 启后端 (新终端)
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run python main.py
#    → http://localhost:8000/docs#/ (接口文档)
```

## 启动前端 (管理后台)

```bash
cd ./packages/web
bun install && bun run dev
# → http://localhost:3000
```

- 后端 FastAPI: 端口 8000
- 前端 Next.js: 端口 3000
- CORS 已配 (`http://localhost:3000`), 无需额外配置
- 前端 5 个主模块: `/` 仪表盘 · `/decode` 解码 · `/output` 文件列表 · `/output/<file>` 详情 · `/knowledge` 知识库 + 知识图谱管理 (含 4 Tab)
- 前端工具链: `tsc` · `oxlint` · `oxfmt` · `vitest` · `playwright` · `husky`
- 详见 [packages/web/CLAUDE.md](packages/web/CLAUDE.md)

## 环境要求

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- ODA File Converter（仅 DWG 转 DXF 需要，[下载](https://www.opendesign.com/guestfiles/oda_file_converter)）
- GPU + Docker（仅 mineru 复杂 PDF 解析需要）

### Docker 镜像加速 (中国大陆)

`~/.docker/daemon.json` 加 (绕开 docker hub 慢):

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

## 启动命令

> 在 `packages/service/` 目录下执行。

| 命令 | 行为 |
|---|---|
| `uv run python main.py` | 默认启动产品订货号解析服务（端口 8000） |
| `uv run python main.py serve` | 同上，显式指定 |
| `uv run python main.py serve --port 9000` | 改端口 |
| `uv run python main.py serve --reload` | 开发热重载 |
| `uv run uvicorn main:app --reload` | 同上（开发时少一层 wrapper） |
| `uv run python main.py ingest` | 跑 RAG 离线流水线（走 `config.toml` `[paths].input_dir`） |
| `uv run python main.py ingest ./pdfs/` | 显式目录 |
| `uv run python main.py ingest ./abc.pdf` | 单文件 |
| `uv run python main.py ingest ./bundle.zip` | zip 自动解压 |

调用测试：

```bash
curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d '{"model": "1LE0001-1AA42-1AA4"}'
```

## 环境变量

| 变量 | 用途 |
|---|---|
| `RAG_DB_URL` | PostgreSQL 连接 URL（详见"数据库"章节） |
| `RAG_ADMIN_TOKEN` | Bootstrap admin token（创首个 admin 用） |
| `RAG_SEED_ADMIN_EMAIL` / `RAG_SEED_ADMIN_PASSWORD` | 创首个 admin 用的 bootstrap env |
| `ODA_WIN_PATH` | ODA File Converter Windows 路径（DWG 转换需要） |
| `ODA_UNIX_PATH` | ODA File Converter Linux 路径 |
| `PRODUCT_DECODERS_CONFIGS` | 覆盖默认产品配置目录（部署数据） |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | docker compose 用的 PG 超级用户 + 默认库 |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` | docker compose 用的 pgAdmin Web UI 登录 |
| `NEO4J_AUTH` | docker compose 用的 Neo4j 初始用户（格式 `neo4j/<password>`） |

## Docker 服务 (本地依赖)

PG / Neo4j / pgAdmin 走 `docker/docker-compose.yml`，3 个服务共享 `app-network` 网络。配置在 `docker/.env`（已 gitignore，从 `.env.example` 复制）。

| 服务 | 镜像 | 端口 | 用途 |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg18` | `5432` | 业务数据库 + 向量检索 |
| `pgadmin` | `dpage/pgadmin4:latest` | `5050` | PG Web 图形界面 (http://localhost:5050) |
| `neo4j` | `neo4j:2026.05.0` | `7474` / `7687` | 知识图谱 Browser / Bolt 协议 |

```bash
# 首次启动: 复制 .env.example, 改密码
cp docker/.env.example docker/.env
# 编辑 docker/.env 改 POSTGRES_PASSWORD / PGADMIN_PASSWORD / NEO4J_AUTH

# 启服务 (后台)
cd docker && docker compose up -d

# 看健康状态
docker compose ps
# postgres: Up (healthy)  ← 等健康检查过了再连
# neo4j: Up (healthy)      ← 首次启要 30s 加载 plugin

# 看日志
docker compose logs -f postgres
docker compose logs -f neo4j

# 停服务
docker compose down
# 删数据 (慎用): docker compose down -v
```

**端口冲突排查**: 本地已有 PG/Neo4j/pgAdmin 占同端口 → docker compose 会启动失败。改 `docker-compose.yml` 里的 `ports` 映射（左侧是宿主机，右侧是容器内）。

## 数据库 (PostgreSQL + pgvector + SQLAlchemy 2.0 + Alembic)

PG 跟 pgvector 共用一个 docker 容器 (`pgvector/pgvector:pg18`, 端口 5432, 数据库 `rag`).
SQLite 已完全删除, 业务代码统一走 ORM 走 PG.

### 数据库 URL

```bash
# 默认 (省略 env 时)
RAG_DB_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag

# 切 PostgreSQL
RAG_DB_URL=postgresql+psycopg://user:pwd@host:5432/rag
```

### 建表 (Alembic migrations)

**所有表的 DDL 在 migration 文件里**, 不在 `scripts/` 脚本里 (Alembic 是行业标准, 跟 ORM model 1:1, autogenerate 能 diff). 一行命令建表:

```bash
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run alembic upgrade head
```

拉新代码 / 重置 DB 后必跑, 否则 PG 缺表 → 后端 500.

#### 当前 migrations 清单

所有文件: [packages/service/src/storage/migrations/versions/](packages/service/src/storage/migrations/versions/)

| Revision                 | 文件                                                                                                                                          | 建/改的表                                                                                                                                | 来源                                                                                                                                                              |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `20260615_000000` (head) | [20260615_000000_consolidated_pg_init.py](packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py)             | 11 张业务表: `accounts` / `users` / `invites` / `password_resets` / `conversations` / `messages` / `evaluations` / `evaluation_samples` / `approvals` / `ingest_tasks` / `kg_audit` | 一次性 consolidated init (2026-06-15, 替原 4 个旧 SQLite migration)                                                                                                |

#### 表与 ORM 模块的映射

| 表                                         | ORM 模块                                                                  |
| ------------------------------------------ | ------------------------------------------------------------------------- |
| `users`                                    | [src/auth/models.py](packages/service/src/auth/models.py) (`User`)        |
| `accounts` / `invites` / `password_resets` | [src/auth/account_models.py](packages/service/src/auth/account_models.py) |
| `conversations` / `messages`               | [src/chat/models.py](packages/service/src/chat/models.py)                 |
| `evaluations` / `evaluation_samples`       | [src/eval/models.py](packages/service/src/eval/models.py)                 |
| `approvals`                                | [src/approvals/models.py](packages/service/src/approvals/models.py)       |

#### 操作方法

> 在 `packages/service/` 目录下执行 (`alembic.ini` 位置)。

```bash
# 跑 migration (建表)
uv run --no-sync alembic upgrade head

# 看当前版本
uv run --no-sync alembic current

# 回滚一步
uv run --no-sync alembic downgrade -1

# 加 model 后自动生成 migration
uv run --no-sync alembic revision --autogenerate -m "<feature>"
```

**生产部署必须走 Alembic**, 别用 `init_db()` 自动建表 (`init_db()` 是 dev/test 用的, 受 `RAG_AUTO_CREATE_SCHEMA=1` 开关)。

#### 加新 model 流程

1. 在 `src/<feature>/models.py` 写新 model, `from ..storage import Base` 继承
2. 跑 `uv run --no-sync alembic revision --autogenerate -m "add xxx"` 查 diff
3. **如果 autogenerate 出来空 migration**: 去 [src/storage/migrations/env.py](packages/service/src/storage/migrations/env.py) 加 `from src.<feature>.models import ...  # noqa: F401` 强制注册 (SQLAlchemy registry 不自动收集, import 时才注册)
4. 人工 review migration 文件
5. 跑 `uv run --no-sync alembic upgrade head` 验证
6. 写测试 (`tests/<feature>/test_models.py`)

#### 公开 API

```python
from src.storage import Base, get_engine, init_db, get_session, session_scope
```

- `Base`: DeclarativeBase, 业务 model 继承
- `get_engine()`: 惰性单例 Engine
- `init_db()`: 跑 `create_all`, **仅 dev/test**, 受 `RAG_AUTO_CREATE_SCHEMA=1` 开关
- `session_scope()`: 事务 context manager (commit on success / rollback on exception)
- `get_session()`: generator 给 FastAPI Depends 用

#### Admin 虚拟 User

调试用 admin token 走 `CurrentUser` Pydantic 模型 (在 [src/middleware/auth.py](packages/service/src/middleware/auth.py) 里), 不入 `users` 表. 业务代码用 `current.is_admin` 决定是否过滤 `WHERE user_id=current.id`.

## 账号系统

RAG 项目支持两种身份:

- **游客** (anon): 首次访问自动生成 32 字节 hex token 存 cookie. 无密码.
- **账号** (email + password): admin 邀请后注册, 可登录获得 session.
- **Bootstrap admin**: `RAG_ADMIN_TOKEN` env 配的虚拟 admin, 仅首次部署用.

### 开发模式

- `RAG_DEV_AUTH=1` + 无 token → 默认 dev user (id=1, is_admin), anon 跟账号都不影响.
- 适合本地快速开发, 不需先注册账号.

### Admin 操作 (UI)

- 登录后, 顶部右上角下拉 → "用户管理" / "画像字段配置" / "字典管理" / "权限管理"
- 创 invite: 输 email + 选 is_admin → 弹"复制 invite URL" → 手工发给用户
- 禁用 / 启用 / 提权 / 取消权限: 行内按钮
- 重设密码: 行内按钮 → 弹"复制临时密码" → 手工发给用户
- 画像字段配置: DataTable 展示所有字段配置, 支持新增 / 编辑 / 软删
- 字典管理: 运行时修改字典项, 无需发版

## 权限系统 (v2 RBAC)

4 身份 + 3 预设角色 + N 自定义角色:

- **游客 (anon)**: 只能 chat, 无记忆 (`/api/memory/*` 返 403, 头部 Brain 按钮隐藏)
- **用户 (user)**: chat + decode
- **管理员 (admin)**: chat + output + knowledge + evaluate + submissions + decode + health
- **超级管理员 (super_admin)**: 全部 + 权限管理 (`/admin/permissions`)

### 自定义角色

Super-admin 在 `/admin/permissions` 创任意角色 (例: 运营, 客服), 跟 7 页面权限点任意勾选。
矩阵修改后通过 `PermissionCache` (30s TTL) 推送给所有用户。

### Anon 记忆

Anon 不支持记忆, 记忆端点 (`/api/memory/*`) 返 403, 前端 UI 隐藏。

### 现有 admin 账号迁移

旧 `is_admin=true` 账号已自动迁为 `super_admin`。

## 加新页面（端到端流程）

**0 CLI 步骤** — 改 yaml + 重启服务, 字典 / 权限 / 导航栏全部自动同步。

### 1. 改字典配置

在 [`packages/service/configs/dictionaries_seed.yaml`](packages/service/configs/dictionaries_seed.yaml) 的 `page_key` 字典下加 item（每个字段含 `path` 控制是否出现在导航栏）：

```yaml
- key: my_new_page, label_zh: 我的新页面, label_en: My New Page, sort: 10,
  metadata_json: { path: "/my-new-page" }
```

### 2. 写 page（前端 / 后端 / 路由）

按正常开发流程加：
- **后端路由**: `src/<feature>/router.py` → `app.include_router()` 已在 `register_routers()` 自动注册
- **前端页面**: `packages/web/app/[locale]/my-new-page/page.tsx`（参照 [packages/web/CLAUDE.md](packages/web/CLAUDE.md)）
- **后端前端契约**: 后端加路由后, 跑 `uv run pytest tests/test_api_contract.py` 验前端期望列表有覆盖

### 3. 重启服务

```bash
cd packages/service
uv run python main.py
```

启动 lifespan 自动跑：
1. `seed_dictionaries.run_seed()` — 读 yaml 同步新字典项
2. 检测到新 `page_key` → **自动给 `user` (False) / `admin` (True) 角色插 `role_permissions` 行**（无需 migration）
3. `warmup_page_keys_sync()` — 预热 page_keys 缓存
4. 前端 `GET /api/permissions/me` 拿到新 page → 导航栏自动出现

### 验证

```bash
# 字典已 seed
uv run python -m scripts.seed_dictionaries
# Expected: "已 seed: 0 个新字典 + 0 个新 item" (新 page_key 已自动补齐 role_permissions)

# 权限已生效 (admin 角色可见)
curl -H "x-admin-token: $RAG_ADMIN_TOKEN" http://localhost:8000/api/permissions/me | jq '.allowed'
```

### 路由可见性调整

`page_key` 字段 `metadata_json.path` 控制是否出现在头部导航栏。admin-only 页面也可单独配 user 不可见（已自动处理：`user=False, admin=True`）。

要临时禁用某个页面？改 `metadata_json.is_active`（业务代码读取）或删 yaml item（下次启动消失）。

## 文档索引

| 文档                                                                                                                                 | 内容                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| [docs/architecture.md](docs/architecture.md)                                                                                         | 项目结构、模块职责、配置文件位置                                                                             |
| [docs/knowledge-graph.md](docs/knowledge-graph.md)                                                                                   | 知识图谱模块 (`src/rag/kg/`) 说明: schema/client/tasks/router 端点                                           |
| [docs/knowledge-management-page.md](docs/knowledge-management-page.md)                                                               | 知识库管理页 (`/knowledge`) 使用说明: 5 页面 + BFF 架构 + 端到端流程                                         |
| [docs/approval-system.md](docs/approval-system.md)                                                                                   | 审核系统使用文档: 提交者看进度 + admin 审批/拒绝/重试                                                        |
| [docs/web-e2e.md](docs/web-e2e.md)                                                                                                   | 前端 E2E (Playwright): 5 页面冒烟 + 解码 + knowledge 4 Tab; 18 用例, 含 Tailwind 修复 + QA 渲染空 items 修复 |
| [docs/product-decoder.md](docs/product-decoder.md)                                                                                   | 产品订货号解析服务使用说明、API、Dify 接入                                                                   |
| [docs/ingest.md](docs/ingest.md)                                                                                                     | Ingest REST 端点 + MinIO 接入说明 (presign / finalize / bucket 布局 / CORS / 故障排查)                       |
| [docs/ingestion.md](docs/ingestion.md)                                                                                               | RAG 流水线用法、转换器选择、ODA 配置、archive 配置                                                           |
| [docs/dev-conventions.md](docs/dev-conventions.md)                                                                                   | 测试、编码规范、shim 禁令                                                                                    |
| [docs/mineru-output-for-rag.md](docs/mineru-output-for-rag.md)                                                                       | mineru 转换产物的逐项说明，哪些文件该进 RAG、哪些是诊断用的中间产物                                          |
| [docs/cad-converter.md](docs/cad-converter.md)                                                                                       | CAD 转 markdown 使用文档：装依赖、跑命令、已知限制、调试技巧                                                 |
| [docs/cad-ezdxf-best-practices.md](docs/cad-ezdxf-best-practices.md)                                                                 | ezdxf 1.4.4 调研沉淀：DWG 版本矩阵、不支持实体、踩坑记录                                                     |
| [docs/superpowers/specs/2026-06-02-multi-format-routing-design.md](docs/superpowers/specs/2026-06-02-multi-format-routing-design.md) | 多格式路由架构设计 spec：4 桶分流、Converter 扩展名声明、Markdown 直通、递归扫描                             |
| [docs/superpowers/handoffs/2026-06-16-rag-minio-integration.md](docs/superpowers/handoffs/2026-06-16-rag-minio-integration.md)       | RAG MinIO 集成交接文档 (2026-06-16): 16 commits + 5 phase + 接手 checklist                                   |

## MinIO 启动

```bash
# 1. 启 MinIO
docker compose up -d minio

# 2. 初始化 bucket + CORS + lifecycle (一次性)
bash docker/scripts/minio_init.sh

# 3. 切 backend
echo "OBJECT_STORE_BACKEND=minio" >> packages/service/.env.local
```

## ObjectStorage 切换

```bash
# Default: 本地 FS (无依赖)
# Production: MinIO (S3 兼容)
export OBJECT_STORE_BACKEND=minio
export OBJECT_STORE_S3_ENDPOINT=http://localhost:9000
# ... 其他 S3 配置
```

详见 [docs/ingest.md](docs/ingest.md) + [packages/service/CLAUDE.md](packages/service/CLAUDE.md) ObjectStore 章节.

## 测试

```bash
uv run pytest tests/                      # 跑全部
uv run pytest tests/ -m "not slow"        # 跑非 slow 测试
```

详见 [docs/dev-conventions.md](docs/dev-conventions.md)。

## Git Hooks (Husky)

仓库根有 `.husky/` + 根 `lint-staged.config.js`, monorepo 统一 git hooks. 首次克隆后**一次性启用**:

```bash
git config core.hooksPath .husky
```

启用后 `git commit` 会自动跑:

| Hook         | 触发时机     | 检查内容                                                                         |
| ------------ | ------------ | -------------------------------------------------------------------------------- |
| `pre-commit` | 暂存后       | ruff / oxlint / oxfmt (staged); pyright / tsc / vitest (全量, 仅对应子目录改时) |
| `commit-msg` | 写完 message | conventional commits 格式 + subject ≤72 字符                                     |

跳过单次 hook: `git commit --no-verify`

**Windows 提示**: lint-staged 走 `bun --cwd <subdir> x <bin>`, 跨平台, 不依赖 cmd `cd` 解析.
