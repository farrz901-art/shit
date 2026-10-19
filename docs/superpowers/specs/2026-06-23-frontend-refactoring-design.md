# 前端代码重构设计方案

> **日期:** 2026-06-23
> **范围:** packages/web 全量前端重构 (311 文件)
> **目标:** 降低结构模式重复率 (当前 jscpd token 2.03%, 但模式重复远高于此), 消除冗余 useMemo/useCallback, 提取通用 hooks/components, 拆分大组件, RSC 收敛, Zustand 状态降维

---

## 1. 当前状态

| 指标 | 值 |
|------|----|
| TS/TSX 文件 | 311 |
| 组件文件 | 100 |
| 页面文件 (page.tsx) | 37 |
| 自定义 Hook | 3 (use-lookup, use-permissions, use-theme) |
| Zustand Store | 2 (app-store, usePermissionsStore) |
| useMemo/useCallback | 37 处 |
| "use client" 页面 | 75 |
| 无 "use client" 页面 | 23 (RSC 候选) |
| 大文件 (>300 行) | 13 |
| es-toolkit | 已安装但零使用 |
| 测试覆盖率 | ~67% lines (baseline: 2026-06-19) |
| 工具链 | tsc 0 error / oxlint --deny-warnings 0 error / vitest pass |

---

## 2. 执行顺序（7 Phase 顺序依赖）

```
Phase 1: es-toolkit + 清理 useMemo/useCallback
    ↓
Phase 2: 提取通用 Hooks (6 个)
    ↓
Phase 3: 提取通用组件 (6 个)
    ↓
Phase 4: 大组件拆分 (6 个)
    ↓
Phase 5: RSC / RSF 拆分
    ↓
Phase 6: Zustand 状态收敛
    ↓
Phase 7: 最终验证 (重复率 + 全量测试)
```

**每个 Phase 必须通过：** `tsc --noEmit 0 error && vitest run 0 new fail && oxlint --deny-warnings 0 error`

---

## 3. Phase 1: react-use 优先 + es-toolkit 辅助 + useMemo/useCallback 清理

### 3.1 工具选择策略

**优先使用 react-use** (已装 v17.6.1)：
| 模式 | react-use 替代 | 预期出现次数 |
|------|---------------|------------|
| `useState(false) + toggle` | `useToggle(initial)` | 15+ 处 |
| `useEffect + loading + data + error` 三板斧 | `useAsync(fn, deps)` / `useAsyncFn(fn, deps)` | 10+ 处 |
| 防抖输入 | `useDebounce(value, ms)` | 4+ 处 |

**react-use 做不了的才用 es-toolkit** (已装)：
| 模式 | es-toolkit | 预期出现次数 |
|------|-----------|------------|
| 数组去重 | `uniq()` / `uniqBy()` | ~5 处 |
| 分组 | `groupBy()` | ~3 处 |
| 排序 | `sortBy()` | ~5 处 |
| 对象操作 | `pick()` / `omit()` / `mapValues()` | ~8 处 |
| 链式操作 | `pipe()` | ~3 处 |
| 延迟 | `delay()` | ~3 处 |
| 数字工具 | `clamp()` / `sum()` / `range()` | ~5 处 |

**策略**: 按需渐进，先替换最高频模式。hooks 用 react-use，工具函数用 es-toolkit。

### 3.2 useMemo/useCallback 清理规则

| 判定 | 标准 | 操作 |
|------|------|------|
| 🔴 可删 | 入参为原始类型 (string/number/boolean)，无引用依赖价值 | 提为普通函数或变量 |
| 🟡 可简 | `useCallback(fn, [])` 包了一个纯函数，子组件无 React.memo | 提为组件外 `const fn` |
| 🟢 保留 | 作为 useEffect 依赖/React.memo 子组件 props | 保持不动 |

**预期**: 37 处中约 20-25 处可删/可简

---

## 4. Phase 2: 提取通用 Hooks

基于项目中重复出现的手写状态管理模式。**优先用 react-use 已有的 hook**（`useToggle`, `useAsync`/`useAsyncFn` 不自己写），**只提取 react-use 没有的**：

### 4.1 useDialog

```typescript
// 替代: 8+ 处 AppDialog + open/close 状态组合
// 返回: { open, openDialog, closeDialog, toggleDialog }
function useDialog(initial = false): DialogControl
```

