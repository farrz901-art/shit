# 后端局部约定

## API规范

- 每个 router 函数加 docstring——FastAPI 会原样渲染成接口说明。
- Pydantic model 用 Field(description=...)——字段说明会进 schema。已在 app.py:27-40 这么做了。
- @router.post(..., response_model=DecodeResponse, summary="...")——summary 是接口标题，description 是详细说明。
- @router.get(..., tags=["知识图谱"])——按 tag 分组，文档侧边栏按业务模块折叠。

## 测试规范

1. 使用 pytest-mock 进行 Mock
2. 不要连接真实数据库
3. 数据库 session 通过参数注入，测试时传 Mock 对象
4. 只测试业务逻辑，不测试 SQL 细节
5. 覆盖正常路径和异常路径

## 测试隔离 4 模式 (2026-06-16 强制)

写新 test 前, **先确认用哪个模式**, 跟现有 100 个 test 保持一致:

| 模式 | 适用 | Fixture | 不该做 |
|---|---|---|---|
| 1 纯单测 (mock) | ORM 字段 / Pydantic / 纯函数 / util | 0 PG 依赖, 用 `monkeypatch` / `unittest.mock` | **不要**连 PG |
| 2 集成 (事务回滚) | repo CRUD / SQL 行为 / FK 约束 | `db_session` (opt-in, 自动 rollback) | **不要** TRUNCATE / autouse 副作用 |
| 3 迁移 (临时 schema) | alembic DDL / schema 完整性 | (本期未实现, 后续 spec 写 `tmp_pg_schema`) | **不要**用公共 public schema |
| 4 E2E (独立测试 DB) | 完整业务流 / CI 全套 | `PG_*` 5 env 指向 `rag_test` 独立 DB | **不要**用 dev DB (`rag`) |

**反模式 (2026-06-15 事故根因)**:

- ❌ `_truncate_tables` autouse fixture (强制清表, 跟 dev DB 共享必炸数据) — 2026-06-16 已删 (commit 6d319a6)
- ❌ `tests/conftest.py` top-level re-export 让 autouse 跨目录 — 已删
- ❌ 写新 test 时 "凭直觉造 fixture" (应该问: 我用 4 模式里哪个?)
- ❌ 跑 test 用 `PG_*` 5 env 指向 dev DB (`rag`) 加 TRUNCATE 行为 — 必出事

**新 test 选择流程**:

1. 写 test 前问: "我用 4 模式里哪个?"
2. 模式 1: 不连 PG, 用 mock
3. 模式 2: 加 `db_session` fixture (来自 `tests/integration/conftest.py`), 在事务内操作
4. 模式 3: 等后续 spec 实现
5. 模式 4: 等后续 spec + CI 集成

**已知 pre-existing 问题 (handoff 记)**:

- 30+ auth/eval/storage tests 用硬编码 email (alice@x.com 等) + `session_scope()` 直接 commit, 跟 `db_session` 模式不兼容, **本次 spec 不修** — 详见 `docs/superpowers/handoffs/2026-06-16-test-isolation.md`
- 这些 test 在 autouse TRUNCATE 删了之后, 数据冲突暴露, 跟"清空数据库"是**两个独立问题**
- 接手者: 不要在本 spec 修, 另起 spec 处理

新 test 选错模式 → 跟事故 user 复盘, spec [2026-06-16-test-isolation-design.md](../specs/2026-06-16-test-isolation-design.md) §4 种模式看完整对比.

## ObjectStore ABC 使用 (2026-06-16)

### 位置
- ABC: `src/storage/object_store.py`
- 单例: `get_object_store()` from `src.storage`

### 业务调用示例

```python
from src.storage import get_object_store

store = get_object_store()  # env OBJECT_STORE_BACKEND 决定 impl
store.put_bytes(uri, data, mime="...")
store.get_bytes(uri)
store.presign_put(uri)  # MinIO 真签 URL, LocalFS 返 None
store.list_prefix("s3://bucket/inputs/")
```

### URI 规范

- `local://<key>` (例: `local://inputs/abc/foo.pdf`)
- `s3://<bucket>/<key>` (例: `s3://rag-ingest/inputs/abc/foo.pdf`)

URI 字符串是 DB 持久化唯一形式, 业务代码不区分 backend.

