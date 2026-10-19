---
name: project-pg-env-unification-done
description: "2026-06-18 PG env 统一重构已完成, 5 个 PG_* env 是 source of truth, get_rag_db_url() util 统一 URL 构造"
metadata: 
  node_type: memory
  type: project
  originSessionId: bbd38558-9e99-4b93-b8fc-d4e462b4c307
---

PG 连接信息统一 (2026-06-18, commit a156c24):
- **5 个 PG_* env (PG_HOST/PORT/USER/PASSWORD/DATABASE)** 是 env 边界唯一来源, 跟 Docker `POSTGRES_*` / Django / `psql` 习惯一致
- **`src.common.db_url.get_rag_db_url()`** util 是 URL 唯一构造点, 用 `urllib.parse.quote(safe='')` 自动 URL-encode 密码/user/database 防 `@`/`:`/`/`/` ` 炸 URL
- **删 RAG_DB_URL env** (`postgresql+psycopg://...` 整体字符串), 删 `get_rag_core_config` 死代码 + 5 个 dataclass, 删 5 个 `PG_VECTOR_DIM/INDEX_TYPE/HNSW_M/HNSW_EF_CONSTRUCTION/IVFFLAT_LISTS` 噪音 env
- **`vector_dim` 从 `EMBED_DIMENSIONS` 派生** (`_get_embed_dim()` helper), 避免 PG_VECTOR_DIM 跟 EMBED_DIMENSIONS 漂移
- mem0 继续直接读 PG_* 5 parts (它的 API 要 dict)
- async 路径 (AsyncPGVectorStore.aconnect + approvals/_get_async_engine) 走 `get_rag_db_url()` → `_to_async_url()` driver 转换 (psycopg → asyncpg), 后续可统一封装

**Why:** 2026-06-15 PGVectorConfig 漂移 bug (`PGVectorConfig()` 无参走默认值 `postgres:postgres` 跟 docker 实际 `deyuan888` 对不上, 半天定位不到根因), 加上 Neo4j URI 噪音事件, 暴露 env 边界 3 套来源并存 (`RAG_DB_URL` / `PG_*` 5 / `config.toml [rag_core.pg]`) 是 bug 重灾区.

**How to apply:** 未来加新 PG 相关配置: env 用 parts (跟 Docker 一致), URL 走 `get_rag_db_url()`, 单一来源. 不要发明 RAG_DB_URL2 / DATABASE_URL 等并行 URL env.

**Spec + Plan:** `docs/superpowers/specs/2026-06-18-pg-env-unification-design.md` + `docs/superpowers/plans/2026-06-18-pg-env-unification.md`

**10 commits (master)**: feat common util (6d73084) → refactor vector_store (679a7ee) → docs (80d6777) → alembic env.py (edbcd72) → 删 config 死代码 (24b02cf) → 切 engine.py (6abb5e8) → env skip + drop RAG_DB_URL (cfd61e9) → fix approvals (a156c24).

**验收**: service 启动 OK, `POST /api/auth/anon` 200 + token, DB 写入链路 (PG_* env → get_rag_db_url → SQLAlchemy async engine → ORM) 全绿.

**相关 memory**:
- `feedback-debug-distinguish-root-causes` — 删跨文件共享函数必须 grep **整个 src/**, 不能只看本模块目录 (Task 4 漏查 src/approvals/router.py 引发 ImportError, commit a156c24 修复)
- `feedback-no-shim-no-minimal-changes` — 硬删 RAG_DB_URL env, 不留 `os.getenv('RAG_DB_URL') or get_rag_db_url()` 兼容 fallback
- `feedback-config-dataclass-needs-from-env` — 历史教训的根因 (PGVectorConfig() 无参走默认值漂移) 这次彻底根治
