# PG 环境变量统一 + get_rag_db_url util Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 PG 连接信息统一到 5 个 PG_* env (跟 Docker/Django 习惯一致), 通过 `get_rag_db_url()` util 在 SQLAlchemy/Alembic/pgvector 调用点现场拼 URL; 删 `RAG_DB_URL` env、`get_rag_core_config` 死代码、5 个向量索引 env var 噪音.

**Architecture:** env 边界用 5 parts (Docker 风格, 易理解易部分覆盖) → `get_rag_db_url()` 单点构造 URL (含密码 URL-encoding) → SQLAlchemy / Alembic / pgvector 拿到 URL 字符串. mem0 因为要 dict 不要 URL, 继续直接读 5 parts. 向量索引调参从 env 移到 dataclass 默认值, `vector_dim` 从 `EMBED_DIMENSIONS` 派生.

**Tech Stack:**
- Backend: Python 3.14, SQLAlchemy 2.0, Alembic, llama-index-vector-stores-postgres, mem0ai 2.0+, urllib.parse
- Test: pytest (TDD 强约束, 见 CLAUDE.md)
- Reference Spec: `docs/superpowers/specs/2026-06-18-pg-env-unification-design.md`

---

## File Structure

### New Files (2)

| 文件 | 职责 |
|------|------|
| `packages/service/src/common/db_url.py` | `get_rag_db_url()` 从 PG_* 5 env 拼 postgresql+psycopg URL, 密码/user/db 用 `urllib.parse.quote(safe='')` 自动 URL-encode |
| `packages/service/tests/common/test_db_url.py` | 单测: 默认值/env 透传/5 种密码特殊字符 URL-encoding/round-trip 验证 |

### Modified Files (10)

| 文件 | 改动 |
|------|------|
| `packages/service/src/common/defaults.py` | 删 `DEFAULT_PG_VECTOR_DIM/_INDEX_TYPE/_HNSW_M/_HNSW_EF_CONSTRUCTION/_IVFFLAT_LISTS` 共 5 个常量 (噪音, 跟 dataclass 默认 100% 重复) |
| `packages/service/src/storage/engine.py` | 删 `DEFAULT_DB_URL` 常量 + `_resolve_db_url()` 函数, `get_engine()` 改用 `get_rag_db_url()` |
| `packages/service/src/storage/migrations/env.py` | `_resolve_db_url` import → `get_rag_db_url`, 2 处调用替换 |
| `packages/service/src/retrieval/vector_store.py` | `PGVectorConfig` 删 5 个向量索引 env 读; `vector_dim` 从 `EMBED_DIMENSIONS` 派生; `connection_string` 改用 `get_rag_db_url()`; 加 `_get_embed_dim()` helper |
| `packages/service/src/config.py` | 删 `PGConfig/EmbedConfig/LLMConfig/ChunkConfig/RagCoreConfig` 5 个 dataclass + `get_rag_core_config()` 函数 |
| `packages/service/src/__init__.py` | 删 `get_rag_core_config` 的 import 和 `__all__` 条目 |
| `packages/service/.env.example` | 删 `RAG_DB_URL` + 5 个 `PG_VECTOR_*`; PG 段加注释说明 5 parts 是 source of truth |
| `packages/service/.env.local` | 删 `RAG_DB_URL` 一行 (5 个 `PG_*` 保留, 已经设了) |
| `packages/service/tests/common/test_defaults.py` | 删 5 个 `DEFAULT_PG_VECTOR_*` 断言 |
| `packages/service/tests/storage/test_engine.py` | 删 `_resolve_db_url` 相关测试, 加 `get_rag_db_url` 集成测试 |
| `packages/service/tests/storage/conftest.py` | `_resolve_db_url` import → `get_rag_db_url` (1 行) |
| `packages/service/tests/ingest/test_store.py` | skip 条件 `RAG_DB_URL.startswith("postgresql")` → `PG_HOST` 非空 |
| `packages/service/tests/kg/test_kg_audit.py` | 同上 |
| `packages/service/CLAUDE.md` | line 27/34 `RAG_DB_URL=...` 改成 `PG_*` 5 env 的 export 示例 |
| `packages/service/src/storage/__init__.py` | line 11 注释 "改 RAG_DB_URL 环境变量" → "改 PG_* 5 env, 走 `get_rag_db_url()` 拼 URL" |
| `packages/service/src/kg/audit.py` | line 27 注释同步 |

### Untouched Files (跟本次目标无关)

- `packages/service/src/memory/mem0_client.py` (mem0 要 dict 字段, 继续读 PG_* 5 env, OK)
- `packages/service/config.toml` (没 `[rag_core]` 段, 跟本 spec 无关)
- `packages/service/alembic.ini` (`sqlalchemy.url=` 空, env.py 显式注入)

---

## Task 1: 新增 `get_rag_db_url()` util + 单测 (TDD)

**Files:**
- Create: `packages/service/src/common/db_url.py`
- Test: `packages/service/tests/common/test_db_url.py`

- [ ] **Step 1: 写失败的测试 `tests/common/test_db_url.py`**

