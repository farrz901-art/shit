# Lookup 模块（业务字典）教程

> 适用版本: lookup 模块首次上线 (2026-06-19, spec 编号 `2026-06-19-lookup-module.md`)
> 代码引用: `c:/doc/Code/rag` 仓库当前实现
> 阅读对象: 第一次接触本项目业务字典机制的后端 / 前端工程师

---

## 一、是什么 & 适用场景

**业务字典 (lookup)** = 把项目里散落的「枚举 / 状态机 / 选项分类」等魔法字符串, 全部入库, 由 DB 作为唯一事实源, 前端统一从 `/api/lookups/*` 拉. 改 enum 不发版, super_admin 可在 Admin UI 运行时增删改.

### 1.1 跟硬编 StrEnum 对比

| 维度 | 硬编 StrEnum (旧) | 业务字典 (新) |
|---|---|---|
| 改一个新选项 | 改 Python 源码 → 提 PR → CI → 发版 → 滚动 | Admin UI 点一下 → DB update + cache invalidate, 5 秒生效 |
| label 多语言 | 业务代码内 `if locale == "zh" ...` 写死 | DB 存 `label_zh` / `label_en`, 前端 `useLookup().labelFor(key, "zh")` |
| 前后端一致 | 前端写一份 `const STATUS = ["pending", ...]`, 跟后端漂移 | 前端零常量, 全部从后端拉 |
| 软删 + 灰度 | 不支持 (代码删了, 历史数据 refer 立即 404) | `is_active=False` + `deprecated_at`, 历史数据仍能查, 新数据不再用 |
| 审计 | 没有 (改 enum 谁改了不知道) | `audit_log` 表记录 `dictionary.item.delete` 等动作 + 前后快照 |
| 引用保护 | 业务裸 DELETE 可能误删还在用的 key | `_REFERENCE_MAP` 反向引用计数, 删除时业务表 refer 仍 >0 → 拒绝 |
| 适用场景 | LLM 框架 / OpenAI SDK 强制的 enum (e.g. response_role) | 业务侧的「状态」「分类」「原因」「配置」 |

### 1.2 跟权限 / 配置 / 国际化对比

- **权限** (page_key / role): 业务字典的一种, 已迁入 (见 `packages/service/src/permissions/cache.py`)
- **配置** (e.g. `MAX_UPLOAD_SIZE_MB`): 走 `config.toml` + env, 不进字典 (静态, 改一发版)
- **国际化** (zh/en 文案): 字典的 `label_zh` / `label_en` 解决字典 label, 业务页面文案仍走 `messages/zh.json` / `en.json` (next-intl)

### 1.3 首批迁移范围

5 个字典 (25 个 item) 已上线 (2026-06-19 commit `05ac28b`):

- `approval_review_status` (3 item) — 原 `approvals/models.py` ApprovalReviewStatus
- `approval_apply_status` (3 item) — 原 ApprovalApplyStatus
- `approval_kind` (5 item) — 原 ApprovalKind
- `reject_reason` (6 item) — 原 RejectReason
- `page_key` (8 item) — 原 `permissions/cache.py` `ALL_PAGE_KEYS_FALLBACK`

未来扩展: `role_preset` / `ingest_state` / `memory_target` / `chat_role` 等任意 enum 都走 lookup.

---

## 二、安装 & 开发环境

**无新 Python 依赖**. 全部用项目已装的库:

| 用途 | 库 (已装) |
|---|---|
| Web 框架 | FastAPI (现成) |
| ORM | SQLAlchemy 2 + Alembic (现成) |
| 缓存 | Redis 7 (现成) |
| 验证 | Pydantic v2 (现成) |
| YAML 解析 | pyyaml (T2 验证) |
| 审计 | 已有 `src.db.models.audit_log.AuditLog` (复用) |
| 限流 | 已有 `src.core.rate_limiter` (复用) |

### 2.1 必跑迁移

启动前必须先跑 alembic migration (建 2 张表):

```bash
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run alembic upgrade head
```

会创建:

- `dictionaries` 表 (PK: `code`)
- `dictionary_items` 表 (UNIQUE: `(dict_code, key)`, FK → `dictionaries.code` ON DELETE CASCADE)

迁移文件: `packages/service/src/storage/migrations/versions/20260619_120000_create_dictionary_tables.py`

### 2.2 启动后自动跑

`main.py` 的 `cmd_serve()` 在 `_setup_dictionaries()` (main.py:55-105) 自动跑 4 步:

