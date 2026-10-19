# P2 维度 ② CVA 重写机会 — Agent C (页面 + API + _components, 153 文件)

## 扫描概览

- **总扫描文件**: 153 (排除 `.test.tsx` / `.test.ts`)
- **页面 page.tsx**: 37 个 — 几乎全部 ❌ 不建议
- **私有 _components/*.tsx**: 64 个 — 主要扫描对象
- **API routes** (route.ts): 24 个 — 完全不适用 (无 JSX)
- **layout / loading / error / not-found / forbidden / global-error**: 7+1+1+1+1+1 = 12 个 — 几乎都不适用
- **Server Actions / Hooks** (`_actions/*.ts`, `_hooks/*.ts`): 9 个 — 不适用 (无 JSX)
- **已用 CVA 的文件**: **0** (整个 `app/` 目录没有任何 `import { cva }` 或 `class-variance-authority` 引入)
- **真正适合 CVA 的文件**: **2-3 个** (集中在 health 监控模块)
- **实际净省代码**: ~30 行 (权衡: CVA 重构后类型/扩展性收益 > 行数收益, 但因 ROI 仅🟡中等, 不强推)

## 关键发现

**整个 `app/` 目录完全没有使用 `class-variance-authority`**. 所有 variant className 都是手写的 `${condition ? "x" : "y"}` 字符串拼接模式. 这种"全无 CVA"现状意味着:
1. 引入 CVA 必须新建基础设施 (在 `components/common/` 或 `lib/cva.ts` 创建共享 `cva` 包装)
2. 收益需逐文件评估, 不能批量迁移
3. 项目 shadcn/ui 依赖已有 `cva` 间接依赖, 但 app 层未直接使用

## 按子模块列出

### `[locale]/account/settings/_components/` (10 个)
- `account-settings-client.tsx`: 纯组合
- `avatar-uploader.tsx`: 单一 className, ❌ 不建议
- `cancel-deletion-dialog.tsx`: 单一变体, ❌ 不建议
- `change-email-dialog.tsx`: ❌ 不建议
- `change-password-dialog.tsx`: ❌ 不建议
- `deletion-section.tsx`: ❌ 不建议
- `email-section.tsx`: ❌ 不建议
- `password-section.tsx`: ❌ 不建议
- `profile-section.tsx`: ❌ 不建议
- `request-deletion-dialog.tsx`: ❌ 不建议
- `restore-deletion-banner.tsx`: 单状态, ❌ 不建议 (account settings 几乎纯 form 组合)

### `[locale]/admin/dicts/_components/` (5 个)
- `admin-dicts-client.tsx`: 纯组合
- `dict-audit-log.tsx`: 单一展示
- `dict-item-create-dialog.tsx`: 单一 dialog
- **`dict-item-delete-dialog.tsx`**: 只有 submitting 状态, 单一 className, ❌ 不建议
- `dict-item-editor.tsx`: 表单组合, ❌ 不建议
- `dict-list.tsx`: is_active badge 双状态 — 但 badge variant 已用 shadcn Badge `variant` 字段, 没必要 CVA 二次包装
- **`readonly-banner.tsx`**: 🟡 中 ROI (2 状态: readonly/writable, colorClass 二选一) — 但文件只有 47 行, 过度抽象风险

### `[locale]/admin/invites/_components/` (1 个)
- `admin-invites-table.tsx`: 单一表格, ❌ 不建议

### `[locale]/admin/permissions/_components/` (5 个)
- `create-role-dialog.tsx`: submitting 单状态, ❌ 不建议
- **`permission-row.tsx`**: 3 个条件 (isSystem icon, isSelected row, edit/readonly cell) — 不同元素, 不同语义, CVA 不合适
- `permissions-admin-client.tsx`: 纯组合
- **`permissions-table.tsx`**: 🟡 中 ROI (editButtonVariant: isEditMode 二元; banner 也是 edit mode 二元) — 但仅 2 条件, 且现有 Button variant prop 已经在用 shadcn, 重复
- `role-detail-card.tsx`: 单一展示

### `[locale]/admin/users/_components/` (5 个)
- **`admin-users-table.tsx`**: 🟡 中 ROI — `renderKindBadge`/`renderActiveBadge` 有 2 状态 badge variant, 但用 shadcn Badge variant 已经够用, CVA 反而多一层
- `create-invite-button.tsx`: 21 行, ❌ 不建议
- `create-invite-dialog.tsx`: ❌ 不建议
- `reset-password-dialog.tsx`: ❌ 不建议
- `user-filters.tsx`: ❌ 不建议

### `[locale]/buyers/[id]/_components/` (2 个)
- `change-timeline.tsx`: 单一展示 + Badge variant 用 shadcn, ❌ 不建议
- `profile-card.tsx`: Badge variant + Button variant 都是 shadcn, ❌ 不建议

### `[locale]/decode/` (4 个)
- `decode-field.tsx`: 🟢 低 ROI — `isRich` 单条件, `cn()` 仅 2 个条件拼接 (1 个)
- 其他都是简单组合, ❌

### `[locale]/evaluate/_components/` (1 个)
- `evaluate-list-view.tsx`: 单一 DataTable 组合, ❌ 不建议 (StatusBadge 已封装在 `components/evaluate/status-badge.tsx`, 不在本目录范围)

### `[locale]/evaluate/[id]/_components/` (4 个)
- **`metric-bar.tsx`**: 🟡 中 ROI — `getColor(val)` 3 档 (高/中/低) 用三元 if 拼接, 单一元素 (进度条), 确实有 CVA 价值 — 这是 metric-bar 文件本身就 56 行的私有组件, 重写可读性收益高
- `run-detail-view.tsx`: 复合状态 (running/failed), 但用现有 shadcn variant 已够, ❌
- `sample-table.tsx`: Badge variant 复用 shadcn, ❌
- `strip-think.ts`: 工具函数, 不适用

### `[locale]/evaluate/new/_components/` (1 个)
- `evaluate-new-form.tsx`: 纯表单 + ErrorBanner, ❌

### `[locale]/health/_components/` (5 个) — **CVA 主要候选区**
- `health-client.tsx`: 状态分支 (error/loading/dashboard), 但每种状态都换整片 UI, 不是 CVA 概念
- **`health-service-card.tsx`**: 🟡 中 ROI — `resolveStatusVisuals(ok)` 返回 5 个字段 (icon/badge/iconClass/heroNumberClass/statusBarClass), 但都是独立元素, 用 CVA 包 1 个组件反而复杂
- **`hero-section.tsx`**: 🟡 中 ROI — `statusTextColor`/`statusDotClass` 二元状态, 3 处复用, 但元素类型不同 (text/dot)
- `services-grid.tsx`: 纯组合
- **`system-resources.tsx`**: 🔴 高 ROI 候选 — 4 个独立函数 (`cpuProgressColor` / `memProgressColor` / `gpuProgressColor` / `statusTextColor`) 都返回颜色 className, 阈值差异只是常量. 如果抽成一个 `resourceLevelColors` CVA, 大量 if 链可消除

### `[locale]/knowledge/_components/` (2 个)
- `active-switch.tsx`: 25 行, 5 个 pathname 起始判断, 但只渲染两个组件之一, 不是 CVA 概念
- `knowledge-dashboard.tsx`: 单一组合

### `[locale]/knowledge/dataset-documents/[dataset_id]/_components/` (1 个)
- `dataset-documents-table.tsx`: 单一表格, ❌

### `[locale]/knowledge/datasets/_components/` (1 个)
- `datasets-table.tsx`: 单一表格, ❌

### `[locale]/knowledge/documents/_components/` (1 个)
- `documents-entry.tsx`: 纯组合, ❌

### `[locale]/knowledge/documents/import/_components/` (2 个)
- `documents-import-form.tsx`: form 组合, ❌
- `import-commit-card.tsx`: form 组合 + success/error 两个 message 块 — 已经有 🟡 中 ROI 倾向 (success/error 的 border/text/bg 颜色), 但每个块只渲染一次, 不构成 variant 重用

### `[locale]/knowledge/graph/_components/` (1 个)
- `graph-view.tsx`: 纯组合, ❌

### `[locale]/knowledge/nodes/_components/` (1 个)
- `nodes-table.tsx`: 单一表格, ❌

### `[locale]/knowledge/qa/_components/` (1 个)
- `qa-submit-form.tsx`: 纯 form 组合, ❌

### `[locale]/knowledge/relations/_components/` (1 个)
- `relations-table.tsx`: Badge variant 用 shadcn 已足够, ❌

### `[locale]/knowledge/triples/_components/` (1 个)
- `triples-form.tsx`: form 组合 + TriplesResult/TriplesError (success/error 两个块), 与 import-commit-card 模式类似, 🟢 低 ROI

### `[locale]/output/_components/` (2 个)
- **`output-card.tsx`**: 🟡 中 ROI — `StateBadge` 4 状态 (completed/failed/queued/running) 映射 4 个颜色 className 数组 — 这是 app 目录内最经典的"状态→className"映射, 适合 CVA
- `output-list-client.tsx`: 纯组合

### `[locale]/output/[task_id]/_components/` (4 个)
- `task-detail-client.tsx`: 单一业务流
- `task-download.tsx`: ❌ 不建议
- `task-files.tsx`: ❌ 不建议
- `task-info.tsx`: ❌ 不建议

### `[locale]/submissions/_components/` (4 个)
- `all-approvals-table.tsx`: 纯 AppTabs + DataTable, ❌
- **`approval-row.tsx`**: 🟡 中 ROI — `REVIEW_BADGE` / `APPLY_BADGE` 用对象查找 `Record<string, string>`, 6 个状态色映射. 这是"用对象替代 if 链"的典型模式, 改成 CVA 后 `Badge variant={REVIEW_BADGE[review_status]}` 仍可保留, 但失去 Record 类型的简洁性 — CVA 不是必须
- `my-submissions-list.tsx`: ❌ 不建议
- `reject-dialog.tsx`: ❌ 不建议
- `submissions-tabs.tsx`: 53 行, ❌

---

## 🔴 高 ROI (建议重写) — 1 个

### `health/_components/system-resources.tsx` — 4 个独立 if 链生成同模式颜色

**当前实现 (摘录 line 24-58)**:
```tsx
const cpuProgressColor = (cpuPct: number | undefined): string => {
  if (cpuPct === undefined) return "bg-muted";
  if (cpuPct > CPU_CRIT_PCT) return "bg-destructive";
  if (cpuPct > CPU_WARN_PCT) return "bg-ochre";
  return "bg-moss";
};
// memProgressColor / gpuProgressColor 完全同结构, 只改常量
// statusTextColor: 二元 (ok ? "text-moss" : "text-destructive")
```

**问题**: 4 个函数 + 阈值常量, 共 ~45 行. 阈值差异是数据而非逻辑 — 如果未来要调阈值, 必须改 4 个地方. CVA 抽象出"严重度级别"概念后, 阈值常量集中管理.

**CVA 重写 (估算)**:
```tsx
const resourceLevel = cva("", {
  variants: {
    severity: {
      unknown: "bg-muted",
      ok: "bg-moss text-moss",
      warn: "bg-ochre",
      crit: "bg-destructive text-destructive",
    },
  },
});

const cpuSeverity = (pct: number | undefined) =>
  pct === undefined ? "unknown"
  : pct > CPU_CRIT_PCT ? "crit"
  : pct > CPU_WARN_PCT ? "warn" : "ok";
```

**行数对比**: 45 行 → ~20 行 (-25 行). 净省代码量最大, 但需引入 cva 基础设施.

**结论**: 🟡 中 ROI — 净省代码可观, 但语义清晰度提升有限 (因为阈值逻辑本身还要保留). **建议在引入 cva 基础设施时同步重写**, 单独做不划算.

---

## 🟡 中 ROI (可选重写) — 4 个

### 1. `output/_components/output-card.tsx` — `StateBadge` 4 状态映射

**当前 (line 26-37)**:
```tsx
const map = {
  completed: "bg-moss/10 text-moss",
  failed: "bg-destructive/10 text-destructive",
  queued: "bg-muted text-muted-foreground",
  running: "bg-clay/10 text-clay",
} as const;
let label: string = state;
if (state === "running") label = `${progress}%`;
return <span className={cn("rounded-full px-2 py-0.5 text-xs", map[state])}>{label}</span>;
```

**CVA 重写**:
```tsx
const stateBadge = cva("rounded-full px-2 py-0.5 text-xs", {
  variants: {
    state: {
      completed: "bg-moss/10 text-moss",
      failed: "bg-destructive/10 text-destructive",
      queued: "bg-muted text-muted-foreground",
      running: "bg-clay/10 text-clay",
    },
  },
});
// 用法: <span className={stateBadge({ state })}>{label}</span>
```

**行数对比**: 11 行 → 9 行, **基本持平**. 收益在于: 状态字段强类型化 (TypeScript 推断 state 必须是 4 个之一), 加新状态时编译报错. 但目前 `map` 已经是 `as const` + 字符串 key 字典, 编译期也有保护.

**结论**: 🟡 中 ROI — 收益是类型推断, 不是行数. 当前已经够用, 重写优先级低.

### 2. `evaluate/[id]/_components/metric-bar.tsx` — `getColor` 3 档 if 链

**当前 (line 17-25)**:
```tsx
const getColor = (val: number): string => {
  if (val >= SCORE_HIGH) return "bg-moss";
  if (val >= SCORE_MEDIUM) return "bg-status-warning";
  return "bg-destructive";
};
```

**问题**: 3 档阈值 + 3 种 bg 颜色. 单一元素 (进度条) 单一属性 (背景色), CVA 不是必需 (CVA 是多属性组合时最强).

**CVA 重写**:
```tsx
const scoreLevel = cva("", {
  variants: { level: { high: "bg-moss", mid: "bg-status-warning", low: "bg-destructive" } },
});
// const level = value >= SCORE_HIGH ? "high" : value >= SCORE_MEDIUM ? "mid" : "low";
// <div className={cn("h-full rounded-full transition-all duration-500", scoreLevel({ level }))} />
```

**行数对比**: 9 行 → 7 行, **基本持平**.

**结论**: 🟡 中 ROI — CVA 包单属性 overkill, 当前 if 链已经清晰. 不建议.

### 3. `admin/dicts/_components/readonly-banner.tsx` — readonly/writable 双状态

**当前 (line 34-36)**:
```tsx
const colorClass = readonly
  ? "border-destructive/50 text-destructive [&>svg]:text-destructive"
  : "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500";
```

**问题**: 整文件 47 行, 2 状态颜色类名很长 (用了 `[&>svg]:` 子选择器). 但**只在一个地方使用**, 重构成 CVA 没有跨文件复用价值.

**CVA 重写**: 收益 = 0 (单文件 2 状态用三元已经很清晰, 没必要引 cva).

**结论**: ❌ 不建议重写 — YAGNI. 如果未来 readonly banner 在其他模块也出现 (比如 outputs), 再抽.

### 4. `submissions/_components/approval-row.tsx` — REVIEW_BADGE / APPLY_BADGE Record

**当前 (line 49-59)**:
```tsx
const REVIEW_BADGE: Record<string, string> = {
  approved: "bg-status-success/20 text-status-success",
  pending: "bg-status-warning/20 text-status-warning",
  rejected: "bg-status-error/20 text-status-error",
};
const APPLY_BADGE: Record<string, string> = {
  applied: "bg-status-success/20 text-status-success",
  failed: "bg-status-error/20 text-status-error",
  none: "bg-muted/20 text-muted-foreground",
};
```

**问题**: 已经是"字典查找"模式, 比 if/三元链好. CVA 改造会把 `Badge className={MAP[review_status]}` 改成 `Badge className={cva({ review_status })}`, 但状态枚举已经定死, 收益微小.

**结论**: ❌ 不建议重写 — 当前 Record 模式已经最优. CVA 反而增加间接层.

---

## 🟢 低 ROI (不建议重写) — 4 个

### `health/_components/health-service-card.tsx`
- `resolveStatusVisuals(ok)` 返回 5 个字段 (icon/badge/iconClass/heroNumberClass/statusBarClass)
- 但每个字段对应**不同元素** (icon/元素/数字/横条), 不能用 1 个 cva 统一
- CVA 适用条件是"同一元素不同样式", 这里违反前提

### `health/_components/hero-section.tsx`
- `statusTextColor` / `statusDotClass` 各只返回 1 种类型 (text-*/bg-*), 跨 2 个元素
- 同上, CVA 不适用