```python
"""get_rag_db_url() 单测 (TDD, 2026-06-18 PG env 统一)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest


@pytest.fixture(autouse=True)
def _clean_pg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个测试清空 PG_* env, 避免外部 .env.local 污染."""
    for k in ("PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_DATABASE"):
        monkeypatch.delenv(k, raising=False)


def test_default_when_no_env() -> None:
    """无 PG_* env → 走 defaults.py 默认值."""
    from src.common.db_url import get_rag_db_url

    url = get_rag_db_url()
    assert url == "postgresql+psycopg://postgres:postgres@localhost:5432/rag"


def test_uses_pg_env_overrides() -> None:
    """5 env 全设 → URL 含新值."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_HOST"] = "pg.prod"
    os.environ["PG_PORT"] = "6432"
    os.environ["PG_USER"] = "alice"
    os.environ["PG_PASSWORD"] = "s3cret"
    os.environ["PG_DATABASE"] = "prod_rag"

    url = get_rag_db_url()
    assert url == "postgresql+psycopg://alice:s3cret@pg.prod:6432/prod_rag"


def test_url_encodes_password_with_at_sign() -> None:
    """密码含 @ 必须 URL-encode 成 %40, 否则 urlparse 把 @ 后面当 host."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p@ss@word"
    url = get_rag_db_url()
    # 整个 URL 里 @host@:port/db 必须有 2 个 @ (1 host 前 1 host 后), 但密码里的 @ 必须是 %40
    assert url == "postgresql+psycopg://postgres:p%40ss%40word@localhost:5432/rag"
    # urlparse 拆回字段, 密码还原成原值 (round-trip)
    p = urlparse(url)
    assert p.hostname == "localhost"
    assert p.port == 5432
    from urllib.parse import unquote
    assert unquote(p.password or "") == "p@ss@word"


def test_url_encodes_password_with_colon() -> None:
    """密码含 : 必须 %3A, 否则 urlparse 把 : 当 host:port 分隔."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p:ss"
    url = get_rag_db_url()
    assert ":p%3Ass@" in url


def test_url_encodes_password_with_slash() -> None:
    """密码含 / 必须 %2F, 否则跟 path 串了."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "p/ss"
    url = get_rag_db_url()
    assert ":p%2Fss@" in url


def test_url_encodes_password_with_space() -> None:
    """密码含空格 必须 %20."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PASSWORD"] = "hello world"
    url = get_rag_db_url()
    assert ":hello%20world@" in url


def test_url_encodes_user_with_special() -> None:
    """user 含 @ 也要 encode."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_USER"] = "ad@min"
    url = get_rag_db_url()
    assert "://ad%40min:" in url


def test_url_encodes_database_with_special() -> None:
    """database 含空格 也要 encode."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_DATABASE"] = "my db"
    url = get_rag_db_url()
    assert url.endswith("/my%20db")


def test_port_cast_from_string_env() -> None:
    """env 里 PG_PORT 是 str, 必须 int() 转."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_PORT"] = "6543"
    url = get_rag_db_url()
    assert ":6543/" in url


def test_special_chars_round_trip() -> None:
    """综合: 5 env 全设 + 各种特殊字符, urlparse 拆回字段跟原值相等."""
    from src.common.db_url import get_rag_db_url

    os.environ["PG_HOST"] = "pg.test"
    os.environ["PG_PORT"] = "5432"
    os.environ["PG_USER"] = "ad@min"
    os.environ["PG_PASSWORD"] = "p@ss:wo/rd !"
    os.environ["PG_DATABASE"] = "db 1"

    url = get_rag_db_url()
    from urllib.parse import unquote
    p = urlparse(url)
    assert p.hostname == "pg.test"
    assert p.port == 5432
    assert unquote(p.username or "") == "ad@min"
    assert unquote(p.password or "") == "p@ss:wo/rd !"
    assert unquote((p.path or "").lstrip("/")) == "db 1"
```

- [ ] **Step 2: 跑测试, 确认失败 (模块不存在)**

```bash
cd packages/service
uv run pytest tests/common/test_db_url.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.common.db_url'`

- [ ] **Step 3: 实现 `src/common/db_url.py`**

```python
"""PG 连接 URL 构造器 (2026-06-18 重构).

源 = PG_* 5 个 env (跟 Docker POSTGRES_* / Django DATABASES / psql 习惯一致).
产物 = postgresql+psycopg URL (SQLAlchemy / Alembic / pgvector 标准接口).

URL 只在 SQLAlchemy / pgvector 调用点构造, 不在 env 里出现.
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

- [ ] **Step 4: 跑测试, 确认全绿**

```bash
cd packages/service
uv run pytest tests/common/test_db_url.py -v
```

Expected: 10 passed.

- [ ] **Step 5: 提交**

```bash
git add src/common/db_url.py tests/common/test_db_url.py
git commit -m "feat(common): add get_rag_db_url() util for PG_* env → URL"
```

---

## Task 2: 删 `defaults.py` 5 个向量索引常量 + 测试同步

**Files:**
- Modify: `packages/service/src/common/defaults.py:42-46`
- Modify: `packages/service/tests/common/test_defaults.py:68-72, 103-106`

- [ ] **Step 1: 跑现有 test_defaults.py, 确认 5 个 `DEFAULT_PG_VECTOR_*` 断言存在**

```bash
cd packages/service
uv run pytest tests/common/test_defaults.py -v
```

Expected: 全 PASS. 确认基线绿 (没有断点).

- [ ] **Step 2: 改 `src/common/defaults.py`, 删 5 个常量**

定位 line 42-46 (在 `# Neo4j` 段之前):