1. `seed_dictionaries.py run_seed(force_sync=False)` — 缺啥补啥
2. `check_dictionary_refs.check_consistency()` — yaml ⊆ DB 校验, fail-fast
3. `lookup_cache.start_invalidation_subscriber()` — 订阅 Redis 跨进程失效广播
4. `permissions.cache.warmup_page_keys()` — 预热 page_keys 进程内缓存

---

## 三、基础语法 & 类型系统

### 3.1 YAML 种子 (5 个字典)

`config/dictionaries_seed.yaml:14` 定义 5 个字典:

```yaml
dictionaries:
  - code: approval_review_status       # 字典 code (PK, 业务引用)
    label_zh: 审核状态                  # 双语显示名 (Admin UI 左侧树)
    label_en: Review Status
    description: 审核项的 review 状态轴 # 字典说明 (Admin UI 鼠标悬停)
    items:                              # 字典项 (UNIQUE: dict_code + key)
      - { key: pending, label_zh: 待审核, label_en: Pending, sort: 1 }
      - { key: approved, label_zh: 已批准, label_en: Approved, sort: 2 }
      - { key: rejected, label_zh: 已拒绝, label_en: Rejected, sort: 3 }
```

**item 字段**:

- `key` (必填, 业务代码引用, Pydantic 422 校验 `[a-z][a-z0-9_]{0,63}`)
- `label_zh` / `label_en` (必填, 1-128 字符)
- `sort` (可选, 默认 0, 0-9999, 影响 Admin UI / 前端下拉顺序)
- `description` (可选, 2000 字符, Admin UI 鼠标悬停)
- `metadata_json` (可选, 扩展位, e.g. `page_key` 字典的 `path: "/admin"`)

### 3.2 StrEnum 编译 (启动时自动)

`packages/service/src/common/dictionaries_enum.py:30-50` 在 Python 启动时编译:

```python
# 启动时编译 (单例, import 一次; 失败立即崩, 避免下游拿到空 enum)
ApprovalReviewStatusEnum = _build_enum("ApprovalReviewStatusEnum", "approval_review_status")
ApprovalApplyStatusEnum  = _build_enum("ApprovalApplyStatusEnum",  "approval_apply_status")
ApprovalKindEnum         = _build_enum("ApprovalKindEnum",         "approval_kind")
RejectReasonEnum         = _build_enum("RejectReasonEnum",         "reject_reason")
PageKeyEnum              = _build_enum("PageKeyEnum",              "page_key")
```

**编译规则** (dictionaries_enum.py:38-41):

- member name = `UPPER(key)`, e.g. `pending` → `PENDING`
- member value = 原 `key` (跟 DB / JSON / Pydantic Literal 兼容)

**业务代码用 alias, 不直接 import** (`packages/service/src/approvals/models.py:34-37`):

```python
ApprovalReviewStatus = ApprovalReviewStatusEnum  # 旧名 alias, 不断 import
ApprovalApplyStatus  = ApprovalApplyStatusEnum
ApprovalKind         = ApprovalKindEnum
RejectReason         = RejectReasonEnum
```

### 3.3 Pydantic schema

`packages/service/src/lookups/schemas.py` 暴露 3 个读 response + 4 个写 request + 2 个审计:

| 类 | 用途 |
|---|---|
| `LookupItemResponse` | GET /api/lookups/{code}/{key} 返参 |
| `DictionaryResponse` | GET /api/lookups/{code} 返参 (含 items[]) |
| `DictionaryListResponse` | GET /api/lookups 返参 (字典概要) |
| `DictionaryCreateRequest` | POST /api/admin/dicts body |
| `DictionaryPatchRequest` | PATCH /api/admin/dicts/{code} body |
| `LookupItemCreateRequest` | POST /api/admin/dicts/{code}/items body |
| `LookupItemPatchRequest` | PATCH /api/admin/dicts/{code}/items/{key} body (含 `expected_version` 乐观锁) |
| `ConfirmTokenResponse` | POST /api/admin/dicts/confirm-token 返参 |
| `AuditLogEntry` | GET /api/admin/dicts/{code}/audit 单条记录 |

`@router.post(..., response_model=DictionarySummaryResponse)` 全部加 summary + description, FastAPI 自动渲染成 OpenAPI.

---

## 四、核心概念

### 4.1 数据模型 (`packages/service/src/lookups/models.py`)

