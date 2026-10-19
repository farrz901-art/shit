# PG 环境变量统一 + get_rag_db_url util

**日期**: 2026-06-18
**状态**: 设计已批准, 待实施
**作者**: Claude (brainstorming with user)

## Context

RAG 项目当前 PG 连接信息散落在 **3 个独立来源**, 必须人工维持一致, 否则连接漂移:

| 来源 | 读取点 | 格式 |
|---|---|---|
| `RAG_DB_URL` env | `src/storage/engine.py:27`、`src/storage/migrations/env.py:16,51,71` | 完整 URL 字符串 |
| `PG_HOST/PORT/USER/PASSWORD/DATABASE` env × 5 | `src/retrieval/vector_store.py:44-48`、`src/memory/mem0_client.py:72-76`、`src/health/checks.py:75` (经 PGVectorConfig.from_env) | 5 个 parts |
| `config.toml [rag_core.pg]` | `src/config.py:121-125` (`get_rag_core_config`) | 5 个 parts |

**历史教训** (`feedback-config-dataclass-needs-from-env`): 2026-06-15 真实事故——`PGVectorConfig()` 无参构造走 dataclass 默认值 `postgres:postgres`, 跟 docker 实际 `deyuan888` 漂移, 登录 500 半天定位不到根因.

**Why 现在做**:

- 同一台 PG 被 3 套配置描述, 任何一处改密码必须改 3 处
- `get_rag_core_config()` 是**死代码**——`config.toml` 没有 `[rag_core]` 段, 调它直接 `KeyError`, 全代码库无任何 caller
- dev 模板里有 5 个 `PG_VECTOR_DIM/INDEX_TYPE/HNSW_M/HNSW_EF_CONSTRUCTION/IVFFLAT_LISTS` env var 跟 `defaults.py` 字字相同, 100% 噪音
- 用户已经在生产调试时踩过 (本次 Neo4j URI 日志噪音 + docker 密码漂移教训)

## 目标

- **PG_* 5 个 env 是 env 边界唯一来源** (跟 Docker `POSTGRES_*` / Django / `psql` 习惯一致)
- **`get_rag_db_url()` util 是 URL 唯一构造点** (SQLAlchemy / Alembic / pgvector 边界要 URL 字符串)
- 删 `RAG_DB_URL` env
- 删 `config.toml` 路径的 `get_rag_core_config` + 5 个 dataclass (死代码)
- 删 5 个向量索引 env var (逐个判断见下文, 全部为噪音)
- 测试覆盖: URL 构造 (含密码特殊字符 URL-encoding)、env 覆盖、默认值回退

## 非目标

- 不保留 `RAG_DB_URL` 兼容 fallback (符合 `feedback-no-shim-no-minimal-changes`)
- 不动 `config.toml` 的 `[paths]/[archive]` 段 (filesystem 路径, env 不合适)
- 不动 `get_paths/get_cad_config/get_archive_config` (有真调用方)
- 不重构 `vector_store.py` / `mem0_client.py` 的字段读法 (它们的 API 要字段不是 URL, 直接读 PG_* 5 个 OK)
- 不改 docker-compose (`POSTGRES_*` 已是 5 parts, 我们 `PG_*` 跟它对齐, 不用 mapping)
- 不优化 SQLAlchemy pool 配置
- 不动 alembic.ini (`sqlalchemy.url =` 是空的, env.py 显式注入, 无需改)

## 5 个向量索引 env var 逐个判断

`PG_VECTOR_DIM/INDEX_TYPE/HNSW_M/HNSW_EF_CONSTRUCTION/IVFFLAT_LISTS` 共 5 个, 全部从 env 删除, 依据如下:

### `PG_VECTOR_DIM=1024`

**用途**: pgvector 列的维度 (`vector(N)`), 建表时 `init_pgvector` 用, query 时 `_build_vector_store` 透传给 llama-index.

**实际行为**:
- 当前 `.env.example` 配 1024
- `PGVectorConfig.from_env`: `int(os.getenv("PG_VECTOR_DIM", "0")) or None` → 1024
- `vector_store.py:85,197` 两处都 `cfg.vector_dim or 1024` → 最终值 1024
- 跟 `EMBED_DIMENSIONS=1024` (embedder 模型输出维度) **必须相等**, 否则 INSERT 维度不匹配报错