### 添加新方法

1. ABC 加 1 个 `@abstractmethod`
2. LocalFS impl + MinIO impl 各实现 1 个
3. 加 1 个测试 (mock store)

## 日志使用约定 (2026-06-17 logging spec)

### 业务代码用 loguru, 不用 stdlib logging

```python
# 旧 (禁用)
import logging
logger = logging.getLogger(__name__)

# 新 (统一)
from loguru import logger

logger.info("operation done user_id={} took={}ms", user_id, took)
logger.warning("retry failed attempt={}", attempt)
logger.opt(exception=True).error("query failed query={}", query)
```

占位符用 `{}` 不用 `%s` (loguru 风格).

### 危险操作必须加 @audited

任何 DELETE / 修改账户 / 修改权限 / 导出数据等加:

```python
from src.core.audit import audited

@router.delete("/foo/{id}")
@audited("foo.delete", target_type="foo")
async def delete_foo(request: Request, id: int, current_user = Depends(...)):
    request.state.audit_ctx.set(target_id=str(id), before={"snapshot": "..."})
    # ... 业务
```

`@audited` 必须接受 `request: Request` 参数.

### PII 字段自动 scrub

`password` / `token` / `api_key` / `secret` / `authorization` / `ssn` 等 18 字段自动 `***REDACTED***` (大小写不敏感).
`user_id` / `email` / `ip` / `request_id` 不算 PII (审计需要).

### 异常处理 (有 global handler)

- 4xx: `raise HTTPException(status_code=404, detail="not found")` → app_logs WARNING
- 5xx: 抛任何 Exception → 全局 handler 接, error_logs ERROR + 返 `{"detail": "Internal server error"}` (不漏 stacktrace)

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): 不连 PG, mock `session_scope` (测试 logging / audit / errors)
- 模式 2 (db_session): 集成测 (测试 log 表 schema / immutability trigger)

## chat_router (2026-06-19 chat spec)

### 已登录用户的聊天历史 CRUD (跟 chat_share 区分)

7 个端点 (`packages/service/src/chat/router.py`):

| Method | Path | 用途 |
|---|---|---|
| POST | /api/chat/conversations | 创建 (title 默认 '新对话') |
| GET | /api/chat/conversations | 列表 (分页 limit/offset, 按 updated_at DESC) |
| GET | /api/chat/conversations/{id} | 详情 (含 messages) |
| PATCH | /api/chat/conversations/{id} | 重命名 (audit "chat.conv.rename") |
| DELETE | /api/chat/conversations/{id} | 软删 (audit "chat.conv.delete", 30d cron hard-delete) |
| GET | /api/chat/conversations/{id}/messages | 单 conv 消息分页 |
| GET | /api/chat/backup | 全量导出 JSON (GDPR) |

### 软删语义 (跟 ChatGPT/Claude 一致)

```sql
DELETE → UPDATE SET deleted_at = NOW()  -- 软删, UI 立即隐藏
cron 30d 后 → DELETE FROM conversations WHERE deleted_at < NOW() - INTERVAL '30 days'  -- 真删
```

### 业务代码用 service 层, 不用裸 SQL

```python
from src.chat import service as svc

# CRUD
conv = svc.create_conversation(user_id=42, title="项目")
convs = svc.list_conversations(user_id=42, limit=20, offset=0)
detail = svc.get_conversation(user_id=42, conv_id="...")

# 软删 / 备份
svc.soft_delete_conversation(user_id=42, conv_id="...")
backup = svc.get_full_backup(user_id=42)

# cron
svc.hard_delete_old_soft_deleted(days=30)
```

### 复用 2026-06-18 Redis

- Token cache 6h (auth): 端点走 resolve_user 自动用
- RateLimiter 5/15min (per IP): 7 端点全受保护 (在 resolve_user 链路里)

### 测试模式 (跟 4 模式一致)

- 模式 2 (db_session): 12 router 测试 + 6 service 测试, 验 7 端点 + 鉴权 + 软删 + cron
- 模式 4 (E2E): Playwright (前端 spec 4 跑端到端)

## Redis 使用约定 (2026-06-18 redis spec)

### 业务代码用 core/redis_client.py facade, 不用 raw aioredis