**Dictionary** (字典定义, 一行 = 一个字典):

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | String(64) PK | 字典唯一标识 (e.g. `approval_review_status`) |
| `label_zh` / `label_en` | String(128) | 双语显示名 |
| `version` | Integer | schema 版本号 (add/remove item 时 +1, 触发缓存失效) |
| `is_active` | Boolean | 紧急下线开关 (字典级, item 仍能查) |
| `is_readonly` | Boolean | 字典级只读 (比 env `DICTIONARY_READONLY` 细粒度) |
| `effective_at` / `deprecated_at` | TIMESTAMP | 灰度上下线时间 |
| `description` | Text | 字典说明 |

**DictionaryItem** (字典项, 一行 = 一个枚举值):

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigInt PK | 自增 |
| `dict_code` | String(64) FK | → `dictionaries.code` ON DELETE CASCADE |
| `key` | String(64) | 业务代码引用的字符串 (UNIQUE 跟 `dict_code` 一起) |
| `label_zh` / `label_en` | String(128) | 双语 label |
| `sort` | Integer | 显示顺序 (升序) |
| `is_active` | Boolean | 项级开关 (False = 已软删, GET 默认过滤) |
| `metadata_json` | JSONB | 扩展位 (颜色/图标/URL 等) |
| `effective_at` / `deprecated_at` | TIMESTAMP | 项级灰度时间 |

**约束**: `UNIQUE(dict_code, key)` 保证业务代码 key 不变 (schema Literal 引用安全).

### 4.2 LookupService (`packages/service/src/lookups/service.py:1-450`)

8 个静态方法 (无状态, 业务侧不实例化):

| 方法 | 行号 | 用途 |
|---|---|---|
| `list_all_dicts()` | 44-64 | 列全部字典概要 (不含 items) |
| `get(code, *, only_active, lang)` | 66-108 | 查单字典 + items (cache → DB fallback) |
| `get_one(code, key)` | 110-130 | 查单个 item |
| `create_item(code, payload, *, actor, actor_id, ip)` | 134-205 | 新增 (super_admin) |
| `patch_dict(code, payload, *, actor, actor_id, ip)` | 207-278 | 改字典 metadata (label/active/readonly) |
| `patch_item(code, key, payload, *, actor, actor_id, ip)` | 280-350 | 改 item (label/sort/description/metadata) |
| `soft_delete_item(code, key, *, actor, actor_id, ip, force)` | 352-407 | 软删 (`is_active=False` + `deprecated_at=NOW()`) |
| `_load_all_from_db()` | 411-450 | DB 全量加载 (cache miss 时重建) |

**写操作三件套** (跟 cache 协同):

```python
# 1. DB 事务 (sync session_scope)
with session_scope() as s:
    # ... insert / update / soft-delete ...
# 2. 失效 cache (跨进程广播 + 本地 L1 清)
await lookup_cache.invalidate(dict_code)
# 3. 审计 (复用 audit_log 表, action 命名空间 "dictionary.*")
log_dict_change(actor=..., actor_id=..., action="item.create", target=..., before=None, after=..., ip=...)
```

### 4.3 LookupCache (`packages/service/src/lookups/cache.py:35-110`)

双层缓存 + 失效广播:

```
L1 (进程内 dict)  ← 5ms
    ↓ miss
L2 (Redis hash)   ← 0.5ms
    ↓ miss / Redis 挂
DB (LookupService._load_all_from_db)  ← 10-50ms
```

**Key 规范**: `_REDIS_KEY = "rag:dict:all"` (全字典 hash 唯一 key, 5 分钟 TTL)
**失效 channel**: `_INVALIDATE_CHANNEL = "rag:dict:invalidate"` (PUBLISH dict_code 广播)

**写后失效** (cache.py:77-86): 清 L1 + DEL Redis + publish 广播. Redis 失败仅本进程 L1 失效, 跨进程靠 TTL 兜底.

**启动时订阅** (cache.py:116-151): `start_invalidation_subscriber()` 在 main.py lifespan 里跑一次, 收到广播 → `reset_l1()`. Redis 挂 / pubsub 失败 → 静默退出, 跨进程失效靠 5 分钟 TTL 兜底.

### 4.4 SafetyGuard (`packages/service/src/lookups/safety_guard.py:59-183`)

**6 层防御**, 顺序固定, 任一失败 raise `LookupSafetyError(http_status, detail)`:

| 层 | 行号 | 检查 | 失败时 HTTP |
|---|---|---|---|
| 1 | 105-108 | 鉴权: `user.role == "super_admin"` | 403 |
| 2 | 110-115 | readonly: env `DICTIONARY_READONLY=true` **优先** → 字典级 `is_readonly` | 403 |
| 3 | 117-140 | 二次确认: delete 必走, 校验 16 字符 hex + sha256 内容 (`secret = "dict-admin-confirm:<user_id>"`, 1 小时桶) | 412 |
| 4 | 142-163 | 引用检查: delete 必走, 查 `_REFERENCE_MAP` 反向引用, 总引用行数 >0 阻断 (force=True 跳过) | 409 |
| 5 | 165-172 | 乐观锁: payload 含 `expected_version` 才校验, 跟 `lookup_cache.get_dict_version()` 不一致阻断 | 412 |
| 6 | 174-179 | rate limit: 60/min/user, 复用 `src.core.rate_limiter` 的 `dict_admin` rule | 429 |

**priority 顺序 (重要!)**: env readonly > 字典级 readonly > 业务逻辑. 一旦 env 启用 readonly, 所有字典 (包括 `is_readonly=False` 的) 都禁写.

### 4.5 _REFERENCE_MAP (反向引用注册表)

`packages/service/src/lookups/safety_guard.py:46-52` 维护「字典 → 业务表引用列表」:

```python
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    "approval_kind":         [("approvals", "kind")],
    "approval_review_status":[("approvals", "review_status")],
    "approval_apply_status": [("approvals", "apply_status")],
    "reject_reason":         [("approvals", "rejection_reason")],
    "page_key":              [("role_permissions", "page_key")],
}
```

新加字典 / 业务表变动必须同步更新本表, **否则引用检查失效** (删除时不会报引用错误, 可能误删仍在用的 key).

`_check_business_references` (safety_guard.py:142-163) 用 `SELECT COUNT(*) FROM <table> WHERE <column> = :key` 累加引用行数, >0 阻断.

---

## 五、常用命令 & 工具链

### 5.1 跑 seed (启动初始化)

```bash
# 标准 seed: 缺啥补啥, 已存在不动 (防 super_admin 后台改的 label 被覆盖)
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run python -m scripts.seed_dictionaries

# 强制重新同步 yaml label (危险, 覆盖 super_admin 后台改的 label, 审计可追)
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run python -m scripts.seed_dictionaries --force-sync
```

成功输出: `已 seed: 5 个新字典 + 25 个新 item` (中文, 跟项目其他 seed 脚本保持一致).

### 5.2 启动时一致性校验

```bash
# 单独跑校验 (不启服务): yaml 字典 ⊆ DB, enum 值 ⊆ DB items
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run python -m scripts.check_dictionary_refs
```

通过: `字典一致性校验通过 (yaml ⊆ DB, enum ⊆ DB items)` (exit 0)
失败: 抛 RuntimeError, exit 1, 启动失败 (fail-fast)

### 5.3 alembic 迁移

```bash
# 升到最新
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run alembic upgrade head

# 回滚 1 个版本 (会 DROP 2 张字典表, 谨慎)
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run alembic downgrade -1

# 离线生成 SQL (review 用)
RAG_DB_URL=postgresql://user:pass@host:5432/rag \
  uv run alembic upgrade head --sql
```

### 5.4 紧急逃生口

```bash
# 全局禁写字典 (env, 优先级最高, 覆盖字典级 is_readonly)
export DICTIONARY_READONLY=true
uv run python main.py serve
# 任何 POST/PATCH/DELETE /api/admin/dicts/* 返 403 "DICTIONARY_READONLY=true (env readonly)"

# 解除
unset DICTIONARY_READONLY
```

### 5.5 Redis 调试

```bash
# 查 cache 内容
redis-cli -h <host> GET "rag:dict:all" | jq .

# 手动失效 (写操作会自动 PUBLISH, 一般不需要手动)
redis-cli -h <host> DEL "rag:dict:all"
redis-cli -h <host> PUBLISH "rag:dict:invalidate" "*"
```

---

## 六、项目集成点

### 6.1 后端集成位置

| 用途 | 文件 | 说明 |
|---|---|---|
| 读 API | `packages/service/src/lookups/router.py:32-128` | 3 个 GET 端点, `resolve_user` 鉴权 |
| 写 API | `packages/service/src/lookups/admin_router.py:1-545` | 7 个端点, `require_super_admin` 鉴权 + SafetyGuard 6 层 |
| 业务 enum 镜像 | `packages/service/src/approvals/models.py:19-37` | 3 个 enum 改从 `dictionaries_enum` 引用, 旧名 alias 兼容 |
| 页面权限 | `packages/service/src/permissions/cache.py:21-103` | `ALL_PAGE_KEYS` fallback 保留, 新增 `get_all_page_keys()` 从 LookupService 拉 |
| 异常类型 | `packages/service/src/lookups/exceptions.py:11-24` | `LookupSafetyError` / `LookupNotFoundError` |
| 审计写入 | `packages/service/src/lookups/audit.py:20-59` | 复用 `src.db.models.audit_log.AuditLog` |
| 导入导出 | `packages/service/src/lookups/import_export.py:42-139` | CSV / JSON 4 个纯函数 |