### 4.2 usePagination

```typescript
// 替代: 重复的 page/size/total/totalPages 计算 + hasPrev/hasNext
// 5 处
function usePagination(total: number, pageSize?: number): { page: number; setPage: (n: number) => void; totalPages: number; hasNext: boolean; hasPrev: boolean }
```

### 4.3 useQueryParams

```typescript
// 替代: 手写 URLSearchParams + new URL() 拼 query 参数
// 5 处
function useQueryParams(defaults?: Record<string, string>): { params: Record<string, string>; setParam: (k: string, v: string) => void }
```

### 4.4 useConfirm

```typescript
// 替代: 5+ 处 AppConfirm + open 状态 + onConfirm handler 组合
function useConfirm(onConfirm: () => Promise<void> | void): { confirm: () => void; confirmProps: { open: boolean; onConfirm: () => void; onOpenChange: (o: boolean) => void } }
```

**提取位置**: `lib/hooks/use-dialog.ts`, `lib/hooks/use-pagination.ts`, `lib/hooks/use-query-params.ts`, `lib/hooks/use-confirm.ts`

**使用 react-use 的 hook（不自己写）:**
- `useToggle` → `import { useToggle } from "react-use";`
- `useAsync` / `useAsyncFn` → `import { useAsync } from "react-use";`

---

## 5. Phase 3: 提取通用组件

基于 shadcn 原语 + 已有封装（AppDialog/AppConfirm/DataEmpty/ErrorBanner 等）构建，不引入新依赖。

### 5.1 PageHeader

```tsx
// 依赖: Button + ArrowLeft from lucide-react
// 替换 12+ 处 pattern: <Button onClick={() => router.push(href)}><ArrowLeft />{t("返回")}</Button> + <h1>title</h1>
interface PageHeaderProps {
  backHref: string;
  title: string;
  actions?: ReactNode;
}
```

### 5.2 LoadingSkeleton

```tsx
// 依赖: Skeleton + cn() 
// 替换 10+ 处 pattern: <div className="space-y-6 p-6"><Skeleton className="h-8 w-48" />...</div>
interface LoadingSkeletonProps {
  rows?: number;      // 骨架行数
  className?: string; // 额外容器类
}
```

### 5.3 ConfirmDialog

```tsx
// 依赖: AppDialog + Button
// 替换 7+ 处: <AppDialog><Button onClick={confirm}>{t("确认")}</Button><Button onClick={cancel}>{t("取消")}</Button></AppDialog>
interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  variant?: "default" | "destructive";
  loading?: boolean;
}
```

### 5.4 SectionCard

```tsx
// 依赖: Card from shadcn
// 替换 8+ 处: <div className="rounded-lg border p-6"><h2>title</h2>children</div>
interface SectionCardProps {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;  // 右上角操作区域
}
```

### 5.5 SearchInput

```tsx
// 依赖: Input + Search from lucide-react + useDebounce (es-toolkit debounce)
// 替换 4+ 处: 带防抖的搜索框
interface SearchInputProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  debounceMs?: number;     // 默认 300
}
```

### 5.6 StatusBadge

```tsx
// 依赖: Badge from shadcn + cn()
// 替换 5+ 处: status→颜色条件渲染
type StatusType = "pending" | "running" | "completed" | "failed" | "cancelled" | "active" | "archived";

interface StatusBadgeProps {
  status: StatusType;
  customLabels?: Record<StatusType, string>;
}
```

### 5.7 DataEmpty 替换

项目中已经用了 `DataEmpty` 组件，但仍有手写空态，用 `DataEmpty` 统一替换。

---

## 6. Phase 4: 大组件拆分

### 6.1 chat-shell.tsx (727 行)

**现状**: 8 个 useState + 内联多条逻辑 (消息流/对话管理/附件/反馈/录音)
**拆为**:
- `components/chat/chat-shell.tsx` → 仅编排
- `components/chat/chat-messages.tsx` → 消息列表渲染
- `components/chat/chat-input.tsx` → 输入区域
- `components/chat/chat-header.tsx` → 头部操作
- `lib/chat/use-chat-state.ts` → 消息流 + 对话管理逻辑

### 6.2 admin-users-table.tsx (539 行)