```python
# 旧 (禁用)
import redis.asyncio as aioredis
r = aioredis.Redis(host=..., port=...)

# 新 (统一)
from src.core.redis_client import safe_get, safe_set, safe_delete, safe_incr

val = await safe_get("rag:foo")
if val is None:
    # cache miss, 走原路径
    val = await db_query()
```

### 6 个 use case 直接 import, 不自己写

| Use case | 函数 | TTL |
|---|---|---|
| Permission 矩阵 | `from src.core.permission_cache_redis import permission_cache` | 60s |
| Auth token | `from src.core.token_cache import get_user_by_token, cache_user_by_token` | 6h sliding |
| IP 限流 | `from src.core.rate_limiter import check_and_increment` | 15min / 1h |
| Mem0 ready | `from src.core.mem0_ready import mark_ready, is_ready` | 1h |
| Dify query | `from src.core.dify_query_cache import get_cached_response, cache_response` | 10min |
| Embedding | `from src.core.embed_cache import get_cached_vector, cache_vector` | 7d |

### Key 规范

- 统一 `rag:` 前缀 + 分域: `rag:perm:matrix`, `rag:auth:tok:...`, `rag:rl:login:1.2.3.4`
- token / cookie 值在 Redis 里存 sha256[:32], 不存原值 (防 dump 泄露)
- 长 key 取 sha256[:16] 前缀 (`rag:embed:abc...`)
- 别用 `KEYS rag:*` 跑生产 (阻塞), 用 `SCAN --pattern "rag:*"`

### 永不抛 + fail-open

所有 Redis 调用经 `safe_*` 函数, 失败返 None / False / 0, 业务侧当 miss 处理.
Redis 挂 = 服务降级 (走原 PG / 进程内存), 不挂服务.

### 限流使用

```python
from src.core.rate_limiter import check_and_increment

@router.post("/login")
async def login(request: Request, ...):
    allowed, _ = await check_and_increment("login", request.client.host)
    if not allowed:
        raise HTTPException(429, "登录请求过于频繁")
    # 业务
```

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): `fakeredis.FakeAsyncRedis` + monkeypatch `get_redis`, 0 真实依赖, 10ms/test
- 模式 4 (E2E): 真 Redis (docker compose), 验证 TTL 过期 / LRU 淘汰, 本期不做 (spec §7)

## 字典使用规范 (2026-06-19 lookup module)

### 业务 enum 必须走 lookup, 不许新增硬编 `StrEnum`

唯一的例外是 LLM 框架 (OpenAI / Anthropic SDK) 强制要求的 enum, 那些必须本地定义 (e.g. response_role / tool_use_block).

业务 enum 改一个值不再发版 — runtime 改 DB + cache invalidate, 5 秒生效. 字典的 value 跟 DB / JSON 完全一致, Pydantic Literal 引用安全.

### 新加字典 5 步流程

1. 改 `src/common/dictionaries_seed.yaml` (出厂种子 + 双语 label)
2. `src/common/dictionaries_enum.py` 加 `_build_enum("Name", "code")` (启动时自动从 yaml 编译, 不手改成员)
3. `_REFERENCE_MAP` (在 `src/lookups/safety_guard.py:46`) 注册新字典的反向引用 `(table, column)`, **不注册则删除时不报引用错误, 可能误删**
4. 跑 `python -m scripts.seed_dictionaries` 同步到 DB
5. 更新 `docs/cookbook/python/lookup.md` 教程 + 通知前端 (`useLookup("新字典 code")` 自动拉)

### DB 是唯一事实源, yaml 仅种子 + 类型提示

- seed 默认 UPSERT, **不覆盖已存在 label** (防 super_admin 后台改的 label 被覆盖)
- 强制重新同步 yaml label: `python -m scripts.seed_dictionaries --force-sync` (危险, 显式 flag, 审计可追)
- 改 yaml 后必须重启服务, `_build_enum` 在 import 阶段编译一次, 不支持 hot reload

### 软删 + 二次确认 + force

- 软删 `is_active=False` + `deprecated_at=NOW()`, 历史数据 refer 仍能查到
- delete 必走 admin API + `X-Confirm-Token` header (16 字符 hex, 1h 小时桶)
- `force=true` 跳过引用检查但仍 audit (action 标 `dictionary.item.delete.forced`)

