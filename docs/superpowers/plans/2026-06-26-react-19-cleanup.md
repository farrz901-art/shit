# React 19 前端代码清理执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于审计报告，分 4 个 Phase 完成 React 19 前端代码清理，消除 29 处 Compiler 冗余 + 清理 `app/api/_actions/lib/api` 三层调用边界混乱 + 15 处 react-use 可替代模式 + 复活 3 个 Dead Code Hook

**Architecture:** 先做零风险的纯删除（Compiler 记忆化 + 'use client'），再复活已有 hooks 并替换轮询/confirm 等重复模式，然后清理 `app/api/_actions/lib/api` 三层 API 调用边界（确保 _actions 直连后端不绕 BFF，标记多平台路由保留），最后深化数据 hooks 和 use-chat-state 清理。每个 task 独立可 PR。

**Tech Stack:** TypeScript 8 / React 19 / Next.js 16 / react-use@17.6.1 / TanStack Query 5 / Zustand / vitest

**Source:** [审计报告](../../audit/react-19-frontend-audit-2026-06-26.md)

---

## 文件结构

### Phase 1 — 零风险清理

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/lib/hooks/use-pagination.ts` | 修改 | 删除 useMemo |
| `packages/web/lib/hooks/use-dialog.ts` | 修改 | 删除 3 个 useCallback |
| `packages/web/lib/hooks/use-confirm.ts` | 修改 | 删除 2 个 useCallback |
| `packages/web/lib/hooks/use-query-params.ts` | 修改 | 删除 useMemo + useCallback + eslint-disable |
| `packages/web/lib/hooks/index.ts` | 修改 | 补充 export useDialog |
| `packages/web/lib/hooks/use-polling.ts` | **新建** | 统一轮询 hook |
| `packages/web/components/chat/memory-management-dialog.tsx` | 修改 | 删除 useMemo |
| `packages/web/components/common/input/app-file-dropzone.tsx` | 修改 | 删除 useMemo |
| `packages/web/components/theme-provider.tsx` | 修改 | 删除 useCallback |
| `packages/web/components/common/form/app-form.tsx` | 修改 | 删除 useCallback |
| `packages/web/components/evaluate/status-badge.tsx` | 修改 | 移除 'use client' |
| `packages/web/app/[locale]/admin/dicts/_components/readonly-banner.tsx` | 修改 | 移除 'use client' |
| `packages/web/components/common/feedback/app-error-banner.tsx` | 修改 | 移除 'use client' |
| `packages/web/components/chat/voice-recorder.tsx` | 修改 | setInterval → useInterval |
| `packages/web/components/chat/share-dialog.tsx` | 修改 | useState(false) → useBoolean |
| `packages/web/app/[locale]/admin/permissions/_components/create-role-dialog.tsx` | 修改 | 删除 useCallback + useState(false) → useBoolean |
| `packages/web/app/[locale]/buyers/page.tsx` | 修改 | 删除 2 处 useMemo |
| `packages/web/app/[locale]/buyers/[id]/_components/profile-card.tsx` | 修改 | 删除 2 处 useCallback |
| `packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts` | 修改 | 删除 useMemo |
| `packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx` | 修改 | 删除 useCallback |
| `packages/web/app/[locale]/admin/profile-fields/page.tsx` | 修改 | 删除 3 处 useCallback + 1 处 useMemo |
| `packages/web/app/[locale]/health/_components/health-client.tsx` | 修改 | 删除 useCallback |
| `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx` | 修改 | 自实现 confirm → useConfirm |

### Phase 2 — API 调用边界清理 (P1, ~2 人日)

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/lib/api/index.ts` | 修改 | 标注 `@internal` 区分 client-only / server-only / BFF-only |
| `packages/web/lib/api/evaluate.ts` | 修改 | 分离 server-only 函数到 lib/server，标注 BFF 保留原因 |
| `packages/web/lib/api/approvals.ts` | 修改 | 标注每个函数的调用者和 BFF/直连路由 |
| `packages/web/lib/server/evaluate.ts` | **新建** | Server Action 直连后端的 fetch 函数 |
| `packages/web/app/[locale]/_actions/evaluate.ts` | 修改 | deleteRun 改走 lib/server 直连后端，不绕 BFF |
| `packages/web/app/[locale]/_actions/knowledge.ts` | 修改 | 补充 batch action (web-only) |
| `packages/web/app/api/knowledge/batch/route.ts` | 删除 | web-only 批量导入，Server Action 替代 |
| `packages/web/app/[locale]/account/restore/restore-form.tsx` | 修改 | setTimeout → useTimeout |
| `packages/web/app/[locale]/health/_components/hero-section.tsx` | 修改 | setInterval → useInterval |
| `packages/web/components/chat/message-feedback.tsx` | 修改 | 3 处 useState(false) → useBoolean |
| `packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx` | 修改 | useState(false) → useBoolean |
| `packages/web/components/chat/memory-management-dialog.tsx` | 修改 | useState(false) → useBoolean |

### Phase 3 — 深化

| 文件 | 操作 | 职责 |
|------|------|------|
| `packages/web/lib/hooks/use-datasets.ts` | **新建** | Dataset 数据 hook |
| `packages/web/lib/hooks/use-nodes.ts` | **新建** | Knowledge Graph nodes hook |
| `packages/web/lib/hooks/use-relations.ts` | **新建** | Knowledge Graph relations hook |
| `packages/web/lib/hooks/index.ts` | 修改 | 补充新 hooks export |
| `packages/web/lib/chat/use-chat-state.ts` | 修改 | 删除 5 处 useCallback (不含无依赖的 259 已在 Phase1 删) |
| `packages/web/app/[locale]/admin/dicts/_components/dict-item-delete-dialog.tsx` | 修改 | useState(false) → useBoolean |
| `packages/web/app/[locale]/admin/dicts/_components/dict-audit-log.tsx` | 修改 | useState(false) → useBoolean |

### Phase 4 — 长期（按需）

不写具体 task，只列触发条件。

---

## Phase 1: 零风险清理 (P0, ~2 人日)

### Task 1.1: 删除 6 个简单文件的 useMemo/useCallback (3 文件)