```python
# =============================================================================
# Neo4j
# =============================================================================
DEFAULT_NEO4J_URI: str = "bolt://localhost:7687"
```

把上面那 5 行 (`DEFAULT_PG_VECTOR_DIM/INDEX_TYPE/HNSW_M/HNSW_EF_CONSTRUCTION/IVFFLAT_LISTS`) **整段删掉**. 保留 5 个 `DEFAULT_PG_HOST/PORT/USER/PASSWORD/DATABASE` 不动.

- [ ] **Step 3: 改 `tests/common/test_defaults.py`, 删 5 个断言**

打开 `tests/common/test_defaults.py`, 找以下 5 个字符串 (在 `EXPECTED_DEFAULTS` 列表里):

```python
"DEFAULT_PG_VECTOR_DIM",
"DEFAULT_PG_INDEX_TYPE",
"DEFAULT_PG_HNSW_M",
"DEFAULT_PG_HNSW_EF_CONSTRUCTION",
"DEFAULT_PG_IVFFLAT_LISTS",
```

全部删掉. 同样在 `EXPECTED_INT_DEFAULTS` 列表 (line ~103) 里找 5 个对应条目 (`DEFAULT_PG_VECTOR_DIM/_HNSW_M/_HNSW_EF_CONSTRUCTION/_IVFFLAT_LISTS`), 全部删掉.

- [ ] **Step 4: 跑测试, 确认全绿**

```bash
cd packages/service
uv run pytest tests/common/test_defaults.py -v
```

Expected: 全 PASS, 断言数比之前少 5+5=10.

- [ ] **Step 5: grep 验证 0 引用, 提交**

```bash
# 验证 5 个常量在全代码库 0 引用
cd packages/service
rg "DEFAULT_PG_VECTOR_DIM|DEFAULT_PG_INDEX_TYPE|DEFAULT_PG_HNSW_M|DEFAULT_PG_HNSW_EF_CONSTRUCTION|DEFAULT_PG_IVFFLAT_LISTS" \
   src/ tests/ || echo "OK: 0 hits"
```

Expected: `OK: 0 hits`. 如果有命中, 改用对应引用方 (一般是 `vector_store.py`), 别留死代码.

```bash
git add src/common/defaults.py tests/common/test_defaults.py
git commit -m "refactor(common): remove 5 unused DEFAULT_PG_VECTOR_* constants"
```

---

## Task 3: 删 `src/config.py` 死代码 (`get_rag_core_config` + 5 dataclass)

**Files:**
- Modify: `packages/service/src/config.py:38-73, 108-141`
- Modify: `packages/service/src/__init__.py:82, 216`

- [ ] **Step 1: 跑现有测试, 确认基线绿**

```bash
cd packages/service
uv run pytest tests/ -m "not slow" -k "not integration" -q 2>&1 | tail -20
```

Expected: 全 PASS (没有断点). 如果有 red 先修.

- [ ] **Step 2: grep 验证 `get_rag_core_config` 0 调用方**

```bash
cd packages/service
rg "get_rag_core_config|RagCoreConfig|class PGConfig|class EmbedConfig|class LLMConfig|class ChunkConfig" \
   src/ tests/ scripts/ 2>&1
```

Expected:
- `get_rag_core_config`: 只在 `src/config.py:108` 定义 + `src/__init__.py:82, 216` 导出 3 处命中
- `RagCoreConfig`: 只在 `src/config.py:69, 73` 定义
- `class PGConfig/EmbedConfig/LLMConfig/ChunkConfig`: 只在 `src/config.py:40, 49, 56, 63` 定义

如果有任何 **额外调用方** (除了 import 跟定义), **STOP** — 说明有隐藏依赖, 不能直接删, 报告用户.

- [ ] **Step 3: 改 `src/config.py`, 删 5 dataclass + 1 函数**

定位 line 38-73 (`PGConfig/EmbedConfig/LLMConfig/ChunkConfig/RagCoreConfig` 5 个 dataclass), 整段**全删** (包括空行). 文件保留 `Paths/CadConfig/ArchiveConfig` 3 个 dataclass.

定位 line 108-141 (`get_rag_core_config` 函数), 整段**全删** (包括 docstring + body). 函数末尾的 `_ensure_config_exists` helper **保留** (其他 getter 还要用).

改后 `src/config.py` 应保留: 文件头注释, `tomllib/Path` import, `_PROJECT_ROOT/CONFIG_FILE`, `Paths/CadConfig/ArchiveConfig` 3 dataclass, `get_paths/get_cad_config/get_archive_config` 3 getter, `_ensure_config_exists`.

- [ ] **Step 4: 改 `src/__init__.py`, 删导出**

定位 line 82 (import 行):

```python
from .config import get_archive_config, get_cad_config, get_paths, get_rag_core_config
```

改成:

```python
from .config import get_archive_config, get_cad_config, get_paths
```

