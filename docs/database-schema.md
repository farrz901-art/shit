# 数据库表字典 (Database Schema Reference)

> 本文档由扫描全部 SQLAlchemy ORM model + alembic migration 生成 (2026-07-01)。
> **事实源**: 各业务模块 `models.py` + `src/storage/migrations/versions/*.py`。
> 本文档为人工阅读汇总，字段以代码 / migration 为准；改表结构后请同步更新本文件。

## 概览

- **数据库**: PostgreSQL (主库 `rag`)，向量走 `pgvector` 扩展，图谱走独立 Neo4j (不在此文档)。
- **表总数**: 25 张 PostgreSQL 表。
- **时区约定**: 业务表多用 `HKT` (香港时区) 落 `created_at`；日志三表用 `UTC`。
- **软删约定**: `conversations` / `messages` / `dictionaries*` 用 `deleted_at` / `is_active` 软删，cron 定期硬删。
- **JSONB 约定**: 新列一律 `JSONB` (禁 `sa.JSON()`)，详见 [packages/service/CLAUDE.md](../packages/service/CLAUDE.md) §JSONB 使用规范。

### 表分组一览

| 领域 | 表 |
|---|---|
| 账号与鉴权 | `users` · `accounts` · `invites` · `password_resets` · `email_changes` · `deletion_restores` |
| 权限 (RBAC) | `roles` · `role_permissions` |
| 聊天 | `conversations` · `messages` · `chat_shares` |
| 字典 (lookup) | `dictionaries` · `dictionary_items` |
| RAG 评估 | `evaluations` · `evaluation_samples` |
| 审核流 | `approvals` |
| 文档摄取 | `ingest_tasks` |
| 知识图谱审计 | `kg_audit` |
| 系统日志 | `app_logs` · `error_logs` · `audit_logs` |
| 买家画像 | `buyer_profiles` · `profile_field_configs` · `profile_change_logs` |
| 向量检索 | `rag_embeddings` |

---

## 账号与鉴权

### `users` — 客户端匿名用户
定义: [src/auth/models.py](../packages/service/src/auth/models.py)

首次访问 `/api/auth/anon` 后端生成 `public_token` 落库；账号体系上线后可 1:1 关联 `Account`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK, autoincrement | 主键 |
| public_token | String(64) | UNIQUE, NOT NULL, index | 32 字节 hex，客户端持有的匿名 token |
| display_name | String(50) | NULL | 用户昵称 (预留) |
| created_at | DateTime(tz) | NOT NULL | 创建时间 (HKT) |
| last_seen_at | DateTime(tz) | NOT NULL, index | 最后活跃，清理冷用户依据 |
| account_id | Integer | FK→accounts.id (SET NULL), NULL, index | 关联真账号，老匿名 user 留空 |

### `accounts` — 真账号 (email + password)
定义: [src/auth/account_models.py](../packages/service/src/auth/account_models.py)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| email | String(255) | NOT NULL, UNIQUE, CHECK 邮箱格式 | 登录邮箱 |
| password_hash | String(255) | NOT NULL | 密码哈希 |
| display_name | String(50) | NULL | 昵称 |
| role | Text | NOT NULL, default 'user', CHECK IN (super_admin/admin/user) | RBAC 角色 |
| is_active | Boolean | NOT NULL, default True, index | 是否启用 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| last_login_at | DateTime(tz) | NULL | 最后登录 |
| avatar_url | String(500) | NULL | 头像 URL |
| deletion_requested_at | DateTime(tz) | NULL | 注销申请时间 (非空=宽限期内) |

> 派生属性 `is_pending_deletion` = `deletion_requested_at is not None` (不落库)。

### `invites` — 一次性邀请 token
定义: [src/auth/account_models.py](../packages/service/src/auth/account_models.py)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| token | String(64) | NOT NULL, UNIQUE | 邀请 token |
| email | String(255) | NOT NULL, index | 被邀请邮箱 |
| invited_by_account_id | Integer | FK→accounts.id (CASCADE), NOT NULL | 邀请人 |
| expires_at | DateTime(tz) | NOT NULL | 过期时间 |
| redeemed_at | DateTime(tz) | NULL | 兑换时间 |
| account_id | Integer | FK→accounts.id (SET NULL), NULL | 兑换后生成的账号 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |

### `password_resets` — 密码重置一次性 token
定义: [src/auth/account_models.py](../packages/service/src/auth/account_models.py)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| account_id | Integer | FK→accounts.id (CASCADE), NOT NULL | 账号 |
| token | String(64) | NOT NULL, UNIQUE | 重置 token |
| expires_at | DateTime(tz) | NOT NULL | 过期时间 |
| used_at | DateTime(tz) | NULL | 使用时间 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |

### `email_changes` — 邮箱修改一次性 token (7 天过期)
定义: [src/auth/account_models.py](../packages/service/src/auth/account_models.py)

`new_email` 验证成功后切换 `accounts.email`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| account_id | Integer | FK→accounts.id (CASCADE), NOT NULL, index | 账号 |
| new_email | String(255) | NOT NULL | 待切换的新邮箱 |
| token | String(64) | NOT NULL, UNIQUE index | 验证 token |
| expires_at | DateTime(tz) | NOT NULL | 过期时间 |
| used_at | DateTime(tz) | NULL | 使用时间 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |

### `deletion_restores` — 注销撤销一次性 token (7 天过期)
定义: [src/auth/account_models.py](../packages/service/src/auth/account_models.py)

跟注销宽限期同步；`UNIQUE(account_id, used_at)` 防重复。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| account_id | Integer | FK→accounts.id (CASCADE), NOT NULL, index | 账号 |
| token | String(64) | NOT NULL, UNIQUE index | 撤销 token |
| expires_at | DateTime(tz) | NOT NULL | 过期时间 |
| used_at | DateTime(tz) | NULL | 使用时间 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |

---

## 权限 (RBAC)

### `roles` — 角色
定义: [src/permissions/models.py](../packages/service/src/permissions/models.py)

3 预设 (user/admin/super_admin) + super_admin 创建的自定义角色。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| name | Text | NOT NULL, UNIQUE | 角色名 (2-32 字符 [a-z0-9_]) |
| label_zh | Text | NOT NULL | 中文显示名 |
| label_en | Text | NOT NULL | 英文显示名 |
| is_system | Boolean | NOT NULL, default False | 系统内置 (不删) |
| is_deletable | Boolean | NOT NULL, default False | 可被 super_admin 删 |
| created_at | DateTime | NOT NULL | 创建时间 (UTC) |
| updated_at | DateTime | NOT NULL, onupdate | 更新时间 |

### `role_permissions` — 角色 × 页面权限矩阵
定义: [src/permissions/models.py](../packages/service/src/permissions/models.py)

`UNIQUE(role_name, page_key)`；super_admin 不入库，走代码 meta 豁免。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| role_name | Text | NOT NULL | 角色名 |
| page_key | Text | NOT NULL | 页面标识 |
| allowed | Boolean | NOT NULL, default True | 是否放行 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL, onupdate | 更新时间 |

---

## 聊天

### `conversations` — 聊天会话
定义: [src/chat/models.py](../packages/service/src/chat/models.py)

复合索引 `(user_id, updated_at)`；软删 `deleted_at`，cron 30d 后硬删 (GDPR)。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | String(36) | PK | UUID 字符串 (前端 crypto.randomUUID 兼容) |
| user_id | Integer | FK→users.id (CASCADE), NOT NULL, index | 所属用户 |
| title | String(200) | NOT NULL | 标题 |
| message_count | Integer | NOT NULL, default 0 | 冗余消息数 (减少 COUNT) |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| updated_at | DateTime(tz) | NOT NULL, index | 更新时间 |
| deleted_at | DateTime(tz) | NULL | 软删时间戳，NULL=活跃 |

### `messages` — 聊天消息
定义: [src/chat/models.py](../packages/service/src/chat/models.py)