### 6.2 前端集成位置

| 用途 | 文件 | 说明 |
|---|---|---|
| Hook | `packages/web/hooks/useLookup.ts:1-70` | TanStack Query, 5 分钟 staleTime, labelFor 工具方法 |
| Hook 测试 | `packages/web/hooks/useLookup.test.ts` | vitest + fake-indexeddb |
| API 封装 | `packages/web/lib/api/lookups.ts` | fetchLookup / fetchAllLookups 跟后端 REST 1:1 |
| Admin UI 入口 | `packages/web/app/[locale]/admin/dicts/page.tsx` | super_admin 路由, 左侧字典树 |
| 字典列表 | `packages/web/app/[locale]/admin/dicts/_components/DictList.tsx` | 字典级展示 + 选中 |
| Item 编辑 | `packages/web/app/[locale]/admin/dicts/_components/DictItemEditor.tsx` | 增删改查 + 乐观锁 `expected_version` |
| 新建弹框 | `packages/web/app/[locale]/admin/dicts/_components/DictItemCreateDialog.tsx` | `<AppDialog>` 包装 |
| 删除弹框 | `packages/web/app/[locale]/admin/dicts/_components/DictItemDeleteDialog.tsx` | 二次确认 + force 开关 |
| 审计日志 | `packages/web/app/[locale]/admin/dicts/_components/DictAuditLog.tsx` | `<DataTable>` 展示 |
| 只读提示 | `packages/web/app/[locale]/admin/dicts/_components/ReadonlyBanner.tsx` | env readonly 时顶部警告条 |

### 6.3 新加一个字典的 5 步流程

1. **改 yaml** (e.g. 加 `role_preset` 字典): 改 `config/dictionaries_seed.yaml`, 加新 code + items
2. **写 StrEnum 类**: 改 `packages/service/src/common/dictionaries_enum.py`, 加 `_build_enum("RolePresetEnum", "role_preset")` (启动时自动从 yaml 编译) + 在 `ENUM_REGISTRY` 加映射
3. **注册反向引用**: 改 `packages/service/src/lookups/safety_guard.py` 的 `_REFERENCE_MAP`, 加 `"role_preset": [("<table>", "<column>"), ...]` (不注册则删除时不会报引用错误)
4. **跑 seed + 校验**:
   ```bash
   uv run python -m scripts.seed_dictionaries
   uv run python -m scripts.check_dictionary_refs
   ```
5. **更新本文档 + 通知前端**: 在本文档 §6.1 / §6.2 表格加新字典条目 + 通知前端用 `useLookup("role_preset")` 即可 (零额外配置, queryKey 自动 cache)

---

## 七、项目代码示例 (真实 file_path:line_number)

### 7.1 `LookupService.get` 读 + cache fallback (`packages/service/src/lookups/service.py:80-95`)

```python
# 读路径: cache (L1 → L2) → DB fallback
data = await lookup_cache.get_all()  # L1 命中就返, 否则读 Redis
if data is None:
    data = LookupService._load_all_from_db()  # DB 全量加载
    await lookup_cache.set_all(data)  # 回写 cache
d = data.get(dict_code)
if d is None:
    raise LookupNotFoundError(f"dictionary '{dict_code}' not found")

items = list(d.get("items", []))
if only_active:
    items = [i for i in items if i.get("is_active", True)]
```

### 7.2 `_check_business_references` 反向引用 (`packages/service/src/lookups/safety_guard.py:140-160`)

```python
async def _check_business_references(self, dict_code: str, key: str) -> None:
    """第 4 层: 反向引用计数, >0 阻断删除."""
    refs = _REFERENCE_MAP.get(dict_code, [])
    if not refs:
        return  # 没注册引用表 = 字典独立, 不检查
    total = 0
    with session_scope() as s:
        for table, column in refs:
            # table / column 是 hardcode 常量 (来自 _REFERENCE_MAP), 安全
            sql = text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :key")
            result = s.execute(sql, {"key": key}).scalar()
            total += int(result or 0)
    if total > 0:
        raise LookupSafetyError(
            409,
            f"item '{dict_code}:{key}' still referenced by {total} rows; "
            f"soft-delete refused. Use ?force=true to bypass (audit logged)",
        )
```