### 紧急逃生口

- env `DICTIONARY_READONLY=true` (优先级最高, 覆盖字典级 `is_readonly`)
- 字典级 `is_readonly=true` (单字典细粒度)
- 优先级: **env > 字典级 > 业务逻辑**
- env 改了需重启服务 (Python 启动时 `os.getenv`)

### 测试必须 mock, 不连真 PG / Redis

- 用 `unittest.mock.patch("src.lookups.service.session_scope")` 等
- `tests/lookups/` 已有 74 测试, 全部模式 1 mock
- 真实 DB 行为由集成测试 (模式 2 `db_session` fixture) / staging 验证

### 启动顺序 (main.py `_setup_dictionaries`, main.py:55-105)

```
seed → check_consistency → Redis subscriber → warmup_page_keys
```

任一失败按级别处理:

- seed 失败 → WARNING, 不阻塞 (R1 兼容期 DB 表可能没建)
- check_consistency 失败 → RuntimeError, **启动失败** (DB 真缺字典 / yaml 拼错, fail-fast)
- subscriber 失败 → WARNING, 跨进程失效靠 5 分钟 Redis TTL 兜底
- warmup 失败 → WARNING, 用 fallback 8 项 (R1 兼容)

## 代码质量清理总结 (2026-06-19 code-quality spec)

### ruff / pyright 起始 vs 结束

| 工具 | 起始 (master 07bda92) | 结束 (P5) | 减幅 |
|---|---|---|---|
| ruff format | 66 files reformatted | 0 reformatted | -66 (P0) |
| ruff check --fix | 4 errors | 0 errors | -4 (P1) |
| pyright errors | 91 errors | **0 errors** | **-91 (P2a)** |

### pytest 起始 vs 结束

| 指标 | 起始 (P0 前) | 结束 (P5) | 减幅 |
|---|---|---|---|
| Passed | 1071 | **1075** | +4 |
| Failed | 26 | **22** | -4 (修了 4 个: 2 loguru + 1 contract + 1 invite audit) |
| Errors | 38 | 38 | 0 (全部 PG 真连接耗尽 / 主机解析, pre-existing) |

Pre-existing fail 不在本期范围, 见 [`KNOWN_ISSUES.md`](./KNOWN_ISSUES.md). test isolation 跟 dev auth 模式有关, 留给 test-isolation spec 处理.

### pytest-cov 起始覆盖率 (2026-06-19 baseline)

| 维度 | 起始 | 目标 (后续 spec) |
|---|---|---|
| Lines | **74.1%** (5410/7304) | ≥ 80% |
| Branches | 估算 ~70% (1542/2178 含 branch coverage) | ≥ 70% |
| Total stmts | 7304 | - |
| Total branches | 1542 | - |

跑法: `uv run pytest`, addopts 自动加 `--cov=src --cov-report=term-missing/html/lcov`. HTML 报告在 `htmlcov/index.html`.

### 本轮发现 top-10 防再犯守则

1. **测试必须 mock, 不连真 PG/Redis** (老规范). 例子: `tests/test_*.py` 跑必须 0 PG 连接. 检查: `pytest --co -q` 后跑 `pytest -v` 看是否启 db_session.
2. **type: ignore 必须带具体错误码 + 注释**. 不接受裸 `# type: ignore`. P2a 删了 2 条已不需要的 (approvals/models.py), 剩 38 条全合理 (ORM Column 推断 / 第三方库无 stub).
3. **noqa 必须带具体错误码 + 注释**. 项目 20 条全合理 (F401 import 副作用 / ARG001 守卫参数 / BLE001 业务故意 broad).
4. **delete / 改账户 / 改权限 / 导出必须加 @audited 装饰器**. 防误删, 留审计.
5. **alembic 迁移必须可回滚**. 写 migration 时同时写 downgrade, 单测验证.
6. **新加 enum 必须走 lookup 字典**, 禁止新增硬编 `StrEnum` (除 LLM 框架强制要求). 见 `src/lookups/README.md`.
7. **dictionaries_enum.py 必须明文 StrEnum 声明** (不用 functional API), 否则 pyright 看不到成员, 报 70+ reportAttributeAccessIssue. 配合 `_verify_against_yaml()` 启动校验.
8. **删 BFF route 前必跑契约测试** (`pytest tests/test_api_contract.py`). 加新路由后端走 BFF 前, 临时加 `KNOWN_DEAD` 防 contract test 红.
9. **audit_ctx.set 走 \*\*kwargs 展开**, 不能传 `metadata=dict` (`set(*, target_id, **metadata)`).
10. **覆盖率起始基线: 74.1% lines (后端). 后续 spec 加 thresholds 门禁前不强制.**

