# 审核系统设计 (admin 审批写入 Dify/Neo4j)

**日期**: 2026-06-13
**状态**: 设计已批准, 待实施
**作者**: Claude (brainstorming with user)
**关联 spec**: [2026-06-13-account-system-design.md](2026-06-13-account-system-design.md) (is_admin 角色) · [2026-06-12-swr-to-rsc-rq-design.md](2026-06-12-swr-to-rsc-rq-design.md) (RSC + RQ 模式) · [2026-06-10-theme-system-design.md](2026-06-10-theme-system-design.md) (主题 token) · [2026-06-10-i18n-design.md](2026-06-10-i18n-design.md) (i18n)

## Context

RAG 项目当前任何登录账号 (含 anon) 都能直接调 server action 写入 Dify / Neo4j, 没有审批环节:

1. **录 QA** — `_actions/knowledge.ts::createQA` → 直调 `DifyDatasets.createDocumentByText`
2. **录三元组** — `_actions/knowledge.ts::createTriples` → 直调 FastAPI `/api/kg/triples` (Neo4j)
3. **批量导入** — `_actions/knowledge.ts::commitDocuments` → 循环 `DifyDatasets.createDocumentByText`
4. **优化回答** (chat 反馈) — 暂无入口, 计划新增

**问题**:

- 低质量 / 重复内容直接污染知识库
- 运维不知道谁写入了什么
- 出问题无法追溯 (写到 Dify 的 doc id 跟提交人没关联)

**Why**: 用户场景是内部 / B2B, 知识库质量是核心资产。需要 admin 守门, 但又不能让提交者体验差 (要看到自己提交的进度)。

## 目标

1. **4 个写动作全部走审核**: 提交者提交后, 写入 `approvals` 表 (review_status=pending, apply_status=none), **不直接** 调 Dify/Neo4j
2. **Admin 审核 UI** (`/submissions?tab=all`): pending 列表, 1 键批准 / 拒绝 (弹原因) / 重试
3. **提交者进度可见** (`/submissions?tab=mine`): 任何登录用户看自己提交的全部 + 状态 + 错误消息
4. **后台执行** (`BackgroundTask`): admin 批准后, FastAPI inline 异步调 Dify/Neo4j, 成功 → applied, 失败 → failed (admin 可重试)
5. **4 状态机**: pending / approved / applied / rejected / failed, 状态转换全部 SQL 化
6. **i18n + 主题 + RSC/RQ 复用**: 跟项目现有 2026-06-10/12 系列 spec 保持一致

## 非目标

- 不做 review workflow (assignee / claimed / 多人协作审) — 1 admin 够用
- 不做审核 audit log (改了什么都不记) — 后续
- 不做 approval 时限 (超过 N 天自动 reject) — 后续
- 不做 webhook 通知 (admin / 提交者) — 后续
- 不做"批量批准" 按钮 — 1 个 1 批简单清晰
- 不改 anon 系统 — 提交者还是 anon 也能提交 (但 admin 必须真账号)
- 不删除任何现有 server action — 仅改其内部实现 (从直调 Dify 改为调 approvals.submit)
- 不改现有 Dify / Neo4j 业务调用 — `apply()` 内部复用原 DifyDatasets / KgClient 调用代码
- 不做 A/B 测试 / 灰度 — 一次性切换
- 不引入新依赖 (APScheduler / Celery / Dramatiq) — 用 FastAPI BackgroundTasks

## 关键决策 (锁定)

| 决策        | 选择                                                           | 理由                                                   |
| ----------- | -------------------------------------------------------------- | ------------------------------------------------------ |
| 拦截层      | **前端提交层 (server action)**                                 | 用户决策 1; 统一入口, 4 个动作改造可控                 |
| 审核者      | **只有 admin** (`accounts.is_admin`)                           | 用户决策 2; 复用现有 admin 角色, 不加 reviewer         |
| 状态颗粒    | **3+1 状态**: pending / approved / applied / rejected / failed | 用户决策 3; 失败独立状态可重试                         |
| 状态机粒度  | **按写动作 1:1**                                               | 用户决策 4; 1 次提交 = 1 个审核项, 简单                |
| 写库失败    | **转 failed + admin 可重试**                                   | 用户决策 5; 状态清晰, 不丢数据                         |
| Admin 页面  | **合并到 `/submissions/*`, admin 才见 "全部待审" tab**         | 用户决策: 2 个页面同模块, 不放 /admin, 不放 /dashboard |
| 提交者页面  | **`/submissions` "我提交的" tab (任何登录用户)**               | 跟 admin tab 同一路由, 切换不切路由                    |
| 数据存      | **`approvals` 单表, payload=JSON 字符串**                      | 避免 4 个 kind 各自建表 schema 漂移                    |
| 异步执行    | **FastAPI BackgroundTask, inline 跑**                          | 不引新依赖                                             |
| 前端架构    | **RSC 首屏 + RQ 接管交互**                                     | 跟 2026-06-12 swr-to-rsc-rq spec 一致                  |
| 主题 / i18n | **复用 next-themes + next-intl**                               | 已有, 不重造                                           |

## 架构

### 数据流

