# P5 注释完整性补全实施计划 — 33 个 P0 文件 + 21 处 P1 行内注释

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 P5 维度审计 (2026-06-28) 的 P0 必修注释补全 — 30 个 `components/common/` 文件补文件头 + 主组件 JSDoc + 2 个 components 业务组件 + 1 个 app 文件头位置挪正 + 21 处 P1 行内注释; 净增 ~230 行注释 (纯文档, 0 业务变更)

**Architecture:** 2 阶段机械补全 — (1) P0 文件头注释 (Phase 1-3); (2) P1 复杂分支行内注释 (Phase 4-5). 标杆文件 `components/common/display/app-data-empty.tsx` 作为 JSDoc 模式参考

**Tech Stack:** 中文 JSDoc / oxfmt + oxlint (不破坏) / TypeScript 8 / 0 业务变更

**Source:** [P5 主报告](../../audit/2026-06-28-code-quality-5d/P5-comments.md) + 4 agent 子报告 (A 报告含完整 30 文件清单)

---

## 文件结构总览

| 阶段 | 文件数 | 范围 | 净增行数 |
|------|--------|------|---------|
| 1 | 30 | `components/common/` 全部 P0 文件 (A 报告 A.1-A.39) | ~150 |
| 2 | 1 | `components/chat/chat-api-provider.tsx` | +2 |
| 3 | 1 | `components/auth/guard-client.tsx` | +3 |
| 4 | 1 | `app/[locale]/knowledge/layout.tsx` (挪 line 1) | 0 |
| 5 | 8 | components/common/ P1 行内注释 (A.1-A.39 中 B.2-B.8) | ~20 |
| 6 | 5 | components/chat/* P1 (chat-shell / message-bubble / composer-attachments / message-feedback / footer) | ~16 |
| 7 | 8 | lib/ P1 (5 × lib/api/wrapper + 3 × state/auth) | ~20 |
| **总计** | **54 文件** | — | **净增 ~211 行注释** |

---

## JSDoc 模板（统一规范）

所有 P0 文件统一用以下 2 个模板:

### 文件头模板 (line 1 或 "use client" 后)

```ts
/**
 * @file <文件名> — <一句话作用> (创建日期 YYYY-MM-DD)
 * @description <业务背景 + 改造历史 + 关键约束>
 * @related <关联文件 / 调用方 / 相关 PR>
 */
```

### 主组件 JSDoc 模板

```ts
/**
 * <组件一句话作用>
 * @param props.<name> <字段含义>
 * @param props.<name> <字段含义>
 * @returns <返回值说明>
 * @example <典型用法>
 */
export const Component = (props: ComponentProps) => { ... }
```

### 内部函数 JSDoc（必填）

```ts
/** <函数作用>; <关键边界条件> */
const helperFn = (...) => { ... }
```

---

## Phase 1 — components/common/ 30 个 P0 文件批量补全

> **执行策略**: 按目录分批 (button/confirm/dialog/display/drawer/feedback/form/input/navigation/overlay/table) — 每批 1 个 commit
> **质量保证**: 每个文件补完跑 `bun run typecheck` (确保 JSDoc 不破坏 TS), 跑对应 .test.tsx (若有)

### Task 1: `components/common/button/` 目录 (3 文件)

**Files:**
- Modify: `packages/web/components/common/button/app-copy-button.tsx`
- Modify: `packages/web/components/common/button/app-loading-skeleton.tsx`
- Modify: `packages/web/components/common/button/app-submit-button.tsx`

- [ ] **Step 1: 补 `app-copy-button.tsx` JSDoc (4 行现有 `//` 注释升级为 `/** */` + 主组件 JSDoc)**

参考 [A 报告 §A.1](p5-comments/A-common-ui-report.md) 完整内容:
- File header: `@file Clipboard 复制按钮 (2026-06-14)`
- Main JSDoc: `复制文本到剪贴板并显示反馈` + @param 4 个

- [ ] **Step 2: 补 `app-loading-skeleton.tsx` JSDoc (无现有注释, 全补)**