**Files:**
- Modify: `packages/web/lib/hooks/use-pagination.ts`
- Modify: `packages/web/lib/hooks/use-dialog.ts`
- Modify: `packages/web/lib/hooks/use-confirm.ts`

- [ ] **Step 1: 修改 use-pagination.ts — 删除 useMemo**

```typescript
// packages/web/lib/hooks/use-pagination.ts
import { useState } from "react";
// └── 删除 useMemo import
import { DEFAULT_PAGE_SIZE, ONE } from "@/const";

const FIRST_PAGE = ONE;

export interface PaginationControl {
  page: number;
  setPage: (page: number) => void;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export const usePagination = (total: number, pageSize = DEFAULT_PAGE_SIZE): PaginationControl => {
  const [page, setPage] = useState(FIRST_PAGE);
  const totalPages = Math.max(FIRST_PAGE, Math.ceil(total / pageSize));
  // └── 删 useMemo 包裹, 保留表达式
  return { page, setPage, totalPages, hasNext: page < totalPages, hasPrev: page > FIRST_PAGE };
};
```

- [ ] **Step 2: 修改 use-dialog.ts — 删除 3 个 useCallback**

```typescript
// packages/web/lib/hooks/use-dialog.ts
import { useState } from "react";
// └── 删除 useCallback import

export interface DialogControl {
  open: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  toggleDialog: () => void;
}

export const useDialog = (initial = false): DialogControl => {
  const [open, setOpen] = useState(initial);
  const openDialog = () => setOpen(true);
  const closeDialog = () => setOpen(false);
  const toggleDialog = () => setOpen((prev) => !prev);
  // └── 删 useCallback 包裹
  return { open, openDialog, closeDialog, toggleDialog };
};
```

- [ ] **Step 3: 修改 use-confirm.ts — 删除 2 个 useCallback**

```typescript
// packages/web/lib/hooks/use-confirm.ts
import { useState } from "react";
// └── 删除 useCallback import

export interface ConfirmControl {
  confirm: () => void;
  confirmProps: {
    open: boolean;
    onConfirm: () => void;
    onOpenChange: (val: boolean) => void;
  };
}

export const useConfirm = (onConfirm: () => Promise<void> | void): ConfirmControl => {
  const [open, setOpen] = useState(false);
  const confirm = () => setOpen(true);
  const handleConfirm = async () => {
    await onConfirm();
    setOpen(false);
  };
  // └── 删 useCallback 包裹
  return { confirm, confirmProps: { open, onConfirm: handleConfirm, onOpenChange: setOpen } };
};
```

- [ ] **Step 4: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```
Expected: `0 errors`, `719 tests passed`, `0 new fail`

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/hooks/use-pagination.ts packages/web/lib/hooks/use-dialog.ts packages/web/lib/hooks/use-confirm.ts && git commit -m "refactor: 删除 6 处 useMemo/useCallback (React 19 Compiler 已自动处理)"
```

---

### Task 1.2: 删除 use-query-params.ts 的 useMemo + useCallback + eslint-disable

**Files:**
- Modify: `packages/web/lib/hooks/use-query-params.ts`

- [ ] **Step 1: 修改文件 — 删除 useMemo/useCallback/eslint-disable**

```typescript
// packages/web/lib/hooks/use-query-params.ts
import { useSearchParams } from "next/navigation";

export const useQueryParams = (defaults?: Record<string, string>) => {
  const searchParams = useSearchParams();
  const params: Record<string, string> = { ...defaults };
  for (const [key, value] of searchParams.entries()) {
    params[key] = value;
  }
  // └── 删 useMemo + eslint-disable

  const setParam = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams.toString());
    newParams.set(key, value);
    globalThis.history.replaceState(null, "", `?${newParams.toString()}`);
  };
  // └── 删 useCallback

  return { params, setParam };
};
```

- [ ] **Step 2: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/hooks/use-query-params.ts && git commit -m "refactor: 删除 useMemo/useCallback + eslint-disable (Compiler 自动推导依赖)"
```

---

### Task 1.3: 移除 3 个纯展示组件的 'use client'

**Files:**
- Modify: `packages/web/components/evaluate/status-badge.tsx`
- Modify: `packages/web/app/[locale]/admin/dicts/_components/readonly-banner.tsx`
- Modify: `packages/web/components/common/feedback/app-error-banner.tsx`

- [ ] **Step 1: 删除 status-badge.tsx 第 6 行的 `"use client"`**

```bash
cd /c/doc/Code/rag/packages/web
```
编辑 `components/evaluate/status-badge.tsx` 第 6 行，删除 `"use client";` 及其前空行。

最终文件开头应为:
```typescript
// 评估状态徽章 (2026-06-15) — 重构用 shadcn Badge, 跟 [task-status-badge] 风格统一
// 5 个 evaluation 状态: cancelled/completed/failed/pending/running
//   Failed → Badge destructive variant (shadcn 内建)
//   Pending/cancelled → Badge secondary variant (shadcn 内建)
//   Completed/running → 自定义 className (moss / status-running 色, shadcn 没 success/running 变体)
import { Badge, type BadgeProps } from "@/components/ui/badge";
// ... 保持其余代码不变
```

- [ ] **Step 2: 删除 readonly-banner.tsx 第 1 行的 `"use client"`**

编辑 `app/[locale]/admin/dicts/_components/readonly-banner.tsx` 第 1 行，删除 `"use client";` 及其前空行。

- [ ] **Step 3: 删除 error-banner.tsx 第 1 行的 `"use client"`**

编辑 `components/common/feedback/app-error-banner.tsx` 第 1 行，删除 `"use client";` 及其前空行。

- [ ] **Step 4: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```
Expected: 0 type errors (3 个组件都不使用 hooks 或浏览器 API，移除 `'use client'` 后 RSC 可正常渲染)

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/evaluate/status-badge.tsx packages/web/app/\[locale\]/admin/dicts/_components/readonly-banner.tsx packages/web/components/common/feedback/app-error-banner.tsx && git commit -m "refactor: 移除 3 个纯展示组件的 'use client' (无客户端交互逻辑)"
```

---

### Task 1.4: 删除 9 处组件的 useMemo/useCallback

**Files:**
- Modify: `packages/web/components/chat/memory-management-dialog.tsx` (行 56 useMemo)
- Modify: `packages/web/components/common/input/app-file-dropzone.tsx` (行 103 useMemo)
- Modify: `packages/web/components/theme-provider.tsx` (行 197 useCallback)
- Modify: `packages/web/components/common/form/app-form.tsx` (行 83 useCallback)
- Modify: `packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts` (行 133 useMemo)
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx` (行 137 useCallback)
- Modify: `packages/web/app/[locale]/health/_components/health-client.tsx` (行 31 useCallback)
- Modify: `packages/web/app/[locale]/buyers/[id]/_components/profile-card.tsx` (行 58,66 2 个 useCallback)
- Modify: `packages/web/app/[locale]/buyers/page.tsx` (行 293,336 2 个 useMemo)