### 7.3 `LookupCache.get_all` 读 Redis L2 → L1 (`packages/service/src/lookups/cache.py:50-70`)

```python
async def get_all(self) -> dict[str, dict] | None:
    """读 L1 → L2. 返 {dict_code: {label_zh, label_en, version, items: [...]}}.

    None 表示 cache miss (业务侧应走 DB 重建 + set_all).
    """
    if self._l1_data is not None:
        return self._l1_data  # L1 命中 (microsecond 级)
    raw = await safe_get(_REDIS_KEY)  # 复用 2026-06-18 redis facade, 失败 None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        self._l1_data = data  # 回填 L1
        return data
    except json.JSONDecodeError as e:
        logger.warning("lookup cache JSON 损坏, 走 DB 重建: {}", e)
        return None
```

### 7.4 StrEnum 编译 (`packages/service/src/common/dictionaries_enum.py:30-50`)

```python
def _build_enum(name: str, code: str) -> type[StrEnum]:
    """从 yaml 字典项编译 StrEnum.

    找不到字典 / 重复 key → 抛 ValueError, 启动期 fail-fast.
    StrEnum(name, names) 实际返回 class (functional API),
    pyright stub 推成 StrEnum 实例 → 用 cast 修.
    """
    d = get_seed_dict(code)
    if d is None:
        raise ValueError(f"seed yaml 找不到字典: {code}")
    members: dict[str, str] = {}
    for item in d.get("items", []):
        if item["key"] in members:
            raise ValueError(f"字典 {code} 有重复 key: {item['key']}")
        # member name = UPPER(key) (e.g. "pending" -> "PENDING"),
        # value = 原 key (跟 DB / JSON 一致, Pydantic 兼容)
        members[item["key"].upper()] = item["key"]
    return cast(type[StrEnum], StrEnum(name, members))

# 启动时编译 (单例, import 一次; 失败立即崩, 避免下游拿到空 enum)
ApprovalReviewStatusEnum = _build_enum("ApprovalReviewStatusEnum", "approval_review_status")
ApprovalApplyStatusEnum  = _build_enum("ApprovalApplyStatusEnum",  "approval_apply_status")
ApprovalKindEnum         = _build_enum("ApprovalKindEnum",         "approval_kind")
RejectReasonEnum         = _build_enum("RejectReasonEnum",         "reject_reason")
PageKeyEnum              = _build_enum("PageKeyEnum",              "page_key")
```

### 7.5 前端 `useLookup` hook (`packages/web/hooks/useLookup.ts:1-50`)

```typescript
// UseLookup hook (2026-06-19 lookup module §5.5)
// TanStack Query 模式 (跟 lib/chat/api.ts useConversations 一致).
// 提供 items + byKey + i18n labelFor 工具方法, 业务组件直接 map 到 <Select> / <RadioGroup> 等.
// StaleTime 5 分钟, 跟后端 Redis L2 缓存对齐; 窗口聚焦不重复拉 (字典数据稳定).
"use client";

import { useQuery } from "@tanstack/react-query";
import {
  type FetchLookupOpts,
  type LookupItem,
  fetchAllLookups,
  fetchLookup,
} from "@/lib/api/lookups";

// 5 分钟 = 后端 Redis LookupCache TTL; staleTime 内不重复发请求.
const FIVE_MIN = 5 * 60 * 1000;

export function useLookup(dictCode: string, opts: FetchLookupOpts = {}) {
  const lang = opts.lang ?? "both";
  const onlyActive = opts.onlyActive ?? true;
  const query = useQuery({
    queryFn: () => fetchLookup(dictCode, opts),
    queryKey: ["lookup", dictCode, lang, onlyActive],
    refetchOnWindowFocus: false,
    staleTime: FIVE_MIN,
  });
  const items: LookupItem[] = query.data?.items ?? [];
  const byKey = Object.fromEntries(items.map((item) => [item.key, item])) as Record<string, LookupItem>;
  return {
    items,
    byKey,
    // 查 i18n label: 默认 zh, locale="en" 切英文. 找不到 (后端没缓存 / key 已删) 返 key 兜底.
    labelFor: (key: string, locale: "zh" | "en" = "zh"): string =>
      byKey[key]?.[`label_${locale}`] ?? key,
    isLoading: query.isLoading,
    error: query.error,
    refresh: query.refetch,
  };
}
```

---

## 八、项目没用到的能力

