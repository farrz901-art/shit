# 2026-07-10 Pre-analysis 表格加 "创建人" 列 设计

> Brainstorming 沉淀. 用户报告: admin/pre-analysis 列表的 DataTable 缺创建人字段,
> 想在表格中看到上传人昵称 (非 user_hash).
>
> 本 spec 在 `pre_analysis_tasks` 表加 2 列 (`creator_account_id` / `creator_name`),
> upload 时写入, list 时透传给前端展示. **list 接口过滤范围不变** (仍按 user_hash 过滤),
> 仅埋好数据结构供未来多用户场景.

## 1. 背景

### 1.1 现状 (代码已确认)

`packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx:147-243`
DataTable 当前 11 列: 任务编号 / PDF 文件名 / 状态 / 总体阶段 / 表格提取器 / 上传时间 /
耗时 / 表格数 / 章节数 / 标记段落数 / 操作. **无 "创建人" 列**.

后端 ORM `packages/service/src/ingest/pre_analysis/models.py:33-50` `pre_analysis_tasks` 表
字段: `id` / `user_hash` / `state` / `pdf_filename` / `pdf_uri` / `started_at` / `finished_at` /
`error` / `output_files_json` / `summary_json` / `task_config_json` / `current_stage`.

- `user_hash: String(64)` 是从 token 派生的 8 字符短哈希 (`sha256(token)[:8]`,
  见 `packages/service/src/ingest/common.py:15-17`), 跟 `accounts` / `users` 表**无 FK**
- 没有任何字段冗余创建人昵称

list 接口 `packages/service/src/ingest/pre_analysis/router.py:154-168`
`list_pre_analysis_tasks` 调用 `pa_list_user_tasks(uhash, limit, offset)`
(`store.py:79-93`), **单表 WHERE `user_hash == uhash`**, 无 JOIN, `_to_dict`
(`store.py:23-45`) 只透传 `user_hash: str`, 真实昵称无源可查.

### 1.2 用户报告

- 表格里希望看到 "这条任务是谁上传的", 而非 8 字符哈希或空白
- 后端 list 接口目前按当前 super_admin 的 user_hash 过滤 (router.py:165-167), 即列表里所有任务的 "创建人" 恒等于当前登录用户
- 用户**已知情**, 仍要加列: 接受 "列里全是当前用户昵称" 的事实, 主要是为 UI 视觉对称 + 埋好数据结构供未来多用户场景

### 1.3 关键设计决策

1. **list 过滤范围不变**: 仍按 `user_hash` 过滤当前 super_admin 的任务, 不放开成全平台
2. **昵称用快照**: tasks 表存 `creator_name` (String, 上传时从 CurrentUser.display_name 复制), 不实时 JOIN accounts 表 — 历史任务不随账号改名而变
3. **同时存 FK**: `creator_account_id` (FK → accounts.id, ON DELETE SET NULL) 供未来真正多人分析用
4. **不做 data migration backfill**: 旧行 `creator_*` 留 NULL, 无法从 user_hash 反查 token (单向哈希)

### 1.4 现有 helper (lib/api/pre-analysis.ts)

- `PreAnalysisTaskItem` type (`packages/web/lib/api/pre-analysis.ts:96-109`) 字段: `id` / `state` / `user_hash` / `pdf_filename` / `pdf_uri` / `started_at` / `finished_at` / `current_stage` / `summary` / `error` / `task_config_json`. **无 `creator_*` 字段**
- `listPreAnalysisTasks({ limit, offset })` 走 catch-all BFF 透传 `GET /api/pre-analysis/tasks`

`CurrentUser` 类型 (`packages/service/src/middleware/auth.py:58-75`): BaseModel, 字段
`id` / `public_token` / `account_id: int | None` / `display_name: str | None` / `email` /
`role` / `is_account` / `is_admin`. super_admin 走真账号路径, **已带 `account_id + display_name`**.

## 2. 数据流

### 2.1 Upload 时

1. 用户上传 PDF → `PreAnalysisUploadDialog` 调 `preAnalysisUpload(file, config, chapterConfig)`
2. → catch-all BFF `packages/web/app/api/[...path]/route.ts:191-205` 透传到后端
3. → `router.py:68` `Depends(require_super_admin)` 解析 `CurrentUser` (带 `account_id` + `display_name`)
4. → `pa_save_task(...)` (`router.py:130-140`) 写入 `creator_account_id = user.account_id` + `creator_name = user.display_name`
5. → ORM 落 PG, 新 task 带创建人快照

### 2.2 List 时

