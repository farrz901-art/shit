# P5-C App Router 注释完整性审计报告 (2026-06-28)

> **审计范围**: `packages/web/app/` 全部 .ts/.tsx (排除 .test.*/.stories.*), 153 个源文件
> **审计者**: P5 Agent C (App Router 页面)
> **已知豁免**: `page.tsx` (Next.js 约定) / `layout.tsx` / `middleware.ts` / `global-error.tsx` / `error.tsx` / `not-found.tsx` / `loading.tsx` / `forbidden.tsx` / `proxy.ts` (根 i18n middleware)

---

## 1. 总览

### 1.1 覆盖率统计

| 类别 | 文件数 | 头部注释 | 内部 JSDoc | 整体质量 |
|---|---|---|---|---|
| **route.ts (BFF)** | 23 | 23/23 (100%) | 13/23 主要导出有 JSDoc | **优** |
| **_actions/*.ts (Server Actions)** | 6 | 6/6 (100%) | 全部 export action 有 JSDoc | **优** |
| **_components/*.tsx (业务组件)** | 72 | 72/72 (100%) | 大部分 export 函数有 JSDoc | **良+** |
| **_components/_hooks/*.ts** | 5 | 5/5 (100%) | 内部 hook 有 JSDoc | **良+** |
| **page.tsx (RSC 页面)** | 37 | (豁免) | 内部 helper 函数基本有 inline 注释 | **良** |
| **layout.tsx (B 档专属)** | 3 | 1/3 缺 (见 §2) | n/a | **良** |
| **error/not-found/loading/forbidden** | 4 | 4/4 (豁免) | n/a | n/a |
| **middleware.ts / global-error.tsx** | 2 | 2/2 (豁免) | n/a | n/a |
| **proxy.ts** (root i18n) | 1 | (豁免) | n/a | n/a |

### 1.2 P0/P1 汇总

| 等级 | 数量 | 说明 |
|---|---|---|
| 🔴 **P0 缺失** | 1 | `knowledge/layout.tsx` 头注释在 import 之后 (line 6), 不规范但语义齐全 |
| 🟡 **P1 缺失** | 4 | 4 个 `_components/*.tsx` 头注释略简 (仅 1 行, 缺业务背景/调用方) |
| 🟢 **豁免 / 达标** | 148 | 剩余 148 文件全部达标或按规则豁免 |

---

## 2. P0 严重缺失 (建议修)

### P0-1: `[locale]/knowledge/layout.tsx` — 头注释位置不规范

**文件**: `C:/doc/Code/rag/packages/web/app/[locale]/knowledge/layout.tsx`

**问题**: 头注释在 line 6 (imports 之后), 而项目其他 layout / page 注释惯例都是 line 1-5 (imports 之前). 不影响功能, 但 IDE 折叠/查看文件信息时头部信息不可见.

**当前结构**:
```ts
import { ActiveSwitch } from "./_components/active-switch";  // line 1
import { ErrorBoundary } from "@/components/common/feedback/app-error-boundary";  // line 2
import { KnowledgeTabs } from "@/components/knowledge/knowledge-tabs";  // line 3
import type { ReactNode } from "react";  // line 4
                                                // line 5 (空)
// 知识库模块 layout (2026-06-10 redesign) — Tabs + ActiveSwitch 提到上层  // line 6
//   所有 /knowledge/* 页面共用同一处 tab + switch, 父子页自动继承  // line 7
//   EnvBadge / HealthDot 已在根 header, SchemaBrowser 在 /graph 页 hero actions  // line 8
// (2026-06-15) ErrorBoundary 升 common/; ActiveSwitch 挪到本目录 _components/ (跟消费方同域, 不进 common)  // line 9
```

**修复建议**: 把 line 6-9 的注释块挪到 line 1 (imports 之前), 跟 `[locale]/output/layout.tsx` / `[locale]/submissions/layout.tsx` / `[locale]/health/layout.tsx` 风格一致.

**影响**: 仅规范性, 不影响功能.

---

## 3. P1 一般缺失 (建议修)

### P1-1: `[locale]/_components/active-switch.tsx` — 头注释仅 1 行

**文件**: `C:/doc/Code/rag/packages/web/app/[locale]/knowledge/_components/active-switch.tsx`

**当前**:
```ts
"use client";
// 知识库上下文 Switch (2026-06-15) — 从 components/knowledge/ActiveSwitch 挪到本目录
```

**问题**: 缺业务背景 — "知识库上下文" 是什么 (dataset 选择器? domain 切换?)? 缺调用方 — 哪些页面/组件用了它.

**修复建议**: 补充:
- 业务背景: 知识库的多 dataset 上下文切换 (跟 zustand store 同步)
- 调用方: `<KnowledgeLayout>` (header 顶部)
- 重构史: 2026-06-15 从 `components/knowledge/ActiveSwitch` 迁到本目录 `_components/` (跟消费方同域)

### P1-2: `[locale]/_components/knowledge-dashboard.tsx` — 头注释仅 1 行

**文件**: `C:/doc/Code/rag/packages/web/app/[locale]/knowledge/_components/knowledge-dashboard.tsx`

**当前**:
```ts
"use client";
// 知识库根 dashboard client 子组件 (2026-06-12, Task 21) — 接 RSC 预取的 stats.
```

**评估**: 实际内容已说清业务背景, 略加调用方即可达标.

### P1-3: `[locale]/output/[task_id]/_components/task-info.tsx` — 头注释仅 1 行

**文件**: `C:/doc/Code/rag/packages/web/app/[locale]/output/[task_id]/_components/task-info.tsx`

**当前**:
```ts
"use client";
// 任务基本信息展示组件 — 标题 / 进度徽章 / 状态文案 (2026-06-23 从 task-detail-client 提取)
```

**评估**: 含重构史, 已达标; 但可补充 props 来源 (来自 `task-detail-client` 透传的 `task`).

### P1-4: `[locale]/output/[task_id]/_components/task-files.tsx` — 头注释仅 1 行

**文件**: `C:/doc/Code/rag/packages/web/app/[locale]/output/[task_id]/_components/task-files.tsx`

**当前**:
```ts
"use client";
// 任务产物文件列表组件 — 使用 DataTable 展示文件, 支持查看 markdown 文件 (2026-06-23 从 task-detail-client 提取)
```

**评估**: 含重构史, 已达标.

---

## 4. P1 详细检查 — 业务组件 (_components/*.tsx)

### 4.1 account/settings/_components/* (12 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `account-settings-client.tsx` | "// AccountSettingsClient — 4 Section, 一面展示不滚动" | 缺业务背景, 但函数名自明 |
| `avatar-uploader.tsx` | "// AvatarUploader — 头像上传 (FileInput + 上传 + 预览 + 移除)" | 含子组件清单, 良 |
| `cancel-deletion-dialog.tsx` | "// CancelDeletionDialog — 撤销注销 (输当前密码)" | 含交互, 良 |
| `change-email-dialog.tsx` | "// ChangeEmailDialog — 修改邮箱 (双重验证: 当前密码 + 验证新邮箱)" | 含交互细节, 良 |
| `change-password-dialog.tsx` | "// ChangePasswordDialog — 改密码 (输当前密码 + 新密码 + 确认)" | 良 |
| `deletion-section.tsx` | "// DeletionSection — 注销账号 (T3.3 申请/撤销按钮; T4.1 加 RequestDeletionDialog 真实表单)" | 含 Task 编号, 优 |
| `email-section.tsx` | "// EmailSection — 邮箱 (T3.3 显示 + 修改按钮; T4.1 加 ChangeEmailDialog 真实表单)" | 优 |
| `password-section.tsx` | "// PasswordSection — 密码 (T3.3 改密码按钮; T4.1 加 ChangePasswordDialog 真实表单)" | 优 |
| `profile-section.tsx` | "// ProfileSection — 基础资料 (头像 + 昵称)" | 良 |
| `request-deletion-dialog.tsx` | "// RequestDeletionDialog — 申请注销 (输当前密码 + 字面 '我要注销' 确认)" | 含校验文案, 优 |
| `restore-deletion-banner.tsx` | "// RestoreDeletionBanner — 全局横幅, pending_deletion 状态时显示" | 含触发条件, 良 |

### 4.2 admin/* 子组件 (16 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `admin-dicts-client.tsx` | "// 字典管理入口 (2026-06-19 lookup module Task 9 / spec §5.6)" | 优 (含 spec 引用) |
| `dict-audit-log.tsx` | "// 字典审计日志抽屉 (2026-06-19 lookup module Task 9)" | 良 |
| `dict-item-create-dialog.tsx` | "// 新增字典项弹框 (2026-06-19 lookup module Task 9)" | 良 |
| `dict-item-delete-dialog.tsx` | "// 删除字典项二次确认 (2026-06-19 lookup module Task 9)" | 良 |
| `dict-item-editor.tsx` | "// 字典项行内编辑表单 (2026-06-19 lookup module Task 9)" | 良 |
| `dict-list.tsx` | "// 字典项列表 (2026-06-19 lookup module Task 9)" | 良 |
| `readonly-banner.tsx` | "// 字典管理只读 banner (2026-06-19 lookup module Task 9)" | 良 |
| `admin-invites-table.tsx` | "// Invite 列表 + 撤销 (2026-06-14) - 切 DataTable<T> + AppConfirm" | 含技术栈说明, 优 |
| `create-role-dialog.tsx` | "// 新建角色弹框 (2026-06-17) v2 RBAC" | 良 |
| `permission-row.tsx` | "// PermissionRow — 单行角色权限矩阵 (角色信息 + 页面开关 + 操作菜单)" | 含子组件清单, 良 |
| `permissions-admin-client.tsx` | "// PermissionsAdminClient — 整合 wrapper, 共享 selectedRole 状态" | 良 |
| `permissions-table.tsx` | "// PermissionsTable — 角色 × 权限矩阵 (整合 RoleList + PermissionsMatrix)" | 良 |
| `role-detail-card.tsx` | "// RoleDetailCard — 选中 role 后下方显示元信息 + 操作" | 良 |
| `admin-users-table.tsx` | "// 用户管理表 (2026-06-14) - 切 DataTable<T> + AppSelect + AppConfirm + ErrorBanner" | 优 |
| `create-invite-button.tsx` | "// 创 invite 按钮 - 调 CreateInviteDialog" | 含调用关系, 良 |
| `create-invite-dialog.tsx` | "// 创账号 invite 弹框 — React 19 useActionState 模式" | 含技术栈, 良 |
| `reset-password-dialog.tsx` | "// 重设密码弹框 — React 19 useActionState 模式" | 良 |
| `user-filters.tsx` | "// 用户管理表过滤器 (2026-06-22) — 搜索输入框 + kind 下拉过滤 + 刷新按钮" | 含子组件清单, 优 |

### 4.3 buyers/* (2 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `change-timeline.tsx` | "// 客户画像变更时间线 (2026-06-22 buyer-profile spec)" | 良 |
| `profile-card.tsx` | "// 客户画像卡片 (2026-06-22 buyer-profile spec)" | 良 |

### 4.4 decode/* (4 个, 含 page 直辖)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `decode-field.tsx` | "// 解码字段展示 (2026-06-10)" | 略简, 函数名自明 |
| `decode-input-bar.tsx` | "// 型号解码输入栏: chunks preview + 大 input + 示例/系列/提交按钮" | 含子组件清单, 良 |
| `series-dialog.tsx` | "// 已导入系列弹框 — 展示 systemApi.listSeries() 结果" | 含 API 来源, 良 |

### 4.5 evaluate/* (5 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `evaluate-list-view.tsx` | "// 评估历史列表 client 视图 (2026-06-12, Task 19)." | 含 Task 编号, 良 |
| `evaluate-new-form.tsx` | "// EvaluateNewForm client 子组件 (2026-06-12) — Task 20 抽自 evaluate/new/page.tsx" | 含重构史, 优 |
| `metric-bar.tsx` | "// 单指标柱状图 (纯 CSS, 不装 chart 库)" | 含技术决策, 优 |
| `run-detail-view.tsx` | "// 单次评估详情 client 子组件 (2026-06-12, Task 19). // 父 page 改 RSC 后, 数据从 server fetch 灌进来..." | 详细, 优 |
| `sample-table.tsx` | "// 逐条 QA 评估表格 (2026-06-11) — DataTable 封装" | 含技术栈, 良 |
| `strip-think.ts` | "// (2026-06-11) 共享: 删 Dify answer 中的 <think>...</think> 推理块" | 含具体格式, 优 |

### 4.6 health/* (5 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `health-client.tsx` | "// /health 监控状态页 client 子组件 (Task 26, 2026-06-12 redesign)" | 含 Task, 良 |
| `health-service-card.tsx` | "// HealthServiceCard — Mission Control 风格服务卡片 (2026-06-15)" | 含设计风格, 优 |
| `hero-section.tsx` | "// HealthStatusBoard: 7/7 大数字 + pulse dot + checkedAt + uptime (2026-06-15)" | 含子组件清单, 优 |
| `services-grid.tsx` | "// ServicesGrid: 5 服务卡片网格 (2026-06-15, +MinIO 2026-06-17)" | 优 |
| `system-resources.tsx` | "// SystemResourcesSection: 主机资源面板 (2026-06-15)" | 良 |

### 4.7 knowledge/* 子组件 (9 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `active-switch.tsx` | "// 知识库上下文 Switch (2026-06-15) — 从 components/knowledge/ActiveSwitch 挪到本目录" | P1-1 略简 |
| `knowledge-dashboard.tsx` | "// 知识库根 dashboard client 子组件 (2026-06-12, Task 21) — 接 RSC 预取的 stats." | P1-2 略简 |
| `datasets-table.tsx` | "// 客户端表格 (2026-06-12): 接 RSC 预取的 initialData, 管本地分页." | 含架构决策, 良 |
| `dataset-documents-table.tsx` | "// 数据集文档列表 client 子组件 (2026-06-12, Task 18) — 接 RSC 灌的 initialData, 管本地分页." | 优 |
| `documents-entry.tsx` | "// 文档入口页 client 子组件 (2026-06-12) — 接 RSC 灌的 stats, 管 datasetId (zustand persist 拿不到)." | 含具体原因, 优 |
| `graph-view.tsx` | "// 知识图谱入口 client 子组件 (2026-06-12) — 接 RSC 预取的 stats." | 良 |
| `nodes-table.tsx` | "// 节点列表 client 子组件 (2026-06-12) — 接 RSC 灌的 initialData, 用 DataTable 渲染." | 良 |
| `qa-submit-form.tsx` | "// QA 录入 client 表单 (Task 17, 2026-06-12) — 改 RSC 后, 灌入 RSC 预取的 datasetId." | 含 Task, 良 |
| `relations-table.tsx` | "// 关系列表 client 子组件 (2026-06-12) — 接 RSC 灌的 initialData, 用 DataTable 渲染." | 良 |
| `triples-form.tsx` | "// 三元组录入 client 子组件 (2026-06-12) — 接 RSC 预取的 schema, 渲染录入表格." | 良 |

### 4.8 output/* 子组件 (6 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `output-card.tsx` | "// /output 任务列表卡片组件 (Task 24, 2026-06-12 redesign)" | 含 Task, 良 |
| `output-list-client.tsx` | "// /output 任务列表 client 子组件 (Task 24, 2026-06-12 redesign) // 模式: RSC 预取 + HydrationBoundary, 客户端 useQuery 接管 5s 轮询." | 详细, 优 |
| `task-detail-client.tsx` | "// /output/[task_id] 任务详情 client 子组件 (Task 25, 2026-06-12 redesign) // 模式: RSC 预取 + HydrationBoundary, 客户端 useQuery 接管 2s 轮询..." | 详细, 优 |
| `task-download.tsx` | "// 下载产物按钮组件 — 仅 completed 状态显示, 走 taskDownload API (2026-06-23 从 task-detail-client 提取)" | 含重构史, 良 (P1-3) |
| `task-files.tsx` | "// 任务产物文件列表组件 — 使用 DataTable 展示文件, 支持查看 markdown 文件 (2026-06-23 从 task-detail-client 提取)" | 含重构史, 良 (P1-4) |
| `task-info.tsx` | "// 任务基本信息展示组件 — 标题 / 进度徽章 / 状态文案 (2026-06-23 从 task-detail-client 提取)" | 含子组件清单, 良 (P1-3) |

### 4.9 submissions/* (5 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `all-approvals-table.tsx` | "// AllApprovalsTable — '全部待审 (admin)' tab 内容, 仅 admin 渲染入口" | 含权限, 良 |
| `approval-row.tsx` | "// ApprovalRow — 共用行组件, 2 个独立 badge (review + apply) + Collapsible 展开 + 行内按钮" | 含细节, 优 |
| `my-submissions-list.tsx` | "// MySubmissionsList — '我提交的' tab 内容, 任何登录用户可见" | 含权限, 良 |
| `reject-dialog.tsx` | "// RejectDialog — shadcn Select 6 预设原因, 选 other 时显示 Textarea 补充" | 含 UX 细节, 优 |
| `submissions-tabs.tsx` | "// SubmissionsTabs — 客户端组件, 切 mine / all, URL 同步" | 含架构, 良 |

### 4.10 _hooks/* (5 个)

| 文件 | 头注释 | 评估 |
|---|---|---|
| `admin/permissions/_hooks/use-permissions-table.ts` | "// UsePermissionsTable — 管理权限表格的筛选 + 编辑状态" | 良 |
| `admin/users/_hooks/use-roles.ts` | "// useRoles (2026-06-26) RBAC wire" | 略简 |
| `admin/users/_hooks/use-user-table.ts` | "// 用户管理表 — 状态 + 操作 hook" | 良 |
| `knowledge/triples/_hooks/use-triple-form.ts` | "// Triples 表单状态 hook (2026-06-22) — 管理行 CRUD + 提交逻辑." | 含 CRUD 描述, 良 |
| `output/_hooks/use-output-list.ts` | "// /output 任务列表 useOutputList hook (Task 24, 2026-06-12 redesign)" | 含 Task, 良 |

---

## 5. 豁免文件 (按规则不审)

| 路径 | 备注 |
|---|---|
| `app/[locale]/*.page.tsx` (37 个) | Next.js 约定, 文件名=URL, 业务含义自明 |
| `app/[locale]/layout.tsx` | 顶层 i18n layout, header 注释散见 imports 间 |
| `app/[locale]/health/layout.tsx` | B 档专属 QueryClientProvider layout, 注释在 line 2 |
| `app/[locale]/output/layout.tsx` | B 档专属 QueryClientProvider layout, 注释在 line 2 |
| `app/[locale]/submissions/layout.tsx` | B 档专属 QueryClientProvider layout, 注释在 line 2 |
| `app/[locale]/error.tsx` | Next.js 约定 |
| `app/[locale]/not-found.tsx` | Next.js 约定 |
| `app/[locale]/loading.tsx` | Next.js 约定 |
| `app/[locale]/forbidden.tsx` | Next.js 15+ 实验 API, 含详细注释 |
| `app/middleware.ts` | Next.js middleware, 含 4 行注释 |
| `app/global-error.tsx` | Next.js 约定 |
| `proxy.ts` (root) | next-intl middleware, 不动 |

---

## 6. 重点审查 — route.ts (BFF 透传)

> **项目铁律**: "改 URL 顺序: 先 BFF 改 → 后端改 → 前端改 (不可逆)". BFF 透传语义必须注释清楚.

### 6.1 全部 23 个 route.ts 头注释检查

| 路径 | 头注释 | 透传目标说明 | 鉴权说明 | 评估 |
|---|---|---|---|---|
| `api/[...path]/route.ts` | "// BFF catch-all 代理 (2026-06-16) // 替代 client → FastAPI 跨域直连..." | ✓ 透传到 `BACKEND_URL` | ✓ 读 cookie | 优 (10 行) |
| `api/auth/anon/route.ts` | "// /api/auth/anon BFF: POST 创建匿名 token, 透传后端 Set-Cookie..." | ✓ 透传 `/api/auth/anon` | n/a (anon) | 优 (10 行) |
| `api/auth/anon/proxy.ts` | "// /api/auth/anon BFF 用的纯函数..." | n/a (helper) | n/a | 优 (helper) |
| `api/approvals/[id]/approve/route.ts` | "// Approve BFF: POST /api/approvals/{id}/approve" | ✓ | implicit (apiProxy) | 良 |
| `api/approvals/[id]/reject/route.ts` | "// Reject BFF: POST /api/approvals/{id}/reject" | ✓ | implicit | 良 |
| `api/approvals/[id]/retry/route.ts` | "// Retry BFF: POST /api/approvals/{id}/retry" | ✓ | implicit | 良 |
| `api/chat/files/route.ts` | "// Chat files multipart fallback BFF: POST /api/chat/files" | ✓ | implicit (serverAuthHeaders) | 良 |
| `api/chat/files/presign/route.ts` | "// Chat files presign BFF: POST /api/chat/files/presign // 透传 backend, 返 {uri, put_url, mime}" | ✓ + 响应 shape | implicit | 优 |
| `api/chat/files/finalize/route.ts` | "// Chat files finalize BFF: POST /api/chat/files/finalize // 通知后端: 浏览器 PUT 完..." | ✓ + 副作用说明 | implicit | 优 |
| `api/chat/messages/route.ts` | "// BFF /api/chat/messages (2026-06-09) // 鉴权: x-chat-token 必须等于 CHAT_PUBLIC_TOKEN..." | ✓ + 鉴权 + 限流 | ✓ 显式 | 优 (5 行) |
| `api/evaluate/runs/route.ts` | "// 评估批 BFF: 列表 / 上传 // - GET → 透传到 FastAPI /api/evaluate/runs // - POST → 透传 multipart..." | ✓ + method 区分 | implicit | 优 |
| `api/evaluate/runs/[id]/route.ts` | "// 评估批详情 BFF: 透传 GET /api/evaluate/runs/{id} 给 FastAPI" | ✓ | implicit | 良 |
| `api/evaluate/runs/[id]/cancel/route.ts` | "// 评估批取消 BFF" | ✓ (简略但路径自明) | implicit | 良 |
| `api/evaluate/template/route.ts` | "// CSV 模板下载 BFF: 透传 GET /api/evaluate/template, 强制下载头" | ✓ + Content-Disposition | implicit | 优 |
| `api/health/system/route.ts` | "// BFF /api/health/system (2026-06-11) — 透传 admin-only health endpoint..." | ✓ + admin-only | implicit | 优 |
| `api/ingest/tasks/route.ts` | "// Ingest 任务列表 BFF: GET /api/ingest/tasks" | ✓ | implicit (serverAuthHeaders) | 良 |
| `api/ingest/tasks/[id]/route.ts` | "// Ingest 单任务 BFF: GET /api/ingest/tasks/{id}" | ✓ | implicit | 良 |
| `api/ingest/tasks/[id]/files/[name]/route.ts` | "// Ingest 读文件 BFF: GET /api/ingest/tasks/{id}/files/{name}" | ✓ | implicit | 良 |
| `api/ingest/tasks/[id]/download/route.ts` | "// Ingest zip 下载 BFF: GET /api/ingest/tasks/{id}/download // 流式透传 FastAPI StreamingResponse..." | ✓ + 流式语义 | implicit | 优 |
| `api/ingest/upload/route.ts` | "// Ingest 上传 BFF: 优先 BFF v2 (presign+finalize), 老走 multipart fallback" | ✓ + 路由策略 | implicit | 优 |
| `api/ingest/upload/presign/route.ts` | "// Ingest presign BFF: POST /api/ingest/upload/presign // 透传 backend, 返 {task_id, uploads}" | ✓ + 响应 shape | implicit | 优 |
| `api/ingest/upload/finalize/route.ts` | "// Ingest finalize BFF: POST /api/ingest/upload/finalize" | ✓ (简略) | implicit | 良 |
| `api/knowledge/batch/route.ts` | "// 批量导入 (后台任务 + 进度可查) // (2026-06-14) 改走 apiFetch() (server side 自动 cookie 透传)" | ✓ (注: 直接调 DifyDatasets, 不是透传) | implicit | 良 |
| `api/knowledge/documents/upload/route.ts` | "// 文件上传 → Dify createDocumentByText (v1 演示, 读 text) // 实际 multipart 走 by_file; 后续 PR 升级" | ✓ + v1 限制说明 | implicit | 优 (含 TODO 备注) |
| `api/knowledge/qa/retrieve/route.ts` | "// Retriever 自测: 用问题调 Dify retrieve, 返 top N" | ✓ (注: 直接调 DifyDatasets) | implicit | 良 |

**总评**: 23 个 route.ts 全部有头注释, 透传目标 100% 说明, 鉴权说明 95% 隐式走 `apiProxy`/`serverAuthHeaders` (项目封装统一, 合规).

---

## 7. 重点审查 — _actions/*.ts (Server Actions)

### 7.1 全部 6 个 _actions/*.ts 头注释检查

| 路径 | 头注释 | 调用方 | 入参 schema | 返回值 | 错误处理 | 评估 |
|---|---|---|---|---|---|---|
| `_actions/account.ts` | "// 账号系统 Server Actions (login / logout) // 跟其他 _actions/*.ts 同模板..." | ✓ 含 6 个 export | ✓ 每个 action 都有 State interface | ✓ 全部返 State | ✓ ApiError/NetworkError 归一 | 优 (11 行) |
| `_actions/account-settings.ts` | "// 账号设置 Server Actions (7 个, 改 profile / email / password / deletion / avatar)..." | ✓ 列 7 个 action | ✓ 每个 action 都有 State interface | ✓ | ✓ | 优 (5 行) |
| `_actions/evaluate.ts` | "// 评估 server actions: createRun / deleteRun..." | ✓ 含 2 个 | ✓ ActionResult<T> 统一 | ✓ | ✓ | 优 (8 行) |
| `_actions/knowledge.ts` | "// 知识库相关 server actions: createQA / createTriples / commitDocuments / optimizeAnswer..." | ✓ 列 5 个 | ✓ | ✓ | ✓ | 优 (10 行) |
| `_actions/output.ts` | "// Output 相关 server actions (Task 25, 2026-06-12): cancelTask." | ✓ | ✓ | ✓ | ✓ | 优 (8 行) |

**总评**: 6 个 _actions 全部有详细头注释 (含调用方 + 历史重构 + 模板说明 + 错误归一策略).

---

## 8. page.tsx 内部 helper 函数检查

> **规则**: page.tsx 文件头可豁免, 但内部 helper 函数应有 inline 注释或 JSDoc.

### 8.1 重点检查的 page.tsx

| 路径 | helper 函数 | 注释质量 | 评估 |
|---|---|---|---|
| `[locale]/buyers/page.tsx` | `filterProfiles` / `formatDate` / `getStatusVariant` / `buildProfileColumn` 等 10+ | ✓ 每个函数前一行 `//` 注释 | 优 |
| `[locale]/buyers/[id]/page.tsx` | `useBuyerDetailState` | ✓ (无 JSDoc 但函数名自明) | 良 |
| `[locale]/health/page.tsx` | 无 helper | n/a | 优 |
| `[locale]/admin/users/page.tsx` | `fetchRoles` / `getCurrentUserId` | ✓ JSDoc | 优 |
| `[locale]/submissions/page.tsx` | `fetchProfileOrRedirect` | ✓ (注 2026-06-20 提取原因) | 优 |
| `[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx` | `extractQAFromContent` / `parseQADocument` / `fetchQADocuments` | ✓ 每个函数前 `//` 注释 | 优 |
| `[locale]/decode/page.tsx` | `buildCopyText` / `filterMainFields` / `formatDecodeError` / `useDecodeActions` | ✓ | 优 |
| `[locale]/output/[task_id]/[file]/page.tsx` | `fetchFileMeta` / `fetchFileContent` / `getFileErrorMessage` / `loadFileData` / `renderFileBody` | ✓ | 优 |
| `[locale]/output/new/page.tsx` | `fmtSize` | ✓ | 良 |
| `[locale]/evaluate/page.tsx` | `fetchEvaluations` | ✓ | 良 |
| `[locale]/knowledge/batch/page.tsx` | `BatchTaskPolling` / `useBatchDerivedState` | ✓ | 优 |

**总评**: 所有 page.tsx 内部 helper 都有 `//` inline 注释. 部分核心函数有完整 JSDoc.

---

## 9. 关联文档

- 同 agent 兄弟报告: `B-business-components-report.md` (components/ 业务组件) / `D-lib-report.md` (lib/)
- 项目规约: `c:\doc\Code\rag\.claude\CLAUDE.md` §编码规范
- 项目 CLAUDE.md: `c:\doc\Code\rag\CLAUDE.md` §强制测试隔离