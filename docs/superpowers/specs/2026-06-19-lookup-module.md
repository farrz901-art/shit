# Lookup 模块（业务字典）设计

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：以 `c:/doc/Code/rag` 仓库当前代码为准
> 🎯 范围：新增通用业务字典模块，DB 为唯一事实源；首批迁移 4 个散落 enum；提供 super_admin CRUD + 前端 useLookup + Admin UI

---

## 一、目标 & 范围

**目标**：把项目里散落的 enum / 字典 / 默认值等"魔法字符串"全部入库为「通用业务字典」，提供 `/api/lookups/{dict_code}` API + Redis 缓存 + 代码 enum 镜像。super_admin 可运行时增删改字典项；前端统一从后端拉。

**首批字典入库范围**：
- 现有 4 个 enum（approvals/models.py × 3 + permissions/cache.py × 1）
- 未来扩展：role preset / ingest state / memory target / chat role 等任意 enum

**核心约束**：
- DB 为唯一事实源（schema Literal、router、StrEnum 全部从 DB 生成的元数据派生）
- Redis 缓存 + 启动预热
- 多语言 label（zh/en）一处维护
- 不破坏现有 API 兼容（迁移期双写）

**4 个痛点全打**：
1. 改 enum 不发版（runtime 改 DB + cache invalidate）
2. 前后端一致（前端只调 `/api/lookups/*`，没有第二份常量）
3. 多语言 label 集中（DB 存 `label_zh` / `label_en`，前端 i18n 直接拿）
4. 后台管理（super_admin CRUD API + 后续接 admin UI）

**本次包含**：
1. DB 表 + Alembic migration
2. seed yaml + 启动脚本
3. `/api/lookups/{dict_code}` GET
4. super_admin CRUD（POST/PATCH/DELETE）+ 软删除 + 引用检查 + 审计
5. Redis 缓存 + 失效广播
6. 现有 4 个 enum 全部迁移（双写兼容期）
7. 前端 `useLookup` hook + admin UI（最小可用）
8. 字典版本控制（`version` + `is_active` + `effective_at` + `deprecated_at`）
9. 字典导入导出（CSV / JSON）
10. **安全 6 层防御**（鉴权 + 引用检查 + 软删 + 审计 + 缓存原子 + 二次确认）
11. **env 逃生口** `DICTIONARY_READONLY=true`