```
┌─────────────┐  拦截 server action  ┌──────────┐  admin 批准  ┌──────────────┐  执行     ┌─────────┐
│  前端 UI     │ ─────────────────→ │ approvals│ ──────────→ │ FastAPI 路由 │ ────────→ │ Dify/   │
│ 4 个写动作  │  server action 改    │ 表 + 状态│  Background │  BackgroundTask│        │ Neo4j  │
│             │  调 approvals.submit│ 机       │  Task inline │              │        │        │
└─────────────┘                    └──────────┘             └──────────────┘        └─────────┘
       │                                  │                          │
       │ toast "已提交审核 #142"          │                          │ 失败
       ↓                                  ↓                          ↓
  /submissions?tab=mine            /submissions?tab=all           status=failed
  (RSC, 自己的 user_id)            (RSC, admin only)          admin 点 "重试"
```

### 后端模块布局

```
packages/service/src/approvals/
├── __init__.py
├── models.py          # Approval / ApprovalStatus / ApprovalKind (SQLAlchemy 2.x)
├── service.py         # ApprovalService (submit/approve/reject/retry/apply)
├── executor.py        # apply_approval(id) — 按 kind dispatch 调 Dify/Neo4j
└── router.py          # FastAPI 路由
packages/service/src/auth/
└── middleware.py      # require_admin 依赖项 (已存在, 复用)
packages/service/src/storage/
└── models.py          # Base 导出 (已存在)
```

### 前端布局

```
packages/web/
├── app/
│   ├── [locale]/
│   │   ├── submissions/                             [新顶层, 避开 /admin + /dashboard]
│   │   │   ├── page.tsx                             # RSC: 拿 /me, 决定渲染哪些 Tabs
│   │   │   ├── page.test.tsx
│   │   │   ├── layout.tsx                           # (可选) 共享 header "审核中心"
│   │   │   └── _components/
│   │   │       ├── SubmissionsTabs.tsx              # 客户端: Tabs 切换 (mine / all-admin)
│   │   │       ├── SubmissionsTabs.test.tsx
│   │   │       ├── MySubmissionsList.tsx            # "我提交的" 列表 (任何登录用户可见)
│   │   │       ├── MySubmissionsList.test.tsx
│   │   │       ├── AllApprovalsTable.tsx            # "全部待审 (admin)" 表格 (仅 admin 渲染入口)
│   │   │       ├── AllApprovalsTable.test.tsx
│   │   │       ├── ApprovalRow.tsx                  # 复用行组件 (mine / all 共用)
│   │   │       ├── RejectDialog.tsx                 # 弹框输拒绝原因
│   │   │       └── RejectDialog.test.tsx
│   │   └── _actions/
│   │       └── knowledge.ts                         # 改: 4 个 action 改调 approvals.submit
│   └── api/
│       └── approvals/                               [新 BFF, admin only]
│           └── [id]/
│               ├── approve/route.ts
│               ├── reject/route.ts
│               └── retry/route.ts
├── messages/
│   ├── zh.json                                       # 加 submissions.*
│   └── en.json                                       # 加 submissions.*
└── middleware.ts                                    # 改: /submissions/* 也走 token 守卫 (仅登录即可, 不 admin)
```

## 数据模型

### `approvals` 表 (SQLAlchemy 2.x typed, 跟 Account/Invite 风格一致)

**重要**: 状态拆成 2 个轴 — `review_status` (admin 审批) + `apply_status` (系统写入)。原因: 被拒 (admin 主动) 跟 写库失败 (系统报错) 是 2 个不同事件, 1 个 status 字段信息密度不够, admin 和提交者都看不清。

```python
# packages/service/src/approvals/models.py
from enum import Enum
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

class ApprovalReviewStatus(str, Enum):
    PENDING = "pending"     # admin 还没看
    APPROVED = "approved"   # admin 批准 (写入排队中 / 已尝试)
    REJECTED = "rejected"   # admin 拒绝 (终态, 不再尝试写入)

class ApprovalApplyStatus(str, Enum):
    NONE = "none"           # 还未尝试 (pending / approved 排队中)
    APPLIED = "applied"     # 写入 Dify/Neo4j 成功 (终态)
    FAILED = "failed"       # 写入失败, admin 可重试

# 预设拒绝原因 key (跟前端 Select 选项 1:1, 后端也校验)
class RejectReason(str, Enum):
    DUPLICATE = "duplicate"
    LOW_QUALITY = "low_quality"
    INCOMPLETE = "incomplete"
    WRONG_CATEGORY = "wrong_category"
    FORMAT_ISSUE = "format_issue"
    OTHER = "other"

class ApprovalKind(str, Enum):
    QA = "qa"                 # 录 QA → Dify
    TRIPLE = "triple"         # 录三元组 → Neo4j
    BATCH = "batch"           # 批量导入 → Dify
    OPTIMIZE = "optimize"     # 优化回答 → Dify

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    # 2 个状态轴
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=ApprovalReviewStatus.PENDING.value, index=True,
    )
    apply_status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=ApprovalApplyStatus.NONE.value, index=True,
    )
    submitter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # 拒绝原因: key (如 "duplicate") + 选 other 时的补充说明
    rejection_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)  # RejectReason key
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)         # "other" 时补充
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)              # 写入失败时 Dify/Neo4j 报错
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(HKT), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_approvals_review_created", "review_status", "created_at"),
        Index("idx_approvals_apply_created", "apply_status", "created_at"),
        Index("idx_approvals_submitter_created", "submitter_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Approval id={self.id} kind={self.kind} review={self.review_status} apply={self.apply_status}>"
```