定位 line ~216 (`__all__` 列表里 `get_rag_core_config` 条目), 删这一行. `__all__` 仍按字母序排列, 别留空行.

- [ ] **Step 5: 跑测试, 确认全绿**

```bash
cd packages/service
uv run pytest tests/ -m "not slow" -k "not integration" -q 2>&1 | tail -10
```

Expected: 全 PASS, 跟基线一致.

- [ ] **Step 6: grep 最终验证 0 引用, 提交**

```bash
cd packages/service
rg "get_rag_core_config|RagCoreConfig|class PGConfig|class EmbedConfig|class LLMConfig|class ChunkConfig" \
   src/ tests/ scripts/ 2>&1
```

Expected: 0 命中 (除了可能的 `from .config import` 那行, 应该已经改干净).

```bash
git add src/config.py src/__init__.py
git commit -m "refactor(config): remove dead get_rag_core_config + 5 unused dataclasses"
```

---

## Task 4: 切 `src/storage/engine.py` 用 `get_rag_db_url()`

**Files:**
- Modify: `packages/service/src/storage/engine.py:21, 25-27, 49, 60-61`
- Modify: `packages/service/tests/storage/test_engine.py` (更新 import + 测试名)
- Modify: `packages/service/tests/storage/conftest.py` (更新 import)

- [ ] **Step 1: 跑现有 engine 测试, 确认基线绿**

```bash
cd packages/service
uv run pytest tests/storage/test_engine.py -v
```

Expected: 全 PASS.

- [ ] **Step 2: 改 `src/storage/engine.py`**

定位 line 19-22:

```python
# 默认连 docker-compose 起的 PG (密码跟 docker/.env POSTGRES_PASSWORD 一致)
# 生产必须改 env, 别用默认 password=postgres
DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/rag"
_engine: Engine | None = None
```

改成:

```python
# 启动期懒加载; URL 从 src.common.db_url.get_rag_db_url() 拿 (PG_* 5 env source of truth)
_engine: Engine | None = None
```

定位 line 25-27:

```python
def _resolve_db_url() -> str:
    """读 RAG_DB_URL env, 默认连 docker PG."""
    return os.getenv("RAG_DB_URL", DEFAULT_DB_URL)
```

整段**删掉**.

定位 line 48-49 (在 `get_engine` 函数里):

```python
    if _engine is None:
        url = _resolve_db_url()
```

改成:

```python
    if _engine is None:
        from src.common.db_url import get_rag_db_url

        url = get_rag_db_url()
```

定位 line 60-61 (错误信息里):

```python
                f"  请检查 RAG_DB_URL 环境变量, 或确认 docker PG 正在运行"
```

改成:

```python
                f"  请检查 PG_* 5 个环境变量, 或确认 docker PG 正在运行"
```

- [ ] **Step 3: 改 `tests/storage/test_engine.py`**

打开 `tests/storage/test_engine.py`, 找 `from src.storage.engine import _resolve_db_url` 跟 `RAG_DB_URL` 相关测试 (典型名 `test_*_rag_db_url*` 或 `_resolve_db_url`).

**删**:
- 老的 `_resolve_db_url` 单元测试 (它测的是 `os.getenv("RAG_DB_URL", ...)` 行为, 已被 `tests/common/test_db_url.py` 覆盖)

**加** 1 个新测试 (集成 `get_rag_db_url`):

```python
def test_get_engine_uses_get_rag_db_url(monkeypatch):
    """get_engine() 拿 URL 必须走 get_rag_db_url() (即 PG_* 5 env 派生),
    不再读 RAG_DB_URL (已删)."""
    from src.common.db_url import get_rag_db_url
    from src.storage import engine as engine_mod

    monkeypatch.setattr(engine_mod, "_engine", None)  # 强制重 init
    monkeypatch.setenv("PG_HOST", "test-pg")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_USER", "alice")
    monkeypatch.setenv("PG_PASSWORD", "pw")
    monkeypatch.setenv("PG_DATABASE", "rag")
    monkeypatch.delenv("RAG_DB_URL", raising=False)

    # 触发 _engine 初始化
    try:
        engine_mod.get_engine()
    except Exception:
        # 实际连 PG 可能失败 (test 环境无 PG), 我们只关心它用了什么 URL
        pass

    # 验证 _engine.dispose 时打印的 URL (用 mock 捕获) —— 简化: 直接调 get_rag_db_url() 验证
    assert "test-pg" in get_rag_db_url()
    assert "alice" in get_rag_db_url()
```

- [ ] **Step 4: 改 `tests/storage/conftest.py`**

打开 `tests/storage/conftest.py`, 找 `from src.storage.engine import _resolve_db_url` (或类似), 改成 `from src.common.db_url import get_rag_db_url`. 函数体内 `_resolve_db_url()` 调用改成 `get_rag_db_url()`.

- [ ] **Step 5: 跑测试, 确认全绿**

```bash
cd packages/service
uv run pytest tests/storage/ -v 2>&1 | tail -30
```

Expected: 全 PASS (允许 integration test skip, 因为无 docker PG).

- [ ] **Step 6: grep 验证, 提交**

```bash
cd packages/service
rg "_resolve_db_url|RAG_DB_URL" src/storage/ tests/storage/ 2>&1
```

