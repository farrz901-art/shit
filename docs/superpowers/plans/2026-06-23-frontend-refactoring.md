# 前端代码重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan phase-by-phase. Each phase produces a working, testable result. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 降低结构模式重复率，消除无用 useMemo/useCallback，提取通用 hooks/components，拆分大组件，RSC 收敛，Zustand 状态降维

**Architecture:** 7 个 Phase 顺序执行，每个 Phase 输出是下一 Phase 输入。Phase 2 (Hooks) 先于 Phase 3 (Components) 和 Phase 6 (Zustand)。每个 Phase 后必须通过 tsc + vitest + oxlint。

**Tech Stack:** React 19 / Next.js 16 / TypeScript 8 / react-use (hooks) / es-toolkit (工具) / Zustand / shadcn/ui / TanStack Query / vitest

---

## 执行统计

| Phase | 内容 | 预计文件数 |
|-------|------|-----------|
| P1 | es-toolkit + useMemo/useCallback 清理 | ~30 |
| P2 | 提取 4 个通用 Hooks (react-use 做不了的) + react-use 替换 | 4 新建 + ~25 消费者 |
| P3 | 提取 6 个通用组件 | 6 新建 + ~30 替换 |
| P4 | 大组件拆分 (6 个) | ~20 |
| P5 | RSC/RSF 拆分 | ~25 |
| P6 | Zustand 状态收敛 | 2 新建 + ~10 替换 |
| P7 | 最终验证 | baseline 比较 |

---

### Phase 1: react-use 优先 + es-toolkit 辅助 + useMemo/useCallback 清理

**工具选择策略:** hooks 用 react-use，数组/对象工具用 es-toolkit，react-use 做不了的才考虑 es-toolkit

**Files:**
- Modify: `packages/web/components/**/*.tsx`
- Modify: `packages/web/app/**/*.tsx`

- [ ] **1a: 扫描可替换模式**

```bash
cd packages/web

# 查找 useToggle 可替换模式
grep -rn "const \[.*setOpen\] = useState(false)" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test\|\.next | head -20

# 查找 useAsync 可替换模式 (useEffect + fetch + useState 三板斧)
grep -rn "useEffect.*fetch\|useEffect.*loading\|useEffect.*setData" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test\|\.next | head -20

# 查找 useDebounce 可替换模式
grep -rn "setTimeout.*clearTimeout" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test\|\.next | head -10

# 数组去重 → es-toolkit
grep -rn "filter.*indexOf\|new Set\|reduce.*push\|\.includes.*map" app/ components/ lib/ --include="*.tsx" --include="*.ts" | grep -v node_modules\|\.test\|\.next | head -20

# 手写排序 → es-toolkit sortBy
grep -rn "\.sort.*a\.\|\.sort.*b\." app/ components/ lib/ --include="*.tsx" --include="*.ts" | grep -v node_modules\|\.test\|\.next | head -10
```

- [ ] **1b: 替换 useToggle (react-use)**

```typescript
// 改前
const [open, setOpen] = useState(false);
const toggle = () => setOpen((v) => !v);
// 改后
import { useToggle } from "react-use";
const [open, toggle] = useToggle(false);
```

- [ ] **1c: 替换 useAsync/useAsyncFn (react-use)**

```typescript
// 改前
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
useEffect(() => { fetchData().then(setData).finally(() => setLoading(false)); }, []);
// 改后
import { useAsync } from "react-use";
const { value: data, loading, error } = useAsync(async () => fetchData(), []);
```

- [ ] **1d: 替换 useDebounce (react-use)**

```typescript
// 改前
const [debouncedVal, setDebounced] = useState(val);
useEffect(() => { const t = setTimeout(() => setDebounced(val), 300); return () => clearTimeout(t); }, [val]);
// 改后
import { useDebounce } from "react-use";
const [debouncedVal] = useDebounce(val, 300);
```

- [ ] **1e: 替换手写数组/对象操作 → es-toolkit**

```typescript
// 数组去重 → uniq/uniqBy
import { uniqBy } from "es-toolkit";
const uniqueItems = uniqBy(items, (i) => i.id);

// 手写排序 → sortBy
import { sortBy } from "es-toolkit";
const sorted = sortBy(items, [(i) => i.name]);
```

- [ ] **1f: 清理无意义 useMemo/useCallback**

```bash
# 扫描候选
grep -rn "useMemo.*\[\]" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test
grep -rn "useCallback.*\[\]" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test
```

逐条判定：入参原始类型 + 无 React.memo 子组件 → 提为普通函数。