本期 (2026-06-19) **明确不做**, 后续 spec 视需求扩展:

- **自动代码生成 (StrEnum → Literal 的 codegen)**: 不在 spec 范围, 当前 yaml 改完需手动重启服务, 启动时 `dictionaries_enum._build_enum()` 会从 yaml 重新编译
- **字典版本兼容迁移工具**: 软删已通过 `is_active=False` + `deprecated_at` 解决, 无需复杂版本迁移. 业务表历史数据 refer 已弃用 key 仍能查 (read 默认 `?only_active=true` 过滤)
- **字典可视化 schema 编辑器**: 本期只 CLI (`seed_dictionaries.py` / `check_dictionary_refs.py`) + Admin UI (增删改查 5 个组件), 不做 ER 图 / JSON Schema 生成
- **字典批量编辑 UI**: Admin UI 只支持单条增删改查, 批量靠 CSV 导入 (`import_items_from_csv` 已就绪, 但 Admin UI 没接)
- **多语言扩展 (zh/en 之外)**: schema 写死 `label_zh` / `label_en`, 不做 i18n 字典 (跟项目 next-intl messages 文件分离, 字典只解决 enum label)
- **A/B 测试 UI**: schema 已 support `effective_at` / `deprecated_at` 灰度时间, UI 暂不做, 业务层 router 需手动判断时间窗
- **跨项目多租户 (`project_id` 字段)**: 本期字典全局共享, 不做租户隔离
- **GraphQL API**: 全部 REST (`/api/lookups/*` + `/api/admin/dicts/*`), GraphQL 端点未实现
- **字典变更 webhooks**: 写后仅 Redis broadcast + audit_log, 第三方系统订阅靠扫表, 不发 webhook
- **强制类型化 (TypeScript Literal 编译)**: 跟 codegen 同性质, yaml 改完前端需手维护类型, 不做自动生成

---

## 九、最佳实践 & 常见坑

### 9.1 双写兼容期不要直接删旧 StrEnum class

**坑**: R1 期 (2026-06-19 上线后 1-2 周), 业务代码可能同时 `import` 旧 StrEnum (`ApprovalReviewStatus`) 跟新字典查 (`LookupService.get("approval_review_status")`). 直接删 `approvals/models.py:34` 的 alias → 旧 import 全部 500.

**做法**: 至少保留 R1 整个 sprint (到 R3 spec 完成为止), alias 引用 `dictionaries_enum` 即可, **不要删旧名**.

### 9.2 `_REFERENCE_MAP` 加新字典必须同步加反向引用

**坑**: 新加字典忘记在 `safety_guard.py:46` 的 `_REFERENCE_MAP` 注册 → 删除时不会报引用错误, 业务表 refer 仍 >0 也直接软删, 历史数据下次查时 key 找不到 (实际还能查, 因为软删保留行, 但 admin UI 看不到, 易造成 admin 误操作).

**做法**: 5 步流程 §6.3 第 3 步必须有. 集成测试可加一个 case: 业务表 refer 1 行 → 尝试软删 → 期望 409.

### 9.3 `DICTIONARY_READONLY=true` 紧急逃生 (env > 字典级 > 业务逻辑)

**优先级**: env 最高, 字典级次之, 业务逻辑兜底.

**用法**: 生产事故需紧急停写字典 (e.g. admin UI 误操作导致业务表 cascade 错乱) → `export DICTIONARY_READONLY=true` → 重启服务 → 排障 → 解除 env. **不需要**逐个字典改 `is_readonly=true`.

**注意**: env 改了**不重启不生效** (Python 进程启动时读 `os.getenv`, 跟 Redis 无关). 重启 → 所有字典 POST/PATCH/DELETE 立即 403.

### 9.4 软删 `is_active=False` + `deprecated_at=NOW()`, 历史数据 refer 仍能查

**正确语义**:

- GET `?only_active=true` (默认): 不返已软删项, 前端下拉看不到
- GET `?only_active=false`: 含已软删项, Admin UI "查看历史" 用
- 业务表 refer: 不变, 历史数据查询仍能 JOIN 出 key (虽然 UI 看不到, 业务逻辑仍跑得通)

**反例**: 业务代码自己 `is_active = False` 后 cascade 删 → 历史数据 refer → FK 报错.

### 9.5 `force=true` 跳过引用检查但仍走 audit (标 `forced`)

**用法**: 删除被引用的字典项 (e.g. `reject_reason.duplicate` 被 200 条 approval 引用), admin 确认要清掉 → `DELETE /api/admin/dicts/reject_reason/items/duplicate?force=true` → SafetyGuard 第 4 层跳过, 但 audit_log 标 `action="dictionary.item.delete.forced"`.

