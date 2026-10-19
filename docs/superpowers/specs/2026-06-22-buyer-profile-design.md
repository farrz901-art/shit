# 买家画像系统设计

**日期**: 2026-06-22
**状态**: 设计稿
**作者**: 设计对话沉淀 (基于 LarkAgent 参考 + 项目现有 mem0 长期记忆)

---

## Context

### 业务场景

平台面向中东/非洲的工业设备采购商 (冶金设备、工作设备、电机设备), AI (Dify Chatflow) 自动跟买家聊天了解需求, 系统需要为每个买家建立**结构化的采购画像**。

- 买家通过 WhatsApp / Web Widget 进入聊天, 无需平台账号
- AI 自动代聊, 理解买家需求、推荐匹配供应商
- 每个买家应该有**结构化的采购画像**供内部团队查看和检索
- 买家画像字段应该**可配置** (不同垂直行业字段不同)
- 画像变化时通知内部团队 (如买家从询价进入比价阶段)

### 现有基础设施

- **mem0 长期记忆** (src/memory/): self-host pgvector, 对话事实抽取 + 语义检索, withMemoryHooks 已在 chat BFF 层集成
- **FastAPI + 鉴权**: require_account / require_super_admin guards
- **lookup 字典** (src/lookups/): 可配置的枚举管理
- **前端组件栈**: DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form + FormField

### 关键决策记录

| 决策 | 选择 |
|---|---|
| mem0 vs BuyerProfile 关系 | **并行**: mem0 继续做对话上下文, BuyerProfile 做结构化画像 |
| 画像存储 | JSONB (buyer_profiles.profile_data) |
| 画像字段配置 | 独立表 profile_field_configs, 按 account_id 隔离 |
| 买家识别 | buyer_key (WhatsApp 号 / Email), 在 memory/add 时传入 |
| 提取时机 | memory/router.py add 端点 -> fire-and-forget 异步提取 |
| 权限 | 复用项目已有 RBAC (普通用户 -> 管理员 -> 超级管理员) |
| 页面位置 | 独立导航菜单项, 跟用户管理分开 |
---

## 架构总览

```
买家发起聊天
     |
     v
Dify Chatflow (AI自动代聊)
     |
     v
withMemoryHooks (已有)
  +-- Pre-LLM: mem0.search -> 注入上下文
  +-- 流中累积对话
  +-- Post-LLM:
        +-- mem0.add() -> 事实抽取 (已有)
        +-- BuyerProfileService.try_extract() -> 新增
              |
              +-- 取 field_configs -> 拼 LLM prompt
              +-- LLM 提取字段值 -> 与旧值 diff
              +-- 有变化 -> UPDATE buyer_profiles
              +-- 写 change_logs
              +-- 关键字段变化 -> 触发通知
```

### 分层图

```
+-----------------------------------+
| 前端 (packages/web/)              |
|  +-- 买家列表 / 买家详情           |
|  +-- 画像字段配置页                |
+-----------------------------------+
         | HTTP
         v
+-----------------------------------+
| FastAPI (packages/service/)       |
|  +-- buyer_profile/router.py      |
|  +-- buyer_profile/service.py     |
|  +-- buyer_profile/extractor.py   |
|  +-- buyer_profile/field_config.py|
|  +-- buyer_profile/change_notifier|
+-----------------------------------+
         |
    +----+----+
    |         |
    v         v
+--------+  +-------------+
| mem0   |  | PostgreSQL  |
|(pgvec) |  | JSONB / SQL |
+--------+  +-------------+
```

---

## 数据模型

### buyer_profiles 表

每个买家一条记录, 以 (account_id, buyer_key) 唯一标识。

```sql
CREATE TABLE buyer_profiles (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id    INTEGER NOT NULL REFERENCES accounts(id),
  buyer_key     VARCHAR(128) NOT NULL,
  buyer_name    VARCHAR(256),
  status        VARCHAR(32) DEFAULT 'active',
  profile_data  JSONB NOT NULL DEFAULT '{}',
    -- { field_code: { value, confidence, source, updated_at }, ... }
  profile_meta  JSONB NOT NULL DEFAULT '{}',
  tags          TEXT[] DEFAULT '{}',
  notes         TEXT,
  assignee_id   INTEGER REFERENCES accounts(id),
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_contact_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, buyer_key)
);

CREATE INDEX idx_buyer_profiles_account ON buyer_profiles(account_id);
CREATE INDEX idx_buyer_profiles_data ON buyer_profiles USING GIN (profile_data jsonb_path_ops);
```