**仍不在本次范围**：
- 自动代码生成（StrEnum → Literal 的 codegen）

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 (Next.js)                                                  │
│  useLookup(dict_code)  +  Admin UI (/admin/dicts)                │
└─────────────────┬───────────────────────────────┬────────────────┘
                  │ GET /api/lookups/{code}       │ POST/PATCH/DELETE /api/admin/dicts/*
┌─────────────────▼───────────────────────────────▼────────────────┐
│  FastAPI routers (src/lookups/)                                   │
│  GET /api/lookups/{code}    (anyone logged in)                    │
│  GET /api/lookups/{code}/{key}                                    │
│  POST   /api/admin/dicts/{code}/items          (super_admin)      │
│  PATCH  /api/admin/dicts/{code}/items/{key}   (super_admin)      │
│  DELETE /api/admin/dicts/{code}/items/{key}   (super_admin)      │
│  POST   /api/admin/dicts/{code}/items/{key}/confirm             │
│                                                                  │
│  ↳ 全部走 SafetyGuard (6 层防御)                                  │
└─────────────────┬──────────────────────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────┐
   │  LookupService           │
   │  get / upsert / patch /  │
   │  soft_delete             │
   └────────┬─────────────────┘
            │ 读：先 Redis 后 DB；写：DB + invalidate Redis + audit_log
            ▼
   ┌──────────────────────────┐         ┌─────────────────────────┐
   │  Redis 缓存              │ ◄────── │  permission_cache_redis │
   │  hash: dict:<code>       │  复用   │  (复用 pattern)         │
   └──────────────────────────┘         └─────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │  PostgreSQL                                    │
   │  dictionaries (code PK, label_zh, label_en,   │
   │               version, is_active, ...)         │
   │  dictionary_items (dict_code, key,             │
   │                   label_zh, label_en,          │
   │                   sort, is_active,             │
   │                   effective_at,                │
   │                   deprecated_at, version)       │
   └────────────────────────────────────────────────┘
            ▲
            │ 启动初始化 (UPSERT)
            │
   ┌────────┴──────────────────────────────┐
   │  scripts/seed_dictionaries.py         │
   │  读 src/common/dictionaries_seed.yaml │
   │  UPSERT（DB 已存在跳过、不存在 insert）│
   └───────────────────────────────────────┘
```

**4 个关键设计原则**：

1. **DB 为唯一事实源**：所有 enum 读取路径只走 `LookupService` → `Redis Cache` → `DB`。schema Literal / StrEnum / Pydantic 都从 `dictionaries_seed.yaml` 派生（编译期）+ DB（运行期），保证两者同步。

2. **写路径强校验**：所有 POST/PATCH/DELETE 走 `SafetyGuard` 6 层防御（鉴权 / 引用检查 / 软删 / 审计 / 缓存原子 / 二次确认 token），不绕过。

3. **缓存原子失效**：PATCH/DELETE 后 `redis_pipeline(DEL + PUBLISH dict.invalidate.{code})`，订阅者（其他进程）收到后清自己进程内 L1 缓存。

4. **代码 enum 镜像**：迁移期双写——`src/common/dictionaries_enum.py` 启动时从 `dictionaries_seed.yaml` 编译成 `StrEnum`，schema Literal 直接引用它。DB 是运行时事实源，yaml 是出厂种子 + 类型提示参考。

**L1/L2 缓存层级**（参考 `permission_cache_redis.py`）：
- **L2 = Redis**（跨进程共享）：默认 5 分钟 TTL，启动预热
- **L1 = 进程内 `lru_cache`**（microsecond 级）：方法级 `@lru_cache(maxsize=128)`，由 Redis 订阅广播失效

---

## 三、数据模型

### 3.1 DB 表（2 张）

**`dictionaries` 表** — 字典定义（一行 = 一个字典）：

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `code` | VARCHAR(64) | PK | 字典唯一标识，如 `approval_review_status` / `reject_reason` / `page_key` |
| `label_zh` | VARCHAR(128) | NOT NULL | 中文名，如 "审核状态" |
| `label_en` | VARCHAR(128) | NOT NULL | 英文名，如 "Review Status" |
| `description` | TEXT | NULL | 说明（管理员用） |
| `version` | INTEGER | NOT NULL DEFAULT 1 | 字典 schema 版本号（add/remove item 时 +1） |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | 字典是否启用（紧急下线） |
| `is_readonly` | BOOLEAN | NOT NULL DEFAULT FALSE | 单字典级只读（比 env 全局逃生口细粒度） |
| `effective_at` | TIMESTAMPTZ | NULL | 生效时间（灰度发布） |
| `deprecated_at` | TIMESTAMPTZ | NULL | 弃用时间（标记下线但保留 key） |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**`dictionary_items` 表** — 字典项（一行 = 一个枚举值）：

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | BIGSERIAL | PK | |
| `dict_code` | VARCHAR(64) | FK→dictionaries(code) ON DELETE CASCADE | |
| `key` | VARCHAR(64) | NOT NULL | 枚举值（业务代码里用的字符串） |
| `label_zh` | VARCHAR(128) | NOT NULL | 中文显示 |
| `label_en` | VARCHAR(128) | NOT NULL | 英文显示 |
| `description` | TEXT | NULL | |
| `sort` | INTEGER | NOT NULL DEFAULT 0 | 显示顺序 |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | 项级开关 |
| `effective_at` | TIMESTAMPTZ | NULL | |
| `deprecated_at` | TIMESTAMPTZ | NULL | |
| `metadata_json` | JSONB | NULL | 扩展位（颜色、图标、URL 等） |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| | | **UNIQUE(dict_code, key)** | |

### 3.2 索引

- `dictionary_items(dict_code, is_active, sort)` — 列表查询主索引
- `dictionary_items(dict_code, key) WHERE is_active = TRUE` — key 查询
- `dictionaries(is_active)` — 列出可用字典

### 3.3 seed yaml 结构

`src/common/dictionaries_seed.yaml`（4 个首批字典）：

```yaml
dictionaries:
  - code: approval_review_status
    label_zh: 审核状态
    label_en: Review Status
    description: 审核项的 review 状态轴
    items:
      - {key: pending,  label_zh: 待审核, label_en: Pending,  sort: 1}
      - {key: approved, label_zh: 已批准, label_en: Approved, sort: 2}
      - {key: rejected, label_zh: 已拒绝, label_en: Rejected, sort: 3}

  - code: approval_apply_status
    label_zh: 写入状态
    label_en: Apply Status
    items:
      - {key: none,    label_zh: 未尝试, label_en: None,    sort: 1}
      - {key: applied, label_zh: 已写入, label_en: Applied, sort: 2}
      - {key: failed,  label_zh: 失败,   label_en: Failed,  sort: 3}

  - code: approval_kind
    label_zh: 审核类型
    label_en: Approval Kind
    items:
      - {key: qa,       label_zh: 录 QA,       label_en: QA,       sort: 1}
      - {key: triple,   label_zh: 录三元组,     label_en: Triple,   sort: 2}
      - {key: batch,    label_zh: 批量导入,     label_en: Batch,    sort: 3}
      - {key: optimize, label_zh: 优化回答,     label_en: Optimize, sort: 4}
      - {key: like,     label_zh: 点赞记录,     label_en: Like,     sort: 5}

  - code: reject_reason
    label_zh: 拒绝原因
    label_en: Reject Reason
    items:
      - {key: duplicate,      label_zh: 重复,   label_en: Duplicate,      sort: 1}
      - {key: low_quality,    label_zh: 低质量, label_en: Low Quality,    sort: 2}
      - {key: incomplete,     label_zh: 不完整, label_en: Incomplete,     sort: 3}
      - {key: wrong_category, label_zh: 分类错, label_en: Wrong Category, sort: 4}
      - {key: format_issue,   label_zh: 格式问题,label_en: Format Issue,  sort: 5}
      - {key: other,          label_zh: 其他,   label_en: Other,          sort: 99}

  - code: page_key
    label_zh: 页面权限
    label_en: Page Permission
    items:
      - {key: admin,        label_zh: 管理中心, label_en: Admin,        sort: 1, metadata_json: {path: "/admin"}}
      - {key: chat,         label_zh: 对话,     label_en: Chat,         sort: 2, metadata_json: {path: "/chat"}}
      - {key: output,       label_zh: 文档结构化,label_en: Output,       sort: 3, metadata_json: {path: "/output"}}
      - {key: knowledge,    label_zh: 知识库,   label_en: Knowledge,    sort: 4, metadata_json: {path: "/knowledge"}}
      - {key: evaluate,     label_zh: 评估,     label_en: Evaluate,     sort: 5, metadata_json: {path: "/evaluate"}}
      - {key: submissions,  label_zh: 审核中心, label_en: Submissions,  sort: 6, metadata_json: {path: "/submissions"}}
      - {key: decode,       label_zh: 型号解析, label_en: Decode,       sort: 7, metadata_json: {path: "/decode"}}
      - {key: health,       label_zh: 健康,     label_en: Health,       sort: 8, metadata_json: {path: "/health"}}
```

### 3.4 启动初始化流程

```
1. Alembic migration 自动建表
2. 启动 main.py 时调用 scripts/seed_dictionaries.py:
   - 读 src/common/dictionaries_seed.yaml
   - 对每个 dict:
     a. UPSERT dictionaries（code 唯一，已存在不动 label_zh/label_en 除非明确标注 force）
     b. 对每个 item:
        UPSERT dictionary_items (dict_code, key)
        已存在 key：保留（不改 label/sort，避免运行时改 label 漂移）
        不存在：INSERT
   - 输出："已 seed N 个字典 + M 个 item"
3. 后端服务正常启动
```

**为什么 UPSERT 不强制同步 label**：
- 防止 super_admin 在后台改的 label 被重启覆盖
- 启动时只补"缺项"，不"覆盖"
- 如需强制重新同步 label：跑 `seed_dictionaries.py --force-sync`（显式 CLI 参数）

### 3.5 现有 4 个 enum 的迁移（双写兼容期）

迁移期方案：**新代码走 lookup，保留 enum 兜底**。

**`approvals/models.py`** 改为：
```python
# 旧 enum 保留为参考，不删除
# class ApprovalReviewStatus(StrEnum): PENDING = "pending" ...

# 新代码：
from src.lookups.service import LookupService

# 业务代码不直接引用 enum，而是查 DB
# 但 schema Literal 用 yaml 编译成的 StrEnum（类型安全）
from src.common.dictionaries_enum import ApprovalReviewStatusEnum

class Approval(...):
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 启动时由 scripts/check_dictionary_refs.py 校验 DB 实际值 ⊆ enum 集合
```

**`permissions/cache.py`** 改为：
```python
# 旧 ALL_PAGE_KEYS 元组保留（兼容）
# ALL_PAGE_KEYS: tuple[str, ...] = (...)

# 新代码：ALL_PAGE_KEYS 从 DB 拉取，启动时缓存
async def get_all_page_keys() -> tuple[str, ...]:
    items = await LookupService.get("page_key")
    return tuple(i["key"] for i in items if i["is_active"])
```

**兼容期长度**：3 个 release（~6 周）。3 个 release 后删掉旧 StrEnum 兜底。

---

## 四、API 设计

### 4.1 读 API（任何登录用户）

**`GET /api/lookups`** — 列出全部字典概要
```json
[
  {"code": "approval_review_status", "label_zh": "审核状态", "label_en": "Review Status", "version": 1, "is_active": true},
  {"code": "reject_reason", "label_zh": "拒绝原因", "label_en": "Reject Reason", "version": 1, "is_active": true}
]
```

**`GET /api/lookups/{dict_code}`** — 列出某字典全部 item
```json
{
  "code": "approval_review_status",
  "label_zh": "审核状态",
  "label_en": "Review Status",
  "version": 1,
  "items": [
    {"key": "pending", "label_zh": "待审核", "label_en": "Pending", "sort": 1, "is_active": true, "metadata_json": null},
    {"key": "approved", "label_zh": "已批准", "label_en": "Approved", "sort": 2, "is_active": true, "metadata_json": null}
  ]
}
```

**Query 参数**：
- `?only_active=true`（默认 true）— 只返回 `is_active=true` 的 item
- `?lang=zh|en|both`（默认 both）— 是否带 en label

**`GET /api/lookups/{dict_code}/{key}`** — 查单个 item
```json
// 200 Response
{"key": "pending", "label_zh": "待审核", "label_en": "Pending", "sort": 1, "is_active": true}
// 404 Response
{"detail": "lookup item 'approval_review_status:foo' not found"}
```

### 4.2 写 API（全部 `require_super_admin` + SafetyGuard）

**`POST /api/admin/dicts/{dict_code}/items`** — 新增 item
```json
// Request
{"key": "qa_refine", "label_zh": "QA 精修", "label_en": "QA Refine", "sort": 6, "metadata_json": {"color": "blue"}}
// 201 Response
{"key": "qa_refine", "label_zh": "QA 精修", "label_en": "QA Refine", ...}
// 409 Conflict
{"detail": "item 'approval_kind:qa_refine' already exists"}
// 403 Forbidden（非 super_admin）
{"detail": "super_admin required"}
```

**`PATCH /api/admin/dicts/{dict_code}/items/{key}`** — 改 item（label/sort/metadata_json/is_active）
```json
// Request - 重命名 key 必须两步
{"label_zh": "已重新审核", "sort": 1}
// 400 Bad Request - 试图改 key
{"detail": "key rename not allowed; POST new item + migrate data + deprecate old"}
// 404 Not Found
{"detail": "item 'approval_kind:foo' not found"}
```

**`DELETE /api/admin/dicts/{dict_code}/items/{key}`** — 软删（必须 confirm token）
```
// Header
X-Confirm-Token: <require_super_admin password hash>
// 200 Response
{"key": "foo", "is_active": false, "deprecated_at": "2026-06-19T10:00:00Z"}
// 409 Conflict - 仍有业务引用
{"detail": "item 'reject_reason:duplicate' still referenced by 12 approvals; soft-delete refused. Use ?force=true to bypass (audit logged)"}
// 412 Precondition Failed - confirm token 错误
{"detail": "invalid confirm token"}
```

### 4.3 字典级管理

**`POST /api/admin/dicts`** — 新建字典
**`PATCH /api/admin/dicts/{dict_code}`** — 改字典 metadata / is_active / version 升级
**`GET /api/admin/dicts/{dict_code}/audit`** — 字典变更历史（接 `audit_log` 表）

### 4.4 错误码统一表

| HTTP | 含义 | 场景 |
|------|------|------|
| 200 | 成功 | GET / 普通 PATCH |
| 201 | 创建成功 | POST |
| 400 | 请求体格式错 | schema 校验失败 |
| 401 | 未登录 | token 缺失/失效 |
| 403 | 无权限 | 非 super_admin / env readonly / 字典 is_readonly |
| 404 | 字典/item 不存在 | |
| 409 | 冲突 | item 已存在 / 业务引用未解 |
| 412 | Precondition 失败 | confirm token 错 / X-If-Version 不匹配 |
| 422 | 语义错 | key 含非法字符 / label 长度超限 |
| 429 | rate limit | IP 超 60 次/分钟 |

### 4.5 rate limit 复用

复用现有 `src/core/rate_limiter.py`，对 `/api/admin/dicts/*` 套 `60 次/分钟/IP` 限制。

### 4.6 输入校验（Pydantic Schema）

```python
class LookupItemCreate(BaseModel):
    key: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,63}$")  # 全小写字母数字下划线
    label_zh: str = Field(..., min_length=1, max_length=128)
    label_en: str = Field(..., min_length=1, max_length=128)
    sort: int = Field(0, ge=0, le=9999)
    metadata_json: dict | None = None

class LookupItemPatch(BaseModel):
    label_zh: str | None = Field(None, min_length=1, max_length=128)
    label_en: str | None = Field(None, min_length=1, max_length=128)
    sort: int | None = Field(None, ge=0, le=9999)
    is_active: bool | None = None
    metadata_json: dict | None = None
    # 禁止改 key（必须 POST 新 + migrate + DELETE 旧）

class LookupItemResponse(BaseModel):
    key: str
    label_zh: str
    label_en: str
    sort: int
    is_active: bool
    metadata_json: dict | None = None
    effective_at: datetime | None = None
    deprecated_at: datetime | None = None
```

### 4.7 审计日志

复用 `audit_log` 表（项目已有），每条字典变更写入：

```python
audit_log.insert(
    actor=current_user.email,
    action="dictionary.item.patch",
    target=f"{dict_code}:{key}",
    before={"label_zh": "原", "sort": 1},
    after={"label_zh": "新", "sort": 2},
    ip=request.client.host,
)
```

---

## 五、SafetyGuard 6 层防御 & 前端

### 5.1 防御层级

```python
# src/lookups/safety_guard.py
class SafetyGuard:
    """所有 POST/PATCH/DELETE 走这 6 层, 任一失败立刻 raise LookupSafetyError"""

    def check_all(
        self,
        *,
        action: Literal["create", "patch", "delete", "rename"],
        dict_code: str,
        key: str | None,
        user: CurrentUser,
        confirm_token: str | None,
        payload: dict,
    ):
        # 第 1 层：鉴权
        self._check_role(user)
        # 第 2 层：env / 字典级只读
        self._check_readonly(dict_code)
        # 第 3 层：二次确认（删除必须）
        self._check_confirm_token(action, user, confirm_token)
        # 第 4 层：引用检查（删除/重命名必须）
        self._check_business_references(action, dict_code, key)
        # 第 5 层：版本冲突（乐观锁）
        self._check_version(dict_code, payload.get("expected_version"))
        # 第 6 层：rate limit
        self._check_rate_limit(user)
```

### 5.2 每层细节

**第 1 层 - 鉴权**：
```python
def _check_role(self, user: CurrentUser):
    if user.role != "super_admin":
        raise LookupSafetyError(403, "super_admin required")
```

**第 2 层 - 只读**：
```python
def _check_readonly(self, dict_code: str):
    # env 全局逃生口
    if os.getenv("DICTIONARY_READONLY", "").lower() == "true":
        raise LookupSafetyError(403, "DICTIONARY_READONLY=true")
    # 字典级只读
    if self._cache.get_dict_readonly(dict_code):
        raise LookupSafetyError(403, f"dictionary '{dict_code}' is readonly")
```

**第 3 层 - 二次确认**（删除必走）：
```python
def _check_confirm_token(self, action, user, confirm_token):
    if action != "delete":
        return
    expected = hashlib.sha256(
        f"{user.password_hash}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        .encode()
    ).hexdigest()[:16]
    if confirm_token != expected:
        raise LookupSafetyError(412, "invalid confirm token (re-fetch and retry)")
```

**第 4 层 - 引用检查**（删除必走）：
```python
def _check_business_references(self, action, dict_code, key):
    if action != "delete":
        return
    # 业务表 → 字典项 的反向引用 map
    refs = self._REFERENCE_MAP.get(dict_code, [])
    total = 0
    for table, column in refs:
        total += self._count_where(table, column == key)
    if total > 0:
        raise LookupSafetyError(
            409,
            f"item '{dict_code}:{key}' still referenced by {total} rows; "
            f"soft-delete refused. Use ?force=true to bypass (audit logged)"
        )

# 引用 map（启动时注册）
_REFERENCE_MAP = {
    "approval_kind":          [("approvals", "kind")],
    "approval_review_status": [("approvals", "review_status")],
    "approval_apply_status":  [("approvals", "apply_status")],
    "reject_reason":          [("approvals", "reject_reason")],
    "page_key":               [("role_permissions", "page_key")],
    "role_kind":              [("accounts", "role")],  # 未来
}
```

**第 5 层 - 乐观锁**：
```python
def _check_version(self, dict_code, expected_version):
    if expected_version is None:
        return  # 不要求乐观锁
    current = self._cache.get_dict_version(dict_code)
    if current != expected_version:
        raise LookupSafetyError(
            412, f"version mismatch: expected={expected_version}, current={current}"
        )
```

**第 6 层 - rate limit**：
```python
def _check_rate_limit(self, user):
    key = f"dict_admin:{user.id}"
    if not rate_limiter.allow(key, max_per_minute=60):
        raise LookupSafetyError(429, "rate limit exceeded")
```

### 5.3 紧急逃生口

**env 全局只读**：`DICTIONARY_READONLY=true` → 所有 PATCH/DELETE/POST 立刻 403，GET 不受影响。

**字典级只读**：DB `dictionaries.is_readonly=true` → 该字典所有写操作 403，其他字典正常。

**优先级**：env > 字典级 > 业务逻辑。

### 5.4 软删除语义

DELETE 不是真删：
```sql
UPDATE dictionary_items
SET is_active = FALSE,
    deprecated_at = NOW(),
    version = version + 1
WHERE dict_code = :dict_code AND key = :key
```
- `is_active=FALSE` → GET 列表自动过滤（除非 `?only_active=false`）
- `deprecated_at` 设置 → 历史数据还能 refer，但前端下拉看不到
- `version + 1` → 触发缓存失效

`?force=true` 绕过引用检查（仍走 SafetyGuard 其他 5 层 + audit 强制标 `forced=true`）。

### 5.5 前端 `useLookup` Hook

`packages/web/hooks/useLookup.ts`：

```typescript
import useSWR from "swr";

export function useLookup(
  dictCode: string,
  opts?: { lang?: "zh" | "en" | "both"; onlyActive?: boolean }
) {
  const lang = opts?.lang ?? "both";
  const onlyActive = opts?.onlyActive ?? true;
  const { data, error, mutate } = useSWR(
    `/api/lookups/${dictCode}?lang=${lang}&only_active=${onlyActive}`,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 5 * 60 * 1000 } // 5 分钟
  );
  return {
    items: data?.items ?? [],
    byKey: Object.fromEntries((data?.items ?? []).map(i => [i.key, i])),
    labelFor: (key: string, locale: "zh" | "en" = "zh") =>
      data?.items.find(i => i.key === key)?.[`label_${locale}`] ?? key,
    error,
    refresh: mutate,
  };
}

// 用法
const { items, labelFor } = useLookup("approval_review_status");
return <Select options={items.map(i => ({value: i.key, label: labelFor(i.key)}))} />;
```

### 5.6 前端 Admin UI（最小可用）

路径：`packages/web/app/[locale]/admin/dicts/page.tsx`

**功能（最小集）**：
- 顶部下拉选 dict_code
- 列表展示：key / label_zh / label_en / sort / is_active
- 行内编辑 label / sort / is_active（PATCH 调用）
- "新增 item" 按钮（POST 调用）
- "删除 item" 按钮（弹二次确认输入框 → 调 confirm-token API → DELETE）
- "查看历史" 按钮（GET audit log）
- "导入/导出" 按钮（CSV / JSON）
- 顶部显示 `DICTIONARY_READONLY` 状态条（绿色正常 / 红色只读）

**不做**：可视化排序（拖拽）、批量编辑、字典 schema 改版（version 升 2 时的字段迁移 UI）— 下个 phase。

### 5.7 测试覆盖（≥90%）

- 单元测试：SafetyGuard 6 层每层一个 case
- 集成测试：完整 CRUD + cache 失效广播
- 端到端：super_admin 登录 → 增删改 → 普通用户 GET 看到新值
- 兼容测试：现有 enum 不变（approvals/router 等通过 contract test）
- 安全测试：非 super_admin 调 POST → 403；env readonly → 403；引用检查 → 409；版本冲突 → 412

---

## 六、实施节奏 & 风险

### 6.1 任务清单（10 个 task）

```
Phase 1 - 数据层 (Task 1-3)
├── Task 1: Alembic migration 建 2 张表 + 索引
├── Task 2: seed yaml + seed_dictionaries.py 启动脚本
└── Task 3: 代码 enum 镜像（dictionaries_enum.py 从 yaml 编译 StrEnum）

Phase 2 - 核心服务 (Task 4-6)
├── Task 4: LookupService + LookupCache（Redis）+ LookupSafetyGuard（6 层）
├── Task 5: /api/lookups/* GET API（任何登录用户）
└── Task 6: /api/admin/dicts/* 写 API（super_admin）

Phase 3 - 迁移期双写 (Task 7)
└── Task 7: 现有 4 个 enum 接入 lookup（保留兼容，schema Literal 改用字典 enum）

Phase 4 - 前端 + 文档 (Task 8-10)
├── Task 8: useLookup hook + 替换现有 enum 用法
├── Task 9: Admin UI 最小可用版
└── Task 10: 文档（spec/plan/README + 子教程 cookbook/python/lookup.md）
```

### 6.2 任务依赖图

```
Task 1 ─→ Task 2 ─→ Task 3 ─┐
                            ├─→ Task 4 ─→ Task 5
                            │     │
                            │     └─→ Task 6
                            │           │
                            │           └─→ Task 7 (迁移 4 个 enum)
                            │                 │
                            │                 └─→ Task 8 (前端 hook)
                            │                       │
                            │                       └─→ Task 9 (Admin UI)
                            │
                            └─→ Task 10 (docs, 并行)
```

### 6.3 每个 task 的可量化验收

| Task | 验收标准 |
|------|---------|
| 1 | migration head 成功；`\d dictionaries` / `\d dictionary_items` 看到正确列+索引 |
| 2 | `python -m scripts.seed_dictionaries` 输出"已 seed N 字典 M item"；重复运行幂等 |
| 3 | `from src.common.dictionaries_enum import ApprovalReviewStatusEnum; ApprovalReviewStatusEnum.PENDING.value == "pending"` |
| 4 | 单元测试覆盖 LookupService 8 个方法、SafetyGuard 6 层；集成测试 cache 失效广播 |
| 5 | curl `/api/lookups/approval_review_status` 200 OK 返回 items 数组 |
| 6 | curl POST `/api/admin/dicts/approval_kind/items` 普通用户 403，super_admin 201 |
| 7 | 现有 approvals router + permissions router 全部走 lookup；旧 StrEnum 仍兼容；contract test 通过 |
| 8 | 前端 `<Select options={useLookup(...).items} />` 实际工作；i18n 走 label_zh |
| 9 | Admin UI 增删改查 4 个 demo dict 全跑通；截图附 PR |
| 10 | `docs/superpowers/specs/2026-06-19-lookup-module.md` 已存 + `docs/cookbook/python/lookup.md` 已写 |

### 6.4 估算工时

| Phase | Tasks | 估算（含测试 + 文档） |
|-------|-------|---------------------|
| Phase 1 数据层 | 3 | 6-8 小时 |
| Phase 2 核心服务 | 3 | 10-12 小时 |
| Phase 3 迁移 | 1 | 4-6 小时 |
| Phase 4 前端 + 文档 | 3 | 8-10 小时 |
| **总计** | **10** | **~30-36 小时** |

### 6.5 风险清单

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| R1 | seed 重启覆盖 super_admin 后台改的 label | 中 | 中 | seed 默认 UPSERT 不覆盖，仅缺项补；强制重新同步需 `--force-sync` |
| R2 | 现有 schema Literal 与 DB 不一致 | 中 | 高 | `scripts/check_dictionary_refs.py` 启动时校验；不一致启动失败 |
| R3 | Redis 挂掉时 LookupService 退化 | 中 | 中 | 复用 permission_cache_redis 的 Redis 挂掉降级模式（进程内 L1 缓存 fallback） |
| R4 | 缓存失效广播丢消息 | 低 | 中 | TTL 兜底（5 分钟）+ 双删策略（DEL + 延迟 100ms 再 DEL） |
| R5 | 双写兼容期太短，新代码漏接 lookup | 中 | 中 | contract test 强制 `/api/admin/dicts/*` 与 schema enum 交叉验证 |
| R6 | soft delete 后历史数据 refer 失败 | 低 | 中 | 软删不真删 + `deprecated_at` 标记 + GET 支持 `?only_active=false` |
| R7 | 字典 API 被滥用打爆 DB | 低 | 中 | rate limit 60/分钟 + env readonly 逃生口 |
| R8 | Admin UI 安全漏洞（XSS / CSRF） | 低 | 高 | 复用现有 CSRF + admin path 已 `require_super_admin`；前端 label 用 React 转义 |
| R9 | 迁移期数据丢失 | 极低 | 极高 | 双写期 DB 唯一事实源，旧 StrEnum 仅镜像；任何写操作只走 DB |
| R10 | 字典改动导致前端下拉错乱 | 中 | 低 | 改动实时生效，但前端 `useSWR` 5 分钟缓存；如需立即生效用 `mutate()` |

### 6.6 验收门（subagent 严格审）

每完成一个 task，dispatch `gsd-code-reviewer` subagent 严格审：
1. 代码风格（与现有 approvals/models.py 等保持一致）
2. 测试覆盖 ≥90%
3. 文档引用真实（file_path:line_number 真实存在）
4. migration 可回滚（提供 downgrade）
5. 安全 6 层防御任一缺失 → FAIL

### 6.7 范围外（本次明确不做）

- ❌ 自动代码生成（StrEnum → Literal codegen）— 收益低、风险高
- ❌ 字典版本兼容迁移工具（version 升 2 时字段迁移脚本）— 下个 phase
- ❌ 字典可视化 schema 编辑器 — 下个 phase
- ❌ 字典批量导入 UI（仅 CLI） — admin UI 第一版只接 CSV
- ❌ 字典使用统计（哪个 item 用得最多） — 评估后决定
- ❌ 字典 i18n 多语言扩展（zh/en 以外）— 下个 phase

---

## 七、迁移兼容 & 文档

### 7.1 双写期兼容矩阵

迁移分 **3 个 release**（~6 周），每个 release 推进一层：

| Release | 范围 | 兼容性 |
|---------|------|--------|
| **R1 (本 plan)** | DB + API + seed + Admin UI 上线，旧 enum 仍可工作 | **完全兼容**，旧 StrEnum 仍 import，旧 Literal 仍生效 |
| **R2** | schema Literal 改用 `dictionaries_enum.StrEnum`，router 走 `LookupService` | API 形态不变，前端零感知 |
| **R3** | 删旧 StrEnum 兜底代码，删除兼容 shim | 已无外部依赖，可干净删除 |

**R1 关键约束**：
- ✅ DB 表加进来，旧 enum 不删
- ✅ 新 API 上线，旧 API 路径不变
- ✅ seed 启动跑一次，旧代码不受影响
- ✅ 旧 StrEnum 仍可 `from src.approvals.models import ApprovalReviewStatus`
- ✅ 旧 Literal 仍可在 router 校验

**R2 关键改动**：
- `approvals/models.py` 的 StrEnum 改为 `from src.common.dictionaries_enum import ApprovalReviewStatusEnum`（仍兼容 StrEnum 接口）
- `permissions/cache.py` 的 `ALL_PAGE_KEYS` 改为 `from src.lookups.service import LookupService; ALL_PAGE_KEYS = tuple(i["key"] for i in LookupService.get_sync("page_key"))`
- 业务代码不直接 import 旧 enum，统一走 lookup

**R3 收尾**：
- 删 `approvals/models.py` 的旧 StrEnum 定义
- 删 `permissions/cache.py` 的硬编元组
- 删兼容 shim 文件
- README 标注 "字典迁移完成"

### 7.2 启动时一致性校验

`src/scripts/check_dictionary_refs.py` 在 main.py 启动时跑：

```python
def check_consistency():
    """启动时检查: DB 字典 ⊇ yaml 字典 (DB 是超集)"""
    yaml_dicts = load_seed_yaml().keys()
    db_dicts = LookupService.list_all_dicts_sync()
    missing = yaml_dicts - db_dicts
    if missing:
        raise RuntimeError(f"DB missing dictionaries: {missing}; run seed_dictionaries")
    # 检查 schema enum ⊆ DB items
    for code, enum_cls in ENUM_REGISTRY.items():
        db_keys = {i.key for i in LookupService.get_sync(code) if i.is_active}
        enum_keys = {e.value for e in enum_cls}
        if not enum_keys.issubset(db_keys):
            extra = enum_keys - db_keys
            raise RuntimeError(f"enum {enum_cls.__name__} has keys not in DB: {extra}")
```

挂到 `main.py` 启动流程（lifespan），不一致就 fail-fast。

### 7.3 contract test 加固

`tests/test_api_contract.py` 加测试：
- 扫所有 `src/**/router.py`，找 `Literal["a","b","c"]` 模式
- 断言：每个 Literal 值都在对应字典的 DB items 里（若该字典已注册到 `_REFERENCE_MAP`）
- 扫所有 StrEnum，断言同上
- 每次 CI 必跑

### 7.4 文档交付

**`docs/superpowers/specs/2026-06-19-lookup-module.md`** — 本 spec 文档

**`docs/superpowers/plans/2026-06-19-lookup-module.md`** — 本 plan 文档（writing-plans 阶段）

**`docs/cookbook/python/lookup.md`** — 教程（按 L-语言类模板 9 节写，~5000 字）

教程章节大纲：
1. 是什么 & 适用场景（定位：业务字典，与硬编 enum 对比）
2. 安装 & 开发环境（无新依赖，复用 alembic / redis / fastapi）
3. 基础语法 & 类型系统（Pydantic schema、StrEnum 编译、YAML）
4. 核心概念（dictionaries / dictionary_items / LookupService / Cache / SafetyGuard / Reference Map）
5. 常用命令 & 工具链（seed / check / migrate / force-sync）
6. 项目集成点（在哪些 router / schema 引用，如何新加一个字典）
7. 项目代码示例（真实 file_path:line_number 引用，至少 5 段）
8. 项目没用到的能力（多租户 / 灰度发布 / codegen 都不做）
9. 最佳实践 & 常见坑（双写期注意事项 / 引用 map 注册 / env readonly 逃生口）

**`packages/service/CLAUDE.md`**（项目内已有）— 加一段「字典使用规范」：
- 业务 enum 必须走 lookup，不许新增硬编 StrEnum（除非 LLM 框架要求）
- 新加字典必须：①yaml 种子 + ②reference map 注册 + ③docs 更新
- DB 是唯一事实源，yaml 仅种子

**`packages/service/src/lookups/README.md`**（模块内）：
- 模块结构图
- 公共 API 一览
- 测试运行方式

### 7.5 spec 自审清单

写到 spec 后自审：
1. 占位符扫描：无 TBD/TODO
2. 内部一致性：架构 ↔ 数据模型 ↔ API ↔ SafetyGuard 6 层 一致
3. 范围：聚焦 DB+API+seed+UI+迁移，codegen/可视化编辑明确出范围
4. 歧义：所有 enum 命名/字段长度/优先级有显式决定

### 7.6 与已有 CLAUDE.md / 项目规约的协同

复用已有规范：
- **中文注释**：所有 Python 加中文 docstring + 行内注释
- **测试位置**：所有测试放 `packages/service/tests/lookups/`（沿用 `tests/` 模式）
- **TDD 流程**：每个 task 先写测试再实现
- **不删注释**：迁移期保留旧 enum 上方注释 "兼容期 R1"，不删
- **不删 BFF 路由**：本模块是后端 + 前端 admin，不动 BFF；如需加 BFF，单独 spec
- **合同测试**：本模块变更会让 contract test 跑过（新增 dict 后 contract test 自动覆盖）

---

## 八、范围外 & 总结

### 8.1 长期范围内但本次不做

| 项 | 原因 | 何时评估 |
|----|------|----------|
| **自动代码生成**（StrEnum → Literal codegen） | 收益低、双向 sync 复杂度高、风险大 | R3 后看团队反馈 |
| **字典版本迁移工具**（version 2 时字段迁移脚本） | 用例少、手工 SQL 够用 | 第一个字典升 v2 时 |
| **字典可视化 schema 编辑器** | 投入大、YAGNI | 字典超过 30 个时 |
| **字典批量编辑 UI** | CSV/JSON 导入够用 | admin 反馈"不够用"时 |
| **字典使用统计**（哪个 item 用得最多） | 业务数据从 audit_log 推算 | 需做产品决策时 |
| **多语言扩展**（ja/ko 等） | zh/en 覆盖目标用户 | 真正支持多语言时 |
| **A/B 测试 / 灰度发布 UI** | `is_active` + `effective_at` 已支持 | super_admin 反馈"需要"时 |
| **跨项目多租户**（`project_id` 字段） | 单租户架构，无需 | 多项目时 |
| **字典 API GraphQL** | REST 够用，GraphQL 复杂 | API 频繁变时 |

### 8.2 永远不在范围内

- ❌ 字典驱动业务逻辑（字典只做 enum，不做 rule engine）
- ❌ 字典内容由 LLM 自动生成（super_admin 人工维护）
- ❌ 字典即代码（DB 唯一事实源，不是 yaml 即代码）

### 8.3 设计总结

**问题**：项目里 enum 散落 4+ 处，magic string 遍布 schema/router/前端，改一发而动全身；多语言 label 不集中；改 enum 必须发版。

**方案**（方向 C）：DB 通用业务字典 + Redis 缓存 + 代码 enum 镜像 + 前端 API + Admin UI + 安全 6 层防御。

**收益**：
- 改 enum 不发版（runtime DB + cache invalidate）
- 前后端一致（前端只调 `/api/lookups/*`）
- 多语言 label 一处维护
- super_admin 后台可增删改 + 审计 + 软删
- env 逃生口 `DICTIONARY_READONLY=true` 紧急下线

**工作量**：~30-36 小时（含测试 + 文档 + 3 个 release 迁移期）。

**安全**：6 层防御（鉴权 / readonly / 二次确认 / 引用检查 / 乐观锁 / rate limit）+ 软删除语义 + audit log + env 逃生口。

**风险**：已识别 10 项，每项有缓解方案；最高风险是"现有 schema 与 DB 不一致"，通过启动时一致性校验 + contract test 兜底。