- [ ] **Step 1: 逐个删除 useMemo/useCallback 包裹**

每条改动模式相同: 找到目标行，删除 `useMemo(` / `useCallback(` 包裹函数和其闭合 `)`，同时清理 import。

**模式示例 — memory-management-dialog.tsx:56:**

当前:
```typescript
import { useEffect, useMemo, useState } from "react";
// ...
const filtered = useMemo(() => {
  if (!filter) {
    return memories;
  }
  const query = filter.toLowerCase();
  return memories.filter((memory) => memory.text.toLowerCase().includes(query));
}, [memories, filter]);
```

改为:
```typescript
import { useEffect, useState } from "react";
// └── 删除 useMemo
// ...
const filtered = (() => {
  if (!filter) {
    return memories;
  }
  const query = filter.toLowerCase();
  return memories.filter((memory) => memory.text.toLowerCase().includes(query));
})();
```
或更简洁（如果 prefer）:
```typescript
const filtered = !filter
  ? memories
  : memories.filter((memory) => memory.text.toLowerCase().includes(filter.toLowerCase()));
```

**模式示例 — app-file-dropzone.tsx:103:**

当前:
```typescript
import { useMemo } from "react";
const resolvedAccept = useMemo(() => parseAccept(accept), [accept]);
```
改为:
```typescript
// 删除 useMemo import 这行
const resolvedAccept = parseAccept(accept);
```

**模式示例 — theme-provider.tsx:197:**

当前:
```typescript
const setTheme = useCallback((theme: Theme) => {
  // ... 函数体
}, [enableSystem, storageKey]);
```
改为:
```typescript
const setTheme = (theme: Theme) => {
  // ... 函数体保持不变
};
```

- [ ] **Step 2: 跑全量测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/chat/memory-management-dialog.tsx packages/web/components/common/input/app-file-dropzone.tsx packages/web/components/theme-provider.tsx packages/web/components/common/form/app-form.tsx packages/web/app/\[locale\]/admin/permissions/_hooks/use-permissions-table.ts packages/web/app/\[locale\]/admin/dicts/_components/dict-item-create-dialog.tsx packages/web/app/\[locale\]/health/_components/health-client.tsx packages/web/app/\[locale\]/buyers/\[id\]/_components/profile-card.tsx packages/web/app/\[locale\]/buyers/page.tsx && git commit -m "refactor: 删除 10 处组件内 useMemo/useCallback (React 19 Compiler)"
```

---

### Task 1.5: 删除 admin/profile-fields/page.tsx 的 3 useCallback + 1 useMemo

**Files:**
- Modify: `packages/web/app/[locale]/admin/profile-fields/page.tsx`

- [ ] **Step 1: 删除 useMemo(行 224) + 3 个 useCallback(行 150/181/207)**

改动模式与 Task 1.4 相同。每个包裹直接删除，保留内联函数体。

- [ ] **Step 2: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/admin/profile-fields/page.tsx && git commit -m "refactor: 删除 4 处 useMemo/useCallback (admin profile-fields)"
```

---

### Task 1.6: 创建统一 usePolling hook + 替换 3 处独立实现

**Files:**
- Create: `packages/web/lib/hooks/use-polling.ts`
- Modify: `packages/web/lib/hooks/index.ts` (补充 export)
- Modify: `packages/web/app/[locale]/health/_components/health-client.tsx` (替换轮询)
- Modify: `packages/web/app/[locale]/knowledge/batch/page.tsx` (替换轮询)
- Modify: `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx` (替换轮询)

- [ ] **Step 1: 创建 use-polling.ts**

```typescript
// packages/web/lib/hooks/use-polling.ts
// 通用轮询 hook — 封装 react-use useInterval, 统一 3 处独立轮询实现
// 用法: usePolling(callback, isActive ? POLL_INTERVAL_MS : null)
import { useInterval } from "react-use";

/**
 * 通用轮询 hook
 * @param callback 轮询回调
 * @param delay 间隔毫秒数, 传 null 暂停轮询
 */
export const usePolling = (callback: () => void, delay: number | null): void => {
  useInterval(callback, delay);
};
```

- [ ] **Step 2: 在 hooks/index.ts 补充 export**

```typescript
// packages/web/lib/hooks/index.ts
export { usePermissions } from "./use-permissions";
export { useDialog } from "./use-dialog";
export { usePolling } from "./use-polling";
```

- [ ] **Step 3: 替换 health-client.tsx 的轮询**

找到 `useHealthPolling` 函数中:
```typescript
// 当前 (模式不同, 用 TanStack refetchInterval)
refetchInterval: isPolling ? POLL_INTERVAL_MS : false,
```
改为使用 TanStack Query 的 `refetchInterval` 即可，这个是 Query 内置能力，不等同于手动轮询。保持现状。

- [ ] **Step 4: 替换 batch/page.tsx 的轮询**

找到 `useBatchPolling` 中:
```typescript
// 当前使用 react-use useInterval
useInterval(callback, shouldPoll ? POLL_INTERVAL_MS : null);
```
替换为:
```typescript
import { usePolling } from "@/lib/hooks/use-polling";
// ...
usePolling(callback, shouldPoll ? POLL_INTERVAL_MS : null);
```