### profile_field_configs 表

画像字段定义, 按 account_id 隔离。管理员可增删改字段。

```sql
CREATE TABLE profile_field_configs (
  id              SERIAL PRIMARY KEY,
  account_id      INTEGER NOT NULL REFERENCES accounts(id),
  code            VARCHAR(64) NOT NULL,
  label           VARCHAR(128) NOT NULL,
  field_type      VARCHAR(32) NOT NULL DEFAULT 'text',
  extraction_prompt TEXT,
  options         JSONB DEFAULT '[]',
  is_required     BOOLEAN DEFAULT FALSE,
  sort_order      INT DEFAULT 0,
  is_active       BOOLEAN DEFAULT TRUE,
  notify_on_change JSONB DEFAULT '[]',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, code)
);
```

### profile_change_logs 表

```sql
CREATE TABLE profile_change_logs (
  id            BIGSERIAL PRIMARY KEY,
  account_id    INTEGER NOT NULL REFERENCES accounts(id),
  profile_id    UUID NOT NULL REFERENCES buyer_profiles(id),
  field_code    VARCHAR(64) NOT NULL,
  old_value     JSONB,
  new_value     JSONB,
  source        VARCHAR(32) NOT NULL DEFAULT 'auto',
  conv_id       VARCHAR(128),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_profile_changes_profile ON profile_change_logs(profile_id, created_at DESC);
```

---

## 组件设计

### buyer_profile 模块 (packages/service/src/buyer_profile/)

| 文件 | 职责 |
|---|---|
| __init__.py | 模块导出 |
| schemas.py | Pydantic request/response 模型 |
| service.py | ProfileService: 提取 -> diff -> 更新 -> 日志 -> 通知 |
| router.py | HTTP 端点 (列表/详情/编辑/搜索/字段配置) |
| field_config.py | 画像字段配置 CRUD |
| extractor.py | LLM 提取引擎: 对话 -> 结构化字段值 |
| change_notifier.py | 变更检测 -> 站内通知 / Webhook |

### module/router.py 端点

```
买家画像
  GET    /api/buyer-profiles             - 列表 (分页+筛选+JSONB 查询)
  GET    /api/buyer-profiles/{id}        - 详情 (含画像+变更历史)
  PATCH  /api/buyer-profiles/{id}        - 人工编辑画像字段值
  DELETE /api/buyer-profiles/{id}        - 归档买家
  GET    /api/buyer-profiles/search      - 按字段全文搜索
  GET    /api/buyer-profiles/{id}/changes - 变更日志

画像字段配置
  GET    /api/buyer-profiles/fields          - 字段列表
  POST   /api/buyer-profiles/fields          - 新增字段
  PATCH  /api/buyer-profiles/fields/{code}  - 编辑字段
  DELETE /api/buyer-profiles/fields/{code}  - 软删字段

调试
  POST   /api/buyer-profiles/_extract       - 手动触发提取
```

---

## 集成点

### 1. memory/add 端点 (1 处改动)

```python
# memory/router.py add 端点
@router.post("/add")
def add(req: AddRequest, current: CurrentUser = Depends(require_account)):
    msg_dicts = [t.model_dump() for t in req.messages]
    _get_service().add(current, msg_dicts, req.conversation_id)

    # 新增: 异步提取买家画像
    if req.buyer_key and current.account_id:
        import asyncio
        asyncio.create_task(
            BuyerProfileService.try_extract(
                account_id=current.account_id,
                buyer_key=req.buyer_key,
                messages=msg_dicts,
            )
        )

    return Response(status_code=204)
```

### 2. memory/schemas.py AddRequest (1 行改动)

```python
class AddRequest(BaseModel):
    messages: list[TurnMessage]
    conversation_id: str | None = None
    buyer_key: str | None = None  # 新增: 买家唯一标识
```

### 3. router 注册

```python
# __init__.py register_routers
from .buyer_profile.router import router as buyer_profile_router
app.include_router(buyer_profile_router)
```

---

## LLM 提取引擎 (extractor.py)

### 提取 prompt 模板

```
你是一个采购需求分析专家。请从以下对话中提取买家的采购画像信息。

已有画像 (这些已确认, 没有新信息则保持原值):
{现有字段值 JSON}

配置的画像字段:
{字段列表: code + label + field_type + extraction_prompt}

对话内容:
{本轮对话全文}

请输出 JSON, key=字段 code, value=提取的值。
对于 tags 类型, value 为数组。无信息时留 null。
只输出 JSON, 不要额外文字。
```

### 提取逻辑