1. 表格 mount → `useQuery(["pre-analysis-tasks"], listPreAnalysisTasks)`
2. → catch-all BFF 透传 `GET /api/pre-analysis/tasks`
3. → `router.py:154-168` `list_pre_analysis_tasks` 调 `pa_list_user_tasks(uhash, limit, offset)` (按 user_hash 过滤, 保持现状)
4. → `store.py:79-93` 不动, 还是单表 WHERE, 无 JOIN
5. → `_to_dict(include_output_files=False)` 多返 `creator_account_id` + `creator_name`
6. → 前端 `PreAnalysisTaskItem.creator_name` 直接展示

**关键**: list 仍按当前 super_admin 的 user_hash 过滤, 列表里所有行的 `creator_name` 都是当前登录用户昵称. 数据结构已就绪, 未来要改 list 接口返全平台任务时, 0 后端改动 (只换 store 的 query).

## 3. 改动清单 (5 后端 + 4 前端 + 3 测试)

### 3.1 后端

#### 3.1.1 ORM `packages/service/src/ingest/pre_analysis/models.py` `PreAnalysisTask` 类

在 `user_hash` 字段后加:

```python
creator_account_id: Mapped[int | None] = mapped_column(
    Integer,
    ForeignKey("accounts.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
creator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

#### 3.1.2 Alembic migration 新文件 `packages/service/alembic/versions/2026_07_10_xxxx-add-pre-analysis-creator-fields.py`

```python
"""add creator fields to pre_analysis_tasks

实施时跑 `alembic revision -m "add creator fields to pre_analysis_tasks"`,
alembic 自动填 revision 字符串 + down_revision (取最新 revision) + create date.
本 spec 只列 upgrade/downgrade 内容, 头部 metadata 由 alembic 生成.
"""

from alembic import op
import sqlalchemy as sa