参考 A 报告 §A.2:
- File header: `@file 表格/卡片加载骨架屏 (2026-06-14)`
- Main JSDoc: `渲染 rows 行骨架占位`

- [ ] **Step 3: 补 `app-submit-button.tsx` JSDoc (3 行现有 `//` 注释升级)**

参考 A 报告 §A.3.

- [ ] **Step 4: Run typecheck + button tests**

Run: `cd packages/web && bun run typecheck && bun run test components/common/button`
Expected: 0 errors, PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/components/common/button/
git commit -m "docs(common): JSDoc for button/* 3 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: `components/common/confirm/` (1 文件)

**Files:**
- Modify: `packages/web/components/common/confirm/app-confirm.tsx`

- [ ] **Step 1: 补 JSDoc (A 报告 §A.4 内容)**

- [ ] **Step 2: Run typecheck**

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/common/confirm/
git commit -m "docs(common): JSDoc for confirm/app-confirm (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: `components/common/dialog/` (1 文件)

**Files:**
- Modify: `packages/web/components/common/dialog/app-dialog.tsx`

- [ ] **Step 1: 补 JSDoc (A 报告 §A.5 内容 + error prop 自动 ErrorBanner 渲染说明)**

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/common/dialog/app-dialog.tsx
git commit -m "docs(common): JSDoc for dialog/app-dialog (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: `components/common/display/` (13 文件, 最大批量)

**Files:**
- Modify: 13 个 display/ 目录文件
  - `app-breathing-dot.tsx` (A.6)
  - `app-collapsible.tsx` (A.7)
  - `app-entry-card.tsx` (A.8)
  - `app-env-badge.tsx` (A.9)
  - `app-health-dot.tsx` (A.10)
  - `app-section-card.tsx` (A.11)
  - `app-settings-card.tsx` (A.12)
  - `app-spinner.tsx` (A.13)
  - `app-stat-card.tsx` (A.14)
  - `app-status-badge.tsx` (A.15)
  - `app-task-status-badge.tsx` (A.16)
  - `entry-card-grid.tsx` (A.17)
  - `stats-grid.tsx` (A.18)

- [ ] **Step 1: 逐文件补 JSDoc (参考 A 报告 §A.6-A.18 完整内容)**

每个文件:
1. 文件头 `/** @file ... */` (line 1 或 `"use client"` 后)
2. 主组件 JSDoc (含 @param + @returns)

- [ ] **Step 2: Run typecheck + display tests**

Run: `cd packages/web && bun run typecheck && bun run test components/common/display`
Expected: 0 errors, PASS

- [ ] **Step 3: Commit (一次性提交 13 文件)**