**为什么是 env 噪音**:
- dev 用 BGE (1024-dim) 永远不变, env 设 1024 跟 dataclass 默认 `or 1024` fallback 完全等价
- 真要换 embedder (BGE → OpenAI text-embedding-3-small = 1536-dim), 是 **schema 迁移** 范畴, 不该靠改 env 临时切换 (改完不重新 `init_pgvector(force=True)` 列维度还是 1024, INSERT 直接炸)
- 跟 `EMBED_DIMENSIONS` 重复, 两套 env 必须手动维持一致, 又一个"漂移源"

**正确归宿**: **删 env**. `vector_dim` 字段从 `EMBED_DIMENSIONS` env 直接派生 (单一来源), 写死在代码里的 1024 也跟着改 dataclass 默认.

### `PG_INDEX_TYPE=hnsw`

**用途**: 二选一, `hnsw` (现代, 召回高) 或 `ivfflat` (老, 内存省). 在 `init_pgvector` 里决定建哪种 index.

**实际行为**:
- 当前 `.env.example` 配 hnsw
- `PGVectorConfig.index_type: str = "hnsw"` (dataclass 默认已经 hnsw)
- `init_pgvector:200` 的 if/elif 二选一

**为什么是 env 噪音**:
- dev 永远用 hnsw (HNSW 是 2026 年事实标准, pgvector 官方文档默认推荐)
- 真要切 ivfflat 做压测对比, 改 `init_pgvector` 那个 if 分支比改 env 直观, 改完跟 schema 一起评审
- 跟"hnsw vs ivfflat"二选一, 不存在连续调参场景, 配 env 没意义

**正确归宿**: **删 env**, 硬编码 hnsw. IVFFlat 分支保留 (代码里), 备未来真要切换时手改 `init_pgvector`.

### `PG_HNSW_M=16`

**用途**: HNSW 算法每层每个节点的最大连接数. pgvector lib 默认 16, 是经验最优值.

**实际行为**:
- `PGVectorConfig.hnsw_m: int = 16` (dataclass 默认 = pgvector lib 默认)
- env 设 16 跟默认完全一致

**为什么是 env 噪音**:
- 调它是 DBA 级性能调优, dev 不会碰
- prod 真要调, 应该走 configmap / terraform, 不是 `.env.local`
- 配 env 反而鼓励"随手调参"反模式

**正确归宿**: **删 env**, 硬编码 16 (pgvector lib 默认).

### `PG_HNSW_EF_CONSTRUCTION=200`

**用途**: HNSW 索引构建时的候选列表大小, 影响构建时间 vs 索引质量. pgvector lib 默认 200.

**实际行为**: 跟 `PG_HNSW_M=16` 完全同构, 100% 跟 dataclass 默认 + lib 默认一致.

**正确归宿**: **删 env**, 硬编码 200.

### `PG_IVFFLAT_LISTS=100`

**用途**: IVFFlat 的 cluster 数量. `init_pgvector:206` 的 ivfflat 分支用.

**实际行为**:
- 永远走不到 (因为 `PG_INDEX_TYPE=hnsw`)
- 即使走了, 100 跟 dataclass 默认 + lib 默认一致

**为什么是 env 噪音**:
- 是上一个 var (`PG_INDEX_TYPE=ivfflat`) 才有意义的参数, 上一个删了, 这个必删
- 即使保留 ivfflat 分支, 100 也不需要可配

**正确归宿**: **删 env**, 硬编码 100.

## 架构

### env 边界: parts (5 个)