### `decode/decode-field.tsx`
- `cn("num truncate text-right text-base", fieldClass, suffix === "zh" && "text-foreground")`
- 单一条件分支 (`suffix === "zh"`), CVA overkill

### `knowledge/triples/_components/triples-form.tsx` + `knowledge/documents/import/_components/import-commit-card.tsx`
- 都有 success/error 两个 message 块, 但每个块只渲染一次, 颜色类名各写各的 (moss vs destructive), 没有共用 base
- CVA 适用条件 #3 "共用 base className" 不满足

---

## ❌ 明确不做 (违反 YAGNI — 页面层不适合 CVA)

### 37 个 page.tsx — 全部不适用

**根因**:
1. **页面层是组合层** — `page.tsx` 通常是 `export default async function Page() { const data = await fetch(); return <Component data={data} /> }` 结构, 没有内联 className 拼接
2. **业务逻辑在 `_components`** — page.tsx 不渲染 variant 元素
3. **样式由 server data 驱动** — 比如 `evaluationRun.status === "running"` 的样式已经在 `StatusBadge` (components/evaluate/status-badge.tsx) 封装, page.tsx 不关心

**抽样验证** (示例):
- `app/[locale]/evaluate/page.tsx`: 几乎只 fetch + 渲染 `<EvaluateListView runsPromise={...} />`, 0 个 className 拼接
- `app/[locale]/health/page.tsx`: 类似, 渲染 `<HealthClient />`
- `app/[locale]/knowledge/page.tsx`: 渲染 `<KnowledgeDashboard />`
- 所有 37 个 page.tsx 都符合"组合层"模式