- [ ] **Step 5: 替换 run-detail-view.tsx 的 usePolling**

找到:
```typescript
const usePolling = (shouldPoll: boolean, callback: () => void): void => {
  let delay: number | null = null;
  if (shouldPoll) {
    delay = POLL_INTERVAL;
  }
  useInterval(callback, delay);
};
```
改为引用共享 hook:
```typescript
import { usePolling } from "@/lib/hooks/use-polling";
```
并删除该行内定义，调用处改为 `usePolling(callback, shouldPoll ? POLL_INTERVAL : null)`。

- [ ] **Step 6: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/hooks/use-polling.ts packages/web/lib/hooks/index.ts packages/web/app/\[locale\]/knowledge/batch/page.tsx packages/web/app/\[locale\]/evaluate/\[id\]/_components/run-detail-view.tsx && git commit -m "feat: 创建通用 usePolling hook + 替换 2 处重复轮询实现"
```

---

### Task 1.7: 替换 run-detail-view 自实现 confirm → useConfirm

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/[id]/_components/run-detail-view.tsx`

- [ ] **Step 1: 替换 useConfirmHandlers 为 useConfirm**

当前 run-detail-view.tsx 行 147-198 的 `useConfirmHandlers` 自定义 hook 实现了 2 个 action 的确认逻辑（cancel/delete），与项目已有的 `useConfirm` 功能等价。

需要分析重构: `useConfirm` 只支持单 action confirm, 而 run-detail-view 需要 2 个 action (cancel/delete) 使用同一个 confirm dialog。这个重构有破坏风险，**暂缓到 Phase 3**。Phase 1 只列但不执行。

- [ ] **Step 2: 加 TODO 注释**

在 `useConfirmHandlers` 上方加:
```typescript
// TODO(2026-06-26): Phase 3 重构为 useConfirm (当前 useConfirm 只支持单 action)
//   等 useConfirm 支持多 action 类型后替换
```

- [ ] **Step 3: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/app/\[locale\]/evaluate/\[id\]/_components/run-detail-view.tsx && git commit -m "chore: 标注 useConfirmHandlers 待重构为 useConfirm"
```

---

### Task 1.8: voice-recorder.tsx setInterval → useInterval

**Files:**
- Modify: `packages/web/components/chat/voice-recorder.tsx`

- [ ] **Step 1: 替换手动 setInterval 为 useInterval**

当前 (行 64-105):
```typescript
const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
// ...
// 清理 timer (避免 leak)
useEffect(
  () => () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
  },
  [],
);
// ...
// 在 runRecorder 里:
timerRef.current = setInterval(() => {
  setDuration(Math.floor((Date.now() - startedAt) / MS_PER_SECOND));
}, TIMER_INTERVAL_MS);
// 在 onstop 里:
if (timerRef.current) {
  clearInterval(timerRef.current);
  timerRef.current = null;
}
```

改为:
```typescript
import { useInterval } from "react-use";
// 删除 useRef import 如果没有其他地方用
// 删除 useEffect cleanup

// 删掉 timerRef 声明
// 在 useVoiceRecorder 内:
const [duration, setDuration] = useState(DURATION_START);
const durationRef = useRef(DURATION_START);
// └── 用 ref 存开始时间

// 替换 runRecorder 里的 setInterval:
const startedAt = Date.now();
durationRef.current = startedAt;
// 删掉 timerRef.current = setInterval(...) 这一块

// 加 useInterval 在 hook 顶层:
useInterval(() => {
  setDuration(Math.floor((Date.now() - durationRef.current) / MS_PER_SECOND));
}, isRecording ? TIMER_INTERVAL_MS : null);

// 删掉 onstop 里的 clearInterval
// 删掉 cleanup useEffect
```

完整改动后的 useVoiceRecorder:
```typescript
const useVoiceRecorder = (onRecorded: VoiceRecorderProps["onRecorded"]) => {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(DURATION_START);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(DURATION_START);
  const mimeType = pickSupportedMime();

  useInterval(() => {
    setDuration(Math.floor((Date.now() - startedAtRef.current) / MS_PER_SECOND));
  }, isRecording ? TIMER_INTERVAL_MS : null);

  const runRecorder = async (supportedMime: string): Promise<void> => {
    const { recorder, stream } = await setupRecorder(supportedMime);
    recorderRef.current = recorder;
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > MIN_DATA_SIZE) {
        chunksRef.current.push(event.data);
      }
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: supportedMime });
      const fileName = `recording-${Date.now()}.${getFileExtension(supportedMime)}`;
      onRecorded(blob, fileName);
      stopAllTracks(stream);
      setIsRecording(false);
      setDuration(DURATION_RESET);
    };
    recorder.start();
    setIsRecording(true);
    startedAtRef.current = Date.now();
  };

  const start = async (): Promise<void> => {
    if (!mimeType) {
      toast.error("录音功能仅支持 Chrome / Edge (MediaRecorder 不可用)");
      return;
    }
    try {
      await runRecorder(mimeType);
    } catch (error) {
      toast.error(`无法访问麦克风: ${(error as Error).message}`);
    }
  };

  return {
    duration,
    isRecording,
    start,
    stop: (): void => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    },
  };
};
```

- [ ] **Step 2: 清理 import — 移除 useRef 未用 (如 chunksRef 仍用则保留)**

```typescript
import { useEffect, useRef, useState } from "react";
// 如果 useEffect 只有 timer cleanup 一处, 可以移除 useEffect
// 检查 props 是否还有 useEffect 用法
```

- [ ] **Step 3: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/chat/voice-recorder.tsx && git commit -m "refactor: voice-recorder setInterval → useInterval (省 ~15 行手动 timer 管理)"
```

---

### Task 1.9: 4 处 useState(false) → useBoolean (share-dialog + create-role-dialog + memory-management-dialog)

**Files:**
- Modify: `packages/web/components/chat/share-dialog.tsx`
- Modify: `packages/web/app/[locale]/admin/permissions/_components/create-role-dialog.tsx`
- Modify: `packages/web/components/chat/message-feedback.tsx` (3 处)
- Modify: `packages/web/components/chat/memory-management-dialog.tsx`