```
┌──────────────────────────────────────────────────────────────┐
│  开发者配 .env.local / docker-compose 注入                    │
│                                                              │
│  PG_HOST=localhost          ┐                                │
│  PG_PORT=5432               ├─ 5 个 parts (source of truth)   │
│  PG_USER=postgres           │  跟 Docker POSTGRES_* 对齐      │
│  PG_PASSWORD=deyuan888      │  跟 Django DATABASES 对齐       │
│  PG_DATABASE=rag            ┘                                │
└────────────────────────────────┬─────────────────────────────┘
                                 │
                                 │ os.getenv × 5
                                 ▼
┌──────────────────────────────────────────────────────────────┐
│  src/common/db_url.py (新文件)                                │
│                                                              │
│  def get_rag_db_url() -> str:                                │
│      return f"postgresql+psycopg://{urlencode(user)}:        │
│              {urlencode(pw)}@{host}:{port}/{urlencode(db)}"  │
│                                                              │
│  • 唯一 URL 构造点                                             │
│  • 密码 / user / database 自动 URL-encode (@ : / 等特殊字符)  │
│  • 默认值从 src/common/defaults.py 拿                         │
└────────────────────────────────┬─────────────────────────────┘
                                 │
                                 │ URL 字符串
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   ┌────────┐               ┌─────────┐              ┌──────────┐
   │ engine │               │ Alembic │              │ pgvector │
   │ .py    │               │ env.py  │              │ (走      │
   │ SQLAlch│               │         │              │ connection_│
   │ emy    │               │         │              │ string)  │
   └────────┘               └─────────┘              └──────────┘
   (业务表 ORM)              (migration)              (向量索引)
```

### mem0 路径: 直接读 parts (不走 URL)

```
PG_* 5 env
    │
    ├─→ vector_store.py:44-48  (PGVectorConfig.from_env)   ─→  pgvector connection_string (内部用 get_rag_db_url)
    └─→ mem0_client.py:72-76  (_build_config)              ─→  mem0 dict config (host/port/user/pw/dbname, 保持)
```

mem0 pgvector config **原生要 dict 不是 URL**, 继续读 5 个 parts 最直接. 跟 vector_store 共享同一份 `PG_*` env, 不需要走 URL.

## 组件

### 1. 新建 `src/common/db_url.py`

```python
"""PG 连接 URL 构造器 (2026-06-18 重构).

源 = PG_* 5 个 env (跟 Docker POSTGRES_* / Django DATABASES / psql 习惯一致).
产物 = postgresql+psycopg URL (SQLAlchemy / Alembic / pgvector 标准接口).

URL 只在 SQLAlchemy/pgvector 调用点构造, 不在 env 里出现.
"""
from __future__ import annotations

import os
from urllib.parse import quote

from . import defaults


def get_rag_db_url() -> str:
    """从 PG_* env 构造 SQLAlchemy 用的 postgresql+psycopg URL.

    密码 / user / database 自动 URL-encode (quote safe=''),
    避免 @ : / 等特殊字符炸 URL 解析.

    默认值从 src.common.defaults 拿 (集中管理, 禁止硬编码).
    """
    host = os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST)
    port = int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT)))
    user = os.getenv("PG_USER", defaults.DEFAULT_PG_USER)
    password = os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD)
    database = os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE)
    return (
        f"postgresql+psycopg://{quote(user, safe='')}:"
        f"{quote(password, safe='')}@"
        f"{host}:{port}/{quote(database, safe='')}"
    )
```

### 2. 改 `src/common/defaults.py`

**删** (5 个向量索引 env, 跟 dataclass 默认值 100% 重复):

```python
DEFAULT_PG_VECTOR_DIM: int = 0
DEFAULT_PG_INDEX_TYPE: str = "hnsw"
DEFAULT_PG_HNSW_M: int = 16
DEFAULT_PG_HNSW_EF_CONSTRUCTION: int = 200
DEFAULT_PG_IVFFLAT_LISTS: int = 100
```

**保留** (5 个 PG 连接 parts, env 唯一来源):

```python
DEFAULT_PG_HOST: str = "localhost"
DEFAULT_PG_PORT: int = 5432
DEFAULT_PG_USER: str = "postgres"
DEFAULT_PG_PASSWORD: str = "postgres"
DEFAULT_PG_DATABASE: str = "rag"
```

### 3. 改 `src/storage/engine.py`

**删**:
- `DEFAULT_DB_URL` 常量 (移到 db_url.py + defaults.py, 或在 engine.py 用 `get_rag_db_url()` 替代)
- `_resolve_db_url()` 函数

**改**: `get_engine()` 内

```python
# 旧
url = _resolve_db_url()

# 新
from src.common.db_url import get_rag_db_url
url = get_rag_db_url()
```

`_mask_password` 保留 (URL 字符串日志脱敏).

### 4. 改 `src/storage/migrations/env.py` (Alembic)

`from src.storage.engine import _resolve_db_url` → `from src.common.db_url import get_rag_db_url`