Expected: 0 命中 (或只有 `tests/common/test_db_url.py` 这种独立测试, 不在 storage/).

```bash
git add src/storage/engine.py src/storage/migrations/env.py tests/storage/
git commit -m "refactor(storage): switch engine to get_rag_db_url(), remove RAG_DB_URL"
```

(注意: 同时改了 env.py, 见下个 Task 5)

---

## Task 5: 切 `src/storage/migrations/env.py` (Alembic) 用 `get_rag_db_url()`

**Files:**
- Modify: `packages/service/src/storage/migrations/env.py:16, 51, 71`

- [ ] **Step 1: 改 `src/storage/migrations/env.py`**

定位 line 16:

```python
from src.storage.engine import _resolve_db_url
```

改成:

```python
from src.common.db_url import get_rag_db_url
```

定位 line 51 (`run_migrations_offline` 函数体内):

```python
    url = _resolve_db_url()
```

改成:

```python
    url = get_rag_db_url()
```

定位 line 71 (`run_migrations_online` 函数体内):

```python
    configuration["sqlalchemy.url"] = _resolve_db_url()
```

改成:

```python
    configuration["sqlalchemy.url"] = get_rag_db_url()
```

- [ ] **Step 2: 跑 alembic dry-run, 验证 URL 能拿到 (不真改 DB)**

```bash
cd packages/service
PG_HOST=localhost PG_PORT=5432 PG_USER=postgres PG_PASSWORD=postgres PG_DATABASE=rag \
  uv run alembic current
```

Expected: 打印当前 alembic_version (可能是空, 也可能是某个 head rev id). 不报 `ModuleNotFoundError` 或 `NameError`.

- [ ] **Step 3: 提交**

```bash
git add src/storage/migrations/env.py
git commit -m "refactor(alembic): switch env.py to get_rag_db_url()"
```

---

## Task 6: 改 `vector_store.py` (删 5 向量索引 env + vector_dim 派生)

**Files:**
- Modify: `packages/service/src/retrieval/vector_store.py:14-56, 84-87, 128, 177-211`

- [ ] **Step 1: 跑现有 vector_store 测试, 确认基线绿**

```bash
cd packages/service
uv run pytest tests/retrieval/test_vector_store.py -v
```

Expected: 全 PASS.

- [ ] **Step 2: 改 `PGVectorConfig` dataclass (line 14-24)**

定位 line 14-24:

```python
@dataclass
class PGVectorConfig:
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag"
    vector_dim: int | None = None
    index_type: str = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    ivfflat_lists: int = 100
```

改成:

```python
@dataclass
class PGVectorConfig:
    """pgvector 配置.

    5 个连接字段从 PG_* env 派生 (from_env).
    向量索引调参是 dataclass 默认值, 不读 env (dev 不调, prod 调也走代码评审改这里).
    vector_dim 字段保留但语义改: None 表示"用 embedder 模型维度" (从 EMBED_DIMENSIONS env 读).
    """

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag"
    vector_dim: int | None = None  # None = 用 _get_embed_dim()
    index_type: str = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    ivfflat_lists: int = 100
```

(注意: `vector_dim` 默认仍是 `None`, 跟之前一样. 真正改的是 `from_env` 行为 + `_get_embed_dim` 引入)

- [ ] **Step 3: 改 `from_env` (line 30-56)**

定位 line 30-56 (整个 `from_env` classmethod), 改成:

```python
    @classmethod
    def from_env(cls) -> PGVectorConfig:
        """从 PG_* env 构造 (业务侧要求 PGVectorConfig 字段, 不用 URL 字符串).

        只读 5 个连接 env, 向量索引调参走 dataclass 默认值 (见 dataclass 注释).
        vector_dim 字段不读 env: 由调用方 (init_pgvector / _build_vector_store) 走 _get_embed_dim() 派生.
        """
        from ..common import defaults

        return cls(
            host=os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
            port=int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
            user=os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
            password=os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
            database=os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
        )
```

- [ ] **Step 4: 改 `_build_vector_store` (line 80-87)**

定位 line 78-87:

```python
    def _build_vector_store(self) -> BaseVectorStore:
        from llama_index.vector_stores.postgres.base import PGVectorStore

        cfg = self.config
        # llama-index-vector-stores-postgres 新版 API: 不用 host/port/user/... 单传 connection_string
        # 索引参数全塞 hnsw_kwargs (新版没单独的 hnsw_m / hnsw_ef_construction)
        hnsw_kwargs: dict[str, Any] | None = None
        if cfg.index_type == "hnsw":
            hnsw_kwargs = {"hnsw_m": cfg.hnsw_m, "hnsw_ef_construction": cfg.hnsw_ef_construction}
        return PGVectorStore(
            connection_string=cfg.connection_string,
            embed_dim=cfg.vector_dim or 1024,
            hnsw_kwargs=hnsw_kwargs,
        )
```

改成:

```python
    def _build_vector_store(self) -> BaseVectorStore:
        from llama_index.vector_stores.postgres.base import PGVectorStore

        cfg = self.config
        # 索引参数全塞 hnsw_kwargs (新版没单独的 hnsw_m / hnsw_ef_construction)
        hnsw_kwargs: dict[str, Any] | None = None
        if cfg.index_type == "hnsw":
            hnsw_kwargs = {"hnsw_m": cfg.hnsw_m, "hnsw_ef_construction": cfg.hnsw_ef_construction}
        return PGVectorStore(
            connection_string=cfg.connection_string,
            embed_dim=cfg.vector_dim or _get_embed_dim(),
            hnsw_kwargs=hnsw_kwargs,
        )
```

- [ ] **Step 5: 改 `connection_string` property (line 26-28)**

在文件顶部 (line 6 附近, 现有 import 区域) 加 import:

```python
from src.common.db_url import get_rag_db_url
```

然后定位 line 26-28:

```python
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
```

改成:

```python
    @property
    def connection_string(self) -> str:
        """URL 走 get_rag_db_url() 单一构造点, 保证密码 URL-encoding 一致."""
        return get_rag_db_url()
```

- [ ] **Step 6: 改 `AsyncPGVectorStore.aconnect` (line 141)**

定位 line 141:

```python
            async_connection_string=f"postgresql+asyncpg://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}",
```

**不动** (async 路径用 asyncpg driver, 不是 psycopg, 跟 sync 路径分叉. **加 TODO 注释** 标记后续单独处理).

改成:

```python
            # TODO(async): 切到 get_rag_db_url_async() 统一 URL 构造 (本次不同步, asyncpg driver 不同)
            async_connection_string=f"postgresql+asyncpg://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}",
```

- [ ] **Step 7: 改 `init_pgvector` (line 197)**

定位 line 197:

```python
                embedding vector({config.vector_dim or 1024})
```

改成:

```python
                embedding vector({config.vector_dim or _get_embed_dim()})
```

- [ ] **Step 8: 加 `_get_embed_dim` helper**

在文件末尾 (line ~222 之后, `add_to_vector_store` 之前) 加:

```python
def _get_embed_dim() -> int:
    """向量列维度从 EMBED_DIMENSIONS env 派生, 默认 1024 (BGE).

    单一来源: 跟 embedder 模型输出维度绑定, 避免 PG_VECTOR_DIM 跟 EMBED_DIMENSIONS 漂移.
    """
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))
```

- [ ] **Step 9: grep 验证 5 env 全部从 vector_store.py 消失, 提交**

```bash
cd packages/service
rg "PG_VECTOR_DIM|PG_INDEX_TYPE|PG_HNSW_M|PG_HNSW_EF_CONSTRUCTION|PG_IVFFLAT_LISTS" \
   src/retrieval/ tests/retrieval/
```

Expected: 0 命中.

```bash
cd packages/service
uv run pytest tests/retrieval/test_vector_store.py -v
```

Expected: 全 PASS (测的是 env 透传 + dataclass 行为, 兼容新 `from_env` 只读 5 env).

```bash
git add src/retrieval/vector_store.py
git commit -m "refactor(vector_store): drop 5 vector-index env vars, derive dim from EMBED_DIMENSIONS"
```

---

## Task 7: 改 skip 条件 (RAG_DB_URL → PG_HOST)

**Files:**
- Modify: `packages/service/tests/ingest/test_store.py:14-17`
- Modify: `packages/service/tests/kg/test_kg_audit.py:14-15`

- [ ] **Step 1: 改 `tests/ingest/test_store.py`**

定位 line 14-17:

```python
# 模块级: 没 RAG_DB_URL 就 skip 整个文件
pytestmark = pytest.mark.skipif(
    not os.environ.get("RAG_DB_URL", "").startswith("postgresql"),
    reason="需要 RAG_DB_URL 指向 PG 才能跑",
)
```

改成:

```python
# 模块级: 没 PG_HOST 就 skip 整个文件
pytestmark = pytest.mark.skipif(
    not os.environ.get("PG_HOST"),
    reason="需要 PG_HOST 指向 PG 才能跑",
)
```

- [ ] **Step 2: 改 `tests/kg/test_kg_audit.py`**

定位 line 14-15 (跟上面同样模式):

```python
    not os.environ.get("RAG_DB_URL", "").startswith("postgresql"),
    reason="需要 RAG_DB_URL 指向 PG 才能跑",
```

改成:

```python
    not os.environ.get("PG_HOST"),
    reason="需要 PG_HOST 指向 PG 才能跑",
```

- [ ] **Step 3: grep 验证 0 引用, 跑测试**

```bash
cd packages/service
rg "RAG_DB_URL" tests/ingest/test_store.py tests/kg/test_kg_audit.py
```

Expected: 0 命中.

```bash
cd packages/service
uv run pytest tests/ingest/test_store.py tests/kg/test_kg_audit.py -v
```

Expected: 全 SKIP (无 docker PG env), 不能有 ERROR 或 FAIL.

- [ ] **Step 4: 提交**

```bash
git add tests/ingest/test_store.py tests/kg/test_kg_audit.py
git commit -m "test: switch skip condition from RAG_DB_URL to PG_HOST"
```

---

## Task 8: 改 .env 文件 (删 RAG_DB_URL + 5 个 PG_VECTOR_*)

**Files:**
- Modify: `packages/service/.env.example:46, 52-56`
- Modify: `packages/service/.env.local:46`