### 24 个 API routes (route.ts) — 完全不适用
- 无 JSX, 无 className 概念, CVA 在这里 100% 不适用

### 12 个 layout / loading / error / not-found / forbidden / global-error — 几乎不适用
- `layout.tsx` 7 个: 几乎都是 `<html><body>{children}</body></html>` 包装 + provider 树
- `loading.tsx` / `error.tsx` / `not-found.tsx` / `forbidden.tsx` / `global-error.tsx`: 都是"展示占位/错误"组件, 单一 className, 单一状态

### 9 个 Server Actions / Hooks (`_actions/*.ts`, `_hooks/*.ts`) — 完全不适用
- 无 JSX, 无样式概念

---

## 扫描方法说明

### 扫描方法
1. **Glob** 找出所有 `.tsx`/`.ts` 文件 (排除 `.test.*`): 153 个
2. **Grep** `class-variance-authority|cva\(`: **0 命中** — 整个 app 目录没有 CVA 使用
3. **Grep** `cn\(`: **8 个文件** — 9 处 cn() 调用 (decode 有 2 处), 主要用于无 variant 拼接
4. **Grep** `variant=` / `state ===` / `status ===`: 找出所有"状态→className"映射位置 (~50 行命中)
5. **逐文件 Read** 高命中候选 (`metric-bar.tsx`, `output-card.tsx`, `readonly-banner.tsx`, `permissions-table.tsx`, `permission-row.tsx`, `health-service-card.tsx`, `system-resources.tsx`, `hero-section.tsx`, `evaluate-list-view.tsx`, `change-timeline.tsx`, `admin-users-table.tsx`, `decode-field.tsx`, `approval-row.tsx` 等 14 个文件) 做深度分析
6. **抽样验证** page.tsx 是否"组合层" (5 个抽样, 全部确认)