## 测试隔离强制规范 (2026-06-19 phase2)

- 写新 test 前必须选 4 模式, 默认走模式 1 (mock)
- 禁止任何 TestClient 测试直连 PG/Redis/Neo4j
- 集成测试必须显式 `@pytest.mark.integration`, 否则 CI 自动跳过 (`-m "not integration"`)
- 跑 test 不需要 docker PG/Redis 启动 (模式 1 mock, 模式 2 可选 db_session)
- 全局 autouse fixture: `tests/conftest.py::mock_all_db_connections`
  mock 了 engine/redis/object_store/neo4j/permission_cache


## JSONB 使用规范 (2026-06-25 json-jsonb spec)

### 新列必须 JSONB, 禁止 sa.JSON()

```python
# 旧 (禁用, 跨 dialect 抽象层泄漏)
sa.Column("data", sa.JSON())

# 新 (统一)
from sqlalchemy.dialects.postgresql import JSONB
sa.Column("data", JSONB())
```

测试 `tests/migrations/test_json_jsonb_policy.py` AST 扫所有 migration, 新增 `sa.JSON()` 必 FAIL.

### raw SQL 写 JSONB 列 3 种正确姿势 (任选, 项目内 3 种都有用)

```python
# A. SQL 内 cast (最直观, buyer_profile 用)
text("INSERT INTO buyer_profiles (..., profile_data) VALUES (..., CAST(:data AS jsonb))")
{"data": json.dumps(data)}  # 传字符串, CAST 解析

# B. bindparam 显式标类型 (最 ORM, logging.py 用)
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB
stmt = text("INSERT INTO app_logs (..., context) VALUES (..., :ctx)").bindparams(
    bindparam("ctx", type_=JSONB)
)
{"ctx": dict_value}  # 传 dict, psycopg3 自动 adapt

# C. 业务侧预序列化 + ::jsonb (chat 用)
text("INSERT INTO messages (..., meta) VALUES (..., :meta::jsonb)")
{"meta": json.dumps(meta)}
```

裸 `:p` 传 dict 必抛 `psycopg.ProgrammingError: cannot adapt type 'dict' using placeholder '%s'` -- 测试 `tests/migrations/test_jsonb_raw_sql_cast.py` regex 扫.

### 读 JSONB 列禁止 `json.loads`, 直接当 dict 用

psycopg3 v3 注册了 jsonb loader, 读 JSONB 列 -> dict; 读老 PG json 列 -> str. 项目里 messages.meta 等历史列已迁 JSONB (2026-06-26 migration), 但保留 `_parse_meta()` 兜底, 兼容历史脏数据 + 单测 mock 给 str 也跑.

### psycopg3 v3 adapter 其他注意

- `INET` 列 (audit_logs.ip) 反序列化为 `ipaddress.IPv4Address`, Pydantic v2 不自动 coerce, 业务 stringify 边界
- `UUID` 列自动反序列化, OK
- 任何 PG 特殊类型给 Python 类型, 不能假设 == str

### 排查信号 (3 个错误关键词, 同源)

| 错误关键词 | 一定是 |
|---|---|
| `operator class "jsonb_path_ops" does not accept data type json` | sa.JSON() + JSONB opclass 不匹配 (migration) |
| `TypeError: the JSON object must be str, bytes or bytearray, not dict` | psycopg3 读 jsonb 返 dict, 业务 `json.loads` 误用 |
| `cannot adapt type 'dict' using placeholder '%s'` | raw SQL 没 cast, psycopg3 不知道 jsonb |

完整分析见 [docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md](../../docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md).

## 函数内 import 规范 (2026-07-06 ruff-E402 spec)

ruff `E402` 已启用 (`pyproject.toml [tool.ruff.lint] extend-select = [..., "E402"]`).