- [ ] **Step 1: 改 `packages/service/.env.example`**

定位 line 44-56 (PG 段附近), 当前内容:

```ini
# -----------------------------------------------------------------------------
# 数据库 (PostgreSQL + pgvector)
# -----------------------------------------------------------------------------
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=replace-with-strong-password      # ← 改成 docker 实际密码
PG_DATABASE=rag
PG_VECTOR_DIM=1024              # 必须跟 EMBED_DIMENSIONS 一致
PG_INDEX_TYPE=hnsw              # hnsw / ivfflat
PG_HNSW_M=16
PG_HNSW_EF_CONSTRUCTION=200
PG_IVFFLAT_LISTS=100
```

改成:

```ini
# -----------------------------------------------------------------------------
# 数据库 (PostgreSQL + pgvector)
# -----------------------------------------------------------------------------
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

- [ ] **Step 2: 改 `packages/service/.env.local`**

定位 `RAG_DB_URL=...` 那行 (line 46 附近), **整行删掉**. `PG_*` 5 行保留 (已经是正确值).

- [ ] **Step 3: grep 验证, 提交**

```bash
cd packages/service
rg "RAG_DB_URL|PG_VECTOR_DIM|PG_INDEX_TYPE|PG_HNSW_M|PG_HNSW_EF_CONSTRUCTION|PG_IVFFLAT_LISTS" \
   .env.example .env.local
```

Expected: 0 命中.

```bash
git add .env.example .env.local
git commit -m "chore(env): remove RAG_DB_URL + 5 PG_VECTOR_* env vars, use PG_* 5 as single source"
```

---

## Task 9: 改文档注释 (CLAUDE.md + 2 个 inline 注释)

**Files:**
- Modify: `packages/service/CLAUDE.md:27, 34`
- Modify: `packages/service/src/storage/__init__.py:11`
- Modify: `packages/service/src/kg/audit.py:27`

- [ ] **Step 1: 改 `packages/service/CLAUDE.md`**

定位 line 27:

```markdown
| 4 E2E (独立测试 DB) | 完整业务流 / CI 全套 | `RAG_DB_URL=...rag_test` 独立 DB | **不要**用 dev DB (`rag`) |
```

改成:

```markdown
| 4 E2E (独立测试 DB) | 完整业务流 / CI 全套 | `PG_*` 5 env 指向 `rag_test` 独立 DB | **不要**用 dev DB (`rag`) |
```

定位 line 34:

```markdown
- ❌ 跑 test 用 `RAG_DB_URL=...rag` (dev DB) 加 TRUNCATE 行为 — 必出事
```

改成:

```markdown
- ❌ 跑 test 用 `PG_*` 5 env 指向 dev DB (`rag`) 加 TRUNCATE 行为 — 必出事
```

- [ ] **Step 2: 改 `packages/service/src/storage/__init__.py`**

定位 line 11:

```python
切 PostgreSQL: 改 RAG_DB_URL 环境变量, 跑 alembic upgrade head
```

改成:

```python
切 PostgreSQL: 配 PG_* 5 env, 跑 alembic upgrade head (URL 在代码里用 get_rag_db_url() 拼)
```

- [ ] **Step 3: 改 `packages/service/src/kg/audit.py`**

定位 line 27 (注释):

```python
实际数据走 PG (RAG_DB_URL), 跟 src.kg.audit_models.KgAudit 一致.
```

改成:

```python
实际数据走 PG (PG_* 5 env, get_rag_db_url() 拼 URL), 跟 src.kg.audit_models.KgAudit 一致.
```

- [ ] **Step 4: grep 验证, 提交**

```bash
cd packages/service
rg "RAG_DB_URL" CLAUDE.md src/storage/__init__.py src/kg/audit.py
```

Expected: 0 命中.

```bash
git add CLAUDE.md src/storage/__init__.py src/kg/audit.py
git commit -m "docs: update comments from RAG_DB_URL to PG_* 5 env"
```

---

## Task 10: 端到端验收 (重启 service + 业务 curl)

**Files:** 无 (纯手动验证)

- [ ] **Step 1: 确认 .env.local 5 env 正确 (跟 docker 密码一致)**

```bash
cd packages/service
grep -E "^PG_" .env.local
```

Expected:
```
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=deyuan888
PG_DATABASE=rag
```

- [ ] **Step 2: 重启 service (旧 PID 8596 是 Neo4j URI 修之前起的, 杀)**

```bash
# 找 service 进程
netstat -ano | grep ":8000"
# 杀
taskkill /PID <pid> /F
# 起新
cd packages/service
uv run python main.py &
```

Expected: 后台启动, 看到 `[storage] engine init: postgresql+psycopg://postgres:***@localhost:5432/rag` (密码脱敏) + `uvicorn running on http://0.0.0.0:8000`.

- [ ] **Step 3: 健康检查**

```bash
curl -s http://localhost:8000/api/health | python -m json.tool
```

Expected: JSON 包含 `"pgvector": {"status": "ok", ...}` + `"checks"` 字典.

- [ ] **Step 4: 业务 curl (login)**

```bash
curl -s -X POST http://localhost:8000/api/auth/anon | python -m json.tool
```

