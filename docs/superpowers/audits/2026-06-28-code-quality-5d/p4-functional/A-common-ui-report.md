# P4 维度 ④ 函数式写法审计 — Agent A (common + ui)

## 扫描概览

- **总扫描文件**: 50 (common/) + 36 (ui/) = **86** (排除 .test/.stories/.index.ts)
- **不纯函数数**: 3 处真实副作用 (CopyButton `navigator.clipboard`+`setTimeout`, HealthDot `fetchDifyHealth`+`setInterval`, BackLink `router.back`+`globalThis.history`)
- **if/else 链可改对象 dispatch 数**: 8 处 (DataTableBody 分支状态, DataTablePagination prev/next 边界, AppField error/help 渲染, CopyButton label 切换, ErrorBoundary 错误 fallback, AppDropdownMenu item 模式, PaginationLink active, calendar captionLayout)
- **es-toolkit 实际使用**: **0 处** (common/ui/, 全项目仅 `lib/chat/migration.ts:10` 1 处)
- **🔴 高 ROI**: **2**
- **🟡 中 ROI**: **5**
- **🟢 低 ROI**: **6**
- **❌ 不建议**: **9** (含 shadcn/ui/* 整目录禁止改 36 文件)

## 关键结论 (TL;DR)

1. **`components/ui/*` 全部禁止改**: 是 shadcn 原语, `package.json` shadcn cli 重新生成会覆盖 (按 [packages/web/CLAUDE.md §封装组件](packages/web/CLAUDE.md) 规范, 业务代码也不应直拼). 全部归 ❌.
2. **`components/common/*` 已大量使用对象 dispatch 模式**: `STATUS_COLORS`、`COLOR_MAP`、`SIZE_MAP`、`VARIANT_BAR`、`COL_CLASS_BY_KEY`、`maxWidthClass` 等都是 record lookup. 多数"看起来像 if 链"的代码其实是已有 dispatch 表.
3. **可挑出的真 FP 机会很少**: 大部分组件已经把 if 拆成 lookup; 剩余几个真分支是 React 渲染分支 (loading/empty/data 三态), 走对象 dispatch 会让 JSX 嵌套更深, **拆完反而难读**.
4. **2 个 🔴 高 ROI** 都集中在数据变换 (es-toolkit `range`/`attempt`), 跟 P3 `applyEvent` 的 dispatch 重写同思路, 但收益更小 (每个仅 1-3 行).
5. **副作用 (fetch/setTimeout/setInterval/navigator.clipboard)** 都不可纯化, 因为调用方就是用户事件 (`onClick`/`useQuery`/`setInterval`), 抽 hook 反而增加文件数.

---

## 🔴 高 ROI (建议重写)

### A.1 [components/common/button/app-loading-skeleton.tsx:17 + table/data-table-skeleton.tsx:18,23,25] — `Array.from({length}).map` 改 `range`

**现状** (2 文件, 4 处):
```tsx
// app-loading-skeleton.tsx:17
{Array.from({ length: rows }).map((_val, idx) => (
  <Skeleton key={idx} className={idx === HEADER_ROW_INDEX ? "..." : "..."} />
))}

// data-table-skeleton.tsx:18,23,25
{Array.from({ length: columns }).map((_unused, index) => (
  <Skeleton key={index} className="h-10 flex-1" />
))}
{Array.from({ length: rows }).map((_unused, rowIndex) => (
  <div key={rowIndex} className="flex gap-2">
    {Array.from({ length: columns }).map((_ignored, colIndex) => (
      <Skeleton key={colIndex} className="h-12 flex-1" />
    ))}
  </div>
))}
```

**改法** (es-toolkit 提供 `range(start, end)`):
```tsx
import { range } from "es-toolkit";

// app-loading-skeleton.tsx
{range(rows).map((idx) => (
  <Skeleton key={idx} className={idx === HEADER_ROW_INDEX ? "..." : "..."} />
))}

// data-table-skeleton.tsx
{range(columns).map((index) => <Skeleton key={index} className="h-10 flex-1" />)}
{range(rows).map((rowIndex) => (
  <div key={rowIndex} className="flex gap-2">
    {range(columns).map((colIndex) => <Skeleton key={colIndex} className="h-12 flex-1" />)}
  </div>
))}
```

**收益**: 净省 ~10 行 (每处省 1 行, 4 处). 一致性: 全项目 es-toolkit 出现从 1 处升到 2-5 处, 跟 `lib/chat/migration.ts` `groupBy` 形成小组规模化.

**风险**: 低. es-toolkit `range(n)` 返回 `[0,1,...,n-1]`, 跟 `Array.from({length: n}).map((_,i)=>i)` 行为完全等价; `key={index}` 索引稳定无副作用.

---

### A.2 [components/common/button/app-copy-button.tsx:43-49] — `try-catch` + Error 类型归一化 改 `attempt`

**现状** (CopyButton 复制失败错误归一化):
```tsx
try {
  await navigator.clipboard.writeText(text);
  setCopied(true);
  onCopied?.();
  setTimeout(() => setCopied(false), COPIED_RESET_MS);
} catch (error) {
  let message = "复制失败";
  if (error instanceof Error) {
    const { message: errMessage } = error;
    message = errMessage;
  }
  toast.error(message);
}
```

**改法** (es-toolkit 提供 `attempt`/`attemptAsync` + `isError`):
```tsx
import { isError } from "es-toolkit";

const [err] = attempt(() => navigator.clipboard.writeText(text));
// ↑ 不行: 这是同步版, 不接 await. 复制是 async, 走 attemptAsync 或保留 try
```

**重新评估**: `attempt` 接 async fn 时返回 `Promise<[Error, undefined] | [undefined, T]>`. 但这里错误**必须** toast.error 走副作用, 不能再缩成三元. 改完是:
```tsx
const [writeErr] = await attemptAsync(() => navigator.clipboard.writeText(text));
if (writeErr) {
  toast.error(isError(writeErr) ? writeErr.message : "复制失败");
  return;
}
setCopied(true);
onCopied?.();
setTimeout(() => setCopied(false), COPIED_RESET_MS);
```

**净省**: ~4 行 (5 → 1 if/instanceof 链 + 1 行 toast). 一致性: 跟 `attemptAsync` + `isError` 组合成 idiom.

**风险**: 低-中. 改完代码确实短, 但 `attempt` 返回 `[err, result]` 数组解构对不熟悉 es-toolkit 的同事是 noise; 当前 `try/catch` 是 ECMA 标准, oxlint 没警告. 项目里没其它 `attempt` 用法做示范.

**结论**: 🔴 高 ROI 但**不**改. 因为:
- 同行 reviewer 看到 `const [err] = await attemptAsync(...)` 要去查 es-toolkit API, 反而增 load
- 节省的 4 行少于阅读增加成本
- 全项目 `attempt` 用例 0 处, 不形成 pattern

**改为 🟡 中 ROI** — 见 A.7.

---

## 🟡 中 ROI (可选)

### A.3 [components/common/table/data-table-body.tsx:125-132] — loading/empty/data 三态可改 dispatch

**现状** (顶层 React 渲染分支):
```tsx
export const DataTableBody = <TData,>({...}: DataTableBodyProps<TData>): ReactNode => {
  if (loading) {
    return <>{renderLoadingRow(columns.length)}</>;
  }
  const { rows } = table.getRowModel();
  if (rows.length > ZERO) {
    return <>{renderDataRows({ columns, table, expandedRowRender, onRowClick, rowClassName })}</>;
  }
  return <>{renderEmptyRow(columns.length, emptyText)}</>;
};
```

**改法候选**: 改 `cond([[loading, renderLoadingRow], [hasRows, renderDataRows], [_, renderEmptyRow]])` — 但项目**没装 `cond`** (es-toolkit 提供 `cond`, 但需 `import { cond } from "es-toolkit/function"`).

**实际净评估**: 改完是:
```tsx
import { cond } from "es-toolkit/function";

const stateMap = cond<[DataTableBodyProps<TData>, ReactNode]>([
  [(p) => p.loading, (p) => <>{renderLoadingRow(p.columns.length)}</>],
  [(p) => p.table.getRowModel().rows.length > ZERO, (p) => <>{renderDataRows({...p})}</>],
  [() => true, (p) => <>{renderEmptyRow(p.columns.length, p.emptyText)}</>],
]);
return <>{stateMap(props)}</>;
```

**对比**:
- 现版 8 行清晰 (loading→return, data→return, empty→return), 读起来像 state machine
- 改完 8 行 (含 import), 多了 `cond` indirection, 需要查 es-toolkit 文档

**净省**: 0 行. **可读性下降**. 

**结论**: 🟡 中 ROI 但**不**改. 当前 if 链已经是项目规约 (oxlint `no-nested-ternary` 强制用 if/else), 跟 dispatch 同义.

---

### A.4 [components/common/table/data-table-pagination.tsx:46-65] — handlePrev/handleNext 双胞胎可抽 1 个 step 函数

**现状**:
```tsx
const handlePrev = () => {
  if (current === ONE) return;
  if (onPageChange) {
    onPageChange(Math.max(ONE, current - PAGE_STEP));
  } else {
    table.previousPage();
  }
};
const handleNext = () => {
  if (current >= totalPages) return;
  if (onPageChange) {
    onPageChange(Math.min(totalPages, current + PAGE_STEP));
  } else {
    table.nextPage();
  }
};
```

**改法** (curry/partial, es-toolkit `clamp`):
```tsx
import { clamp } from "es-toolkit";

const step = (delta: number) => () => {
  const next = clamp(current + delta, ONE, totalPages);
  if (next === current) return;
  if (onPageChange) onPageChange(next);
  else delta > ZERO ? table.nextPage() : table.previousPage();
};
const handlePrev = step(-PAGE_STEP);
const handleNext = step(PAGE_STEP);
```

**净省**: ~5 行. 一致性: `clamp` 是 es-toolkit `math` 模块, 跟项目 `import { ONE, ZERO } from "@/const"` 已用 clamp 等价但更声明式.

**风险**: 低. `clamp(n, min, max)` 跟 `Math.max(ONE, current - PAGE_STEP)` + `Math.min(totalPages, current + PAGE_STEP)` 完全等价.

**结论**: 🟡 中 ROI. 改完更声明式, 但 5 行净省少于阅读 es-toolkit `clamp` 的成本; **可选**.

---

### A.5 [components/common/table/data-table-pagination.tsx:25-31] — `buildButtonClass` 可省, 直接 lookup

**现状**:
```tsx
const buildButtonClass = (current: number, totalPages: number): { next: string; prev: string } => {
  const isFirstPage = current === ONE;
  const isLastPage = current >= totalPages;
  const prevClass = isFirstPage ? DISABLED_OPACITY : CURSOR_POINTER;
  const nextClass = isLastPage ? DISABLED_OPACITY : CURSOR_POINTER;
  return { next: nextClass, prev: prevClass };
};
```

**改法**: 纯函数化时, 改 2 个独立 lookup 函数 (helper), 或合并成 1 个 `clamp`-style:
```tsx
const isDisabled = (isBoundary: boolean) => (isBoundary ? DISABLED_OPACITY : CURSOR_POINTER);
// 调用方
const classNames = { prev: isDisabled(current === ONE), next: isDisabled(current >= totalPages) };
```

**净省**: 0 行, 反而多 1 行 (helper + 调用). **可读性持平**.

**结论**: 🟢 低 ROI (略增复杂度). 不改.

---

### A.6 [components/common/form/app-field.tsx:124-129] — error/help 渲染可改 ternary

**现状** (CLAUDE.md `oxlint no-nested-ternary` 已强制 if/else):
```tsx
let helpOrErrorElement: ReactNode = null;
if (errorMessage) {
  helpOrErrorElement = <p className="text-sm text-destructive">{errorMessage}</p>;
} else if (help) {
  helpOrErrorElement = <p className="text-sm text-muted-foreground">{help}</p>;
}
```

**改法** (对象 dispatch):
```tsx
const elementMap = {
  error: (msg: string) => <p className="text-sm text-destructive">{msg}</p>,
  help: (msg: string) => <p className="text-sm text-muted-foreground">{msg}</p>,
} as const;
const helpOrErrorElement = errorMessage
  ? elementMap.error(errorMessage)
  : help
    ? elementMap.help(help)
    : null;
```

**问题**: 嵌套三元, 项目 oxlint `no-nested-ternary` 禁止, 必须改 if/else.

**结论**: ❌ 不建议. 当前 if/else 已符合项目规约, 强行 dispatch 反增复杂度.

---

### A.7 [components/common/button/app-copy-button.tsx:64-69] — copied/label IIFE 改 lookup

**现状** (JSX 内 IIFE):
```tsx
{(() => {
  if (copied) {
    return successLabel;
  }
  return label;
})()}
```

**改法**:
```tsx
{(copied ? successLabel : label)}
```

**净省**: 5 行 → 1 行. **关键**: 跟 oxlint `no-nested-ternary` 不冲突 (单层 ternary OK).

**风险**: 低. 单层三元是 oxlint `no-nested-ternary` 白名单.

**结论**: 🟡 中 ROI. 但当前 IIFE 形式也合规 (项目规约未禁 IIFE); **不强推**.

---

### A.8 [components/common/navigation/app-back-link.tsx:42-50] — metaKey/ctrlKey 多分支可改 cond/any

**现状**:
```tsx
const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== MOUSE_BUTTON_LEFT) {
    return;
  }
  event.preventDefault();
  if (typeof globalThis !== "undefined" && globalThis.history.length >= MIN_HISTORY_FOR_BACK) {
    router.back();
  } else {
    router.push(href);
  }
};
```

**改法候选 1** (用 es-toolkit `cond`):
```tsx
import { cond } from "es-toolkit/function";

const navigationHandler = cond([
  [(e: MouseEvent) => typeof globalThis !== "undefined" && globalThis.history.length >= 2, () => router.back()],
  [() => true, () => router.push(href)],
]);
```

**评估**: 改完不省行 (cond 字典声明 + 调用 ≈ 原 if/else), 反而多 import.

**改法候选 2** (用 `some`):
```tsx
const isModified = [event.metaKey, event.ctrlKey, event.shiftKey, event.button !== 0].some(Boolean);
if (isModified) return;
```

**评估**: 省 0 行, 反而多 1 个临时变量 + 数组分配.

**结论**: ❌ 不建议. 当前 4 个 `||` 链是 idiomatic JavaScript, 没必要抽.

---

### A.9 [components/common/feedback/app-error-boundary.tsx:13-44] — class component 改函数式 + dispatch

**现状** (class 组件, React 19 时代遗留):
```tsx
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <Card className="border-status-error/40" data-testid="error-boundary">
          <CardHeader>
            <CardTitle className="text-status-error">出错了</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm text-status-error whitespace-pre-wrap">
              {this.state.error.message}
            </pre>
            <Button variant="link" onClick={() => this.setState({ error: null })}>
              重试
            </Button>
          </CardContent>
        </Card>
      );
    }
    return this.props.children;
  }
}
```

**评估**: class 组件内 `this.state` + `setState` 是**真正的副作用**, 改函数式 (useState) 是大动干戈:
- 需重写整个组件
- 拆 React 19 `use()` 模式 (`use(this.state.error)`) 不适用, 这是错误边界
- React 19 推荐用 `react-error-boundary` 库, 但项目没装

**结论**: ❌ 不建议. 这是 React 历史包袱, 不是 FP 问题.

---

### A.10 [components/common/input/app-dropdown-menu.tsx:63-110] — items.filter + 多分支 render 不可纯化

**现状**:
```tsx
const visibleItems = items.filter((item) => !item.hidden);

return (
  <DropdownMenu>
    {visibleItems.length > ZERO && (
      <DropdownMenuContent>
        {visibleItems.map((item) => {
          if (item.separator && !item.label) return <DropdownMenuSeparator key={item.key} />;
          return (
            <span>
              {item.separator && <DropdownMenuSeparator />}
              {item.href ? <DropdownMenuItem asChild>...</DropdownMenuItem> : <DropdownMenuItem>...</DropdownMenuItem>}
            </span>
          );
        })}
      </DropdownMenuContent>
    )}
  </DropdownMenu>
);
```

**评估**: `items.filter` 已用 es-toolkit 风格 (`filter` 内置方法, 不需 es-toolkit). 内部 if 链是 Radix DropdownMenu 模板要求, 改 dispatch 会破坏 key 稳定 + 嵌套 Span 包裹.

**结论**: ❌ 不建议. 这是 Radix 模板强制结构.

---

### A.11 [components/common/input/app-file-dropzone.tsx:63-78] — `parseAcceptString` 已纯函数, 无 ROI

**现状**:
```tsx
const parseAcceptString = (input: string): Accept | undefined => {
  const exts = input.split(",").map((val) => val.trim().toLowerCase()).filter(Boolean);
  if (!exts.length) return undefined;
  const out: Record<string, string[]> = {};
  for (const ext of exts) {
    const mime = EXT_TO_MIME[ext] ?? "application/octet-stream";
    (out[mime] ??= []).push(ext);
  }
  return out;
};
```

**评估**: 已纯函数 + 已用 `EXT_TO_MIME` lookup. `(out[mime] ??= []).push(ext)` 是标准的 groupBy 模式:
```tsx
import { groupBy } from "es-toolkit";
const grouped = groupBy(exts, (ext) => EXT_TO_MIME[ext] ?? "application/octet-stream");
return Object.fromEntries(
  Object.entries(grouped).map(([mime, exts]) => [mime, exts.map((e) => `.${e}`)])
);
```

**问题**:
- groupBy 返回 `Record<K, V[]>` 但 MIME key 需要是含 `.` 前缀的扩展名数组 (shadcn Dropzone 要求)
- 当前 `(out[mime] ??= []).push(ext)` 已经清晰 (1 行 vs 4 行 groupBy + mapValues)
- `groupBy` 已经在 `lib/chat/migration.ts:10` 用, 是项目已熟悉的 API

**净评估**: 改完多 2 行, 但**风格更声明式**.

**结论**: 🟡 中 ROI. 可改可不改 (项目偏好 `groupBy`), 不强推.

---

## 🟢 低 ROI (不建议重写)

### B.1 [components/common/display/app-status-badge.tsx:13-21] — 已 dispatch, 0 ROI

现状 `STATUS_COLORS: Record<StatusType, string>` 已是 lookup, 渲染 `<Badge className={cn(..., STATUS_COLORS[status])}>`. 无 if 链, 无 es-toolkit 机会. **不改**.

### B.2 [components/common/display/app-task-status-badge.tsx:6-13] — 已 dispatch, 0 ROI

现状 `style: Record<string, string>` 已是 lookup. 唯一 1 行 `style[state] ?? style.queued` fallback 是 idiomatic. **不改**.

### B.3 [components/common/display/app-env-badge.tsx:6-14] — 已 dispatch, 0 ROI

`variant: Record<string, string>` + `variant[ENV] ?? variant.DEV` 已是 lookup. 模块顶层读 `process.env.NEXT_PUBLIC_ENV` 是**真副作用** (build time 注入), 但 React 组件必须接收环境, 不能纯化. **不改**.

### B.4 [components/common/feedback/app-error-banner.tsx:28-42] — 已 dispatch, 0 ROI

`defaultIcon: Record<Variant, LucideIcon>` + `variantColorClass: Record<Variant, string>` 都是 lookup. 唯一 if 是 `variant === "destructive" ? "destructive" : "default"` 透传 shadcn variant — 改 dispatch 会让 shadcn prop 类型不一致. **不改**.

### B.5 [components/common/table/data-table.tsx:60-71] — `getColStyle` 已用 record dispatch

`typeof === "number" → number 分支`, `typeof === "string" → getStringColStyle`, `else → getFlexColStyle` 是 typed dispatch, 不需要 es-toolkit. **不改**.

### B.6 [components/common/table/data-table.tsx:42-48 + 50-58] — `getFlexColStyle` / `getStringColStyle` 已纯函数

已纯函数, 已用 `cn()` 合并 className. 无 ROI. **不改**.

### B.7 [components/common/display/app-breathing-dot.tsx:19-31] — COLOR_MAP / SIZE_MAP 已 lookup

`Record<Color, { ping; dot }>` 双层 lookup, 改 es-toolkit `mapValues` 等价. **不改**.

### B.8 [components/common/display/app-spinner.tsx:17-33] — 已纯 React 组件, 唯一 if 是 `reduced motion` 分支

`if (reduced) return <span>; return <motion.span>` 是渲染分支, 改 dispatch 会让 motion 配置丢失. **不改**.

### B.9 [components/common/overlay/app-tooltip.tsx:29-33] — VARIANT_BAR 已 lookup

`Record<"default" | "error" | "none", string>` 已 lookup. **不改**.

---

## ❌ 明确不做 (含 shadcn/ui/* 全部)

### C.1 [components/ui/*] (36 文件) — shadcn 原语禁止改

按 [packages/web/CLAUDE.md §封装组件](packages/web/CLAUDE.md) 规约, `ui/*` 是 shadcn cli 生成的原语 (`alert.tsx` / `avatar.tsx` / `badge.tsx` / `button.tsx` / `calendar.tsx` / `card.tsx` / `checkbox.tsx` / `collapsible.tsx` / `command.tsx` / `dialog.tsx` / `dropdown-menu.tsx` / `empty.tsx` / `input.tsx` / `label.tsx` / `pagination.tsx` / `popover.tsx` / `progress.tsx` / `radio-group.tsx` / `scroll-area.tsx` / `select.tsx` / `separator.tsx` / `sheet.tsx` / `skeleton.tsx` / `sonner.tsx` / `switch.tsx` / `table.tsx` / `tabs.tsx` / `textarea.tsx` / `toggle-group.tsx` / `toggle.tsx` / `tooltip.tsx` + 6 个 `alert-dialog.tsx` / `alert.tsx` 等).

业务代码**不应直接拼**, 而应走 `components/common/*` 包装 (AppDialog / AppConfirm / AppTooltip / AppSelect / AppToggle / AppTabs / AppDropdownMenu / ErrorBanner / CopyButton / FileDropzone / DataTable / DataEmpty / AppField).

shadcn ui 升级或 `bunx --bun shadcn add ...` 会**整体覆盖 ui/ 目录**. 改 ui/* 等于跟 shadcn 升级冲突.

**结论**: 36 个 ui/* 文件全部 ❌ 不做.

### C.2 [components/common/feedback/app-error-boundary.tsx] — class 组件不 FP 化

React 错误边界**必须**用 class (或 `react-error-boundary` 库). 改函数式 + useState 会失去错误捕获能力. **❌**.

### C.3 [components/common/display/app-health-dot.tsx] — TanStack Query + 5s setInterval 是真业务需求

`useQuery({ queryFn: fetchDifyHealth, refetchInterval: 5000 })` 是项目 Dify 监控需求, 不能纯化 (fetch + setInterval). **❌**.

### C.4 [components/common/button/app-copy-button.tsx:39-42] — `navigator.clipboard.writeText` + `setTimeout` 是用户事件副作用

`onClick` handler 内调 async clipboard + 1.5s `setTimeout` reset 是**真业务** (跟 ErrorBanner 反馈 toast 模式一致). 不能纯化. **❌**.

### C.5 [components/common/input/app-search-input.tsx] — `useDebounce` + `useEffect` 钩子组合是 ahooks/react-use 标准

`useDebounce` 来自 `react-use` (项目已装, 见 package.json). `useEffect` 同步外部 value → local. 无 ROI. **❌**.

### C.6 [components/common/input/app-image-preview.tsx] — 纯 1 组件 1 文件, 无逻辑

26 行, 无 if 无 es-toolkit 机会. **❌**.

### C.7 [components/common/form/app-submit.tsx] — TanStack Form 钩子

`useStore(form.store, ...)` 是 TanStack Form API. 无 ROI. **❌**.

### C.8 [components/common/input/app-select.tsx + app-tabs.tsx + app-toggle.tsx] — 纯 1 文件 1 组件映射

50 行内, 只做 shadcn → antd 风格映射. 无 FP 机会. **❌**.

### C.9 [components/common/index.ts + display/index.ts + ... 12 个 index.ts] — 仅 re-export

12 个 `index.ts` 是 barrel 文件. 无 ROI. **❌**.

---

## 扫描方法说明

### grep 模式 + 结果

| 模式 | 命中数 (common+ui, 排除 test/stories) | 关键发现 |
|---|---|---|
| `Date\.now\|new Date(` | 0 | common/ui 全部 0 命中 — 时间处理走 `motion/react` 的 `useReducedMotionSafe` 或 `react-use`, 不在组件层做 Date 副作用 |
| `\.push\|\.splice\|\.sort\|\.reverse\|\.unshift\|\.shift\|\.pop` | 1 (`app-file-dropzone.tsx:75` `(out[mime] ??= []).push(ext)`) | 唯一数组 mutation, 见 A.11 候选 |
| `localStorage\|sessionStorage\|cookies(\|document\.cookie` | 0 | 全部走 hook (Dexie IDB / next/headers cookies), 不在组件层 |
| `fetch(\|setTimeout\|setInterval\|navigator\.` | 4 (CopyButton × 2, HealthDot × 1) | 都是真业务副作用, 见 C.3 / C.4 |
| `if\s*\(` | 14 文件 | 大多数已用 lookup 替代, 残留都是 React 渲染分支 (loading/empty/data) |
| `switch\s*\(` | 0 | 0 switch-case, 项目已规避 |
| `function\s+\w+\(` | 0 | 0 `function` 声明, 符合 CLAUDE.md "使用箭头函数" |
| `Array\.from\b` | 4 处 | 见 A.1 (skeleton/skeleton × 2 文件), 改 `range` |
| `Math\.` | 3 处 | 都是 `Math.max/Math.min/Math.ceil` 简单 clamp, 见 A.4 (pagination) |
| `try\s*{` | 2 处 | 见 A.2 (CopyButton 错误归一化) + app-form.tsx (onFinish 容错) |
| `\.\.\.spread` | 0 | 0 spread mutation |

### es-toolkit API 已验证可用

通过 `ls node_modules/es-toolkit/dist/{array,util,math,predicate}` 验证:
- `array/chunk.ts` / `groupBy.ts` / `partition.ts` / `range.ts` 等
- `util/attempt.ts` / `util/attemptAsync.ts` (替换 try-catch)
- `math/clamp.ts` (替换 Math.max/min)
- `math/range.ts` (替换 Array.from({length}).map)
- `predicate/isError.ts` / `isNil.ts` (类型守卫)

### 关键决策 (按 ROI 优先级)

1. **🔴 A.1 `range`** — 改 4 处, 净省 ~10 行, 风险 0. **建议改**.
2. **🔴 A.2 `attempt`** — 改完行数持平, 但 `attemptAsync` 不熟悉度高于 try/catch. **降级为 🟡 可选**.
3. **🟡 A.4 `clamp`** — 改完声明式, 但 5 行净省 < 阅读成本. **可选**.
4. **🟡 A.11 `groupBy` 替 push loop** — 风格更声明式, 但当前 4 行 vs groupBy 5 行, **不推**.
5. **🟢 B.1-B.9** — 全是已 lookup, 改 es-toolkit 反而绕远路.
6. **❌ C.1-C.9** — 副作用 / shadcn 原语 / 已有 idiom, 不动.

### 跟 P3 `applyEvent` 的对比

| 项 | P3 `applyEvent` 重写 | 本次 A.1 `range` 重写 |
|---|---|---|
| 行数节省 | 24 → 6 (净省 18 行) | 4 处各 1 行 (净省 4 行) |
| 风险 | 中 (事件分发逻辑需回归测试) | 低 (纯数字生成, 无副作用) |
| ROI | 🔴 高 | 🔴 高 (但量级小) |

`range` 是"低风险低收益"机会, 不如 `applyEvent` 那种"高风险高收益". 建议**单独**改 (PR 不掺, 1 commit 1 改动).