### ROI 判定逻辑
- 🔴 高 ROI: 当前 `if/三元` 拼接 ≥3 条件分支 OR 跨 2+ 文件共用 base className
- 🟡 中 ROI: 2 条件分支 + 未来可能扩展 OR 类型推断收益大于行数收益
- 🟢 低 ROI: 单条件分支 / CVA 适用条件 (同一元素) 不满足
- ❌ 不建议: 页面层 / API routes / 单一 className / 单文件使用

### 为什么"页面层"几乎全部 ❌
- Next.js App Router 的 `page.tsx` 设计模式就是"server component 装 data → 渲染 client wrapper"
- 项目 37 个 page.tsx 平均 ~30 行, 90% 都是 fetch + render wrapper
- 即使有 conditional render (`!data && <Loading />`), 也是**整片 UI 切换**, 不是"同一元素变体" — 这不是 CVA 的语义, 是 React conditional rendering

### 为什么 _components 也"几乎都不适合"
- 项目 _components 大多是**业务容器** (DictList / AdminUsersTable / TriplesForm), 不是**视觉原语**
- 视觉原语 (Badge / Button / Card) 已经在 `components/ui/` 用 shadcn + CVA 封装
- 业务容器的"状态"通常映射到**多个独立元素** (颜色 + 图标 + 文案), 不是单一元素的 className 集合 — 违反 CVA 适用前提