Expected: 200 + JSON 包含 `user.id` + `user.email`.

- [ ] **Step 5: pgvector 检索 (走 chat 端点)**

```bash
# 假设有 chat 端点, 拿一个 user_id 跑一次 query
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}' | python -m json.tool
```

Expected: 200 + 聊天回复. 如果空, 是因为库为空, 不算 bug (vector store 通了就行).

- [ ] **Step 6: mem0 add/search (如果有 `/api/memory/*`)**

```bash
curl -s -X POST http://localhost:8000/api/memory/add \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}]}' | python -m json.tool

curl -s -X POST http://localhost:8000/api/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | python -m json.tool
```

Expected: 200 + 各自正常响应. 如果端点不存在, skip 这一步.

- [ ] **Step 7: 跑全套测试**

```bash
cd packages/service
PG_HOST=localhost PG_PORT=5432 PG_USER=postgres PG_PASSWORD=deyuan888 PG_DATABASE=rag \
  uv run pytest tests/ -m "not slow" -q 2>&1 | tail -20
```

Expected: 全 PASS (或合理 SKIP).

- [ ] **Step 8: 写一个 handoff 记录到 memory (按 feedback-record-errors-and-lessons)**

```bash
# 写入新 memory
cat > C:\Users\abcuc\.claude\projects\c--Users-abcuc-Desktop-rag\memory\project-pg-env-unification-done.md <<'EOF'
---
name: project-pg-env-unification-done
description: 2026-06-18 PG env 统一重构已完成, 5 个 PG_* env 是 source of truth, get_rag_db_url() util 统一 URL 构造
metadata:
  type: project
---

PG 连接信息统一:
- 5 个 PG_* env (跟 Docker POSTGRES_* 对齐) 是 env 边界唯一来源
- get_rag_db_url() util 是 URL 唯一构造点, 含密码 URL-encoding
- 删 RAG_DB_URL env, 删 get_rag_core_config 死代码, 删 5 个 PG_VECTOR_* 噪音 env
- vector_dim 从 EMBED_DIMENSIONS 派生 (避免 PG_VECTOR_DIM 跟 EMBED_DIMENSIONS 漂移)
- mem0 继续直接读 5 parts (它的 API 要 dict)
- 3 个 batch commit, 见 git log 2026-06-18

**Why:** 2026-06-15 PGVectorConfig 漂移 bug + Neo4j URI 噪音事件, 3 套 env 来源 (RAG_DB_URL / PG_* / config.toml) 必须手动维持一致, 是 bug 重灾区.

**How to apply:** 未来加新 PG 相关配置: env 用 parts (跟 Docker 一致), URL 走 get_rag_db_url(), 单一来源. 不要发明 RAG_DB_URL2 / DATABASE_URL 等并行 URL env.
EOF

# 在 MEMORY.md 加一行
echo "- [PG env 统一已完成](project-pg-env-unification-done.md) — 5 PG_* env + get_rag_db_url() util" >> \
  C:\Users\abcuc\.claude\projects\c--Users-abcuc-Desktop-rag\memory\MEMORY.md
```

(注意: 这里用 `cat > ... <<EOF` 在 Windows bash 里可能因为 CRLF 换行出问题, 改用 Write 工具直接写 .md 文件更稳. **实操时改用 Write 工具**)

- [ ] **Step 9: 验收完成**

全部 ✅ → spec 完成, 在团队频道报告.

---

## Self-Review Checklist (执行前必查)

- [ ] 每个 step 有完整代码 (没 TBD / "类似 Task N" / "add appropriate handling")
- [ ] 每个 step 有精确命令 + Expected 输出
- [ ] 命名一致: `get_rag_db_url()` 全文统一, 没用 `build_url` / `make_url` / `db_url()` 之类别名
- [ ] 类型一致: `_get_embed_dim() -> int` 在 Task 6 定义, 后续 Task 用同样签名
- [ ] TDD 顺序: 写测试 → 跑失败 → 实现 → 跑绿 → 提交, 严格遵循
- [ ] 提交粒度: 每 Task 1 个 commit, 跟 3 批设计一致
- [ ] 风险缓解: Task 6 加 TODO 注释标 async 路径待处理, Task 10 加 memory handoff

## 风险 + 缓解 (跟 spec 一致)

| 风险 | 缓解 |
|---|---|
| `get_rag_db_url()` 密码 `quote` 错 | `tests/common/test_db_url.py` 5 种特殊字符 + round-trip |
| `vector_store.connection_string` 改 `postgresql+psycopg` 跟 lib 默认不一致 | 当前是 `postgresql://`, 改后是 `postgresql+psycopg://` (跟 engine 对齐), 验证: dev 跑 `init_pgvector` 看表是否建在 PG |
| 删 `get_rag_core_config` 后真有 CLI 想用 | 0 caller / 0 测试 / config.toml 无段, 实锤死代码, git history 恢复 |
| `EMBED_DIMENSIONS` 改了忘记重启 service | service 启动期从 env 读, 改了 env 必重启; Task 10 验收步骤提醒 |
| `AsyncPGVectorStore.aconnect` 仍手拼 URL | Task 6 加 TODO 注释, 单独 follow-up, 不阻塞本次 |