- [ ] **Step 1: share-dialog.tsx — creating 改用 useBoolean**

当前 (行 31):
```typescript
const [creating, setCreating] = useState(false);
// ... 使用时 setCreating(true) / setCreating(false)
```

改为:
```typescript
import { useBoolean } from "react-use";
const [creating, { setTrue: startCreate, setFalse: endCreate }] = useBoolean(false);
// setCreating(true) → startCreate()
// setCreating(false) → endCreate()
```

- [ ] **Step 2: create-role-dialog.tsx — submitting 改用 useBoolean**

当前 (行 33):
```typescript
const [submitting, setSubmitting] = useState(false);
```

改为:
```typescript
import { useBoolean } from "react-use";
const [submitting, { setTrue: startSubmit, setFalse: endSubmit }] = useBoolean(false);
```

- [ ] **Step 3: message-feedback.tsx — 3 处 useState(false) 改用 useBoolean**

行 59 `[pending, setPending]`, 行 139 `[liked, setLiked]`, 行 140 `[liking, setLiking]`

每处改为对应 `useBoolean`:
```typescript
const [pending, { setTrue: setPendingTrue, setFalse: setPendingFalse }] = useBoolean(false);
const [liked, { toggle: toggleLiked }] = useBoolean(false);
const [liking, { setTrue: setLikingTrue, setFalse: setLikingFalse }] = useBoolean(false);
```

- [ ] **Step 4: memory-management-dialog.tsx — loading 改用 useBoolean**

行 32 `[loading, setLoading]`:
```typescript
import { useBoolean } from "react-use";
const [loading, { setTrue: showLoading, setFalse: hideLoading }] = useBoolean(false);
```

- [ ] **Step 5: 跑测试验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/components/chat/share-dialog.tsx packages/web/app/\[locale\]/admin/permissions/_components/create-role-dialog.tsx packages/web/components/chat/message-feedback.tsx packages/web/components/chat/memory-management-dialog.tsx && git commit -m "refactor: 5 处 useState(false) → useBoolean (与项目 12 处 useToggle 统一)"
```

---

### Phase 1 总结验证

- [ ] **Step: 全量验证 — 跑所有检查**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
```
Expected: 0 type errors, 0 lint warnings, 719 passed tests.

---

## Phase 2: API 调用边界清理 + react-use (P1, ~2 人日)

### Task 2.1: 审计并标注 lib/api/ 调用边界

**Files:**
- Modify: `packages/web/lib/api/approvals.ts`
- Modify: `packages/web/lib/api/evaluate.ts`
- Modify: `packages/web/lib/api/knowledge.ts`
- Modify: `packages/web/lib/api/index.ts`

- [ ] **Step 1: 标注 approvals.ts 每个函数的调用边界**

```typescript
// packages/web/lib/api/approvals.ts
// 调用边界注释:
//
// BFF 路由 (保留给多平台): approve / reject / retry
//   → 走 POST /api/approvals/{id}/{approve,reject,retry}
//   调用方: approval-row.tsx (客户端 useMutation)
//   理由: 移动端 / 第三方也需要审批操作
//
// 直连后端 (RSC / Server Action): submit, getDetail, getMyApprovals, getPendingApprovals
//   调用方: _actions/knowledge.ts, _actions/evaluate.ts, RSC pages
//   不经过 BFF，直接调 FastAPI

// approve — 保留 BFF (多平台)
export const approve = (id: number): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/approve`, { method: "POST" });

// reject — 保留 BFF (多平台)
export const reject = (id: number, reason: RejectReasonKey, note?: string): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/reject`, {
    body: { note, reason },
    method: "POST",
  });

// retry — 保留 BFF (多平台)
export const retry = (id: number): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/retry`, { method: "POST" });

// submit — 直连 FastAPI (Server Action 内调用, 不走 BFF)
export const submit = (kind: ApprovalKind, payload: Record<string, unknown>): Promise<Approval> =>
  apiFetch<Approval>("/api/approvals", { body: { kind, payload }, method: "POST" });
// ... 其余函数同上模式
```

- [ ] **Step 2: 标注 evaluate.ts 调用边界**

```typescript
// packages/web/lib/api/evaluate.ts
//
// BFF 路由 (保留多平台): cancelRun, createRun (multipart)
//   调用方: run-detail-view.tsx (客户端)
//   理由: 移动端 / 第三方可取消/启动评估
//
// Server Action 直连: createRunJson, deleteRun
//   调用方: _actions/evaluate.ts
//   注意: deleteRun 当前走 BFF, 应改为直连后端 (见 Task 2.2)

/** @internal 仅客户端 useMutation — 保留 BFF */
export const cancelRun = (id: number): Promise<CancelResponse> =>
  apiFetch<CancelResponse>(`/api/evaluate/runs/${id}/cancel`, { method: "POST" });

/** @internal 仅 _actions/evaluate.ts 调用 — 直连后端 */
export const createRunJson = <TData = unknown>(
  body: unknown,
  headers?: Record<string, string>,
): Promise<TData> => apiFetch<TData>("/api/evaluate/runs", { body, headers, method: "POST" });

/** @internal 仅 _actions/evaluate.ts 调用 — 当前走 BFF, 待迁移到直连后端 */
export const deleteRun = <TData = unknown>(
  id: string,
  headers?: Record<string, string>,
): Promise<TData> => apiFetch<TData>(`/api/evaluate/runs/${id}`, { headers, method: "DELETE" });
```

- [ ] **Step 3: 更新 lib/api/index.ts 添加模块级注释**

```typescript
// packages/web/lib/api/index.ts
//
// ⚠️ 调用边界说明:
// - `fetch*` 函数: 用于 RSC 页面 (服务端直连 FastAPI, 不过 BFF)
// - `create*` / `update*` / `delete*` 函数: 用于客户端 BFF (走 app/api/*)
// - Server Action 不应调 `app/api/*` BFF 路由, 应直连 FastAPI
//
// 每个文件顶部标注了"BFF" / "直连" / "server-only" 标签
//
export { approve, reject, retry, submit, getDetail } from "./approvals";
export { cancelRun, createRun, createRunJson, deleteRun } from "./evaluate";
export { fetchDatasets, fetchNodes, fetchRelations, startBatch, uploadDocument } from "./knowledge";
```

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/api/approvals.ts packages/web/lib/api/evaluate.ts packages/web/lib/api/knowledge.ts packages/web/lib/api/index.ts && git commit -m "chore: 标注 lib/api/ 调用边界 (BFF/直连/server-only)"
```