```typescript
// 可删
const options = useMemo(() => ["a", "b", "c"], []);
// → const OPTIONS = ["a", "b", "c"];

// 可删
const handleClick = useCallback(() => console.log("click"), []);
// → const handleClick = () => console.log("click"); (组件内)
```

- [ ] **1g: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
bun run format:check
```

- [ ] **1h: Commit**

```bash
git add packages/web/
git commit -m "refactor(P1): react-use + es-toolkit 替换手写模式 + 清理 useMemo/useCallback"
```

---

### Phase 2: 提取通用 Hooks (react-use 做不了的才自己写)

**优先用 react-use:**
- `useToggle` → `import { useToggle } from "react-use";`
- `useAsync` / `useAsyncFn` → `import { useAsync } from "react-use";`
- `useDebounce` → `import { useDebounce } from "react-use";`

**自己写的 (react-use 没有):**
- `useDialog` — Dialog open/close 状态管理
- `usePagination` — 分页计算
- `useQueryParams` — URL query 参数管理
- `useConfirm` — 确认弹窗状态管理

**Files:**
- Create: `lib/hooks/use-dialog.ts`
- Create: `lib/hooks/use-pagination.ts`
- Create: `lib/hooks/use-query-params.ts`
- Create: `lib/hooks/use-confirm.ts`

- [ ] **2a: useDialog**

```typescript
import { useCallback, useState } from "react";

export interface DialogControl {
  open: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  toggleDialog: () => void;
}

export const useDialog = (initial = false): DialogControl => {
  const [open, setOpen] = useState(initial);
  const openDialog = useCallback(() => setOpen(true), []);
  const closeDialog = useCallback(() => setOpen(false), []);
  const toggleDialog = useCallback(() => setOpen((prev) => !prev), []);
  return { open, openDialog, closeDialog, toggleDialog };
};
```

- [ ] **2b: usePagination**

```typescript
import { useMemo, useState } from "react";