2 处调用 (`run_migrations_offline`、`run_migrations_online`) 替换.

### 5. 改 `src/retrieval/vector_store.py`

- `PGVectorConfig` 删 5 个向量索引字段的 `os.getenv` 读取 (见上文"逐个判断"章节, 全部为噪音)
- `vector_dim` 字段从 `EMBED_DIMENSIONS` env 派生 (单一来源, 避免 `PG_VECTOR_DIM` 跟 `EMBED_DIMENSIONS` 漂移)
- `index_type/hnsw_m/hnsw_ef_construction/ivfflat_lists` 硬编码为 dataclass 默认值 (hnsw/16/200/100)
- `PGVectorConfig.from_env()` 只读 5 个 PG_* 连接 env, 其它字段用 dataclass 默认
- `PGVectorConfig.connection_string` property 改为调 `get_rag_db_url()` (单一构造点)
- `init_pgvector` 里 `vector({config.vector_dim or 1024})` 改为 `vector({_get_embed_dim()})` (从 `EMBED_DIMENSIONS` 读)
- `_build_vector_store` 里 `embed_dim=cfg.vector_dim or 1024` 同样改 `embed_dim=_get_embed_dim()`

新增私有 helper (放在 `vector_store.py` 末尾):

```python
def _get_embed_dim() -> int:
    """向量列维度从 EMBED_DIMENSIONS env 派生, 默认 1024 (BGE).
    
    单一来源: 跟 embedder 模型输出维度绑定, 避免 PG_VECTOR_DIM 跟 EMBED_DIMENSIONS 漂移.
    """
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))
```

### 6. 改 `src/memory/mem0_client.py`

**不变**: `_build_config()` 继续读 PG_* 5 个 (mem0 dict config 原生要字段).

### 7. 删 `src/config.py` 死代码

**删 5 个 dataclass**:
- `PGConfig`
- `EmbedConfig`
- `LLMConfig`
- `ChunkConfig`
- `RagCoreConfig`

**删 1 个函数**: `get_rag_core_config()`.

**保留 3 个 dataclass** + **3 个 getter** (有真调用方):
- `Paths` + `get_paths()`
- `CadConfig` + `get_cad_config()`
- `ArchiveConfig` + `get_archive_config()`

### 8. 改 `src/__init__.py`

- 删 `get_rag_core_config` 的 import (`src/__init__.py:82`)
- 删 `get_rag_core_config` 的 `__all__` 条目 (`src/__init__.py:216`)

### 9. 改 `.env.local` + `.env.example`

**删 6 行** (`RAG_DB_URL` + 5 个向量索引):

```diff
- RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag
  PG_HOST=localhost
  PG_PORT=5432
  PG_USER=postgres
  PG_PASSWORD=replace-with-strong-password      # ← 改成 docker 实际密码
  PG_DATABASE=rag
- PG_VECTOR_DIM=1024              # 必须跟 EMBED_DIMENSIONS 一致
- PG_INDEX_TYPE=hnsw              # hnsw / ivfflat
- PG_HNSW_M=16
- PG_HNSW_EF_CONSTRUCTION=200
- PG_IVFFLAT_LISTS=100
```

**PG 段加注释**:

```ini
# PG 5 个 env 是 PG 连接的 source of truth, 跟 Docker POSTGRES_* 对齐
# 业务表 (SQLAlchemy) / pgvector / mem0 / Alembic 全用这 5 个
# 不用配 RAG_DB_URL, URL 在代码里用 get_rag_db_url() 现场构造
# 向量列维度自动从 EMBED_DIMENSIONS 读, 不用单独配
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=replace-with-strong-password      # ← 改成 docker 实际密码
PG_DATABASE=rag
```

### 10. 改 `tests/common/test_defaults.py`

- **删** 5 个 `DEFAULT_PG_VECTOR_*` 断言 (`DEFAULT_PG_VECTOR_DIM/_INDEX_TYPE/_HNSW_M/_HNSW_EF_CONSTRUCTION/_IVFFLAT_LISTS`)
- **保留** 5 个 `DEFAULT_PG_*` 断言 (`DEFAULT_PG_HOST/_PORT/_USER/_PASSWORD/_DATABASE`)

### 11. 改 `tests/storage/test_engine.py`