### 允许的 3 种函数内 import

必须紧贴函数体顶部, 上方留 1 行空行 + 1 行中文注释说明动机 + `# noqa: E402`:

1. **重依赖 lazy**: 模块加载慢 (langchain_postgres / pynvml / mineru / deepeval) 或启动期不需要
2. **软依赖**: `try / except ImportError` 探测可选库 (langfuse / tqdm / tiktoken)
3. **防循环**: 顶层 import 触发循环依赖链 (auth 模块引用 token_cache, scheduler 引用 chat service)

模板:

```python
def get_vector_store(...):
    # 重依赖 lazy: langchain_postgres 冷启动 1.2s, 非向量路径不需要
    from langchain_postgres import PGVectorStore  # noqa: E402


def optional_langfuse_trace(...):
    # 软依赖: langfuse 未装时降级到本地 logger, 不抛 ImportError
    try:
        from langfuse import Langfuse  # noqa: E402
    except ImportError:
        Langfuse = None


def register_chat_jobs():
    # 防循环: 顶层 from ..chat.service 会触发 import chain
    from ..chat.service import hard_delete_old_soft_deleted  # noqa: E402
```

### 禁止

除上述 3 种外, 函数内 import 必须挪到模块顶部. 实施期按 `grep -rE "^[[:space:]]+(from|import)" packages/service/src/` 全量扫, 逐文件判断.

### 范围

仅治理 `packages/service/src/`. `tests/` 不强制 (mock fixture / `importlib` 动态 / `TYPE_CHECKING` 守卫场景多, 改造价值低). `src/__init__.py` 动态 router 注也保留 (改架构超出本期).

### 历史背景

实施前 src/ 函数内 import 188 处, 实施后预计 ~120 处 (B 类挪顶 12 处 + 防循环 / 重依赖 lazy 合理保留 ~60 处 + 其它 ~50 处逐文件评估). 见 [docs/superpowers/specs/2026-07-06-ruff-e402-design.md](../../docs/superpowers/specs/2026-07-06-ruff-e402-design.md).

## 任务 ID 生成规范 (2026-07-08 task-id spec)

### 任务型 ID 必须走中央 helper, 禁止 inline 生成

```python
# 旧 (禁用, 无可读性 + 散落各处)
task_id = f"pa-{uuid.uuid4().hex[:12]}"

# 新 (统一)
from src.common.task_id import make_task_id, TASK_PREFIX_PRE_ANALYSIS
task_id = make_task_id(TASK_PREFIX_PRE_ANALYSIS)  # pa_20260708143012_a1b2c3
```

### 格式: `{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}`

- 3 段, 2 个下划线分隔: 类型前缀 | 14 位香港时区时间戳 | 24 bit 随机
- 时间戳可读 + 字典序≈时间序; 下划线让 ID 可双击整选 (终端/浏览器)
- 时区用 `src/utils/timezone.py` 的 `HKT`, 跟 DB 存储一致

### 前缀常量唯一事实源 (禁止传字面量)

| 任务类型 | 常量 | 值 |
|---|---|---|
| pre_analysis | `TASK_PREFIX_PRE_ANALYSIS` | `pa` |
| ingest | `TASK_PREFIX_INGEST` | `ig` |
| kg_extract | `TASK_PREFIX_KG_EXTRACT` | `kge` |
| kg_batch | `TASK_PREFIX_KG_BATCH` | `kgb` |

新增任务类型: 在 `src/common/task_id.py` 加 `TASK_PREFIX_*` 常量, 勿在调用方写 `make_task_id("xx")` 字面量.

### 范围与例外

- **只治理任务型 ID** (跑批任务, 用户会在 UI/URL/日志看到)
- **不治理**: DB 自增主键 (evaluations/approvals) / chat UUID / auth token / request_id — 各有其诉求 (安全熵 / DB 语义), 不追求可读
- **存量 ID 不迁移**: 老 `pa-xxx` 与新 `pa_xxx` 共存, 代码对 task_id 无格式校验

## Camelot Borderless 兜底流程 (2026-07-09)

针对 PDF 中**无竖线 borderless 表**的 3 类问题: 漏识别 / 多表合 1 cell / 列错位, 在 `table_extractors/camelot_extractor.py` 落地兜底流程.