```bash
git add packages/web/components/common/display/
git commit -m "docs(common): JSDoc for display/* 13 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: `components/common/drawer/` (1 文件)

**Files:**
- Modify: `packages/web/components/common/drawer/app-drawer.tsx`

- [ ] **Step 1-3: 同 Task 2 模式 (A.19)**

---

### Task 6: `components/common/feedback/` (2 文件)

**Files:**
- Modify: `packages/web/components/common/feedback/app-error-banner.tsx` (A.20)
- Modify: `packages/web/components/common/feedback/app-error-boundary.tsx` (A.21)

- [ ] **Step 1: 逐文件补 JSDoc**

A.20 含 lookup map (豁免), 但 ErrorBanner 业务复杂 (16 处统一), 需详述 5 variant.
A.21 是 class component (项目少用), 需说明 getDerivedStateFromError + "重试" 行为.

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/common/feedback/
git commit -m "docs(common): JSDoc for feedback/* 2 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: `components/common/form/` (3 文件)

**Files:**
- Modify: `packages/web/components/common/form/app-field.tsx` (A.22)
- Modify: `packages/web/components/common/form/app-form.tsx` (A.23)
- Modify: `packages/web/components/common/form/app-submit.tsx` (A.24)

- [ ] **Step 1: 逐文件补 JSDoc + 内部 helper JSDoc (extractEventValue / buildInputElement / useFormCtx)**

- [ ] **Step 2: Run typecheck + form tests**

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/common/form/
git commit -m "docs(common): JSDoc for form/* 3 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: `components/common/input/` (6 文件)

**Files:**
- Modify: `app-dropdown-menu.tsx` (A.25)
- Modify: `app-file-dropzone.tsx` (A.26)
- Modify: `app-image-preview.tsx` (A.27)
- Modify: `app-search-input.tsx` (A.28 — 完全无注释, 优先)
- Modify: `app-select.tsx` (A.29)
- Modify: `app-tabs.tsx` (A.30)
- Modify: `app-toggle.tsx` (A.31)

- [ ] **Step 1: 逐文件补 JSDoc**

A.28 优先 (完全无注释, 双重缺失).
A.26 含 parseAcceptString / parseAccept helper.

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/common/input/
git commit -m "docs(common): JSDoc for input/* 7 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: `components/common/navigation/` (2 文件)

**Files:**
- Modify: `app-back-link.tsx` (A.32)
- Modify: `app-page-header.tsx` (A.33 — 完全无注释, 优先)
- Modify: `app-page-hero.tsx` (A.34)

- [ ] **Step 1: 逐文件补 JSDoc**

A.33 优先 (完全无注释).
A.32 业务复杂 (修饰键透传逻辑) — 详述 useHistory 行为.

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/common/navigation/
git commit -m "docs(common): JSDoc for navigation/* 3 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: `components/common/overlay/` (1 文件)

**Files:**
- Modify: `packages/web/components/common/overlay/app-tooltip.tsx`

- [ ] **Step 1-3: 同 Task 2 模式 (A.35, 含 variant="error" 视觉说明 + TooltipProvider 易漏教训)**

---

### Task 11: `components/common/table/` (4 文件)

**Files:**
- Modify: `data-table-body.tsx` (A.36)
- Modify: `data-table-pagination.tsx` (A.37)
- Modify: `data-table-skeleton.tsx` (A.38)
- Modify: `data-table.tsx` (A.39)

- [ ] **Step 1: 逐文件补 JSDoc**

A.39 是项目最复杂公共 API (4 列宽模式), 详述 getColStyle 4 种 ColumnWidth mode.

- [ ] **Step 2: Run typecheck + table tests**

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/common/table/
git commit -m "docs(common): JSDoc for table/* 4 files (P5 Phase 1)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2 — 业务组件 P0 (2 文件)

### Task 12: `chat-api-provider.tsx` Provider JSDoc

**Files:**
- Modify: `packages/web/components/chat/chat-api-provider.tsx`

- [ ] **Step 1: 补 Provider JSDoc (B 报告 §P0-2)**

```tsx
/**
 * Chat TanStack Query provider (2026-06-19 chat spec §3)
 * 跟 ThemeProvider / I18nProvider 嵌套一致, 放在 layout.tsx 包裹.
 * useState 初始化 QueryClient 防 SSR 跨请求泄漏 (每个 tab 1 个 client, 避免状态污染).
 * staleTime: 60s (跟 Redis 60s 对齐)
 */
export const ChatApiProvider = ({ children }: ChatApiProviderProps) => { ... }
```

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/chat/chat-api-provider.tsx
git commit -m "docs(chat): ChatApiProvider JSDoc (P5 Phase 2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 13: `guard-client.tsx` 双层防御注释

**Files:**
- Modify: `packages/web/components/auth/guard-client.tsx`

- [ ] **Step 1: 扩头注释到 4-5 行 (B 报告 §P0-1)**

```tsx
/**
 * @file Client 页面权限守卫 (2026-06-23 取代 ClientPageGuard)
 * @description 读 zustand store 权限快照, 无权 → router.replace("/404")
 *   跟 GuardPage (RSC 守卫) 形成双层防御:
 *   - GuardPage 在服务端拦截 (page-level, 拒绝则 forbidden())
 *   - GuardClient 在客户端拦截 (client-side route 切换时, 服务端不可达, 必须从 zustand 读)
 */