- 删 `_resolve_db_url` 相关 import / 测试
- 加 `get_rag_db_url` 集成测试 (5 env + 默认值)

### 12. 改 `tests/storage/conftest.py`

- `_resolve_db_url` import → `get_rag_db_url` import

### 13. 改 `tests/ingest/test_store.py` + `tests/kg/test_kg_audit.py`

- `os.environ.get("RAG_DB_URL", "").startswith("postgresql")` skip 条件
- 改为 `os.environ.get("PG_HOST")` 非空检查 (任一核心 env 存在即视为 PG 已配)

### 14. 新建 `tests/common/test_db_url.py`

测 `get_rag_db_url()`:

| 测试 | 断言 |
|---|---|
| `test_default_when_no_env` | 清空 PG_* env → 返 `postgresql+psycopg://postgres:postgres@localhost:5432/rag` |
| `test_uses_pg_env_overrides` | monkeypatch 5 env 全设 → URL 含新值 |
| `test_url_encodes_password_with_at_sign` | `PG_PASSWORD=p@ss@word` → URL 含 `%40` (不能用 `@` 裸) |
| `test_url_encodes_password_with_colon` | `PG_PASSWORD=p:ss` → URL 含 `%3A` |
| `test_url_encodes_password_with_slash` | `PG_PASSWORD=p/ss` → URL 含 `%2F` |
| `test_url_encodes_password_with_space` | `PG_PASSWORD=hello world` → URL 含 `%20` |
| `test_url_encodes_user_with_special` | `PG_USER=ad@min` → URL 含 `%40` |
| `test_url_encodes_database_with_special` | `PG_DATABASE=my db` → URL 含 `%20` |
| `test_port_cast_to_int` | `PG_PORT=5432` (str env) → URL 端口正确 |
| `test_special_chars_round_trip` | 用 `urlparse` 拆回字段, 验证 `password == 原值` (说明 SQLAlchemy 拿 URL 能正确还原) |

### 15. 改 `packages/service/CLAUDE.md`

把 `RAG_DB_URL=...rag_test` (line 27) 和 `RAG_DB_URL=...rag` (line 34) 改成 `PG_*` 5 env 的 export 示例.

### 16. 改 `src/storage/__init__.py:11` + `src/kg/audit.py:27` 注释

把"改 RAG_DB_URL 环境变量"改成"改 PG_* 5 env, 走 `get_rag_db_url()` 拼 URL".

## 数据流

### 启动时 (不变)

```
uv run python main.py
  → alembic upgrade head
      → env.py: url = get_rag_db_url()
      → context.configure(url=url, ...)
  → uvicorn 启动
  → _get_pg_engine() (src/health/checks.py)
      → PGVectorConfig.from_env() (走 PG_* 5 env)
      → PGVectorConfig.connection_string → get_rag_db_url()
  → 业务请求进来 → src/storage/engine.py:get_engine()
      → url = get_rag_db_url()
      → create_engine(url, pool_pre_ping=True, ...)
```

### pgvector 检索 (不变)

```
HTTP /api/chat
  → src/retrieval/query_engine.py
    → PGVectorStore(config=PGVectorConfig.from_env())
      → _build_vector_store(): PGVectorStore(connection_string=config.connection_string, ...)
      → SELECT ... FROM llamaindex_embeddings ORDER BY embedding <=> $1 LIMIT k
```

### mem0 add/search (不变)

```
HTTP /api/memory/add
  → src/memory/router.py
    → MemoryService.add(...)
      → Mem0Store(user_id)
        → Memory.from_config(_build_config())
            vector_store.config: {host, port, user, password, dbname, ...}  ← 直接读 PG_* 5 env
```

## 错误处理

| 失败点 | 行为 |
|---|---|
| `get_rag_db_url()` 读 env 缺 `PG_PORT` | `int("")` ValueError, 上浮到 get_engine 启动崩溃, 提示 "请配 PG_* 5 env" |
| `PG_PORT=abc` 非数字 | `int("abc")` ValueError, 启动崩溃 |
| 密码含 ` ` 空格未 URL-encode | urlparse 解析可能错位; 我们的 `quote(safe='')` encode 全部, SQLAlchemy 拿到 URL 后自动 unquote, 行为一致 |
| `mem0 _build_config()` 缺 `PG_HOST` | 走 `defaults.DEFAULT_PG_HOST="localhost"`, 不报错 (跟当前行为一致) |
| 测试时 `PG_HOST` 未设 | skip 条件触发, 跳过整个 module (现有行为, 改后 skip 条件改用 `PG_HOST` 非空) |

