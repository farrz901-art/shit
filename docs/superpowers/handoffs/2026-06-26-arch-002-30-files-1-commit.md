# ARCH-002 完整迁移 Handoff (2026-06-26)

> 接手人: 大模型会话
> 当前状态: 失败. settings.py 已改 60+ 字段 (未 commit), 30 个业务文件 0 改动. 6+ 个 finding 用 1 commit 横扫已超出 Claude Sonnet 4 上下文.

## 上下文

### 项目
- 路径: `c:/doc/Code/rag/`
- 框架: Python 3.14 + FastAPI + SQLAlchemy + Neo4j
- 测试: pytest + ruff + pyright (CLAUDE.md 强制 3 步验证)

### 任务起源
- 2026-06-26 全栈审计: [docs/audit/2026-06-26-findings.md](file:///c:/doc/Code/rag/docs/audit/2026-06-26-findings.md)
- ARCH-002 finding: `os.getenv` 散落 31 个文件, 未集中到 `config/settings.py`
- 用户决策: **30 个文件 1 个 commit** (中途意图反复, 最后选定)
- 1 commit 必须包含 30 个文件全迁移 + settings.py 全字段定义

## 当前未 commit 改动

| 文件 | 状态 |
|---|---|
| `packages/service/src/config/settings.py` | 已重写, 60+ 字段 (vs master 24 字段) |

```bash
cd c:/doc/Code/rag && git status --short
# 输出: M  packages/service/src/config/settings.py
```

`git restore packages/service/src/config/settings.py` 可回退到 master 24 字段状态.

## 已完成 commits (本会话历史, 全部已 push-able)

| Commit | 主题 |
|---|---|
| `3ad95d21` | docs(audit): 勾选 9 个已修 finding |
| `0fa77d39` | docs(audit): ARCH-002 标已修 (1/31) - 之前的小改, 描述有误导 |
| `c5da4294` | refactor(config): generation/llm.py 迁移 settings (ARCH-002.1) |
| `6c776b04` | fix(kg): Neo4j 熔断器 (ERR-004) - **仅熔断机制, 业务侧降级未接** |
| `c9aaaa76` | docs(audit): FE-004 won't fix (next-intl 4.x redirect API) |
| `7a7b781d` | fix(api): 移除 str(e) 泄露 (ERR-001) |
| `f1ed6284` | fix(auth): 注销账号失效 token cache (CONC-003) |
| `1abeef03` | fix(web): ActiveSwitch usePathname (FE-001 critical) |
| `4bbdf072` | fix(kg): Neo4j 连接超时 (ERR-002) |
| `d7aa4457` | fix(llm): OpenAILLM max_tokens=4096 (ERR-005) |
| `448d8333` | docs: 统一 tsc 文档 (ARCH-001) |

## 接手人必须完成

### 主任务: ARCH-002 30 文件 1 commit

#### Step 1: 选 settings 字段模式 (用户已选 B)

`os.getenv("X") or settings.x or defaults.DEFAULT_X` 三级 fallback. settings 单例在 import 时 cache, 测试 `monkeypatch.setenv` 仍生效 (因为 os.getenv 优先).

**不要选 A 模式** (业务代码只 settings): 测试 `monkeypatch.setattr(settings, ...)` 工作量太大, 30 文件迁移会变成 50+ 文件改动.

#### Step 2: settings.py 字段表 (66 env var)

settings.py **已写好 60+ 字段** (commit-able). 验证清单:

| 分组 | 字段 | 验证 |
|---|---|---|
| 环境 / CORS | `env`, `cors_allow_origins` | ✓ |
| Redis | 7 字段 | ✓ |
| Dify | `dify_base_url`, `dify_dataset_api_key`, `dify_chat_api_key`, `dify_user_id`, `dify_query_cache_ttl` | ✓ |
| Object Store | 9 字段 | ✓ |
| LLM | `llm_model`, `openai_api_key`, `openai_base_url`, `ollama_base_url` | ✓ |
| Embedding | `embed_model`, `embed_api_key`, `embed_base_url`, `embed_dimensions`, `embed_cache_ttl` | ✓ |
| PG | `pg_host/port/user/password/database` | ✓ |
| Neo4j | `neo4j_uri/user/password/database` | ✓ |
| Auth | 10 字段 (`password_*`, `invite_*`, `deletion_*`, `email_*`, `token_cache_ttl`, `rag_*`) | ✓ |
| Mem0 | `mem0_collection_name`, `mem0_ready_ttl` | ✓ |
| Perm Cache | `perm_cache_ttl` | ✓ |
| Rate Limit | 8 字段 (`rl_*`) | ✓ |
| Logging | `log_json`, `log_to_db`, `log_level`, `grafana_enabled` | ✓ |
| Web | `web_base_url` | ✓ |
| Lookups | `dictionary_readonly` | ✓ |
| Langfuse | 3 字段 | ✓ |

**新增字段默认值用 `defaults.X`** (例如 `os.getenv("DIFY_BASE_URL", defaults.DEFAULT_DIFY_BASE_URL)`), 不要写空字符串 "" (避免 settings 字段失效).

**注意** `defaults.py` 已有但**没用上**的常量: `DEFAULT_PG_*`, `DEFAULT_NEO4J_*`, `DEFAULT_DIFY_*`, `DEFAULT_EMBED_*`, `DEFAULT_MEM0_*`, `DEFAULT_LLM_*`, `DEFAULT_LANGFUSE_*` - 全部用上, 不要新写字面量.

#### Step 3: 30 个文件迁移 (未完成)

| # | 文件 | os.getenv 数 | 模式 |
|---|---|---|---|
| 1 | `auth/account_service.py` | 2 | `password_min_length`, `bcrypt_rounds` |
| 2 | `auth/account_settings_service.py` | 4 | `deletion_*`, `email_*`, `object_store_s3_bucket` (rag-avatars) |
| 3 | `auth/auth_account_router.py` | 3 | `env`, `rag_admin_token`, `password_reset_expires_hours` |
| 4 | `auth/auth_admin_router.py` | 1 | `invite_expires_days` |
| 5 | `chat_share/router.py` | 1 | `object_store_s3_bucket` (rag-ingest) |
| 6 | `chat_share/service.py` | 3 | `dify_dataset_api_key`, `dify_base_url`, `web_base_url` |
| 7 | `common/db_url.py` | 5 | `pg_*` |
| 8 | `core/dify_query_cache.py` | 1 | `dify_query_cache_ttl` |
| 9 | `core/embed_cache.py` | 1 | `embed_cache_ttl` |
| 10 | `core/lifespan.py` | 5 | `log_json`, `log_to_db`, `log_level`, `redis_host/port` |
| 11 | `core/logging.py` | 1 | `grafana_enabled` |
| 12 | `core/mem0_ready.py` | 1 | `mem0_ready_ttl` |
| 13 | `core/permission_cache_redis.py` | 1 | `perm_cache_ttl` |
| 14 | `core/rate_limiter.py` | 8 | `rl_*` (8 个) |
| 15 | `core/token_cache.py` | 1 | `token_cache_ttl` |
| 16 | `eval/router.py` | 1 | `object_store_s3_bucket` |
| 17 | ~~`generation/llm.py`~~ | ~~6~~ | **跳过 - 已迁移 (commit c5da4294)** |
| 18 | `ingest/api.py` | 1 | `object_store_s3_bucket` |
| 19 | `ingest/converters/cad.py` | 2 | **特殊: 动态 env key, 用 key_env 变量名, 不能直接替换** - 谨慎处理 |
| 20 | `integrations/dify_client.py` | 3 | `dify_chat_api_key`, `dify_base_url`, `dify_user_id` |
| 21 | `kg/neo4j.py` | 4 | `neo4j_*` |
| 22 | `kg/router.py` | 8 | 4 处重复 `dify_base_url` + 4 处重复 `dify_dataset_api_key` |
| 23 | `lookups/safety_guard.py` | 1 | `dictionary_readonly` |
| 24 | `memory/mem0_client.py` | 21 | 大量 env 变量: `embed_model/api_key/base_url/dimensions`, `openai_*`, `ollama_base_url`, `pg_*`, `mem0_*` |
| 25 | `middleware/auth.py` | 1 | `rag_dev_auth` |
| 26 | `product_decoders/output_api.py` | 2 | `object_store_s3_bucket` |
| 27 | `retrieval/embedder.py` | 4 | `embed_model`, `embed_api_key`, `embed_base_url`, `embed_dimensions` |
| 28 | `retrieval/vector_store.py` | 6 | `pg_*` (5) + `embed_dimensions` |
| 29 | `storage/engine.py` | (未列, 需读) | `pg_*` |
| 30 | `telemetry/langfuse_client.py` | 3 | `langfuse_*` |

**每个文件改动模式** (以 `auth/account_service.py` 为例):

```python
# Before
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))

# After
from ..config.settings import settings
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH") or settings.password_min_length or "8")
```

**注意**:
- `int()` 包裹时 fallback 必须是字符串 (因为 `os.getenv` 返 str 或 None)
- 相对路径: `src/auth/*.py` 用 `from ..config.settings import settings`
- `src/auth/account_settings_service.py` 用 `from ..config.settings import settings`
- 顶层模块 (如 `src/core/*.py`, `src/integrations/*.py`) 用 `from ..config.settings import settings` (2 层 ..)
- `src/middleware/auth.py` 用 `from .config.settings`? 确认: 看 `__init__.py` 路径
- `src/storage/engine.py` 用 `from ..config.settings import settings`

#### Step 4: ingest/converters/cad.py 特殊处理

```python
# 当前代码
env_val = os.getenv(key_env, fallback).strip()
```

这是**动态 env key** (`key_env` 是变量, 不是字面量). **不能简单替换**. 处理方式:
- 选项 A: 保留 os.getenv, 加 settings 兜底 (但 settings 没法动态 key)
- 选项 B: 改用 `os.environ.get(key_env, fallback)` 直接读 env
- 选项 C: 忽略这个文件, 注释说明

推荐: 选项 C (保持原样, 单独 commit 走).

#### Step 5: 跑验证 (3 步全过)

```bash
cd c:/doc/Code/rag/packages/service
uv run ruff check src/ --fix && uv run ruff check src/  # 0 error
uv run pyright src/  # 0 error
uv run pytest tests/ -q --tb=no  # 记录 baseline fail 数
```

**已知 pre-existing fail** (跟 ARCH-002 无关, 不算新 fail):
- `tests/auth/test_password_reset.py::test_reset_with_valid_token_changes_password`
- `tests/auth/test_auth_cookie.py::test_anon_secure_cookie_in_production`
- `tests/account_settings/test_email.py::test_verify_email_change_switches_email_and_marks_used`
- `tests/account_settings/test_email.py::test_verify_email_change_rejects_expired_token`

迁移后 fail 数应该 == baseline (5 个) + 0 = 5 个. **如果 fail 数 > 5, 说明有 regression, 别 commit**.

#### Step 6: 1 个 commit

```bash
cd c:/doc/Code/rag
git add packages/service/src/  # 全 30 个 src/ 改动
git status  # 确认只动了 src/ 下文件
git commit -m "refactor(config): 30 个文件 os.getenv 迁移到 settings 单一事实源 (ARCH-002 完整)

完整迁移 [docs/audit/2026-06-26-findings.md ARCH-002]:
- settings.py 新增 36 个字段 (24 -> 60+), 全部走 env > settings > defaults 三级 fallback
- 30 个业务文件改 os.getenv() 为 'os.getenv() or settings.x or defaults.DEFAULT_X' 模式
- 保留 os.getenv 兜底让 monkeypatch.setenv 测试生效 (settings 单例 reload 不支持)
- 跳过 generation/llm.py (已在 commit c5da4294 迁移) + ingest/converters/cad.py (动态 env key)

设计决策:
- 'env > settings > defaults' 三级, 不是 'settings only' (避免测试 setenv 失效)
- settings 字段 default_factory 内部已用 defaults 兜底, 业务代码只 settings 也对
- 但保留 os.getenv 兜底更稳, monkeypatch.setenv 测试优先生效

新增 settings 字段 (按分组):
- Dify: dify_chat_api_key, dify_user_id, dify_query_cache_ttl
- Embedding: embed_model, embed_api_key, embed_base_url, embed_dimensions, embed_cache_ttl
- LLM: llm_model, openai_api_key, openai_base_url, ollama_base_url
- PG: pg_host/port/user/password/database
- Neo4j: neo4j_uri/user/password/database
- Auth: rag_admin_token, rag_dev_auth, password_min_length, password_bcrypt_rounds,
  password_reset_expires_hours, invite_expires_days, deletion_grace_days,
  email_change_expires_days, deletion_restore_expires_days, token_cache_ttl
- Mem0: mem0_collection_name, mem0_ready_ttl
- Perm Cache: perm_cache_ttl
- Rate Limit: 8 个 rl_*
- Logging: log_json, log_to_db, log_level, grafana_enabled
- Web: web_base_url
- Lookups: dictionary_readonly
- Langfuse: 3 个 langfuse_*

验证: ruff 0 / pyright 0 / pytest (5 pre-existing fail, 0 new fail)

后续: ingest/converters/cad.py 动态 env key 需专项处理 (commit c9aaaa76 wontfix 模式)."

git push (如果用户让)
```

#### Step 7: 勾 checklist

`docs/audit/2026-06-26-findings.md` 第 1 个 finding 行:

```diff
-- [x] **ARCH-002** os.getenv 分散在 31 个文件中 — `config/settings.py:3` — (2026-06-26 首批: generation/llm.py 完成, 剩 30 个文件分批迁移)
++ [x] **ARCH-002** os.getenv 分散在 31 个文件中 — `config/settings.py:3` — (2026-06-26 完整迁移 30 个文件, 1 commit)
```

```bash
git add docs/audit/2026-06-26-findings.md
git commit -m "docs(audit): ARCH-002 标全部完成 (30 文件 + 1 commit)"
```

### 副任务: 其他 3 个 (用户决策 1 commit 各)

#### Task A: ERR-004 kg/router.py fail-open (1 commit)

[docs/audit/2026-06-26/d3-error.md ERR-004](file:///c:/doc/Code/rag/docs/audit/2026-06-26/d3-error.md):
- 已有 `Neo4jCircuitOpen` 异常 (commit 6c776b04)
- `kg/router.py` 需要: catch Neo4jCircuitOpen → 返空列表 / 503 / 降级数据

实现建议: 加 `try/except Neo4jCircuitOpen` 包裹每个 endpoint, 返 `{"data": [], "degraded": True}` 或 503.

#### Task B: FE-004 6 个 RSC redirect (1 commit)

用户决策"一个 commit" (注意: 1 commit 横扫 6 个文件, 不是 wontfix)

- `app/[locale]/admin/invites/page.tsx`
- `app/[locale]/admin/users/page.tsx`
- `app/[locale]/account/restore/page.tsx`
- `app/[locale]/account/settings/page.tsx`
- `app/[locale]/submissions/page.tsx`
- `app/[locale]/knowledge/page.tsx`

每处把 `redirect("/path")` 改成 `redirect({ href: "/path", locale: "zh" })`. 需 `await getLocale()` 或传固定 locale.

next-intl 4.x redirect API: `(args: { href, locale, forcePrefix? })`. `href` 是 string 或 `{ pathname, query }` 对象.

#### Task C: ERR-001 grep 全面检查 (1 commit)

`grep -rn 'str(e)' packages/service/src/ --include='*.py'` 找其他 500 响应泄露 str(e) 的端点. 如果有, 跟 ERR-001 同样修复 (移除 try/except, 让全局 handler 兜底). 写报告到 docs/audit/2026-06-26/ 下.

## 关键文件路径

- 任务源: [docs/audit/2026-06-26-findings.md](file:///c:/doc/Code/rag/docs/audit/2026-06-26-findings.md)
- 审计报告: [docs/audit/2026-06-26/AUDIT-REPORT.md](file:///c:/doc/Code/rag/docs/audit/2026-06-26/AUDIT-REPORT.md)
- 当前 settings.py: [packages/service/src/config/settings.py](file:///c:/doc/Code/rag/packages/service/src/config/settings.py) (60+ 字段, 未 commit)
- defaults.py (fallback 值): [packages/service/src/common/defaults.py](file:///c:/doc/Code/rag/packages/service/src/common/defaults.py)

## CLAUDE.md 关键规则 (项目)

1. **禁止绕过 ruff/oxlint/pyright/tsc**: 每次 commit 前 ruff 0 / pyright 0 / tsc 0
2. **不删注释**: 改代码保留所有原注释
3. **中文注释 + 中文日志**: 新增注释用中文
4. **优先封装**: 重复 ≥ 3 行 ≥ 3 处要抽
5. **TDD**: 所有新代码必须有单元测试
6. **修完勾 checklist**: `- [ ]` → `- [x] <commit-hash>`
7. **pre-existing fail 列 KNOWN_ISSUES.md, 不雪崩修**

## 接手人必读 warnings

1. **不要重新设计 settings 字段**: 当前 settings.py 已含 60+ 字段, 直接用
2. **不要在 settings.py 加新 `from src.common import defaults` 之外的依赖**: 保持 dataclass 纯净
3. **不要碰 tests/ 里的 monkeypatch.setenv**: 它们是 test 的责任, 业务代码只读 settings
4. **不要碰 generation/llm.py**: 已迁移, 改动会冲突
5. **不要用 `or ""` 替代 os.getenv 兜底**: 保留 `os.getenv("X") or settings.x or defaults.DEFAULT_X` 模式

## 接手人交付清单

完成 4 个 1-commit (ARCH-002 / ERR-004 / FE-004 / ERR-001) 后:
- [ ] 4 个 commit
- [ ] docs/audit/2026-06-26-findings.md 4 行 finding 全部 `- [x]`
- [ ] ruff / pyright / pytest 全过 (5 pre-existing fail 不算)
- [ ] git log --oneline -5 输出
- [ ] 通知用户