```

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/components/auth/guard-client.tsx
git commit -m "docs(auth): guard-client 双层防御说明 (P5 Phase 2)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3 — app/ 文件头位置挪正 (1 文件)

### Task 14: `knowledge/layout.tsx` 注释挪到 line 1

**Files:**
- Modify: `packages/web/app/[locale]/knowledge/layout.tsx`

- [ ] **Step 1: Move header comment to line 1**

Current (line 6-9 has comment, lines 1-5 are imports).
After: line 1-4 = header comment, then imports.

- [ ] **Step 2: Run typecheck + commit**

```bash
git add packages/web/app/[locale]/knowledge/layout.tsx
git commit -m "docs(app): knowledge/layout.tsx header position normalized (P5 Phase 3)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4 — components/common/ P1 行内注释 (8 处)

### Task 15: components/common/ P1 行内注释

**Files:**
- Modify: 8 个 components/common/ 文件 (A 报告 §B.2-B.8)

- [ ] **Step 1: `app-status-badge.tsx` — 加 `customLabels?.[status] ?? status` fallback 行内注释 (B.2)**

- [ ] **Step 2: `app-task-status-badge.tsx` — 加 `style[state] ?? style.queued` fallback 注释 (B.3)**

- [ ] **Step 3: `app-field.tsx:65` — 加 cloneElement 5 字段语义注释 (B.4)**

- [ ] **Step 4: `app-form.tsx:74-77` — 加 onFinish catch 注释 (B.5)**

- [ ] **Step 5: `app-back-link.tsx:53` — 加 MOUSE_BUTTON_LEFT 注释 (B.6)**

- [ ] **Step 6: `data-table.tsx:131-155` — 加受控/非受控 spread 注释 (B.7)**

- [ ] **Step 7: `data-table-pagination.tsx:46-65` — 加 handlePrev/Next Math.max/min 注释 (B.8)**

- [ ] **Step 8: Run typecheck + commit**

```bash
git add packages/web/components/common/
git commit -m "docs(common): 8 P1 inline注释 (P5 Phase 4)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 5 — 业务组件 P1 (5 文件)

### Task 16-20: chat/ 5 个 P1 文件

**Files:**
- Modify: `chat/chat-shell.tsx` (P1-1)
- Modify: `chat/message-bubble.tsx` (P1-2)
- Modify: `chat/composer-attachments.tsx` (P1-3)
- Modify: `chat/message-feedback.tsx` (P1-4)
- Modify: `layout/footer.tsx` (P1-5)

- [ ] **Step 1: chat-shell.tsx — 加 3-5 行业务背景总览 (B 报告 P1-1)**

- [ ] **Step 2: message-bubble.tsx — 加头注释 + bodyContent 分支注释 (P1-2)**

- [ ] **Step 3: composer-attachments.tsx — inferType + uploadAndAdd try/catch 内联注释 (P1-3)**

- [ ] **Step 4: message-feedback.tsx — open/closed 双状态 + handleSubmitSuccess 注释 (P1-4)**

- [ ] **Step 5: layout/footer.tsx — 加 1-2 行头注释 (P1-5)**

- [ ] **Step 6: Run typecheck + commit**

```bash
git add packages/web/components/chat/ packages/web/components/layout/
git commit -m "docs(components): chat/* 5 files P1 注释 (P5 Phase 5)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 6 — lib/ P1 (8 文件)

### Task 21-28: lib/ P1 注释补全

**Files (8 files from D 报告):**
- Modify: `lib/api/auth.ts` — `createAnonToken` JSDoc + 调用方
- Modify: `lib/api/users.ts` — 4 个函数 JSDoc + 调用方
- Modify: `lib/api/permissions.ts` — JSDoc
- Modify: `lib/api/buyer-profile.ts` — JSDoc
- Modify: `lib/api/system.ts` — JSDoc
- Modify: `lib/store/app-store.ts` — state 字段注释 (datasetId/domain 含义)
- Modify: `lib/auth/permission.ts` — `can()` super_admin 短路语义注释
- Modify: `lib/hooks/use-permissions.ts` — 同上

- [ ] **Step 1-8: 逐文件补 JSDoc (参考 D 报告 §P1-1 ~ §P1-8 完整内容)**