**注意**: soft-delete 仍执行 (只跳过引用检查, 不跳过软删), 历史数据 refer 仍保留行 (`is_active=False`), 业务查询不受影响.

### 9.6 seed 默认 UPSERT 不覆盖, `--force-sync` 危险

**默认行为** (`scripts/seed_dictionaries.py:50-61`): 已存在不动, 缺啥补啥. 防 super_admin 后台改的 label 被覆盖.

**`--force-sync`** (`scripts/seed_dictionaries.py:62-67`): 强制用 yaml 覆盖 DB label + sort. **危险**: 覆盖掉 admin 改的"友好文案" / "业务术语调整", 需显式 flag + 审计可追.

**反例**: CI 流水线自动跑 seed 想保持"出厂配置" → 改 `force_sync=True` → 覆盖 admin 改的 label → 业务方投诉"我改的中文没了".

### 9.7 启动顺序: seed → check → subscriber → warmup

**顺序错的后果**:

- check 在 seed 之前: DB 没字典, check 抛 `DB missing dictionaries: [...]` → 启动失败
- subscriber 没启动: 跨进程失效失效, 5 分钟后才靠 TTL 兜底 (用户看到 stale 数据)
- warmup 没跑: 业务读 page_key 走 fallback 8 项 (R1 兼容), 不致命但 page_key 字典新增的项不生效

**做法**: `main.py:55-105` 已有固定顺序, 改时**保持顺序**, 任一失败按级别处理 (check fail-fast raise, 其他 warn 降级).

### 9.8 测试必须 mock, 不连真 PG/Redis

**项目老规范** (跟 4 模式一致): 单测 mock, 不连真 DB. 例子:

```python
# tests/lookups/test_service.py
from unittest.mock import patch

@patch("src.lookups.service.session_scope")
def test_create_item_duplicate(mock_session):
    # ... mock session.execute return 已存在 item ...
    with pytest.raises(LookupSafetyError) as exc:
        asyncio.run(LookupService.create_item(
            "approval_review_status",
            {"key": "pending", "label_zh": "待审核", "label_en": "Pending"},
            actor="alice@x.com", actor_id=1, ip="127.0.0.1",
        ))
    assert exc.value.http_status == 409
```

**真实 DB 行为**: 由集成测试 (模式 2 `db_session` fixture) / staging 验证, 不在单测范围.

### 9.9 yaml key 改了不重启 = enum 错位

**坑**: 改了 `dictionaries_seed.yaml` 的 key (e.g. `pending` → `pending_v2`), 没重启服务 → `ApprovalReviewStatusEnum.PENDING.value` 仍为 `pending` (启动时编译的旧值). 新增的 `pending_v2` 在 enum 里不存在, 业务代码 if 判断全错.

**做法**: 改 yaml → 重启服务. 长期方案: 接 Redis pubsub 自动 reload (本期不做, spec §8 出范围).

### 9.10 不要手工 SQL 删字典项

**坑**: DBA 直接 `DELETE FROM dictionary_items WHERE key = 'duplicate'` → cache 不知道失效, 所有进程 stale 5 分钟 → 前端用户看到 `reject_reason.duplicate` 还能选 → 提交后业务表 refer → 查不到 enum label → UI 显示 key 字符串.

**做法**: 永远走 admin API (`DELETE /api/admin/dicts/reject_reason/items/duplicate?force=true`), 走 SafetyGuard + cache invalidate + audit.

---

## 附录: 跟项目其他 spec 的协同

- **2026-06-16 test isolation**: 字典测试全部走模式 1 mock, 见 `tests/lookups/` 74 个测试
- **2026-06-17 logging**: 字典写操作 audit_log 走 `src.lookups.audit.log_dict_change` (复用 `src.db.models.audit_log.AuditLog`)
- **2026-06-18 redis**: cache + 失效广播 + 限流全部复用 `src.core.redis_client` / `src.core.rate_limiter` facade
- **2026-06-19 chat**: 跟 chat_router 解耦, 字典不依赖 chat 模块
- **后端 CLAUDE.md**: 见 `packages/service/CLAUDE.md` 「字典使用规范」段 (本次追加)

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-19-lookup-module.md`
- Plan: `docs/superpowers/plans/2026-06-19-lookup-module.md`
- 模块 README: `packages/service/src/lookups/README.md`
- 后端 CLAUDE.md: `packages/service/CLAUDE.md`