复合索引 `(conversation_id, created_at)` 按时间正序拉。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| conversation_id | String(36) | FK→conversations.id (CASCADE), NOT NULL, index | 所属会话 |
| role | String(20) | NOT NULL | user / assistant / system |
| content | Text | NOT NULL | 消息正文 |
| meta | JSONB | NULL | token 用量 / 模型名 / 工具调用 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| deleted_at | DateTime(tz) | NULL | 软删时间戳 |

### `chat_shares` — 对话分享快照
定义: [src/chat_share/models.py](../packages/service/src/chat_share/models.py)

anon 公开读，所有者可撤销；消息以 JSON 快照存。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| share_id | String(12) | PK | nanoid 12 字符 |
| conv_id | String(36) | FK→conversations.id (CASCADE), NOT NULL, index | 源会话 |
| user_id | Integer | FK→users.id (CASCADE), NOT NULL, index | 所有者 |
| title | String(200) | NULL | 快照标题 |
| messages_json | Text | NOT NULL | 消息快照 JSON |
| model | String(64) | NULL | 模型名 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| expires_at | DateTime(tz) | NULL | 过期时间 |

---

## 字典 (lookup)

### `dictionaries` — 字典定义
定义: [src/lookups/models.py](../packages/service/src/lookups/models.py)

一行 = 一个字典 (如 approval_review_status / page_key)。DB 是运行时事实源，yaml 仅种子。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| code | String(64) | PK | 字典唯一标识 |
| label_zh | String(128) | NOT NULL | 中文名 |
| label_en | String(128) | NOT NULL | 英文名 |
| description | Text | NULL | 描述 |
| version | Integer | NOT NULL, default 1 | schema 版本号 (变更触发缓存失效) |
| is_active | Boolean | NOT NULL, default True | 紧急下线开关 |
| is_readonly | Boolean | NOT NULL, default False | 单字典级只读 |
| effective_at | TIMESTAMP(tz) | NULL | 生效时间 |
| deprecated_at | TIMESTAMP(tz) | NULL | 下线时间 |
| created_at | TIMESTAMP(tz) | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP(tz) | NOT NULL, onupdate | 更新时间 |

### `dictionary_items` — 字典项
定义: [src/lookups/models.py](../packages/service/src/lookups/models.py)

`UNIQUE(dict_code, key)`；`is_active` + `deprecated_at` 配合软删。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK | 主键 |
| dict_code | String(64) | FK→dictionaries.code (CASCADE), NOT NULL | 所属字典 |
| key | String(64) | NOT NULL | 枚举值 key (业务引用，不可变) |
| label_zh | String(128) | NOT NULL | 中文名 |
| label_en | String(128) | NOT NULL | 英文名 |
| description | Text | NULL | 描述 |
| sort | Integer | NOT NULL, default 0 | 排序 |
| is_active | Boolean | NOT NULL, default True | 是否启用 |
| effective_at | TIMESTAMP(tz) | NULL | 生效时间 |
| deprecated_at | TIMESTAMP(tz) | NULL | 下线时间 |
| metadata_json | JSONB | NULL | 扩展位 (颜色/图标/路径) |
| created_at | TIMESTAMP(tz) | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP(tz) | NOT NULL, onupdate | 更新时间 |

---

## RAG 评估

### `evaluations` — 评估任务 (元数据)
定义: [src/eval/models.py](../packages/service/src/eval/models.py)

复合索引 `(user_id, created_at)`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| user_id | Integer | FK→users.id, NOT NULL, index | 发起用户 |
| dataset_name | String(200) | NOT NULL | 数据集名 |
| dataset_path | String(500) | NULL | 本地路径 (旧) |
| dataset_uri | String(500) | NULL | MinIO/local URI (新) |
| status | String(20) | NOT NULL, index | pending/running/completed/failed/cancelled |
| total_samples | Integer | NOT NULL, default 0 | 样本总数 |
| successful | Integer | NOT NULL, default 0 | 成功数 |
| failed | Integer | NOT NULL, default 0 | 失败数 |
| concurrency | Integer | NOT NULL, default 5 | 并发度 |
| avg_metrics | JSONB | NULL | 平均指标 (faithfulness 等 4 项) |
| duration_seconds | Float | NULL | 总耗时 |
| error_message | Text | NULL | 错误信息 |
| cancel_requested_at | DateTime(tz) | NULL | 取消请求时间 |
| created_at | DateTime(tz) | NOT NULL, index | 创建时间 |
| finished_at | DateTime(tz) | NULL | 完成时间 |

