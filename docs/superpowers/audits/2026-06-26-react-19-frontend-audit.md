# React 19 前端代码审计报告

> **审计日期**: 2026-06-26
> **项目**: RAG 平台 (packages/web)
> **技术栈**: Next.js + React 19 + TypeScript 8 + Tailwind CSS 4
> **范围**: 394 tsx + 213 ts 源文件

---

## 目录

1. [审计概览](#1-审计概览)
2. [React 19 Compiler 遗留分析](#2-react-19-compiler-遗留分析)
3. [Server Actions / RSC / RSF 迁移分析](#3-server-actions--rsc--rsf-迁移分析)
4. [react-use 替代分析](#4-react-use-替代分析)
5. [可封装 Hooks 分析](#5-可封装-hooks-分析)
6. [综合行动计划](#6-综合行动计划)
7. [风险与注意事项](#7-风险与注意事项)

---

## 1. 审计概览

### 当前状态

| 维度 | 状态 | 等级 |
|------|------|:----:|
| React 19 Compiler | 已启用 `reactCompiler: true` | ✅ |
| Server Actions | 5 个文件 / ~30 actions | 🟡 覆盖不足 |
| RSC 页面 | 24/34 (70%) | 🟡 有提升空间 |
| `'use client'` 组件 | ~150 个 | 🟡 约 10% 可移除 |
| react-use 依赖 | `@17.6.1` 已安装 | 🟡 利用率仅 ~15% |
| 自定义 Hooks | `lib/hooks/` 7 个文件 | 🔴 存在 dead code |

### 发现汇总

| 审计维度 | 发现数量 | 可立即执行 | 预估工作量 |
|----------|:--------:|:----------:|:----------:|
| Compiler 遗留 (useMemo/useCallback) | 29 处 | 29 (100%) | 1 人日 |
| Server Action 替代 BFF | 6 个路由 | 4 个 | 2 人日 |
| `'use client'` 可移除 | 10+ 个组件 | 3 个 | 0.25 人日 |
| react-use 可替换 | 15 处 | 5 处 | 0.5 人日 |
| 可封装 Hooks | 10+ 个候选 | 3 个 (复活 dead code) | 1 人日 |

---

## 2. React 19 Compiler 遗留分析

### 2.1 总览

**结论: 29 处 useMemo/useCallback 全部可被 Compiler 替代，零例外。**

| 类别 | 数量 | 可被 Compiler 替代 | 比例 |
|------|:----:|:------------------:|:----:|
| useMemo | 8 | 8 | 100% |
| useCallback | 21 | 21 | 100% |
| React.memo | 0 | 0 | N/A |
| 手动记忆化 | 0 | 0 | N/A |

### 2.2 高优先级清理清单（15 处，无风险）

可直接删除 `useMemo`/`useCallback` 包裹，行为零差异。

#### useMemo

| # | 文件 | 行号 | 内容 | 理由 |
|:-:|------|:----:|------|------|
| 1 | `lib/hooks/use-pagination.ts` | 16 | `totalPages = Math.max(Math.ceil(total / pageSize))` | 纯数学计算 |
| 2 | `components/chat/memory-management-dialog.tsx` | 56 | `filtered` — 按 filter 过滤 memories | 纯数组 filter |
| 3 | `components/common/input/app-file-dropzone.tsx` | 103 | `resolvedAccept` — 解析 accept 字符串 | 纯函数结果 |
| 4 | `app/[locale]/admin/permissions/_hooks/use-permissions-table.ts` | 133 | `filteredRoles` — 按搜索词过滤角色 | 纯 filter 函数 |
| 5 | `app/[locale]/buyers/page.tsx` | 293 | `activeFields` — 按 sort_order 排序过滤配置 | 纯链式调用 |
| 6 | `app/[locale]/buyers/page.tsx` | 336 | `columns` — 构建 DataTable 列定义 | 纯函数结果 |
| 7 | `app/[locale]/admin/profile-fields/page.tsx` | 224 | `columns` — 构建 DataTable 列定义 | 纯函数结果 |
| 8 | `lib/hooks/use-query-params.ts` | 6 | `params` — 构建 URL 参数字典 | 纯函数+需删除 eslint-disable |

#### useCallback

| # | 文件 | 行号 | 内容 | 理由 |
|:-:|------|:----:|------|------|
| 1 | `lib/hooks/use-dialog.ts` | 12-14 | `openDialog`/`closeDialog`/`toggleDialog` | 3 个均无依赖 |
| 2 | `lib/hooks/use-confirm.ts` | 14-15 | `confirm`/`handleConfirm` | 1 个无依赖, 1 个简单闭包 |
| 3 | `lib/hooks/use-query-params.ts` | 15 | `setParam` | 简单闭包+需删除 eslint-disable |
| 4 | `components/theme-provider.tsx` | 197 | `setTheme` | 简单函数 |
| 5 | `components/common/form/app-form.tsx` | 83 | `handleSubmit` | 简单回调 |
| 6 | `app/[locale]/buyers/[id]/_components/profile-card.tsx` | 58,66 | `handleSave`/`handleCancel` | 含 1 个无依赖 |
| 7 | `app/[locale]/admin/profile-fields/page.tsx` | 150,181,207 | `handleCreate`/`handleEditSave`/`handleToggleConfirm` | 3 个简单回调 |
| 8 | `app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx` | 137 | `handleSubmit` | 简单回调 |
| 9 | `app/[locale]/admin/permissions/_components/create-role-dialog.tsx` | 43 | `handleSubmit` | 简单回调 |
| 10 | `lib/chat/use-chat-state.ts` | 259 | `persistMessages` | 无依赖 |
| 11 | `app/[locale]/health/_components/health-client.tsx` | 31 | `togglePolling` | 简单函数 |

### 2.3 低优先级暂缓清单

| 文件 | 数量 | 原因 |
|------|:----:|------|
| `lib/chat/use-chat-state.ts` | 5 个 (243,259,263,326,352) | 逻辑复杂，19 个关联测试文件，需单独 PR 充分验证 |

### 2.4 注意事项

- 删除后同步清理 import: `import { useMemo, useCallback, useState }` → `import { useState }`
- 保留注释 `// eslint-disable-next-line react-hooks/exhaustive-deps` 的删除：Compiler 不再需要依赖数组，可一并移除
- 特别关注 `use-query-params.ts:12` 的 eslint-disable：删除 useMemo 后该抑制注释也随之失效

---

## 3. Server Actions / RSC / RSF 迁移分析

### 3.1 当前覆盖率

| 模块 | 覆盖状态 | gap |
|------|:-------:|-----|
| 认证 (login/register/forgot-password) | ✅ 已全覆盖 (useActionState) | 无 |
| 账号设置 | ✅ 已全覆盖 (7 个 action) | 无 |
| Evaluate | 🟡 部分覆盖 | 缺 cancelRun |
| Knowledge | 🟡 部分覆盖 | 缺 batch / retrieve / uploadDocument |
| Output | 🟡 部分覆盖 | cancelTask 已有, download 不适用 |
| Approvals | 🔴 未覆盖 | approve/reject/retry 全缺 |
| BFF route count | 当前 31 个 | 可消除 6 个 |

### 3.2 P0 — 立即迁移

#### 新增 `app/[locale]/_actions/approvals.ts`

| 当前 BFF route | 替换 Action | 理由 |
|----------------|------------|------|
| `app/api/approvals/[id]/approve/route.ts` | `approveAction` | 纯 JSON POST 透传 |
| `app/api/approvals/[id]/reject/route.ts` | `rejectAction` | 纯 JSON POST 透传 |
| `app/api/approvals/[id]/retry/route.ts` | `retryAction` | 纯 JSON POST 透传 |

**收益**: 消除 3 个 BFF route + `lib/api/approvals.ts` 客户端代码，利用 `revalidatePath` 刷新 submissions 页面。

**工作量**: 1 人日

#### 迁移 `/api/knowledge/batch` 到 `_actions/knowledge.ts`

**当前**: `app/api/knowledge/batch/route.ts` 内置 in-memory task map + 循环调 Dify API，纯 server 逻辑。

**收益**: 消除 1 个 BFF route，消除不必要的网络跳转。

**工作量**: 0.5 人日

#### 移除 3 个纯展示组件的 `'use client'`

| 组件 | 理由 |
|------|------|
| `components/evaluate/status-badge.tsx` | 无 hooks/事件，纯 props→UI |
| `app/[locale]/admin/dicts/_components/readonly-banner.tsx` | 纯展示 Alert banner |
| `components/common/feedback/app-error-banner.tsx` | 纯展示 ErrorBanner |

### 3.3 P1 — 跟进迁移

| 任务 | 工作量 |
|------|:------:|
| 补充 evaluate `cancelRun` action | 0.25 人日 |
| 清理已迁移的 BFF route 文件 | 0.25 人日 |

### 3.4 暂不迁移的 BFF route

| 路由 | 原因 |
|------|------|
| `/api/knowledge/documents/upload` | Multipart 上传，暂保留 |
| `/api/chat/messages` | SSE 流，不适用 |
| `/api/ingest/upload` | Multipart，暂保留 |
| `/api/auth/anon` | Set-Cookie 操作，不适用 |
| `/api/[...path]` | catch-all 通用 BFF，暂保留 |

### 3.5 RSC 可拆分候选

| 组件 | 当前 | 建议 |
|------|------|------|
| `components/knowledge/knowledge-tabs.tsx` | `'use client'` (usePathname) | 通过 prop 传入 pathname |
| `components/i18n/localized-link.tsx` | `'use client'` (useLocale) | 改用服务端 `getLocale()` |

---

## 4. react-use 替代分析

### 4.1 已用情况

**16 个文件已使用 react-use**，覆盖 6 种 hook:

| Hook | 使用文件数 |
|------|:---------:|
| `useToggle` | 12 |
| `useInterval` | 2 |
| `useEvent` | 2 |
| `useLocalStorage` | 2 |
| `useDebounce` | 1 |
| `useEffectOnce` | 1 |

### 4.2 高优替换 Top 5

| P | 文件 | 当前模式 | 替换方案 | 省行数 |
|:-:|------|---------|----------|:------:|
| 1 | `components/chat/voice-recorder.tsx` | 手动 `setInterval` + `timerRef` + `clearInterval` | `useInterval` | ~15 行 |
| 2 | `components/chat/share-dialog.tsx` | 手写 `navigator.clipboard.writeText` + try/catch | `useCopyToClipboard` | ~8 行 |
| 3 | `app/[locale]/account/restore/restore-form.tsx` | 手动 `setTimeout` + cleanup | `useTimeout` / `useTimeoutFn` | ~5 行 |
| 4 | 8 个文件 | `const [x, setX] = useState(false)` + `setX(true)`/`setX(false)` | `useBoolean` (与 12 处 useToggle 统一) | 每处 2 行 |
| 5 | `app/[locale]/health/_components/hero-section.tsx` | 手动 `setInterval` + cleanup | `useInterval` | ~5 行 |

### 4.3 不可替代的 hooks

| Hook | 理由 |
|------|------|
| `lib/hooks/use-query-params.ts` | 与 Next.js App Router 路由系统深度绑定 |
| `lib/hooks/use-pagination.ts` | react-use 无对应 hook，仅 20 行 |
| `lib/hooks/use-lookup.ts` | TanStack Query 专用业务 hook |
| `lib/hooks/use-permissions.ts` | Zustand store |

---

## 5. 可封装 Hooks 分析

### 5.1 🔴 关键发现: 3 个已有 hook 成为 Dead Code

| Hook | 位置 | 现状 | 问题 |
|------|------|:----:|------|
| `useDialog` | `lib/hooks/use-dialog.ts` | **废弃** | 8+ 处业务组件手动 `useState(false)` 管理弹窗，却无人使用 useDialog |
| `useConfirm` | `lib/hooks/use-confirm.ts` | **被忽略** | `run-detail-view.tsx` 自实现等价 confirm 逻辑 |
| `usePolling` | 无统一文件 | **散落 3 处** | health-client/batch/run-detail-view 各写一套轮询 |

**复活成本**: 0.5 人日 × 2 (useDialog + usePolling)

### 5.2 数据获取 Hook 候选

| Hook | 来源模块 | 覆盖组件 | 优先级 |
|------|---------|:--------:|:------:|
| `useDatasets` | knowledge | 2+ 组件 | P1 |
| `useNodes` | knowledge | 1 page | P2 |
| `useRelations` | knowledge | 1 page | P2 |
| `useApprovals` | submissions | 2+ 组件 | P2 |
| `useApprovalDetail` | submissions | 1 组件 | P2 |

### 5.3 通用逻辑 Hook 候选

| Hook | 模式 | 当前重复数 | 优先级 |
|------|------|:----------:|:------:|
| `useFormSubmit` | submitting + error + toast + redirect | 4+ 表单 | P2 |
| `useDialogState` | dialog open + 重置状态 + submitting | 3+ dialog | P2 |
| `useSubmitRedirect` | toast + router.push | 3 处 | P2 |
| `useFilePicker` | 文件选择 + 解析 + error | 3 处 | P3 |
| `usePolling` | 定时轮询 + 退避策略 | 3 处 | **P0** |
| `useKeyboard` | 键盘快捷键 | decode 独占但通用 | P3 |

### 5.4 跨组件共享模式

**5+ 页面重复的 PagePrefetch 模式**:
```
RSC prefetch → HydrationBoundary → GuardPage → 骨架屏
```
建议封装 `PagePrefetchWrapper` 组件统一。

---

## 6. 综合行动计划

### 6.1 行动路径

```
Phase 1 (P0, ~2 人日)           Phase 2 (P1, ~2 人日)
─────────────────               ─────────────────
┌ 复活 useDialog (0.5d)         ┌ approvals action (1d)
├ 统一 usePolling (0.5d)         ├ batch migration (0.5d)
├ 删 15 处 memo/cb (0.5d)       ├ react-use Top 5 (0.5d)
├ 移除 3 个 'use client' (0.25d)├ cancelRun 补充 (0.25d)
└ 复活 useConfirm (0.25d)       └

Phase 3 (P2, ~2 人日)           Phase 4 (P3, 按需)
─────────────────               ─────────────────
┌ use-chat-state 清理 (1d)      ┌ data hooks 扩展
├ 剩下 react-use 替换 (0.5d)     └ FilePicker/CSV parser/etc
└ useDatasets 等 hooks (1d)     └
```

### 6.2 详细任务分解

#### Phase 1: 低风险高收益（建议本周执行）

| ID | 任务 | 文件 | 预估 |
|:--:|------|------|:----:|
| 1.1 | 删除 15 处简单 useMemo/useCallback | 9 个文件 | 0.5d |
| 1.2 | 移除 3 个组件的 `'use client'` | status-badge / readonly-banner / error-banner | 0.25d |
| 1.3 | 复活 useDialog，替换业务中手写状态 | 8+ 组件 | 0.5d |
| 1.4 | 创建统一 usePolling，替换 3 处独立实现 | lib/hooks/use-polling.ts + 3 组件 | 0.5d |
| 1.5 | 复活 useConfirm，替换 run-detail-view 自实现 | run-detail-view.tsx | 0.25d |

#### Phase 2: 架构左移（建议下周执行）

| ID | 任务 | 预估 |
|:--:|------|:----:|
| 2.1 | 新增 `_actions/approvals.ts` | 1d |
| 2.2 | batch 迁移到 `_actions/knowledge.ts` | 0.5d |
| 2.3 | react-use Top 5 替换 | 0.5d |
| 2.4 | 补充 cancelRun action | 0.25d |
| 2.5 | 删除已迁移的 BFF route 文件 | 0.25d |

#### Phase 3: 深化（建议 2 周内）

| ID | 任务 | 预估 |
|:--:|------|:----:|
| 3.1 | use-chat-state.ts 5 个 useCallback 清理 | 0.5d |
| 3.2 | 封装 useDatasets / useNodes / useRelations | 1d |
| 3.3 | 剩余 10 处 react-use 替换 | 0.5d |

#### Phase 4: 长期迭代

| ID | 任务 | 触发条件 |
|:--:|------|---------|
| 4.1 | 封装 useApprovals / useApprovalDetail | action 稳定后 |
| 4.2 | 封装 useFormSubmit | 下个表单需求 |
| 4.3 | 封装 PagePrefetchWrapper | 下个新页面 |
| 4.4 | FilePicker / CSV parser hooks | 下个文件上传需求 |

---

## 7. 风险与注意事项

### 7.1 BFF Route 删除契约检查

项目 `.claude/CLAUDE.md` 规定:
> **删 BFF route 前必须跑 `pytest tests/test_api_contract.py`**
> **改前端 URL 顺序不可逆**: 后端实现 → 改前端 URL → 删 BFF

### 7.2 React Compiler 清理注意事项

- 先对 15 处简单场景开 PR，观察 CI 通过后再推进 use-chat-state.ts
- 删除后跑全量 `bun run test` (719 tests) + `bun run typecheck` (tsc --noEmit)
- 同步清理 import 语句

### 7.3 react-use tree-shaking

维持命名导入模式 `import { useXXX } from 'react-use'`，不引入 default import。

### 7.4 useDialog 复活前检查

- 先 grep 确认当前无人引用 useDialog（已确认是 dead code）
- 逐个 Dialog 文件评估 props 签名兼容性
- 建议先 mock 替换 1 个组件验证 CI 通过

### 7.5 Pre-existing Test Fails

- 后端: 22 fail + 38 errors (见 `packages/service/KNOWN_ISSUES.md`)
- 前端: 不产生新 fail，不修 pre-existing fail

---

## 附录 A: 文件清单

### A.1 Compiler 清理涉及文件

```
packages/web/lib/hooks/use-pagination.ts
packages/web/lib/hooks/use-dialog.ts
packages/web/lib/hooks/use-confirm.ts
packages/web/lib/hooks/use-query-params.ts
packages/web/lib/chat/use-chat-state.ts
packages/web/components/chat/memory-management-dialog.tsx
packages/web/components/common/input/app-file-dropzone.tsx
packages/web/components/theme-provider.tsx
packages/web/components/common/form/app-form.tsx
packages/web/app/[locale]/buyers/page.tsx
packages/web/app/[locale]/buyers/[id]/_components/profile-card.tsx
packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts
packages/web/app/[locale]/admin/permissions/_components/create-role-dialog.tsx
packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx
packages/web/app/[locale]/admin/profile-fields/page.tsx
packages/web/app/[locale]/health/_components/health-client.tsx
```

### A.2 Server Action 迁移涉及文件

```
packages/web/app/api/approvals/[id]/approve/route.ts    → 删除
packages/web/app/api/approvals/[id]/reject/route.ts     → 删除
packages/web/app/api/approvals/[id]/retry/route.ts      → 删除
packages/web/app/api/knowledge/batch/route.ts            → 迁移
packages/web/app/api/knowledge/qa/retrieve/route.ts      → 可选迁移
packages/web/app/api/evaluate/runs/[id]/cancel/route.ts  → 删除
packages/web/lib/api/approvals.ts                        → 可删除
packages/web/app/[locale]/_actions/approvals.ts          → 新建
packages/web/app/[locale]/_actions/knowledge.ts          → 补充
packages/web/app/[locale]/_actions/evaluate.ts            → 补充
```

### A.3 react-use 替换涉及文件

```
packages/web/components/chat/voice-recorder.tsx
packages/web/components/chat/share-dialog.tsx
packages/web/components/chat/message-feedback.tsx
packages/web/components/chat/memory-management-dialog.tsx
packages/web/app/[locale]/account/restore/restore-form.tsx
packages/web/app/[locale]/health/_components/hero-section.tsx
packages/web/app/[locale]/admin/dicts/_components/dict-item-delete-dialog.tsx
packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx
packages/web/app/[locale]/admin/dicts/_components/dict-audit-log.tsx
packages/web/app/[locale]/admin/permissions/_components/create-role-dialog.tsx
```

### A.4 'use client' 可移除文件

```
packages/web/components/evaluate/status-badge.tsx
packages/web/app/[locale]/admin/dicts/_components/readonly-banner.tsx
packages/web/components/common/feedback/app-error-banner.tsx
packages/web/components/common/display/app-collapsible.tsx        (待验证)
packages/web/components/knowledge/knowledge-tabs.tsx              (需 prop 改造)
packages/web/components/knowledge/schema-field-renderer.tsx       (待验证)
```

### A.5 Dead Code Hook 复活涉及文件

```
packages/web/lib/hooks/use-dialog.ts          → export 到 barrel
packages/web/lib/hooks/use-confirm.ts         → 已在 barrel 但未被用
packages/web/lib/hooks/use-polling.ts         → 新建
packages/web/lib/hooks/index.ts              → 补充 export
```

---

*审计结束。由 4 个并行扫描 agent + 1 个综合 agent 生成。*