每个文件调用边界标注: `@client-bff` / `@server-only` / `@shared` (项目现有规约).

- [ ] **Step 9: Run typecheck + lib tests**

- [ ] **Step 10: Commit**

```bash
git add packages/web/lib/
git commit -m "docs(lib): 8 P1 JSDoc补全 (P5 Phase 6)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 7 — 验证

### Task 29: 全量验证

- [ ] **Step 1: Run full test suite**

Run: `cd packages/web && bun run test`
Expected: 0 new failures

- [ ] **Step 2: Run typecheck + lint + format**

Run: `cd packages/web && bun run typecheck && bun run lint && bun run format:check`
Expected: 0 errors

Note: oxfmt 不会重排 JSDoc 中文标点; oxlint 不会报 JSDoc 错.

- [ ] **Step 3: Verify 注释覆盖率**

Run:
```bash
# 检查 common/ 文件头覆盖率 (从 22/52 → 应为 52/52)
grep -lE "^/\*\*|^//[^/]" packages/web/components/common/**/*.tsx | wc -l
```
Expected: 52

- [ ] **Step 4: 最终 commit (如有残留)**

```bash
git status
```

---

## 强烈推荐执行顺序

| 顺序 | Phase | 净增行数 | ROI |
|------|-------|---------|-----|
| 1 | Phase 1 (30 common/ 文件) | +150 | 🔴 极高 (公共 API 缺文档影响最广) |
| 2 | Phase 2 (业务 P0) | +5 | 🔴 高 |
| 3 | Phase 3 (app 文件头挪正) | 0 | 🟡 低 (规范化) |
| 4 | Phase 4 (common P1 行内) | +20 | 🟡 中 |
| 5 | Phase 5 (业务 P1) | +16 | 🟡 中 |
| 6 | Phase 6 (lib P1) | +20 | 🟡 中 |
| **总计** | **6 phases / 29 tasks / 54 文件** | **净增 ~211 行注释** | — |

## 风险评估

- **Phase 1 (common/ 30 文件)**: 极低 — 纯文档, 0 业务变更; 唯一风险: 中文标点被 oxfmt 重排 (实测不会, JSDoc block 不会被改)
- **Phase 2 (业务 P0)**: 极低 — 纯 JSDoc
- **Phase 3 (挪位置)**: 极低 — 仅调整 comment 位置, 不改代码
- **Phase 4-6 (P1 行内)**: 极低 — 加 `//` 注释, 不影响执行流

## 关联文档

- [P5 主报告](../../audit/2026-06-28-code-quality-5d/P5-comments.md)
- [P5 A 报告 (common+ui)](../../audit/2026-06-28-code-quality-5d/p5-comments/A-common-ui-report.md) — 含完整 30 文件 JSDoc 内容参考
- [P5 B 报告 (业务组件)](../../audit/2026-06-28-code-quality-5d/p5-comments/B-business-components-report.md)
- [P5 C 报告 (app)](../../audit/2026-06-28-code-quality-5d/p5-comments/C-pages-report.md)
- [P5 D 报告 (lib)](../../audit/2026-06-28-code-quality-5d/p5-comments/D-lib-report.md)
- 项目规约: [`.claude/CLAUDE.md §编码规范`](../../.claude/CLAUDE.md)

## Self-Review Checklist

- [x] **Spec coverage**: P5 主报告 §4 (33 个 P0) + §5 (21 处 P1) 全部覆盖
- [x] **Placeholder scan**: 无 "TBD"; 每个文件路径具体
- [x] **JSDoc 模板一致性**: 全项目统一 3 模板 (文件头 / 主组件 / 内部 helper)
- [x] **覆盖率提升**: common/ 从 22/52 → 52/52; lib/ P1 从 8 缺失 → 0
- [x] **中文注释**: 全部用中文 (项目规约强制)
- [x] **不删注释**: 现有 `//` 注释升级为 `/** */`, 不删除内容

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-p5-comments-completion.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 task 派 fresh subagent (机械批量适合 subagent)

**2. Inline Execution** - 当前 session 批量执行 (Phase 1 30 文件可一次 commit)

**选哪种方式?**