## 测试

按 `feedback-tdd-test-real-behavior-not-just-no-crash` + `feedback-must-test-both-ends`:

### 单测 (纯 mock, 0 真实 DB)

| 文件 | 测什么 |
|---|---|
| `tests/common/test_db_url.py` (新) | `get_rag_db_url()` 默认/env/特殊字符 URL-encoding |
| `tests/storage/test_engine.py` (改) | `get_rag_db_url()` 集成 (5 env 透传到 engine), `_resolve_db_url` 删 |
| `tests/common/test_defaults.py` (改) | 删 5 个 `DEFAULT_PG_VECTOR_*`, 保留 5 个 `DEFAULT_PG_*` |
| `tests/retrieval/test_vector_store.py` (不变) | 已测 PG_* 5 env 透传, 行为不动 |
| `tests/memory/test_mem0_client.py` (不变) | 已测 PG_* 5 env 透传, 行为不动 |
| `tests/test_health_pgvector_env.py` (不变) | 已测 PG_* 5 env 透传, 行为不动 |

### 集成 (真 PG, skip 模式 2)

| 文件 | 改 |
|---|---|
| `tests/ingest/test_store.py` | skip 条件从 `RAG_DB_URL.startswith("postgresql")` 改 `PG_HOST` 非空 |
| `tests/kg/test_kg_audit.py` | 同上 |
| `tests/storage/conftest.py` | `_resolve_db_url` → `get_rag_db_url` (1 行) |
| `tests/storage/test_init_exports.py` | 验证 `get_rag_db_url` 是 `src.common.db_url` 的 export |

### Test 命令

```bash
# 单测 (无 docker PG 也能跑)
cd packages/service
uv run pytest tests/common/test_db_url.py tests/common/test_defaults.py tests/storage/test_engine.py -v

# 集成 (需要 docker PG + 配 PG_* env)
PG_HOST=localhost PG_PORT=5432 PG_USER=postgres PG_PASSWORD=deyuan888 PG_DATABASE=rag \
  uv run pytest tests/ingest/test_store.py tests/kg/test_kg_audit.py -v
```

## 实施批次

按 `feedback-commit-in-batches-for-large-changes` (3 批, 每批可独立 review/回滚/bisect):

### Batch 1: 核心 util + 死代码清理

- 新增 `src/common/db_url.py` (get_rag_db_url 实现)
- 新增 `tests/common/test_db_url.py` (10 个 TDD 用例)
- 改 `src/common/defaults.py` (删 5 个 `DEFAULT_PG_VECTOR_*`)
- 改 `tests/common/test_defaults.py` (删对应断言)
- 删 `src/config.py` 里 `PGConfig/EmbedConfig/LLMConfig/ChunkConfig/RagCoreConfig` + `get_rag_core_config`
- 改 `src/__init__.py` (删 `get_rag_core_config` 导出)
- **验证**: `uv run pytest tests/common/` 全绿, grep 无 `get_rag_core_config` 引用

### Batch 2: 切 engine + Alembic 到 get_rag_db_url

- 改 `src/storage/engine.py` (`_resolve_db_url` → `get_rag_db_url`)
- 改 `src/storage/migrations/env.py` (同上)
- 改 `src/retrieval/vector_store.py` (PGVectorConfig.connection_string 走 get_rag_db_url)
- 改 `tests/storage/test_engine.py` + `tests/storage/conftest.py`
- 改 `tests/ingest/test_store.py` + `tests/kg/test_kg_audit.py` (skip 条件)
- **验证**: `uv run alembic upgrade head` + `uv run python main.py` 启动, 业务 API curl 走通

### Batch 3: env 文件 + 文档收尾

- 改 `.env.local` + `.env.example` (删 `RAG_DB_URL` + 5 个 `PG_VECTOR_*`)
- 改 `packages/service/CLAUDE.md:27,34` (RAG_DB_URL → PG_* env)
- 改 `src/storage/__init__.py:11` + `src/kg/audit.py:27` 注释
- 重启 service 验证:
  - `curl /api/health` → 200 + `pgvector.status == "ok"`
  - 业务表写入 (login + create user) 走通
  - pgvector 检索 (chat 端点) 走通
  - mem0 add/search 走通 (如果有 `/api/memory/*` 端点)