### `evaluation_samples` — 评估样本
定义: [src/eval/models.py](../packages/service/src/eval/models.py)

复合索引 `(evaluation_id, index)`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| evaluation_id | Integer | FK→evaluations.id (CASCADE), NOT NULL, index | 所属评估 |
| index | Integer | NOT NULL | 样本序号 |
| question | Text | NOT NULL | 问题 |
| ground_truth | Text | NULL | 标准答案 |
| answer | Text | NULL | 模型答案 |
| contexts | JSONB | NULL | 召回上下文列表 |
| sources | JSONB | NULL | 召回文件元数据 [{name,position,score,snippet}] |
| metrics | JSONB | NULL | 单样本 4 指标 |
| error | Text | NULL | 错误信息 |
| duration_ms | Integer | NULL | 耗时 (毫秒) |

---

## 审核流

### `approvals` — 审核项
定义: [src/approvals/models.py](../packages/service/src/approvals/models.py)

状态拆 2 轴 (review + apply)；枚举走 `dictionaries_enum`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| kind | String(20) | NOT NULL, index | 审核类型 |
| payload | Text | NOT NULL | JSON 字符串 |
| review_status | String(20) | NOT NULL, default PENDING, index | 审核状态轴 |
| apply_status | String(20) | NOT NULL, default NONE, index | 应用状态轴 |
| submitter_id | Integer | FK→users.id, NOT NULL, index | 提交人 |
| reviewer_id | Integer | FK→users.id, NULL, index | 审核人 |
| rejection_reason | String(40) | NULL | 拒绝原因 key |
| rejection_note | Text | NULL | 拒绝补充说明 |
| error_msg | Text | NULL | 写库失败信息 |
| created_at | DateTime(tz) | NOT NULL, index | 创建时间 |
| reviewed_at | DateTime(tz) | NULL | 审核时间 |
| applied_at | DateTime(tz) | NULL | 应用时间 |

---

## 文档摄取

### `ingest_tasks` — 摄取任务元数据
定义: [src/ingest/models.py](../packages/service/src/ingest/models.py)

