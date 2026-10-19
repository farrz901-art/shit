# Lookups 模块

业务字典: DB 唯一事实源, 通用 enum 集中管理 (2026-06-19 lookup spec).

> 让"改 enum 不发版"成为可能: 前端 / 后端所有 enum / 状态机 / 选项分类都入库, super_admin 可运行时增删改, 5 秒生效 (cache invalidate).

## 模块结构

| 文件 | 职责 |
|---|---|
| `models.py` | `Dictionary` / `DictionaryItem` SQLAlchemy 模型 (跟 spec §3.1 一致) |
| `schemas.py` | Pydantic schema (3 个读 response + 4 个写 request + 2 个审计) |
| `service.py` | `LookupService` 8 个静态方法 (CRUD + cache 协同 + audit) |
| `cache.py` | `LookupCache` Redis L2 + 进程内 L1 + 失效广播订阅 |
| `safety_guard.py` | 6 层防御 (鉴权 + readonly + 二次确认 + 引用 + 乐观锁 + rate limit) |
| `router.py` | 读 API: GET `/api/lookups/*` (任何登录用户, 3 端点) |
| `admin_router.py` | 写 API: POST/PATCH/DELETE `/api/admin/dicts/*` (super_admin, 7 端点) |
| `audit.py` | 审计日志写入 (复用 `src.db.models.audit_log.AuditLog`) |
| `import_export.py` | CSV / JSON 4 个纯函数 (无 DB / Redis 依赖) |
| `exceptions.py` | `LookupSafetyError` (4xx 统一表达) / `LookupNotFoundError` (404) |

## 公共 API

### LookupService (静态方法, 业务侧不实例化)

```python
from src.lookups.service import LookupService
from src.lookups.exceptions import LookupNotFoundError, LookupSafetyError
```

| 方法 | 签名 | 用途 |
|---|---|---|
| `list_all_dicts` | `async () -> list[dict]` | 列全部字典概要 (不含 items) |
| `get` | `async (code, *, only_active=True, lang="both") -> dict` | 查单字典 + items (cache → DB fallback) |
| `get_one` | `async (code, key) -> dict` | 查单个 item (raise `LookupNotFoundError`) |
| `create_item` | `async (code, payload, *, actor, actor_id, ip) -> dict` | 新增 item (super_admin, raise 409 重名) |
| `patch_dict` | `async (code, payload, *, actor, actor_id, ip) -> dict` | 改字典 metadata (label/active/readonly) |
| `patch_item` | `async (code, key, payload, *, actor, actor_id, ip) -> dict` | 改 item (label/sort/description/metadata) |
| `soft_delete_item` | `async (code, key, *, actor, actor_id, ip, force=False) -> dict` | 软删 (`is_active=False` + `deprecated_at=NOW()`) |
| `_load_all_from_db` | `() -> dict` | DB 全量加载 (cache miss 时重建, sync) |

### SafetyGuard (单例, 写操作入口)

```python
from src.lookups.safety_guard import safety_guard
from src.lookups.exceptions import LookupSafetyError

await safety_guard.check_all(
    action="delete",                   # "create" | "patch" | "delete"
    dict_code="reject_reason",
    key="duplicate",
    user=current_user,                 # CurrentUser (有 .id / .role)
    confirm_token=token,               # 16 字符 hex, delete 必传
    payload={},                        # 含 expected_version 时校验乐观锁
    force=False,                       # True 跳过引用检查, audit 标 forced
)
# 任一层失败 raise LookupSafetyError(http_status, detail)
```

### 7 层读 + 写端点

**读** (任何登录用户, `resolve_user` 鉴权):

- `GET /api/lookups` — 全部字典概要
- `GET /api/lookups/{dict_code}` — 单字典 + items (`?only_active` + `?lang`)
- `GET /api/lookups/{dict_code}/{key}` — 单个 item

**写** (super_admin, `require_super_admin` + SafetyGuard 6 层):

- `POST /api/admin/dicts` — 新建字典
- `PATCH /api/admin/dicts/{code}` — 改字典 metadata
- `POST /api/admin/dicts/{code}/items` — 新增 item
- `PATCH /api/admin/dicts/{code}/items/{key}` — 改 item
- `DELETE /api/admin/dicts/{code}/items/{key}` — 软删 (header `X-Confirm-Token` 必传)
- `POST /api/admin/dicts/confirm-token` — 签发删除二次确认 token (1h 有效)
- `GET /api/admin/dicts/{code}/audit` — 字典变更历史 (audit_log)

## 测试