revision = "..."
down_revision = "..."
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pre_analysis_tasks",
        sa.Column("creator_account_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "pre_analysis_tasks",
        sa.Column("creator_name", sa.String(100), nullable=True),
    )
    op.create_foreign_key(
        "fk_pre_analysis_tasks_creator",
        "pre_analysis_tasks",
        "accounts",
        ["creator_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_pre_analysis_tasks_creator_account",
        "pre_analysis_tasks",
        ["creator_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pre_analysis_tasks_creator_account", table_name="pre_analysis_tasks")
    op.drop_constraint("fk_pre_analysis_tasks_creator", "pre_analysis_tasks", type_="foreignkey")
    op.drop_column("pre_analysis_tasks", "creator_name")
    op.drop_column("pre_analysis_tasks", "creator_account_id")
```

#### 3.1.3 store `packages/service/src/ingest/pre_analysis/store.py:23-45` `_to_dict`

result dict 多塞 2 个 key:

```python
"creator_account_id": task.creator_account_id,
"creator_name": task.creator_name,
```

#### 3.1.4 router upload `packages/service/src/ingest/pre_analysis/router.py:89-140` `pa_save_task({...})` 调用

传入 2 个新字段:

```python
pa_save_task(
    {
        "id": task_id,
        "user_hash": uhash,
        "creator_account_id": user.account_id,
        "creator_name": user.display_name,
        "state": "pending",
        ...
    },
    task_config=full_task_config,
)
```

注意 `user.account_id: int | None` / `user.display_name: str | None` 都是 optional, ORM 字段 `nullable=True` 兜底, anon 路径不崩.

#### 3.1.5 retry endpoint **不动**

`router.py:313-378` `retry_pre_analysis_task` 重置 task 状态但**不重写 `creator_*`**, 保留创建人快照语义 (重试者 ≠ 创建者). JSDoc 提一句.

### 3.2 前端

#### 3.2.1 type `packages/web/lib/api/pre-analysis.ts:96-109` `PreAnalysisTaskItem` 加 2 字段

```ts
creator_account_id: number | null;
creator_name: string | null;
```

#### 3.2.2 列 `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` `columns` 数组

在 `pdf_filename` 后加一列 (跟 "上传时间" 语义上靠近):

```tsx
{
  accessorKey: "creator_name",
  cell: (ctx) => ctx.row.original.creator_name ?? PLACEHOLDER_DASH,
  header: () => translate("创建人"),
},
```

#### 3.2.3 i18n `packages/web/messages/zh.json` + `en.json`

- `zh.json`: `"创建人": "创建人"` (identity)
- `en.json`: `"创建人": "Creator"`

#### 3.2.4 测试 `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` (新建)

列渲染测试: 有 `creator_name` 时显示昵称, 无时显示 `—`.

### 3.3 测试

#### 3.3.1 后端 `tests/ingest/pre_analysis/test_store.py`

测 `_to_dict` 包含新字段, 字段缺失时返 None.

#### 3.3.2 后端 `tests/ingest/pre_analysis/test_router.py`

测 upload mock CurrentUser 后, `creator_account_id` / `creator_name` 正确写入.

#### 3.3.3 前端 `admin-pre-analysis-client.test.tsx` (新建)

列渲染断言.

## 4. 错误处理 + 风险

### 4.1 历史脏数据

- 现存 `pre_analysis_tasks` 行 `creator_account_id` / `creator_name` 都是 NULL
- migration `add column nullable=True`, 旧行 NULL 合法
- 前端 cell `?? PLACEHOLDER_DASH` 兜底
- 不写 data migration backfill (无法从 `user_hash` 反查 token, 单向哈希)

### 4.2 anon 路径兜底

`CurrentUser.account_id` / `display_name` 是 `int | None` / `str | None`. 当前 pre-analysis 路由要求 super_admin, 实际请求 `account_id` 必有值, ORM 字段 `nullable=True` 兜底未来放开.

### 4.3 retry 行为

`creator_*` 不重写, 历史创建人语义保留. retry endpoint JSDoc 注释提一句.

### 4.4 字段命名一致性

| 层 | 字段名 |
|----|--------|
| ORM (snake_case) | `creator_account_id` / `creator_name` |
| Pydantic 字典 key (透传) | `creator_account_id` / `creator_name` |
| 前端 type field | `creator_account_id` / `creator_name` |
| 列头 (中文 UI) | "创建人" |
| i18n key (zh) | `创建人` |
| i18n value (en) | `Creator` |

### 4.5 alembic 历史漂移 (走项目铁律)

- 迁移前先 `cd packages/service && uv run alembic current` 拿最新 revision 编号作 `down_revision`
- 文件名 `2026_07_10_HHMM-add-pre-analysis-creator-fields.py` (HHMM 用生成时的本地时间)
- downgrade 反向删: 删 index → 删 FK → 删 2 column
- 验证: `alembic downgrade -1 && alembic upgrade head` 干净
- 跟项目 [[feedback-check-constraint-drift-on-stage-rename]] 一样: 加列必须同 commit migration

### 4.6 错误处理

- upload 写入失败 (PG 异常) → 走现有 500 错误路径, 不新加 try/except
- migration 失败 → alembic 标准报错, 不动 schema (alembic 事务回滚)
- 前端 `creator_name` 为 null → 列显示 `—` (跟现有 `pdf_filename` / `current_stage` / `summary.*` 缺失字段统一用 `PLACEHOLDER_DASH` 兜底)
- i18n 缺失 → next-intl dev 报 MISSING_MESSAGE, 重启 `bun run dev` + hard refresh (项目 [[feedback-next-intl-dev-messages-cache]])

## 5. 不做的事 (YAGNI)

- ❌ 不改 list 接口过滤逻辑 (用户确认 "仅显示当前 user")
- ❌ 不改 retry endpoint (creator 字段不重写, 历史语义保留)
- ❌ 不写 backfill data migration (无法反向查 token)
- ❌ 前端暂不消费 `creator_account_id` (后续真多人时才用)
- ❌ 不引入新 Pydantic schema (沿用 dict 透传, 跟现状一致)
- ❌ 不改 BFF / 不加新 API (透传现成的)

## 6. 验证

### 6.1 后端单文件测试

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v
```

### 6.2 前端单文件测试

```bash
cd packages/web && bun run test -- admin-pre-analysis-client.test.tsx
```

### 6.3 手测流程

1. `cd packages/service && uv run alembic upgrade head` — 看 2 列已加
2. 重启后端 `uv run python main.py`
3. 上传 PDF → 表格出现 "创建人" 列, 显示当前 super_admin 昵称
4. 历史脏数据行 → 显示 `—`

### 6.4 Commit 前必跑

```bash
cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright
cd packages/web && bun run format && bun run lint:fix && bun run typecheck
```

## 7. 范围 + 工作量

- **总代码行数: ~70 行** (含测试)
- **改动文件: 9 个** (5 后端 + 4 前端)
- **新建文件: 3 个** (migration + 2 测试文件)
- **单 commit 可完成**, 不需要拆分
- **预估耗时: 30-45 分钟**

## 8. 关联

- [[feedback-check-constraint-drift-on-stage-rename]] — 加列必须同 commit migration
- [[feedback-next-intl-dev-messages-cache]] — i18n 加 key 后 dev 重启
- [[feedback-i18n-sync-on-ui-changes]] — 改 UI 加 t("...") 必同步 zh/en.json
- [[feedback-no-shim-no-minimal-changes]] — 列定义用 `?? PLACEHOLDER_DASH` 现有 const, 不新加 wrapper
- [[feedback-clarify-ambiguous-instructions]] — 用户改 "上传人" → "创建人" 已记录
- [[feedback-verify-with-import-not-pip]] — migration 验证靠 alembic upgrade head, 不靠 pip show