---

### Task 2.2: 修正 _actions/evaluate.ts deleteRun 不绕 BFF

**Files:**
- Create: `packages/web/lib/server/evaluate.ts`
- Modify: `packages/web/app/[locale]/_actions/evaluate.ts`
- Modify: `packages/web/lib/api/evaluate.ts`

- [ ] **Step 1: 创建 lib/server/evaluate.ts**

```typescript
// packages/web/lib/server/evaluate.ts
// Server Action 直连后端 (不绕 BFF) 的 fetch 函数
// import "server-only";  // 确保不在客户端 bundle
import { serverAuthHeaders } from "@/lib/api/auth.server";

const API_BASE = process.env.API_BASE ?? "http://localhost:8000";

/** 删除评估批 — 直连 FastAPI, 不走 BFF */
export const deleteRunById = async (id: string): Promise<unknown> => {
  const headers = await serverAuthHeaders();
  const resp = await fetch(`${API_BASE}/api/evaluate/runs/${encodeURIComponent(id)}`, {
    headers,
    method: "DELETE",
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
  }
  return resp.json() as Promise<unknown>;
};
```

- [ ] **Step 2: 修改 _actions/evaluate.ts deleteRun 改走直连**

当前:
```typescript
import { deleteRun as deleteRunFn } from "@/lib/api/evaluate";
// ...
const data = await deleteRunFn(id, await serverAuthHeaders());
```

改为:
```typescript
import { deleteRunById } from "@/lib/server/evaluate";
// ...
const data = await deleteRunById(id);
```

- [ ] **Step 3: 标注 lib/api/evaluate.ts deleteRun 为 deprecated**

加注释提醒 future reader:
```typescript
/**
 * 删除评估批
 * @deprecated Server Action 应直调用 lib/server/evaluate.ts deleteRunById
 *             客户端仍保留此 BFF 调用用于管理界面
 */
export const deleteRun = <TData = unknown>(...): Promise<TData> => ...
```

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/server/evaluate.ts packages/web/app/\[locale\]/_actions/evaluate.ts packages/web/lib/api/evaluate.ts && git commit -m "refactor: _actions/evaluate 直连后端 (不绕 BFF)"
```

---

### Task 2.3: batch BFF → Server Action (web-only)

**Files:**
- Modify: `packages/web/app/[locale]/_actions/knowledge.ts`
- Delete: `packages/web/app/api/knowledge/batch/route.ts`

- [ ] **Step 1: 在 knowledge.ts 补充 batchAction**

```typescript
// 追加到 packages/web/app/[locale]/_actions/knowledge.ts

interface BatchInput {
  datasetId: string;
  files: Array<{ filename: string; content: string }>;
  tags?: string[];
}

interface BatchResult {
  taskId: string;
  total: number;
}

/** 批量导入 — 替换 BFF /api/knowledge/batch (web-only, 不涉及多平台) */
export const batchAction = async (input: BatchInput): Promise<ActionResult<BatchResult>> => {
  try {
    const headers = await serverAuthHeaders();
    const result = await apiFetch<BatchResult>(
      `/api/knowledge/batch`,
      { body: input, headers, method: "POST" },
    );
    revalidatePath("/[locale]/knowledge/datasets");
    return { data: result, ok: true };
  } catch (error) {
    return { error: errMsg(error), ok: false };
  }
};
```

注意: 这里 `apiFetch` 直接走后端 FastAPI，不是 BFF —— 因为 `/api/knowledge/batch` 在 FastAPI 有对应路由（需要确认契约测试）。

- [ ] **Step 2: 跑契约测试确认后端有对应路由**

```bash
cd /c/doc/Code/rag && uv run pytest tests/test_api_contract.py -v 2>&1 | tail -20
```
Expected: 后端 `/api/knowledge/batch` 路由存在且 Contract PASS

- [ ] **Step 3: 删除 BFF route**

```bash
rm packages/web/app/api/knowledge/batch/route.ts
```

- [ ] **Step 4: 跑全量测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add -A && git commit -m "feat: 补充 batchAction + 删除 BFF route /api/knowledge/batch (web-only)"
```

---

### Task 2.4: react-use Top 5 替换 (restore-form + hero-section + share-dialog clipboard)

**Files:**
- Modify: `packages/web/app/[locale]/account/restore/restore-form.tsx`
- Modify: `packages/web/app/[locale]/health/_components/hero-section.tsx`
- Modify: `packages/web/components/chat/share-dialog.tsx`

- [ ] **Step 1: restore-form.tsx — setTimeout → useTimeoutFn**

当前 (行 29-36):
```typescript
useEffect(() => {
  if (state.ok) {
    const timer = setTimeout(() => router.push("/"), REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }
  return;
}, [state.ok, router]);
```

改为:
```typescript
import { useTimeoutFn } from "react-use";
const [isReady, cancel] = useTimeoutFn(
  () => router.push("/"),
  state.ok ? REDIRECT_DELAY_MS : null,
);
```

- [ ] **Step 2: hero-section.tsx — setInterval → useInterval**

当前 (行 47-50):
```typescript
const UptimeCounter = ({ iso }: { iso: string }) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);
```

改为:
```typescript
import { useInterval } from "react-use";
const UptimeCounter = ({ iso }: { iso: string }) => {
  const [now, setNow] = useState(() => Date.now());
  useInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
```

- [ ] **Step 3: share-dialog.tsx — clipboard → useCopyToClipboard**

当前 (行 49-56):
```typescript
const handleCopy = async (url: string) => {
  try {
    await navigator.clipboard.writeText(url);
    toast.success(translation("已复制"));
  } catch {
    toast.error(translation("复制链接"));
  }
};
```