替原 SQLite `ingest_tasks.db`；复合索引 `(user_hash, started_at)`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | String(36) | PK | 业务 UUID 字符串 |
| user_hash | String(64) | NOT NULL, index | 用户标识 (cookie hash) |
| state | String(20) | NOT NULL | pending/running/completed/failed |
| total_files | Integer | NOT NULL, default 0 | 文件总数 |
| processed | Integer | NOT NULL, default 0 | 已处理数 |
| failed | Integer | NOT NULL, default 0 | 失败数 |
| started_at | DateTime(tz) | NOT NULL | 开始时间 |
| finished_at | DateTime(tz) | NULL | 结束时间 |
| error | Text | NULL | 错误信息 |
| work_dir | String(500) | NULL | input prefix URI (s3://.../local://) |
| input_files_json | Text | NOT NULL, default '[]' | 输入文件列表 JSON |
| output_files_json | Text | NOT NULL, default '[]' | 输出文件列表 JSON |

---

## 知识图谱审计

### `kg_audit` — 知识图谱审计日志
定义: [src/kg/audit_models.py](../packages/service/src/kg/audit_models.py)

替原 SQLite `kg_audit.db`；记录对 Neo4j 图谱的操作。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| ts | Float | NOT NULL, index | Unix 时间戳 (秒) |
| action | String(100) | NOT NULL | 操作类型 (create_triple 等) |
| actor | String(100) | NULL | 操作者标识 |
| target | String(200) | NULL | 操作目标 (triple/node id) |
| result | String(20) | NOT NULL | ok / error |
| detail | Text | NOT NULL | 详细信息 JSON 字符串 |

---

## 系统日志

> 三表均**按月 RANGE 分区** (如 `app_logs_2026_07`)，带 BRIN(ts) 索引，UTC 时间。
> DDL 见 [20260617_000000_create_log_tables.py](../packages/service/src/storage/migrations/versions/20260617_000000_create_log_tables.py)。
> 写入逻辑见 [src/core/logging.py](../packages/service/src/core/logging.py)。

### `app_logs` — 应用日志 (WARNING+)
定义: [src/db/models/app_log.py](../packages/service/src/db/models/app_log.py)

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK (BIGSERIAL) | 主键 |
| ts | DateTime(tz) | NOT NULL, 分区键 | 时间 |
| level | Text | NOT NULL, CHECK IN (DEBUG..CRITICAL) | 级别 (仅写 WARNING+) |
| logger | Text | NOT NULL | logger 名 |
| message | Text | NOT NULL | 日志正文 |
| request_id | UUID | NULL | 请求 ID |
| user_id | BigInteger | NULL | 用户 ID |
| trace_id | CHAR(32) | NULL | 链路 ID |
| context | JSONB | NOT NULL, default {} | 上下文 (PII 已 scrub)，GIN 索引 |

### `error_logs` — 错误日志 (5xx)
定义: [src/db/models/error_log.py](../packages/service/src/db/models/error_log.py)

由全局 5xx handler 同步写入。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK | 主键 |
| ts | DateTime(tz) | NOT NULL, 分区键 | 时间 |
| level | Text | NOT NULL | 级别 |
| exception_type | Text | NOT NULL | 异常类型 |
| exception_msg | Text | NOT NULL | 异常消息 (截断 1000) |
| stacktrace | Text | NULL | 堆栈 (截断 5000) |
| request_id | UUID | NULL | 请求 ID |
| user_id | BigInteger | NULL | 用户 ID |
| path | Text | NULL | 请求路径 |
| method | Text | NULL | HTTP 方法 |
| status_code | Integer | NULL | 状态码 |
| context | JSONB | NOT NULL, default {} | 上下文 |

### `audit_logs` — 审计日志 (append-only)
定义: [src/db/models/audit_log.py](../packages/service/src/db/models/audit_log.py)

**只追加**：触发器禁 UPDATE/DELETE。由 `@audited` 装饰器写入 (DELETE/改账户/改权限/导出)。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK | 主键 |
| ts | DateTime(tz) | NOT NULL, 分区键 | 时间 |
| actor_id | BigInteger | NOT NULL | 操作者 ID |
| actor_type | Text | NOT NULL, default 'user' | 操作者类型 |
| action | Text | NOT NULL | 动作 (foo.delete 等) |
| target_type | Text | NOT NULL | 目标类型 |
| target_id | Text | NOT NULL | 目标 ID |
| ip | INET | NULL | 来源 IP |
| user_agent | Text | NULL | UA |
| request_id | UUID | NULL | 请求 ID |
| result | Text | NOT NULL, default 'success' | 结果 |
| before | JSONB | NULL | 变更前快照 |
| after | JSONB | NULL | 变更后快照 |
| metadata | JSONB | NOT NULL, default {} | 附加信息 (ORM 属性名 `meta`，映射列 `metadata`)，GIN 索引 |

---

## 买家画像

> DDL 见 [20260622_000000_create_buyer_profiles.py](../packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py)。
> 走 raw SQL 访问 (无 ORM model)，业务逻辑见 [src/buyer_profile/service.py](../packages/service/src/buyer_profile/service.py)。

### `buyer_profiles` — 买家结构化画像
每个买家一条，`UNIQUE(account_id, buyer_key)`；`profile_data` 带 GIN(jsonb_path_ops) 索引。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | 主键 |
| account_id | Integer | FK→accounts.id, NOT NULL, index | 所属账号 |
| buyer_key | String(128) | NOT NULL | 买家唯一 key |
| buyer_name | String(256) | NULL | 买家名 |
| status | String(32) | NOT NULL, default 'active' | active / archived |
| profile_data | JSONB | NOT NULL, default {} | 画像结构化数据 (GIN 索引) |
| profile_meta | JSONB | NOT NULL, default {} | 画像元数据 |
| tags | ARRAY(String) | NULL, default {} | 标签 |
| notes | Text | NULL | 备注 |
| assignee_id | Integer | NULL | 负责人 |
| first_seen_at | DateTime(tz) | NOT NULL | 首次接触 |
| last_contact_at | DateTime(tz) | NULL | 最后联系 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| updated_at | DateTime(tz) | NOT NULL | 更新时间 |

### `profile_field_configs` — 画像字段定义
`UNIQUE(account_id, code)`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer | PK | 主键 |
| account_id | Integer | FK→accounts.id, NOT NULL | 所属账号 |
| code | String(64) | NOT NULL | 字段代码 |
| label | String(128) | NOT NULL | 字段显示名 |
| field_type | String(32) | NOT NULL, default 'text' | 字段类型 |
| extraction_prompt | Text | NULL | LLM 抽取提示词 |
| options | JSONB | NULL, default [] | 可选项 (枚举型) |
| is_required | Boolean | NOT NULL, default False | 是否必填 |
| sort_order | Integer | NOT NULL, default 0 | 排序 |
| is_active | Boolean | NOT NULL, default True | 是否启用 |
| notify_on_change | JSONB | NULL, default [] | 变更通知配置 |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |
| updated_at | DateTime(tz) | NOT NULL | 更新时间 |

### `profile_change_logs` — 画像字段变更日志
索引 `(profile_id, created_at DESC)`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK | 主键 |
| account_id | Integer | FK→accounts.id, NOT NULL | 所属账号 |
| profile_id | UUID | FK→buyer_profiles.id, NOT NULL | 所属画像 |
| field_code | String(64) | NOT NULL | 变更字段 |
| old_value | JSONB | NULL | 旧值 |
| new_value | JSONB | NULL | 新值 |
| source | String(32) | NOT NULL, default 'auto' | 变更来源 (auto/manual) |
| conv_id | String(128) | NULL | 触发变更的会话 ID |
| created_at | DateTime(tz) | NOT NULL | 创建时间 |

---

## 向量检索

### `rag_embeddings` — RAG 向量表 (pgvector)
DDL 见 [20260629_000000_lc_pgvector_schema.py](../packages/service/src/storage/migrations/versions/20260629_000000_lc_pgvector_schema.py)。

由 LangChain `PGVectorStore` 管理 (标准 schema)，封装见 [src/retrieval/vector_store.py](../packages/service/src/retrieval/vector_store.py)。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| langchain_id | UUID | PK, default gen_random_uuid() | 主键 |
| content | Text | NOT NULL | 文本块内容 |
| embedding | vector(dim) | — | 向量 (维度由 embedder 决定)，HNSW cosine 索引 |
| langchain_metadata | JSONB | default {} | 元数据 (含 ref_doc_id)，GIN(jsonb_path_ops) 索引 |

> 索引: `rag_embeddings_hnsw_idx` (HNSW m=16, ef_construction=200) + `rag_embeddings_metadata_gin_idx`。
> 删除按 `metadata.ref_doc_id` 走 `@>` 操作符匹配。

---

## 附注

- **知识图谱**: 节点/关系存 Neo4j (非 PostgreSQL)，schema 定义在 `configs/knowledge-schema.yaml`，不在本文档范围。
- **Redis**: 仅做缓存/限流 (无持久化表)，key 规范见 [packages/service/CLAUDE.md](../packages/service/CLAUDE.md) §Redis 使用约定。
- **对象存储**: 文件走 MinIO/LocalFS (URI 形式存于业务表字段)，见 §ObjectStore ABC。
- **迁移**: 全部 DDL 以 [src/storage/migrations/versions/](../packages/service/src/storage/migrations/versions/) 为准；改表结构走 `uv run alembic revision` 且必须写可回滚 `downgrade`。