export interface PaginationControl {
  page: number;
  setPage: (n: number) => void;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export const usePagination = (total: number, pageSize = 20): PaginationControl => {
  const [page, setPage] = useState(1);
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
  return { page, setPage, totalPages, hasNext: page < totalPages, hasPrev: page > 1 };
};
```

- [ ] **2c: useQueryParams**

```typescript
import { useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";

export const useQueryParams = (defaults?: Record<string, string>) => {
  const searchParams = useSearchParams();
  const params = useMemo(() => {
    const result: Record<string, string> = { ...defaults };
    for (const [key, value] of searchParams.entries()) {
      result[key] = value;
    }
    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const setParam = useCallback(
    (key: string, value: string) => {
      const newParams = new URLSearchParams(searchParams.toString());
      newParams.set(key, value);
      window.history.replaceState(null, "", `?${newParams.toString()}`);
    },
    [searchParams],
  );

  return { params, setParam };
};
```

- [ ] **2d: useConfirm**

```typescript
import { useCallback, useState } from "react";

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
  const confirm = useCallback(() => setOpen(true), []);
  const handleConfirm = useCallback(async () => {
    await onConfirm();
    setOpen(false);
  }, [onConfirm]);
  return { confirm, confirmProps: { open, onConfirm: handleConfirm, onOpenChange: setOpen } };
};
```

- [ ] **2e: 替换消费者**

```bash
# 替换手写 useState(false) + toggle → react-use useToggle
grep -rn "const \[.*setOpen\] = useState(false)" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test | head -20
```

每处改为:
```typescript
import { useToggle } from "react-use";
const [open, toggle] = useToggle(false);
```

- [ ] **2f: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
```

- [ ] **2g: Commit**

```bash
git add packages/web/lib/hooks/
git commit -m "refactor(P2): 提取 4 个通用 hooks + react-use 替换手写 useState pattern"
```

---

### Phase 3: 提取通用组件

**Files:**
- Create: `components/common/page-header.tsx`
- Create: `components/common/loading-skeleton.tsx`
- Create: `components/common/confirm-dialog.tsx`
- Create: `components/common/section-card.tsx`
- Create: `components/common/search-input.tsx`
- Create: `components/common/status-badge.tsx`
- Modify: 各处替换 (约 30 文件)

- [ ] **3a: PageHeader**

```typescript
// components/common/page-header.tsx
"use client";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
import type { ReactNode } from "react";

interface PageHeaderProps {
  backHref: string;
  title: string;
  actions?: ReactNode;
}

export const PageHeader = ({ backHref, title, actions }: PageHeaderProps) => {
  const router = useRouter();
  return (
    <div className="mb-6 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Button onClick={() => router.push(backHref)} size="sm" variant="ghost">
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回
        </Button>
        <h1 className="text-xl font-semibold">{title}</h1>
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
};
```

- [ ] **3b: LoadingSkeleton**

```typescript
// components/common/loading-skeleton.tsx
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
}

export const LoadingSkeleton = ({ rows = 3, className }: LoadingSkeletonProps) => (
  <div className={cn("space-y-6 p-6", className)}>
    {Array.from({ length: rows }).map((_, idx) => (
      <Skeleton key={idx} className={idx === 0 ? "h-8 w-48" : "h-4 w-full"} />
    ))}
  </div>
);
```

- [ ] **3c: ConfirmDialog**

```typescript
// components/common/confirm-dialog.tsx
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (val: boolean) => void;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  variant?: "default" | "destructive";
  loading?: boolean;
}

export const ConfirmDialog = ({
  open, onOpenChange, title, description,
  confirmText = "确认", cancelText = "取消",
  onConfirm, variant = "default", loading = false,
}: ConfirmDialogProps) => (
  <AppDialog
    open={open}
    onOpenChange={onOpenChange}
    title={title}
    description={description}
    footer={
      <div className="flex justify-end gap-2">
        <Button disabled={loading} onClick={() => onOpenChange(false)} variant="outline">
          {cancelText}
        </Button>
        <Button disabled={loading} onClick={onConfirm} variant={variant === "destructive" ? "destructive" : "default"}>
          {loading ? "..." : confirmText}
        </Button>
      </div>
    }
  >
    {description && <p className="text-sm text-muted-foreground">{description}</p>}
  </AppDialog>
);
```

- [ ] **3d: SectionCard**

```typescript
// components/common/section-card.tsx
import type { ReactNode } from "react";

interface SectionCardProps {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}

export const SectionCard = ({ title, description, children, actions }: SectionCardProps) => (
  <div className="rounded-lg border p-6">
    <div className="mb-4 flex items-start justify-between">
      <div>
        <h2 className="text-lg font-medium">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
    {children}
  </div>
);
```

- [ ] **3e: SearchInput**

```typescript
// components/common/search-input.tsx
"use client";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { debounce } from "es-toolkit";
import { useEffect, useMemo, useState } from "react";

interface SearchInputProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

export const SearchInput = ({
  value, onChange, placeholder = "搜索...", debounceMs = 300,
}: SearchInputProps) => {
  const [local, setLocal] = useState(value);
  const debouncedOnChange = useMemo(() => debounce(onChange, debounceMs), [onChange, debounceMs]);

  useEffect(() => {
    debouncedOnChange(local);
    return () => debouncedOnChange.cancel();
  }, [local]);

  useEffect(() => { setLocal(value); }, [value]);

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="pl-10"
        placeholder={placeholder}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
      />
    </div>
  );
};
```

- [ ] **3f: StatusBadge**

```typescript
// components/common/status-badge.tsx
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusType = "pending" | "running" | "completed" | "failed" | "cancelled" | "active" | "archived";

const STATUS_COLORS: Record<StatusType, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
  active: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-800",
};

interface StatusBadgeProps {
  status: StatusType;
  customLabels?: Partial<Record<StatusType, string>>;
}

export const StatusBadge = ({ status, customLabels }: StatusBadgeProps) => (
  <Badge className={cn("font-medium", STATUS_COLORS[status])} variant="outline">
    {customLabels?.[status] ?? status}
  </Badge>
);
```

- [ ] **3g: 替换消费者 — 用 DataEmpty 替换手写空态**

```bash
# 扫描手写空态
grep -rn "暂无数据\|暂无内容\|空列表\|empty" app/ components/ --include="*.tsx" | grep -v node_modules\|\.test | head -15
```

对每处手写空态，改为：
```typescript
import { DataEmpty } from "@/components/common/data-empty";
// 改前
<div className="py-8 text-center text-sm text-muted-foreground">暂无数据</div>
// 改后
<DataEmpty title="暂无数据" />
```

- [ ] **3h: 替换 PageHeader — 各处返回按钮 + 标题**

替换 `app/[locale]/buyers/[id]/page.tsx` 等文件中的：
```typescript
// 改前
<Button onClick={() => router.push("/buyers")} size="sm" variant="ghost">
  <ArrowLeft className="mr-1 h-4 w-4" />
  {t("返回")}
</Button>
// 改后
<PageHeader backHref="/buyers" title={t("买家详情")} />
```

- [ ] **3i: 替换 LoadingSkeleton**

替换 `app/[locale]/buyers/[id]/page.tsx` 等文件中的：
```typescript
// 改前
<div className="space-y-6 p-6">
  <Skeleton className="mb-4 h-8 w-48" />
  <Skeleton className="h-64 w-full" />
</div>
// 改后
<LoadingSkeleton />
```

- [ ] **3j: 替换 StatusBadge — 各处 status 条件渲染**

替换各文件中手写的 status→Badge 条件逻辑：
```typescript
// 改前
<Badge className={status === "completed" ? "bg-green-100" : status === "failed" ? "bg-red-100" : "..."}>{status}</Badge>
// 改后
<StatusBadge status={status as StatusType} />
```

- [ ] **3k: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
```

- [ ] **3l: Commit**

```bash
git add packages/web/components/common/
git commit -m "refactor(P3): 提取 6 个通用组件 + DataEmpty 替换手写空态"
```

---

### Phase 4: 大组件拆分

**Files:**
- Modify: `components/chat/chat-shell.tsx` (727 行)
- Create: `components/chat/chat-messages.tsx`
- Create: `components/chat/chat-input.tsx`
- Create: `components/chat/chat-header.tsx`
- Create: `lib/chat/use-chat-state.ts`
- Modify: `app/[locale]/admin/users/_components/admin-users-table.tsx` (539 行)
- Create: `app/[locale]/admin/users/_components/user-filters.tsx`
- Create: `app/[locale]/admin/users/_components/user-actions.tsx`
- Create: `app/[locale]/admin/users/_hooks/use-user-table.ts`
- Modify: `app/[locale]/knowledge/triples/_components/triples-form.tsx` (444 行)
- Create: `app/[locale]/knowledge/triples/_components/triple-row.tsx`
- Create: `app/[locale]/knowledge/triples/_hooks/use-triple-form.ts`
- Modify: `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` (437 行)
- Modify: `app/[locale]/admin/permissions/_components/permissions-table.tsx` (400 行)
- Modify: `app/[locale]/output/_components/output-list-client.tsx` (366 行)

- [ ] **4a: chat-shell 拆分 — 提取 useChatState**

```typescript
// lib/chat/use-chat-state.ts — 提取全部 useState + 消息流逻辑
export const useChatState = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  // ... 迁移 chat-shell.tsx 中所有状态 + handler 逻辑
};
```

- [ ] **4b: chat-shell 拆分 — 提取 ChatMessages**

```typescript
// components/chat/chat-messages.tsx — 消息列表渲染
interface ChatMessagesProps {
  messages: Message[];
  isLoading: boolean;
  onFeedback: (msgId: string, rating: number) => void;
}
```

- [ ] **4c: chat-shell 拆分 — 提取 ChatInput**

```typescript
// components/chat/chat-input.tsx — 输入区域
interface ChatInputProps {
  onSend: (text: string, files?: ChatFile[]) => void;
  disabled: boolean;
}
```

- [ ] **4d: admin-users-table 拆分 — 提取 useUserTable + UserFilters**

```typescript
// app/[locale]/admin/users/_hooks/use-user-table.ts
export const useUserTable = () => {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  // ... useQuery + pagination + operations
};
```

- [ ] **4e: 其余 4 个大组件按同样模式拆分 → hooks + smaller components**

每个大组件拆分的通用模式：
1. 提取全部 useState/useEffect/handler 到 `_hooks/use-xxx.ts`
2. 每块独立 UI 区域 → 独立组件文件
3. 主文件只做编排（import hook + 组合子组件）

- [ ] **4f: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
```

- [ ] **4g: Commit**

```bash
git add packages/web/
git commit -m "refactor(P4): 拆分 6 个大组件 (chat-shell/admin-users-table/triples-form/task-detail/permissions-table/output-list)"
```

---

### Phase 5: RSC/RSF 拆分

- [ ] **5a: 逐页检查 23 个 RSC 候选页面**

```bash
cd packages/web

# 列出所有无 "use client" 的 page.tsx
for f in $(find app -name "page.tsx" ! -path "*/node_modules/*" ! -path "*/.next/*"); do
  if ! grep -q '"use client"' "$f" 2>/dev/null; then
    echo "$f"
    # 检查 import 链中是否有 "use client" 组件
    grep "import.*from.*@/" "$f" | head -5
  fi
done
```

逐页判定：
- 纯 data-fetching + 传 props 给 client 组件 → 保持 RSC ✅
- 有 useEffect/useState 交互 → 拆为 RSC wrapper + Client Component

- [ ] **5b: 将有 `"use client"` 但实际可 server 渲染的页面降级**

```bash
# 扫描 "use client" 页面中实际只做 data-fetching + 渲染的
for f in $(grep -rl '"use client"' app/ --include="*.tsx" | grep -v node_modules\|\.test\|\.next); do
  uses=$(grep -c "useState\|useEffect\|useCallback\|useMemo\|onClick\|onSubmit" "$f" 2>/dev/null)
  if [ "$uses" -eq 0 ]; then
    echo "$f — 可移出 use client"
  fi
done
```

对可降级的页面：删除 `"use client"` 行，验证没有客户端 hook 使用。

- [ ] **5c: 提取 RSF — 通用 Server Functions**

```typescript
// lib/actions/server-profile.ts
"use server";
import { apiFetch } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

export const getServerProfile = async () => {
  return apiFetch("/api/account/me", { headers: await serverAuthHeaders() });
};
```

- [ ] **5d: 替换 RSC 页面中的 apiFetch + serverAuthHeaders → RSF**

```typescript
// 改前 (page.tsx)
const me = await apiFetch<MeResponse>("/api/account/me", { headers: await serverAuthHeaders() });
// 改后
import { getServerProfile } from "@/lib/actions/server-profile";
const me = await getServerProfile();
```

- [ ] **5e: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
```

- [ ] **5f: Commit**

```bash
git add packages/web/
git commit -m "refactor(P5): RSC/RSF 拆分 + server function 提取"
```

---

### Phase 6: Zustand 状态收敛

**Files:**
- Create: `lib/store/ui-store.ts`
- Create: `lib/store/chat-store.ts`
- Modify: 各消费者文件 (~10)

- [ ] **6a: 创建 useUIStore**

```typescript
// lib/store/ui-store.ts
import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  setSidebarOpen: (val: boolean) => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  setSidebarOpen: (val) => set({ sidebarOpen: val }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
```

- [ ] **6b: 创建 useChatStore — 替代 chat-shell 中 8 个 useState**

```typescript
// lib/store/chat-store.ts
import { create } from "zustand";
import type { Conversation, Message } from "@/lib/chat/types";

interface ChatState {
  conversations: Conversation[];
  currentConvId: string | null;
  messages: Message[];
  isSending: boolean;
  // actions
  setConversations: (convs: Conversation[]) => void;
  setCurrentConvId: (id: string | null) => void;
  setMessages: (msgs: Message[]) => void;
  appendMessage: (msg: Message) => void;
  setIsSending: (val: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  currentConvId: null,
  messages: [],
  isSending: false,
  setConversations: (conversations) => set({ conversations }),
  setCurrentConvId: (currentConvId) => set({ currentConvId }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  setIsSending: (isSending) => set({ isSending }),
}));
```

- [ ] **6c: 替换 chat-shell 中的 useState → useChatStore**

```typescript
// 改前
const [messages, setMessages] = useState<Message[]>([]);
const [isSending, setIsSending] = useState(false);
// 改后
const { messages, setMessages, isSending, setIsSending } = useChatStore();
```

- [ ] **6d: 替换跨组件共享的 UI 状态 → useUIStore**

将 header/sidebar/main layout 中通过 props 透传的 sidebar open 状态改为 zustand store。

- [ ] **6e: 验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
```

- [ ] **6f: Commit**

```bash
git add packages/web/lib/store/
git commit -m "refactor(P6): Zustand 状态收敛 (useUIStore + useChatStore)"
```

---

### Phase 7: 最终验证

- [ ] **7a: 安装 jscpd + 基准对比**

```bash
cd packages/web && bun add -D jscpd
bun x jscpd --threshold 5 --pattern "**/*.{ts,tsx}" --ignore "**/*.test.*,**/*.spec.*,**/node_modules/**,**/.next/**"
```

- [ ] **7b: 全量验证**

```bash
cd packages/web
bun x tsc -b --noEmit
bun x vitest run
bun x oxlint . --deny-warnings
bun run format:check
```

- [ ] **7c: 全量测试**

```bash
cd packages/web && bun run test
# Expected: 0 failed (允许 pre-existing)
```

- [ ] **7d: Final commit**

```bash
git add -A && git commit -m "chore(P7): 最终验证 + 重复率 baseline 更新"
```

---

## 执行提示

- **每个 sub-step 后** 都跑 `tsc + vitest + oxlint`（不是完成整个 Phase 后才跑）
- **Phase 间依赖**：P2 → P3 → P4 顺序不可逆（hooks 先于组件，组件先于拆分）
- **大文件拆分**：P4 的 chat-shell 是最高风险项，可以先做 admin-users-table 练手
- **导出命名统一**：hooks 用 `useXxx` 命名，组件用 `PascalCase`，store 用 `useXxxStore`