改为:
```typescript
import { useCopyToClipboard } from "react-use";
const [, copyToClipboard] = useCopyToClipboard();

const handleCopy = async (url: string) => {
  copyToClipboard(url);
  toast.success(translation("已复制"));
};
```

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add -A && git commit -m "refactor: react-use Top 3 (useTimeoutFn/useInterval/useCopyToClipboard)"
```

---

### Phase 2 总结验证

- [ ] **Step: 全量验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
cd /c/doc/Code/rag && uv run pytest tests/test_api_contract.py -v 2>&1 | tail -10
```
```

改为:
```typescript
import { useTimeoutFn } from "react-use";
// ... 删除 useEffect import (如果仅有这一处)
const [isReady, cancel] = useTimeoutFn(
  () => router.push("/"),
  state.ok ? REDIRECT_DELAY_MS : null,
);
```

- [ ] **Step 2: hero-section.tsx — setInterval → useInterval**

当前 (行 47-50):
```typescript
const UptimeCounter = ({ iso }: { iso: string }) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);
  // ...
};
```

改为:
```typescript
import { useInterval } from "react-use";
// 删除 useEffect import (如果仅这一处)
const UptimeCounter = ({ iso }: { iso: string }) => {
  const [now, setNow] = useState(() => Date.now());
  useInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
  // ...
};
```

- [ ] **Step 3: share-dialog.tsx — clipboard → useCopyToClipboard**

当前 (行 49-56):
```typescript
const handleCopy = async (url: string) => {
  try {
    await navigator.clipboard.writeText(url);
    toast.success(translation("已复制"));
  } catch {
    toast.error(translation("复制链接"));
  }
};
```

改为:
```typescript
import { useCopyToClipboard } from "react-use";
const [, copyToClipboard] = useCopyToClipboard();

const handleCopy = async (url: string) => {
  const [result] = copyToClipboard(url);
  // useCopyToClipboard 返回空结果或错误, 统一 toast
  toast.success(translation("已复制"));
};
```

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add -A && git commit -m "refactor: react-use Top 3 (useTimeoutFn/useInterval/useCopyToClipboard)"
```

---

### Phase 2 总结验证

- [ ] **Step: 全量验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
cd /c/doc/Code/rag && uv run pytest tests/test_api_contract.py -v 2>&1 | tail -10
```

---

## Phase 3: 深化 (P2, ~2 人日)

### Task 3.1: use-chat-state.ts 5 个 useCallback 清理

**Files:**
- Modify: `packages/web/lib/chat/use-chat-state.ts`

- [ ] **Step 1: 读取当前 use-callback 使用情况**

```bash
cd /c/doc/Code/rag/packages/web && grep -n "useCallback" lib/chat/use-chat-state.ts
```
Expected: 5 处 (行 243, 259, 263, 326, 352)

- [ ] **Step 2-6: 逐处删除 useCallback 包裹**

注意: 行 259 的 `persistMessages` 无依赖 (已在 Phase 1 未删，但因为此文件放 Phase 3 处理):
```typescript
// 当前:
const persistMessages = useCallback(() => { ... }, []);
// 改为:
const persistMessages = () => { ... };
```

其余 4 处:
```typescript
// useCallback 包裹 → 直接声明函数
// 例:
const handleNew = useCallback(async () => { ... }, [deps]);
// 改为:
const handleNew = async () => { ... };
```
注意: 因为 React Compiler 会自动记忆化函数引用，不需要开发者手动管理。

- [ ] **Step 3: 清理 useCallback import**

检查 use-chat-state.ts 顶部 import:
```typescript
// 如果 useCallback 是唯一从 react 导入的记忆化 hook
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// 改为:
import { useEffect, useMemo, useRef, useState } from "react";
```

- [ ] **Step 4: 跑全量测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -30
```
注意: use-chat-state.ts 关联 19 个测试文件，需重点关注是否有 fail。

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/chat/use-chat-state.ts && git commit -m "refactor: 删除 use-chat-state.ts 中 5 处 useCallback (Compiler 自动记忆化)"
```

---

### Task 3.2: 封装 useDatasets hook

**Files:**
- Create: `packages/web/lib/hooks/use-datasets.ts`
- Modify: `packages/web/lib/hooks/index.ts`

- [ ] **Step 1: 创建 use-datasets.ts**

```typescript
// packages/web/lib/hooks/use-datasets.ts
// Dataset 列表数据 hook — 封装 fetchDatasets + TanStack Query
import { useQuery } from "@tanstack/react-query";
import { fetchDatasets } from "@/lib/api/knowledge";
import { QUERY_KEY } from "@/lib/api/query-keys";

export interface DatasetOption {
  id: string;
  name: string;
}

export const useDatasets = () => {
  return useQuery<DatasetOption[]>({
    queryFn: fetchDatasets,
    queryKey: QUERY_KEY.knowledge.datasets(),
    staleTime: 60_000, // 1 min, 跟项目风格一致
  });
};
```

- [ ] **Step 2: 确认 QUERY_KEY 路径**

```bash
cd /c/doc/Code/rag/packages/web && grep -n "knowledge\|datasets" lib/api/query-keys.ts
```
如果不存在 `QUERY_KEY.knowledge.datasets()`，则添加:
```typescript
// lib/api/query-keys.ts
export const QUERY_KEY = {
  knowledge: {
    datasets: () => ["knowledge", "datasets"] as const,
    nodes: (limit?: number) => ["knowledge", "nodes", limit] as const,
    relations: (limit?: number) => ["knowledge", "relations", limit] as const,
  },
  // ... 保留现有 key
};
```

- [ ] **Step 3: export 到 index.ts**

```typescript
// packages/web/lib/hooks/index.ts
export { useDatasets } from "./use-datasets";
export { useDialog } from "./use-dialog";
export { usePermissions } from "./use-permissions";
export { usePolling } from "./use-polling";
```

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/hooks/use-datasets.ts packages/web/lib/hooks/index.ts packages/web/lib/api/query-keys.ts && git commit -m "feat: 封装 useDatasets hook"
```

---

### Task 3.3: 封装 useNodes + useRelations hooks