**状态组合矩阵 (5 个有效组合, 3 个终态)**:

| review_status | apply_status | 含义                             | 终态   | 显示色          |
| ------------- | ------------ | -------------------------------- | ------ | --------------- |
| pending       | none         | 待审                             | 否     | warning (黄)    |
| approved      | none         | 已批, 写入排队中 (BGTask 刚启动) | 否     | success 浅 (青) |
| approved      | applied      | ✅ 批准 + 写入成功               | **是** | success (绿)    |
| approved      | failed       | ✅ 批准但写入失败 (admin 可重试) | 否     | error (红)      |
| rejected      | none         | ❌ 被拒 (终态, 不再尝试写入)     | **是** | error (红)      |

**首次部署说明**: 项目 production 还没上线, 无 migration 负担 — 改 schema 直接 deploy。如果将来要回填, 旧 `status` 字段值映射到 2 字段: `pending→(pending,none)` / `approved→(approved,none)` / `applied→(approved,applied)` / `rejected→(rejected,none)` / `failed→(approved,failed)`。

### Payload schema (按 kind)

```python
# 仅文档化, 实际代码用 TypedDict / Pydantic model
QA_PAYLOAD = {
    "dataset_id": str,
    "question": str,
    "answer": str,
    "tags": list[str],         # 可选
    "sync_to_neo4j": bool,     # 可选
}
TRIPLE_PAYLOAD = {
    "rows": [{"from_label": str, "from_key": str, "from_value": str,
              "rel_type": str, "to_label": str, "to_key": str, "to_value": str,
              "properties": dict}, ...],
}
BATCH_PAYLOAD = {
    "dataset_id": str,
    "rows": [{"question": str, "answer": str, "tags": str}, ...],
}
OPTIMIZE_PAYLOAD = {
    "dataset_id": str,
    "question": str,
    "original_answer": str,
    "improved_answer": str,
    "reason": str,             # 改了什么, 为什么
}
```

**为什么 payload 是 JSON 字符串而非 4 张子表**: 4 个 kind 的 payload 字段差异大, 各建子表 schema 漂移风险高 + 跨 kind 通用查询 / 索引都麻烦。存 JSON 字符串, 仅在 executor dispatch 时反序列化。

## API 设计

### FastAPI 路由 (`src/approvals/router.py`)

| 方法   | 路径                                                | 鉴权                         | 行为                                                                                     |
| ------ | --------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------- |
| `GET`  | `/api/approvals?review=&apply=&skip=&limit=`        | **admin**                    | 列出 (默认 review=pending, 按 created_at DESC)                                           |
| `GET`  | `/api/approvals/me?review=&apply=&skip=&limit=`     | 登录                         | 自己 submitter_id=me 的项 (按 review/apply 过滤)                                         |
| `GET`  | `/api/approvals/{id}`                               | 登录 + 是 submitter 或 admin | **详情 (含完整 payload)**, 用于 ApprovalRow 展开时拉                                     |
| `POST` | `/api/approvals`                                    | 登录                         | 新建审核项 (kind + payload), 返回 `{ id, review_status, apply_status }`                  |
| `POST` | `/api/approvals/{id}/approve`                       | **admin**                    | review: pending → approved, 触发 BackgroundTask 跑 apply                                 |
| `POST` | `/api/approvals/{id}/reject` body=`{reason, note?}` | **admin**                    | review: pending → rejected, 写 `rejection_reason=key` + `rejection_note=note` (other 时) |
| `POST` | `/api/approvals/{id}/retry`                         | **admin**                    | apply: failed → none, 触发 BackgroundTask 重跑 (review 必须 = approved)                  |
| `GET`  | `/api/approvals/stats`                              | **admin**                    | dashboard 数字: pending=5 / applied=32 / failed=1                                        |

**reject 端点 body schema** (Pydantic):

```python
class RejectBody(BaseModel):
    reason: RejectReason            # 枚举校验, 必须是 6 个 key 之一
    note: str | None = None         # reason="other" 时必填, 其他选填, 500 字符上限
```

### Service 层 (TDD-friendly 纯函数)

```python
# packages/service/src/approvals/service.py
class ApprovalService:
    async def submit(
        self, kind: ApprovalKind, payload: dict, submitter: CurrentUser
    ) -> Approval:
        """新建审核项, review=pending, apply=none. 任何登录用户可调."""

    async def approve(
        self, approval_id: int, reviewer: CurrentUser
    ) -> Approval:
        """admin 批准. review: pending → approved, apply 保持 none. 抛 ApprovalNotFoundError / InvalidStateError."""
        # 写 reviewer_id, reviewed_at=now()

    async def reject(
        self, approval_id: int, reason: RejectReason, note: str | None, reviewer: CurrentUser
    ) -> Approval:
        """admin 拒绝. review: pending → rejected, apply=none (终态). 写 rejection_reason=key + rejection_note."""
        # reason 必填 (枚举校验, 6 个 key 之一); note 仅 reason="other" 时必填, 其他选填, 500 字符上限

    async def retry(
        self, approval_id: int, reviewer: CurrentUser
    ) -> Approval:
        """admin 重试. apply: failed → none, review 保持 approved. 限制: 仅 (review=approved, apply=failed) 可重试."""

    async def apply(
        self, approval_id: int
    ) -> None:
        """BackgroundTask 跑. 按 kind dispatch executor. 成功 → apply=applied; 异常 → apply=failed + error_msg."""
        # 捕获所有异常 → apply_status=failed, error_msg=str(e)[:1000]
```