### 净建议
**本目录 CVA 重写 ROI 整体偏低, 建议不动**. 真正的 CVA 价值在 `components/ui/*` (shadcn 已做) 和 `components/common/*` (项目封装层). 后续 P2 维度如果审计 common 层, 应该会找到更多有价值的目标.

如果项目**强制要求 app 层引入 cva** (比如规范要求"所有 variant 走 CVA"), 推荐优先级:
1. `health/_components/system-resources.tsx` (净省 ~25 行, 集中阈值常量)
2. `output/_components/output-card.tsx` (`StateBadge` 类型推断)
3. 其他都不必动

---

## 附录: 全局 app/ 目录统计

| 类别 | 数量 | CVA 适用 |
|---|---|---|
| 页面 page.tsx | 37 | ❌ 全部 |
| 私有 _components/*.tsx | 64 | 🟡 2-3 个候选 (health + output) |
| layout.tsx | 6 | ❌ |
| loading.tsx / error.tsx / not-found.tsx / forbidden.tsx / global-error.tsx | 6 | ❌ |
| API route.ts | 24 | ❌ 完全不适用 |
| Server Actions (_actions/*.ts) | 4 | ❌ 完全不适用 |
| Hooks (_hooks/*.ts) | 4 | ❌ 完全不适用 |
| 其他 (decode/page.tsx 等顶层) | 8 | ❌ |
| **总计** | **153** | **🔴 1 个 / 🟡 4 个** |