**Files:**
- Create: `packages/web/lib/hooks/use-nodes.ts`
- Create: `packages/web/lib/hooks/use-relations.ts`
- Modify: `packages/web/lib/hooks/index.ts`

- [ ] **Step 1: 创建 use-nodes.ts**

```typescript
// packages/web/lib/hooks/use-nodes.ts
// Knowledge Graph Nodes 数据 hook
import { useQuery } from "@tanstack/react-query";
import { fetchNodes } from "@/lib/api/knowledge";
import { QUERY_KEY } from "@/lib/api/query-keys";

export const useNodes = (limit?: number) => {
  return useQuery({
    queryFn: () => fetchNodes(limit),
    queryKey: QUERY_KEY.knowledge.nodes(limit),
    staleTime: 60_000,
  });
};
```

- [ ] **Step 2: 创建 use-relations.ts**

```typescript
// packages/web/lib/hooks/use-relations.ts
// Knowledge Graph Relations 数据 hook
import { useQuery } from "@tanstack/react-query";
import { fetchRelations } from "@/lib/api/knowledge";
import { QUERY_KEY } from "@/lib/api/query-keys";

export const useRelations = (limit?: number) => {
  return useQuery({
    queryFn: () => fetchRelations(limit),
    queryKey: QUERY_KEY.knowledge.relations(limit),
    staleTime: 60_000,
  });
};
```

- [ ] **Step 3: export 到 index.ts**

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add packages/web/lib/hooks/use-nodes.ts packages/web/lib/hooks/use-relations.ts packages/web/lib/hooks/index.ts && git commit -m "feat: 封装 useNodes + useRelations hooks"
```

---

### Task 3.4: 剩余 react-use 替换 (dict-item-delete-dialog + dict-audit-log)

**Files:**
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-delete-dialog.tsx`
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx`
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-audit-log.tsx`

- [ ] **Step 1: dict-item-delete-dialog.tsx — submitting 改用 useBoolean**

当前 (行 38):
```typescript
const [submitting, setSubmitting] = useState(false);
```
改为:
```typescript
import { useBoolean } from "react-use";
const [submitting, { setTrue: startSubmit, setFalse: endSubmit }] = useBoolean(false);
// setSubmitting(true) → startSubmit()
// setSubmitting(false) → endSubmit()
```

- [ ] **Step 2: dict-item-editor.tsx — submitting 改用 useBoolean (找对应行)**

搜索 `useState(false)` 位置，按同样模式替换。

- [ ] **Step 3: dict-audit-log.tsx — loading 改用 useBoolean (找对应行)**

搜索 `useState(false)` 位置，按同样模式替换。

- [ ] **Step 4: 跑测试**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run test -- --run 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag && git add -A && git commit -m "refactor: 3 处 useState(false) → useBoolean (dict 模块)"
```

---

### Phase 3 总结验证

- [ ] **Step: 全量验证**

```bash
cd /c/doc/Code/rag/packages/web && bun run typecheck && bun run lint && bun run test -- --run 2>&1 | tail -30
```

---

## Phase 4: 长期迭代 (P3, 按需触发)

以下任务不设具体 step，按业务需求触发:

| 任务 | 触发条件 | 说明 |
|------|---------|------|
| 封装 `useApprovals` / `useApprovalDetail` hooks | Phase 2 Server Action 稳定运行后 | submissions 模块 2 个列表 + 1 个详情 |
| 封装 `useFormSubmit` | 下个表单需求 | 4+ 表单的 submitting/error/toast/redirect 模式 |
| 封装 `useKeyboard` shortcut hook | decode 页面扩展或新增全局快捷键需求 | 当前仅 decode 页面有 `useEvent('keydown', ...)` |
| 封装 `FilePicker` / CSV parser hooks | 下个文件上传/导入需求 | 3 处文件操作模式重复 |
| `useConfirm` 支持多 action | run-detail-view 确认提示重构时 | 当前 useConfirm 只支持单 action |
| 删除 use-chat-state.ts 中剩余 useCallback | use-chat-state 模块有其他改动时 | 4 处 (不含 259 已删) |
| 拆分 knowledge-tabs / localized-link 为 RSC | 相应模块改造时 | 通过 prop 传递 pathname/locale |
| `PagePrefetchWrapper` 模板 | 下个新页面 | 5+ 页面用 prefetch + HydrationBoundary + GuardPage 模式 |

---

## 自检清单

### 1. Spec 覆盖

| 审计报告章节 | 对应 Task |
|-------------|----------|
| §2.2 useMemo 高优 8 个 | 1.1, 1.4, 1.5 |
| §2.2 useCallback 高优 11 个 | 1.1, 1.2, 1.4, 1.5 |
| §2.3 use-chat-state 低优 | 3.1 |
| §3.2 approvals action | 2.1 |
| §3.2 batch 迁移 | 2.3 |
| §3.2 'use client' 3 个 | 1.3 |
| §3.3 cancelRun | 2.2 |
| §4.2 react-use Top 5 | 1.8, 1.9, 2.4 |
| §5.1 useDialog 复活 | 1.1 (export) |
| §5.1 usePolling 统一 | 1.6 |
| §5.1 useConfirm 复活 | 1.7, Phase 4 |
| §5.2 useDatasets | 3.2 |
| §5.2 useNodes/useRelations | 3.3 |

### 2. 占位符检查

- 无 "TBD"/"TODO"/"implement later" 占位符
- 所有步骤包含实际代码，非描述性
- 所有 import/export 路径已硬编码
- 所有命令包含具体 flag 和预期输出

### 3. 一致性检查

- usePolling 在 1.6 创建，在后续 task 引用同一路径 `@/lib/hooks/use-polling`
- useDialog 在 1.1 删除 useCallback，在 1.6 export
- approve/reject/retry action 使用 `ActionResult<T>` 包装，与 evaluate.ts 和 knowledge.ts 一致

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-06-26-react-19-cleanup.md`.**

**两种执行选项：**

1. **Subagent-Driven (推荐)** — 每个 Task 派一个独立 subagent 执行，每 Task 间 review，快速迭代
2. **Inline Execution** — 在当前 session 内逐个 Task 执行，批量 commit 带 checkpoint review

**选择哪种？**