### 默认 backend 仍是 pymupdf

Admin 选 `table_backend="camelot"` 才走下面这套流程. `factory.get_table_extractor` 路由到 `_CamelotFallbackWrapper`, wrapper 内部调 `CamelotTableExtractor.extract_with_fallback`.

### ml flavor 推荐值 (硬阈值, admin 无需懂)

`_FLAVOR_DEFAULTS["ml"]` 写死以下推荐值, `_run_camelot_single_page` ml 分支显式 `setdefault` 注入:

| 参数 | 值 | 来源 |
|---|---|---|
| `detection_threshold` | 0.3 | Camelot 默认 0.5 太严, borderless 召回差 |
| `structure_threshold` | 0.4 | DETR 内部 cell 识别比 detection 准, 略高于 detection |
| `row_tol` | 5 | 跟 stream 对齐, 1-2 行小表也能识别 |

admin 显式传值时 user params 优先 (用 `setdefault` 而非覆盖).

### 页间并发

`ThreadPoolExecutor(max_workers=4)` 默认. admin 可 `params={"max_page_workers": 8}` 覆盖. 失败兜底: 任一页抛异常 → 该页返 `[]`, 不阻断其他页.

### 单页 0 表门控

`_extract_single_page` 调度顺序: **lattice → 0 表? → ml → 仍 0 表? → network → stream**. 每个 flavor 返非空就停. ml 走 GPU Semaphore 限流 (见下).

### ml GPU 并发

进程级单例 + 懒初始化:

- `_ML_MODEL` 哨兵 + `_ML_MODEL_LOCK`: 首次 `read_pdf(flavor="ml")` 互斥加载
- `_ML_INFERENCE_SEM` 动态算: `pynvml.nvmlDeviceGetMemoryInfo().free` → 按 `_ML_SINGLE_INSTANCE_MB` (1.75 GB) 切 worker 数, clamp [1, 6]
- 显存预算: model 1 GB + 推理 0.75 GB = 1.75 GB / 实例; OS reserve 1 GB

admin 可 `params={"ml_max_workers": 3}` 强制覆盖探测值.

### C2 cross_page_merge 双 strategy

`CrossPageMerger.merge` 同时跑 `strategy="lines"` + `strategy="text"`, 同页用 `_bbox_overlap > 0.7` 判重 (lines + text 同一区域算重复). `strategy="text"` 兜底 borderless 跨页续表 (PyMuPDF `text` strategy 不依赖竖线).

### bbox 字段 + IoU 判重

`TableData.bbox: tuple[float, float, float, float] | None = None` (2026-07-09 Task 0 加), frozen dataclass → `.replace(bbox=...)` 设值.

`_bbox_overlap(b1, b2) -> float` IoU helper, None 输入返 0.0. 表格场景阈值:

- `> 0.7` → 同表高置信 (lattice/ml, lines/text 重复)
- `< 0.5` → 不同表, 都保留

`_merge_dedup_lattice_ml(lattice, ml) -> list[TableData]` 双档去重 helper (spec 4.6). **本期不集成到 extract 流程**, 仅落地供未来 v2 (lattice+ml 并行版) 集成.

### 后处理链

每页结果出 `_extract_single_page` 后:

1. `_unmerge_combined_with_ml`: 1 cell 长文本 (>200 字符 + 换行) 疑似合并 → 调 ml 重识别该页
2. `[realign_columns(t) for t in tables]`: 按表头列宽补空列 / 合多余 cell
3. C1 `_stack_contiguous_in_flavor`: 单 flavor 内列数匹配 + 页号相邻 → 合并, `page_no="5+6"` 编码
4. C2 `CrossPageMerger.merge`: PyMuPDF bbox + LLM 判 header 重复 + 行拼接
5. `TableData.filter_valid`: 退化表过滤 (1×1 / 1×N / 全空白行)

### 失败兜底

C1/C2 失败 → log warning + 保留前一步结果, 不阻断. `read_pdf` 抛异常 → 返 `[]` (单页), 不影响其他页.

### OOM 注意

camelot / torch OOM 整个进程崩 (本期不专门 wrap). 业务层 `runner.mark_stage_failed` 兜底. 显存不够的服务器建议 admin 显式 `params={"ml_max_workers": 1}` 限流.