**拆为**:
- `_components/admin-users-table.tsx` → 精简表格
- `_components/user-filters.tsx` → 搜索/过滤栏
- `_components/user-actions.tsx` → 操作列 (重置密码/封禁/删除)
- `_hooks/use-user-table.ts` → 列表 + 分页 + 操作逻辑

### 6.3 triples-form.tsx (444 行)

**拆为**:
- `_components/triples-form.tsx` → 表单编排
- `_components/triple-row.tsx` → 单行输入
- `_hooks/use-triple-form.ts` → 表单状态管理

### 6.4 task-detail-client.tsx (437 行)

**拆为**:
- TaskInfo → 任务基本信息
- TaskFiles → 文件列表
- TaskDownload → 下载区域

### 6.5 permissions-table.tsx (400 行)

**拆为**:
- PermissionRow → 单行渲染
- PermissionFilters → 过滤

### 6.6 output-list-client.tsx (366 行)

**拆为**:
- `useOutputList` hook
- OutputCard → 单个任务卡片

---

## 7. Phase 5: RSC/RSF 拆分

### 7.1 当前 23 个 RSC 候选页面

逐页检查 import 链，按 3 类处理：

| 类别 | 判定 | 操作 |
|------|------|------|
| 纯 data-fetching | 无 `useState`/`useEffect`/事件处理器 | 保持 RSC ✅ |
| 有 client 交互 | 页面本身交互简单，但含 client 子组件 | RSC wrapper + Client Component |
| 需迁移 | 当前用了 `"use client"` 但实际可改为 server | 去掉 `"use client"`，将交互部分下沉 |

### 7.2 RSF (React Server Functions)

提取通用 server action 模式 `serverAuthHeaders() + apiFetch()` 到 `lib/actions/` 目录：

```typescript
// lib/actions/profile.ts (server-only)
"use server";
export async function getServerProfile() {
  return apiFetch("/api/account/me", { headers: await serverAuthHeaders() });
}
```

---

## 8. Phase 6: Zustand 状态收敛

### 8.1 现有 Store

- `lib/store/app-store.ts` → `useAppStore` (已存在)
- `lib/hooks/use-permissions.ts` → `usePermissionsStore` (已存在)

### 8.2 新增 Store

| Store | 状态 | 替代目标 |
|-------|------|---------|
| `useUIStore` | sidebarOpen, activeTab, locale | 跨页面共享 UI 状态 |
| `useChatStore` | conversations, currentConvId | chat-shell 内的 8 个 useState 降维 |

### 8.3 不动

- 表单临时状态 (每个表单自己的 loading/error/submitting)
- 纯组件内 UI 开关 (菜单打开等)

---

## 9. Phase 7: 最终验证

### 9.1 重复率工具

```bash
# 安装 jscpd
cd packages/web && bun add -D jscpd
# 扫描
bun x jscpd --threshold 5 --pattern "**/*.{ts,tsx}" --ignore "**/*.test.*,**/*.spec.*,**/node_modules/**"
```

**目标**: 结构模式重复率显著降低（jscpd baseline: 2.03% token）

### 9.2 全量验证

```bash
cd packages/web
bun x tsc -b --noEmit      # 0 error
bun x vitest run            # 0 new fail (允许 pre-existing)
bun x oxlint . --deny-warnings  # 0 warning
bun run format:check        # 0 format issue
```

---

## 10. 执行统计

| Phase | 预计文件数 | 主要风险 |
|-------|-----------|---------|
| P1: es-toolkit + cleanup | ~30 | useMemo/useCallback 误判 |
| P2: Hooks | 6 新建 + ~20 消费者 | Hook API 设计不合理需回头改 |
| P3: Components | 6 新建 + ~30 替换 | 与现有组件边界划分 |
| P4: 大组件拆分 | ~20 | chat-shell 拆后回归测试 |
| P5: RSC/RSF | ~25 | client→server 导致缺失浏览器 API |
| P6: Zustand | 2 新建 + ~10 替换 | 状态设计粒度 |
| P7: Verify | — | jscpd 阈值可能需要调整 |

## 11. 不做的

- 不改 UI 样式/表现只重构代码结构
- 不改功能逻辑
- 不引入新依赖（es-toolkit 已装）
- 不修改测试文件（除非 import 路径变了）