```python
def extract_from_conversation(account_id, buyer_key, messages):
    # 1. 取 active field_configs
    configs = field_config.get_active_configs(account_id)
    if not configs:
        return  # 没有配置字段, 跳过

    # 2. 取已有画像
    profile = service.get_profile(account_id, buyer_key)
    existing = profile.profile_data if profile else {}

    # 3. 拼 prompt 调 LLM
    prompt = _build_extraction_prompt(configs, existing, messages)
    llm_result = _call_llm(prompt)  # -> {field_code: value_or_null}

    # 4. diff 并更新
    changes = _detect_changes(existing, llm_result)
    if changes:
        service.update_profile_fields(account_id, buyer_key, changes)
        change_logger.log_changes(account_id, profile_id, changes)
        change_notifier.check_and_notify(account_id, changes, configs)
```

---

## 变更通知

### 触发规则

每个 `profile_field_config` 有 `notify_on_change` 字段, 定义当字段值变为什么时触发通知。

```json
// notify_on_change 示例
[
  {"type": "value_in", "values": ["比价", "样品", "下单", "紧急"]},
  {"type": "any_change", "fields": ["equipment_type", "budget"]}
]
```

### 通知渠道 (Phase 1 先做站内通知)

- **站内通知**: 用项目已有的通知表
- **Webhook**: 用于对接外部 CRM (Phase 2)

---

## 权限矩阵

| 操作 | 游客 | 普通用户 | 管理员 | 超级管理员 |
|---|---|---|---|---|
| 查看买家列表 | - | 自己负责的 | 全部 | 全部 |
| 查看买家详情 | - | 自己负责的 | 全部 | 全部 |
| 编辑画像值 | - | 自己负责的 | 全部 | 全部 |
| 归档/删除买家 | - | - | 是 | 是 |
| 管理字段配置 | - | - | 是 | 是 |
| 查看所有账号 | - | - | - | 是 |

实现: 复用项目已有 guards (require_account / require_super_admin)。

---

## 前端页面

### 页面结构

```
导航
  +-- 仪表盘 (已有)
  +-- 对话 (已有)
  +-- 买家画像 (新增)
  |     +-- 买家列表 /zh/buyers
  |     +-- 买家详情 /zh/buyers/{id}
  +-- 用户管理 (已有)
  +-- 系统设置
        +-- 画像字段配置 /zh/admin/profile-fields (新增)
```

### 买家列表页

- 筛选栏: 国家 / 设备类型 / 决策阶段 / 日期范围 / 负责人
- DataTable 展示: 买家名称 / 国家 / 设备类型 / 决策阶段 / 最后联系时间
- 点击行进入详情

### 买家详情页

- ProfileCard: 所有字段展示, 每个字段带 confidence badge
- 编辑模式: 点击编辑按钮, 表单修改字段值
- 变更历史时间线: 显示每次字段变化
- 对话记录: 该买家的历史对话列表

### 画像字段配置页

- 字段列表 (表格)
- 新增字段弹窗: code / label / type / extraction_prompt / options
- 编辑字段
- 软删字段 (is_active=false)

---

## 测试策略

| 测试类型 | 模式 | 覆盖 |
|---|---|---|
| 单元测试 (service) | 模式 1 (mock) | ProfileService diff/update/change_detect |
| 单元测试 (extractor) | 模式 1 (mock LLM) | Extraction prompt 构建 + 结果解析 |
| 单测 (field_config) | 模式 1 (mock session) | 字段配置 CRUD |
| 单测 (router) | 模式 1 (mock service) | HTTP 端点参数校验 + 权限 |
| 集成测试 | 模式 2 (db_session) | SQL + JSONB 查询 |
| 前端测试 | vitest mock fetch | 页面渲染 + 交互 |

降级策略: extractor 任何异常 -> WARNING log, 不阻断对话, 跟 mem0 一致。

---

## 非目标 (YAGNI)

- 不重写 mem0: mem0 保持独立, 不做合并
- 不做跨账号数据互通: 每个 account_id 完全隔离
- 不做 E2E Playwright 测试: 单测 + 集成测试覆盖关键路径
- 不做画像导出/导入
- 不做批量导入买家 (只有 AI 对话发现)
- 不做 Webhook 通知 (Phase 2)

---

## 未来扩展

- **Webhook 通知**: 画像变化推送到外部 CRM
- **画像导出**: 买家名单导出 CSV
- **自动匹配**: 根据画像字段自动推荐匹配供应商
- **画像对比**: 对比买家在不同时间的画像变化趋势