### Executor (`src/approvals/executor.py`)

```python
async def apply_approval(approval_id: int) -> None:
    """同步执行, 失败捕获. 写 apply_status=applied 或 failed."""
    approval = await repo.get(approval_id)
    payload = json.loads(approval.payload)
    try:
        if approval.kind == ApprovalKind.QA:
            await DifyDatasets.createDocumentByText(...)  # 跟现 createQA 同
            if payload.get("sync_to_neo4j"):
                await KgClient(...).batch_upsert_triples(...)  # 跟现 createQA 同
        elif approval.kind == ApprovalKind.TRIPLE:
            await KgClient(...).batch_upsert_triples(payload["rows"])
        elif approval.kind == ApprovalKind.BATCH:
            for r in payload["rows"]:
                await DifyDatasets.createDocumentByText(...)
        elif approval.kind == ApprovalKind.OPTIMIZE:
            await DifyDatasets.createDocumentByText(...)
        await service.mark_applied(approval_id)  # apply_status=applied + applied_at=now()
    except Exception as e:
        await service.mark_failed(approval_id, str(e)[:1000])  # apply_status=failed + error_msg
```

**复用原则**: executor 内部调用的 DifyDatasets / KgClient 方法跟现 server action 完全一致, **不引入新逻辑**。仅是"包了一层 try/except + 状态机写回"。

## Server Actions 改造 (4 处)

### `packages/web/app/[locale]/_actions/knowledge.ts` 改写

```typescript
// 改前: 直接调 DifyDatasets / FastAPI
export async function createQA(input: QAInput): Promise<ActionResult<QA>> {
  const doc = await DifyDatasets.createDocumentByText(...);
  return { data: { id: doc.id, ... }, ok: true };
}

// 改后: 调 approvals.submit (经 BFF)
export async function createQA(input: QAInput): Promise<ActionResult<{ approval_id: number; status: "pending" }>> {
  const r = await fetch(`${API_BASE}/api/approvals`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ kind: "qa", payload: input }),
  });
  if (!r.ok) return { error: `HTTP ${r.status}: ${await r.text()}`, ok: false };
  return { data: (await r.json()), ok: true };
}
```

**4 处全部**:

- `createQA` → kind=`qa`
- `createTriples` → kind=`triple`
- `commitDocuments` → kind=`batch`
- 新增 `optimizeAnswer` → kind=`optimize` (从 chat 反馈触发, 见 [前端 UI 集成](#前端-ui-集成))

### POST /api/approvals (新建) — 任何登录用户

```python
@router.post("")
async def submit(
    body: SubmitBody,  # { kind: str, payload: dict }
    user: CurrentUser = Depends(require_login),
) -> Approval:
    kind = ApprovalKind(body.kind)
    return await service.submit(kind, body.payload, user)
```

### Form 层文案改 (4 个表单)

```tsx
// 改前
if (result.ok) toast.success("已写入 Dify");

// 改后
if (result.ok) {
  toast.success(t("submissions.submitted", { id: result.data.approval_id }));
  router.push(`/${locale}/submissions`);
}
```

**改 4 处**:

1. `knowledge/qa/_components/QASubmitForm.tsx`
2. `knowledge/triples/_components/TriplesForm.tsx`
3. `knowledge/documents/import/_components/ImportForm.tsx` (批量)
4. `chat/_components/MessageFeedback.tsx` (新增, 反馈按钮触发 optimizeAnswer)

## 前端 UI 集成

### A) /submissions (新顶层, 1 个 RSC 页面 + Tabs 切换)

**路由策略**: 单 URL `/submissions`, Tabs 切 mine / all (admin 才见 all)。URL 同步 `?tab=mine|all`, RSC 读 searchParams 决定初始 tab + 预取对应数据。

**page.tsx (RSC, 服务端决定 tab 列表)**:

```tsx
// 拿 /me 决定渲染哪些 Tabs, 普通用户根本看不到 "全部待审" 入口
export default async function SubmissionsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const cookieHeader = (await cookies()).toString();
  const meRes = await fetch(`${API_BASE}/api/account/me`, {
    cache: "no-store",
    headers: { cookie: cookieHeader },
  });
  if (!meRes.ok) redirect("/login?next=/submissions");
  const me = await meRes.json();

  const t = await getTranslations();
  // 普通用户: 只渲染 "我提交的"; admin: 加 "全部待审"
  const tabs = me.is_admin
    ? [
        { key: "mine", label: t("submissions.tabs.mine") },
        { key: "all", label: t("submissions.tabs.all") },
      ]
    : [{ key: "mine", label: t("submissions.tabs.mine") }];

  const sp = await searchParams;
  const activeTab = sp.tab ?? "mine";

  // 预取两路数据 (admin 时), 普通用户只预取 mine
  // 默认过滤: mine = (review=pending OR apply=failed), admin = review=pending
  const initialMine = await fetch(`${API_BASE}/api/approvals/me?skip=0&limit=20`, {
    cache: "no-store",
    headers: { cookie: cookieHeader },
  }).then((r) => r.json());

  const initialAll = me.is_admin
    ? await fetch(`${API_BASE}/api/approvals?review=pending&skip=0&limit=20`, {
        cache: "no-store",
        headers: { cookie: cookieHeader },
      }).then((r) => r.json())
    : null;

  return (
    <div className="space-y-6 p-6">
      <h1 className="display text-3xl">{t("submissions.title")}</h1>
      <SubmissionsTabs
        tabs={tabs}
        activeTab={activeTab}
        initialMine={initialMine}
        initialAll={initialAll}
        isAdmin={me.is_admin}
      />
    </div>
  );
}
```

**SubmissionsTabs (client 子组件, 走 RQ + 复用 shadcn Tabs)**:

- `<Tabs value={activeTab}>` (URL 同步)
- 切 tab: `router.push(\`/submissions?tab=\${key}\`)` → 触发 RSC 重跑预取 (跟 swr-to-rsc-rq 一致)
- **mine tab 内容**: `<MySubmissionsList>` (任何登录用户, 只读)
  - RQ `useQuery(['approvals', 'me', { review, apply }, page], ...)` 拉 `/api/approvals/me`
  - 列: ID / kind Badge / **审批状态 Badge** / **写入状态 Badge** / 摘要 (前 50 字) / created_at
  - 行可展开 (用 `<Collapsible>`): 展开时 RQ `useQuery(['approval-detail', id], ...)` 拉 `/api/approvals/{id}` 拿完整 payload
  - 失败 / 被拒行展开区显示: `rejection_reason` 翻译 + `rejection_note` (rejected 时) / `error_msg` (failed 时) / "重新提交" 链接
  - **不显示** 批准 / 拒绝 / 重试按钮
- **all tab 内容 (仅 admin 渲染入口)**: `<AllApprovalsTable>` (复用 shadcn Table + 内嵌状态切换)
  - 内嵌 `<Tabs>` 切 review_status: pending / approved / rejected (admin 关注 3 状态; applied/failed 是写入阶段, admin 可在 "approved" tab 看到)
  - 切 review: RQ `useQuery(['approvals', 'all', { review }, page], ...)` 拉 `/api/approvals?review=`
  - 行可展开 (同 mine, 用 `<ApprovalRow>` 共用)
  - 行内按钮:
    - **批准** (仅 review=pending) → `useMutation` 调 BFF `/api/approvals/[id]/approve`
    - **拒绝** (仅 review=pending) → 弹 `<RejectDialog>` 用 shadcn **Select** 选预设原因 (6 个 key), 选 `other` 时显示 Textarea 补充
    - **重试** (仅 review=approved, apply=failed) → `useMutation` 调 BFF `/api/approvals/[id]/retry`
- 状态 badge (复用 shadcn Badge + 主题 token, mine/all 共用 `<ApprovalRow>` 渲染, **2 个独立 badge**):
  - **审批 badge** (review_status):
    - `pending` → `bg-status-warning/20 text-status-warning` ("待审")
    - `approved` → `bg-status-success/20 text-status-success` ("已批")
    - `rejected` → `bg-status-error/20 text-status-error` ("被拒")
  - **写入 badge** (apply_status):
    - `none` → `bg-muted/20 text-muted-foreground` ("未写入") — pending / rejected 时
    - `applied` → `bg-status-success/20 text-status-success` ("已写入")
    - `failed` → `bg-status-error/20 text-status-error` ("写库失败")
- 展开区 (Collapsible, 复用 shadcn `<Collapsible>`):
  - 任何状态都可展开, 拉 `/api/approvals/{id}` 详情
  - 渲染规则按 kind (mine / all 共用):
    - `qa`: 完整 Q + A + tags (按 markdown 渲染)
    - `triple`: rows 表格化展示 (from → rel → to)
    - `batch`: "共 N 条, 预览前 5 条" + 可展开全部 (避免 1 次渲染 500 行)
    - `optimize`: 完整原回答 + 优化后 + reason
  - 失败 / 被拒原因在 payload 下方固定显示 (rejected → `rejection_reason` 翻译 + `rejection_note`; failed → `error_msg`)
- 成功 / 失败: `router.refresh()` 让 RSC 重拉
- 成功 / 失败: `router.refresh()` 让 RSC 重拉

**关键: 服务端 conditional 渲染, 不靠客户端隐藏** (跟 [feedback-fix-root-cause-not-remove-feature] 一致)

- 普通用户的 page.tsx 不传 `initialAll`, 不渲染 "all" tab
- 普通用户直接 GET `/api/approvals` (无 admin) 后端 401 兜底
- 客户端也不会暴露 "all" tab 的入口 URL 给普通用户 (RSC 不渲染就没 link)

### B) Middleware 守卫调整

```ts
// packages/web/middleware.ts 改
function isProtected(pathname: string): boolean {
  return LOCALE_PREFIXES.some(
    (l) =>
      pathname.startsWith(`${l}/admin`) ||
      pathname === `${l}/admin` ||
      pathname.startsWith(`${l}/submissions`) ||
      pathname === `${l}/submissions`,
  );
}
```

- `/admin/*` — 需账号 + is_admin=true (后端再 401 兜底)
- `/submissions/*` — 仅需账号 (无 token 走 `/login?next=`, 不检查 is_admin)
- **不引入** `/dashboard/*` 命名空间 (本 spec 改用 `/submissions/*`)

### D) i18n (`messages/zh.json` + `messages/en.json`)

```json
{
  "submissions": {
    "title": "审核中心",
    "submitted": "已提交审核 #{id}, 等待管理员批准",
    "tabs": {
      "mine": "我提交的",
      "all": "全部待审"
    },
    "status": {
      "pending": "待审",
      "approved": "已批",
      "applied": "已写入",
      "rejected": "被拒",
      "failed": "写库失败"
    },
    "kind": {
      "qa": "QA 录入",
      "triple": "三元组",
      "batch": "批量导入",
      "optimize": "优化回答"
    },
    "actions": {
      "approve": "批准",
      "reject": "拒绝",
      "retry": "重试",
      "resubmit": "重新提交",
      "viewDetail": "查看详情"
    },
    "rejectDialog": {
      "title": "拒绝原因",
      "description": "请选择预设原因, 提交者会看到。",
      "reasons": {
        "duplicate": "重复内容",
        "low_quality": "质量问题",
        "incomplete": "信息不完整",
        "wrong_category": "分类错误",
        "format_issue": "格式问题",
        "other": "其他"
      },
      "otherPlaceholder": "补充说明 (选 \"其他\" 时填写)",
      "submit": "确认拒绝",
      "reasonRequired": "请选择拒绝原因"
    },
    "reviewStatus": {
      "label": "审批",
      "pending": "待审",
      "approved": "已批",
      "rejected": "被拒"
    },
    "applyStatus": {
      "label": "写入",
      "none": "未写入",
      "applied": "已写入",
      "failed": "写库失败"
    },
    "errors": {
      "loadFailed": "加载失败",
      "approveFailed": "批准失败",
      "rejectFailed": "拒绝失败",
      "retryFailed": "重试失败"
    },
    "rejectionReason": "拒绝原因",
    "appliedAt": "写入时间",
    "errorMsg": "错误信息"
  }
}
```

### E) 复用 shadcn 组件清单 (跟 [2026-06-10-ui-component-library-design](2026-06-10-ui-component-library-design.md) 一致)

| 组件          | 用途                                                  |
| ------------- | ----------------------------------------------------- |
| `Table`       | 列表                                                  |
| `Tabs`        | status 切换                                           |
| `Badge`       | 状态色 + kind 标签 (reviewStatus + applyStatus)       |
| `Dialog`      | RejectDialog (拒绝选原因) + DetailDialog (看完整内容) |
| `Select`      | RejectDialog 拒绝原因下拉                             |
| `Textarea`    | RejectDialog 选 "其他" 时补充说明                     |
| `Collapsible` | ApprovalRow 展开查看完整 payload                      |
| `Button`      | 批准 / 拒绝 / 重试 / 展开                             |
| `Card`        | 顶部统计 (pending / applied / failed 数量)            |
| `Empty`       | 空状态                                                |
| `Button`      | 批准 / 拒绝 / 重试                                    |
| `Card`        | dashboard 顶部统计 (pending / applied / failed 数量)  |
| `Empty`       | 空状态                                                |

## 错误处理

| 场景                                                  | 行为                                                                                                                                                                    |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **未登录调 /api/approvals (POST)**                    | 401, 前端 redirect /login                                                                                                                                               |
| **非 admin 调 /api/approvals/{id}/approve**           | 403, 前端 toast "权限不足"                                                                                                                                              |
| **从非 review=pending 状态调 approve**                | 409 Conflict `{ error: "状态非法" }`                                                                                                                                    |
| **从非 (review=approved, apply=failed) 状态调 retry** | 409 Conflict `{ error: "状态非法" }`                                                                                                                                    |
| **reject 缺 reason**                                  | 422, Pydantic 枚举校验 (必须是 6 个 RejectReason 之一)                                                                                                                  |
| **reject reason=other 但 note 缺 / 超 500 字符**      | 422, 字段级错误                                                                                                                                                         |
| **BackgroundTask apply 失败 (Dify 502 / Neo4j down)** | apply_status=failed, error_msg=str(e)[:1000]                                                                                                                            |
| **重复 submit 同一 payload**                          | **不阻**, 允许 (1 次提交 = 1 个审核项, 跟颗粒度决策一致)                                                                                                                |
| **Dify 写入成功但 status 没写回 (进程崩)**            | **已知风险**: 下次 admin 进 `/submissions?tab=all`, 看到 (review=approved, apply=none) 但 applied_at 是 None, 需手工重试或 admin 标 "manually applied" (后续 spec 处理) |

## 测试 (TDD, 跟项目 [feedback-tdd-test-real-behavior] 一致)

### 后端

| 文件                               | 覆盖                                                                                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/approvals/test_models.py`   | Approval 字段 + 3 enum (ReviewStatus, ApplyStatus, RejectReason)                                                                                                                                |
| `tests/approvals/test_service.py`  | 5 service 方法 TDD: submit/approve/reject/retry/apply, **真行为** (apply mock Dify 抛异常 → apply_status=failed + error_msg 含原异常 message)                                                   |
| `tests/approvals/test_executor.py` | 4 kind dispatch 全覆盖: QA / TRIPLE / BATCH / OPTIMIZE; 成功 → apply=applied, 异常 → apply=failed                                                                                               |
| `tests/approvals/test_router.py`   | 8 端点: 鉴权 (admin vs 非 admin) + 状态过滤 (review + apply) + pagination + reject 缺 reason 422 + reject reason=other 缺 note 422 + retry 限制 (仅 approved+failed) + POST /api/approvals 新建 |
| `tests/api_contract.py`            | 加 8 路由到后端 API 清单                                                                                                                                                                        |

### 前端

| 文件                                                              | 覆盖                                                                                                                                                             |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/api/approvals/[id]/approve/route.test.ts`                    | BFF: 鉴权 + 调 FastAPI + 返 200 (admin 路径)                                                                                                                     |
| `app/api/approvals/[id]/reject/route.test.ts`                     | BFF: 鉴权 + 调 FastAPI + 422 透传 (缺 reason / reason=other 缺 note)                                                                                             |
| `app/api/approvals/[id]/retry/route.test.ts`                      | BFF: 鉴权 + 调 FastAPI                                                                                                                                           |
| `app/[locale]/_actions/knowledge.test.ts` (改)                    | **关键**: 验 server action 改调 `approvals.submit`, **不**调 DifyDatasets.createDocumentByText (mock DifyDatasets.assertNotCalled) — 防止回归                    |
| `app/[locale]/submissions/page.test.tsx`                          | RSC: 鉴权重定向 + 普通用户不渲染 "all" tab + admin 渲染 2 tab + 拉数据 + 渲染                                                                                    |
| `app/[locale]/submissions/_components/SubmissionsTabs.test.tsx`   | Tabs 切换 / URL 同步 / 切 tab 调 RQ                                                                                                                              |
| `app/[locale]/submissions/_components/MySubmissionsList.test.tsx` | 渲染 2 个独立 badge (review + apply) / 不显示批准按钮 / 行展开拉详情 / 失败显示 error_msg / 被拒显示 rejection_reason+note / 重新提交链接                        |
| `app/[locale]/submissions/_components/AllApprovalsTable.test.tsx` | admin 可见: Tabs 切 review / 渲染 2 badge / 行展开拉详情 / 批准按钮 调 BFF (仅 pending) / 拒绝 Dialog 调 BFF (仅 pending) / 重试按钮 调 BFF (仅 approved+failed) |
| `app/[locale]/submissions/_components/RejectDialog.test.tsx`      | 弹框: 6 个原因下拉 / 选 other 出现 Textarea / 提交 reason (other 时带 note) / 取消 / 必填校验                                                                    |
| `app/[locale]/submissions/_components/ApprovalRow.test.tsx`       | 共用行组件: 渲染 2 badge / Collapsible 展开调 RQ 拉详情 / 按 kind 渲染 payload (qa / triple / batch / optimize) / 失败 / 被拒时显示原因                          |
| `messages/zh.json` 翻译断言                                       | vitest snapshot 锁死 14 个新 key (6 reject reasons + 3 review + 3 apply + 2 dialog)                                                                              |

**关键 TDD 原则** (跟 [feedback-tdd-test-real-behavior] 一致):

- ✅ 测真行为, 不只测"不崩"
- ✅ apply 失败路径必须有 (Dify mock 抛异常 → apply_status=failed + error_msg 含原异常 message)
- ✅ 4 个 server action 测试要验"调 approvals.submit, **不**调 DifyDatasets" (防止回归)
- ✅ RQ `useMutation` 失败返错 (不能 silently zero)
- ✅ 集成测试: 提交 → admin 批准 → apply 成功 → apply_status=applied (覆盖整链路)
- ✅ reject 端点 422 必填校验 (缺 reason / reason=other 缺 note / note 超 500 字符)

## 文件清单

**新增 (后端 5):**

- `packages/service/src/approvals/__init__.py`
- `packages/service/src/approvals/models.py`
- `packages/service/src/approvals/service.py`
- `packages/service/src/approvals/executor.py`
- `packages/service/src/approvals/router.py`

**新增 (后端测试 4):**

- `packages/service/tests/approvals/__init__.py`
- `packages/service/tests/approvals/test_models.py`
- `packages/service/tests/approvals/test_service.py`
- `packages/service/tests/approvals/test_executor.py`
- `packages/service/tests/approvals/test_router.py`

**新增 (前端 14):**

- `packages/web/app/api/approvals/[id]/approve/route.ts` + `.test.ts`
- `packages/web/app/api/approvals/[id]/reject/route.ts` + `.test.ts`
- `packages/web/app/api/approvals/[id]/retry/route.ts` + `.test.ts`
- `packages/web/app/[locale]/submissions/page.tsx` + `page.test.tsx`
- `packages/web/app/[locale]/submissions/layout.tsx` (可选, 共享 header "审核中心")
- `packages/web/app/[locale]/submissions/_components/SubmissionsTabs.tsx` + `.test.tsx`
- `packages/web/app/[locale]/submissions/_components/MySubmissionsList.tsx` + `.test.tsx`
- `packages/web/app/[locale]/submissions/_components/AllApprovalsTable.tsx` + `.test.tsx`
- `packages/web/app/[locale]/submissions/_components/ApprovalRow.tsx`
- `packages/web/app/[locale]/submissions/_components/RejectDialog.tsx` + `.test.tsx`

**改 (4 个写动作 + middleware + i18n + 现有 4 个表单 + 1 个新表单):**

- `packages/web/app/[locale]/_actions/knowledge.ts` (4 个 action 改写)
- `packages/web/app/[locale]/_actions/knowledge.test.ts` (测试改写)
- `packages/web/middleware.ts` (+ `/submissions/*` 守卫, 改 isProtected 函数)
- `packages/web/middleware.test.ts` (加 submissions 守卫测试)
- `packages/web/messages/zh.json` (加 11 个 key under `submissions.*`)
- `packages/web/messages/en.json` (加 11 个 key under `submissions.*`)
- `packages/web/app/[locale]/knowledge/qa/_components/QASubmitForm.tsx` (toast 改)
- `packages/web/app/[locale]/knowledge/triples/_components/TriplesForm.tsx`
- `packages/web/app/[locale]/knowledge/documents/import/_components/ImportForm.tsx`
- `packages/web/app/[locale]/chat/_components/MessageFeedback.tsx` (新增, 反馈按钮触发 optimize)

**改 (数据库 / 配置):**

- `packages/service/src/storage/__init__.py` (Base.metadata 注册 Approval)
- `packages/service/src/product_decoders/app.py` (include approvals router)
- `.env.example` (无新增, 复用现有 NEXT_PUBLIC_API_BASE / DATABASE_URL)

**改 (文档):**

- `docs/knowledge-management-page.md` (加 1 节 "审核集成" 说明 4 个写动作已改)
- `docs/approval-system.md` (新, 用户使用文档: 提交者怎么查 / admin 怎么审)
- `README.md` (如有需要, 加 1 行 "审核" 链接)

## 实施分阶段 (P0-P3)

| 阶段   | 任务                                                                              | 验收                                                         |
| ------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **P0** | 后端 Approval model + service + executor + router + 全部测试 (后端先 TDD 红 → 绿) | `uv run pytest tests/approvals/` 全绿                        |
| **P1** | 前端 server action 改写 (4 个改 1 个新) + 测试                                    | `bun run test` 全绿, 关键断言: 4 个 action 不调 DifyDatasets |
| **P2** | 前端 /submissions/\* (单 RSC + 2 Tabs) + middleware 改 + 4 个表单 toast 改        | `bun run test` + `bun run e2e` 全绿                          |
| **P3** | i18n zh/en 翻译 + docs 更新                                                       | `bun run test` snapshot 通过, README/docs 无 lint 错         |

每阶段独立可回滚 (git revert), 不影响生产。

## 风险 & 缓解

| 风险                                                   | 影响                                                          | 缓解                                                                          |
| ------------------------------------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| BackgroundTask 进程崩 → status 留 approved             | Dify / Neo4j 写入未确认, UI 显示 "已批" 但 applied_at 是 None | 错误处理章节已列; 后续 spec 加 "scan approved > 1h 仍无 applied_at" 报警      |
| 提交者删 cookie / 换浏览器 → 看不到自己提交            | 自己 dashboard 看不到, 体验差                                 | 鉴权靠 user_id 跟 cookie 绑定, 重新登录拿 token 仍能查 (跟现有 anon 行为一致) |
| 大量 bulk (5000 条) payload 写 JSON 字符串, 表 size 爆 | DB 慢 / 备份慢                                                | BATCH kind 加 max_rows 限制 (config, 默认 1000), 超出 422                     |
| Admin 误点批准后, Dify 已写, 想撤销                    | 难 (Dify 不支持事务)                                          | 文档说明: 撤销 = 拒绝 + 手动去 Dify 删, 不自动化                              |
| 现有 4 个 server action 测试要全改, 工作量大           | 1 天内可能改不完                                              | 4 个测试都是同样模式, 抽 helper `assertCallsApprovals(action, kind, payload)` |

## 关联 spec

- [2026-06-13-account-system-design.md](2026-06-13-account-system-design.md) — `is_admin` 角色 / `require_admin` 依赖项
- [2026-06-12-swr-to-rsc-rq-design.md](2026-06-12-swr-to-rsc-rq-design.md) — RSC + RQ 数据层
- [2026-06-10-web-frontend-architecture.md](2026-06-10-web-frontend-architecture.md) — BFF 边界规则
- [2026-06-10-theme-system-design.md](2026-06-10-theme-system-design.md) — 主题 status token
- [2026-06-10-i18n-design.md](2026-06-10-i18n-design.md) — 国际化 + messages 嵌套结构
- [2026-06-10-ui-component-library-design.md](2026-06-10-ui-component-library-design.md) — shadcn 组件清单
- [2026-06-10-knowledge-management-page-design.md](2026-06-10-knowledge-management-page-design.md) — 4 个写动作现有 page
- [2026-06-09-chat-agent-design.md](2026-06-09-chat-agent-design.md) — chat 流式 + 反馈入口