## 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| `get_rag_db_url()` 拼 URL 时密码 `quote` 错, SQLAlchemy 拿到坏 URL 报认证失败 | `tests/common/test_db_url.py` 测 5 种特殊字符 (含 round-trip) |
| `vector_store.py` 的 `PGVectorConfig.connection_string` 改成调用函数后, 原本 hardcode 拼的 `postgresql://` 跟 `postgresql+psycopg://` 不一致 | 改后统一 `postgresql+psycopg://`, 跟 engine 一致, 验证: dev 跑 `init_pgvector` 看表是否建在 PG 而非本地 |
| 删 `get_rag_core_config` 后, 真有 rag_core CLI 想用 | 0 caller, 0 测试, 0 config.toml 段 — 实锤死代码; 未来真要恢复, 从 git history 拿 |
| Batch 2 切 engine 时旧 `_resolve_db_url` 还有 import | grep 验证, `rg "_resolve_db_url" packages/service/` 必须 0 命中 (除了 alembic env.py 自身) |
| `.env.local` 删 `RAG_DB_URL` 后用户忘了重启 | 重启提醒在 Batch 3 验收步骤 |
| 测试 skip 条件改 `PG_HOST` 后, 某次 CI 注入 `RAG_DB_URL` 但没 `PG_HOST` 导致误跑 | CI env 文件也同步改; 验证: 跑 `tests/ingest/test_store.py` 不带 env 必 skip |

## 验收

```bash
# 1. 切到 master, 拉最新
cd packages/service
git pull

# 2. 验证 dev 模板只剩 5 个 PG_* env
grep -E "^PG_" .env.example
# Expected:
#   PG_HOST=localhost
#   PG_PORT=5432
#   PG_USER=postgres
#   PG_PASSWORD=replace-with-strong-password
#   PG_DATABASE=rag
# (无 RAG_DB_URL, 无 PG_VECTOR_*)

grep "RAG_DB_URL" .env.example
# Expected: 0 命中

# 3. 单测全绿
uv run pytest tests/common/test_db_url.py tests/common/test_defaults.py tests/storage/test_engine.py -v
# Expected: 全 PASS

# 4. 启动后端 (用 docker 配的 PG_*)
docker compose -f ../docker/docker-compose.yml up -d postgres
# 配 .env.local 跟 docker POSTGRES_PASSWORD 一致
uv run alembic upgrade head
uv run python main.py &
# Expected: engine init log 显示正确 URL (密码脱敏)

# 5. 健康检查
curl http://localhost:8000/api/health
# Expected: {"checks": {"pgvector": {"status": "ok", ...}}}

# 6. 业务 curl
curl -X POST http://localhost:8000/api/auth/anon
# Expected: 200 + 用户 JSON

# 7. 集成测试 (需要 PG)
PG_HOST=localhost PG_PORT=5432 PG_USER=postgres PG_PASSWORD=deyuan888 PG_DATABASE=rag \
  uv run pytest tests/ingest/ tests/kg/ tests/retrieval/ tests/memory/ -v
# Expected: 全 PASS
```

## 相关链接

- [README.md](../../README.md) - 现状 (不用改, env 模板是 source of truth)
- [packages/service/CLAUDE.md](../../../packages/service/CLAUDE.md) - 后端局部约定 (改 RAG_DB_URL → PG_* env 提及)
- memory: `feedback-no-shim-no-minimal-changes` - 无 shim 原则
- memory: `feedback-config-dataclass-needs-from-env` - 2026-06-15 PG 密码漂移教训
- memory: `feedback-commit-in-batches-for-large-changes` - 大改分批
- memory: `feedback-debug-distinguish-root-causes` - 区分根因 (本次根因是"3 来源 + 5 噪音 env", 不是"拼 URL 错了")
- memory: `feedback-check-old-code-before-refactor` - 改前 grep 老代码
- spec: `2026-06-15-sqlite-to-pgvector-migration-design.md` - 跟本 spec 互补 (那个把所有 SQLite 切 PG, 这次统一 env 边界)