```bash
# 跑全部字典测试 (模式 1 mock, 不连真 PG / Redis)
cd packages/service
RAG_DB_URL=postgresql://test:test@localhost:5432/rag_test \
  uv run --no-sync pytest tests/lookups/ -v

# 跑单个文件
uv run --no-sync pytest tests/lookups/test_service.py -v

# 看覆盖率
uv run --no-sync pytest tests/lookups/ --cov=src.lookups --cov-report=term-missing
```

**74 个测试**, 全部模式 1 mock (不连真实外部依赖), 覆盖:

- `test_models.py` — Dictionary / DictionaryItem 模型
- `test_service.py` — LookupService 8 个方法
- `test_cache.py` — LookupCache L1 / L2 / 失效广播
- `test_safety_guard.py` — 6 层防御每层一个 case
- `test_router.py` — GET API
- `test_admin_router.py` — POST/PATCH/DELETE + confirm token
- `test_import_export.py` — CSV/JSON
- `test_seed.py` — seed 幂等
- `test_check_consistency.py` — 启动校验
- `test_migration.py` — alembic up + down

## 启动

`main.py` 的 `cmd_serve()` (main.py:197-209) 自动跑 4 步, 顺序固定:

```
_setup_dictionaries() 在 main.py:55-105
  1. scripts.seed_dictionaries.run_seed(force_sync=False)
       → 缺啥补啥, 不覆盖 admin 在 DB 改的 label
  2. scripts.check_dictionary_refs.check_consistency()
       → fail-fast: yaml ⊄ DB 或 enum ⊄ DB → RuntimeError 启动失败
  3. src.lookups.cache.start_invalidation_subscriber()
       → 订阅 Redis dict.invalidate 广播, 跨进程失效
  4. src.permissions.cache.warmup_page_keys_sync()
       → 预热 page_keys 进程内缓存, 业务 router 同步读
```

**失败行为**:

- seed 失败 → WARNING, 不阻塞 (R1 兼容期 DB 表可能没建)
- check_consistency 失败 → RuntimeError, 启动失败 (DB 真缺字典 / yaml 拼错)
- subscriber 失败 → WARNING, 跨进程失效靠 5 分钟 Redis TTL 兜底
- warmup 失败 → WARNING, 用 fallback 8 项 (R1 兼容)

## 安全 6 层

写操作 (`POST / PATCH / DELETE`) 在 router 入口处走 `safety_guard.check_all()`, 任一层失败立刻 raise `LookupSafetyError`:

| 层 | 检查 | 失败 HTTP |
|---|---|---|
| 1 鉴权 | `user.role == "super_admin"` | 403 |
| 2 只读 | env `DICTIONARY_READONLY=true` **优先** → 字典级 `is_readonly` | 403 |
| 3 二次确认 | delete 必走, 校验 16 字符 hex + sha256 内容 (1h 小时桶) | 412 |
| 4 引用检查 | delete 必走, 查 `_REFERENCE_MAP` 反向引用, 总引用行数 >0 阻断 (force=True 跳过) | 409 |
| 5 乐观锁 | payload 含 `expected_version` 才校验, 跟 `lookup_cache.get_dict_version()` 不一致阻断 | 412 |
| 6 rate limit | 60/min/user, 复用 `src.core.rate_limiter` 的 `dict_admin` rule | 429 |

## 反向引用 _REFERENCE_MAP

`src/lookups/safety_guard.py:46` 维护「字典 → 业务表引用列表」, 新加字典 / 业务表变动必须同步更新, **否则引用检查失效**.

```python
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    "approval_kind":          [("approvals", "kind")],
    "approval_review_status": [("approvals", "review_status")],
    "approval_apply_status":  [("approvals", "apply_status")],
    "reject_reason":          [("approvals", "rejection_reason")],
    "page_key":               [("role_permissions", "page_key")],
}
```

## 字典使用规范

详见 `packages/service/CLAUDE.md`「字典使用规范」段. 简言之:

- 业务 enum 必须走 lookup, 不许新增硬编 StrEnum (除非 LLM 框架要求)
- 新加字典 5 步流程: yaml → enum 编译 → _REFERENCE_MAP 注册 → seed → 更新文档
- DB 是唯一事实源, yaml 仅种子 + 类型提示
- 删除 key 必走 admin API + 二次确认, 禁止手工 SQL 删

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-19-lookup-module.md`
- Plan: `docs/superpowers/plans/2026-06-19-lookup-module.md`
- Cookbook 教程: `docs/cookbook/python/lookup.md`
- 后端 CLAUDE.md: `packages/service/CLAUDE.md`
- 前端 hook: `packages/web/hooks/useLookup.ts`
- 前端 API 封装: `packages/web/lib/api/lookups.ts`
- Admin UI: `packages/web/app/[locale]/admin/dicts/`
