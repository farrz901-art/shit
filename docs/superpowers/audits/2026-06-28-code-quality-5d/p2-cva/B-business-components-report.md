# P2 维度 ② CVA 重写机会 — Agent B (业务组件)

## 扫描概览

- **总扫描文件数**: 47 (排除 `common/`、`ui/`、`.test.*`、index 文件后)
- **已用 CVA 的文件**: 0 (全部在 `ui/` shadcn 原语层)
- **建议重写 (🔴 高 ROI)**: 2
- **可选重写 (🟡 中 ROI)**: 3
- **不建议 (🟢 低 ROI / ❌ YAGNI)**: 42
- **预计净省代码行数**: 约 -8 行 (CVA 模板占用大于简化收益, 大部分建议标注为"不建议重写")

## 按子模块列出

### chat/ (14 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| message-bubble.tsx | 2 状态气泡 (user/ai), 三元拼接 className | 中等 | 🟡 中 ROI |
| citation-panel.tsx | 纯列表渲染, 单层 className | 不适配 | ❌ |
| compose.tsx | streaming/idle 二态按钮 (Button variant 已用), textarea 单 className | 不适配 | ❌ |
| composer-attachments.tsx | 3 slot 入口 (image/file/voice) 用 if/else 渲染, ThumbnailList 缩略图行单 className | 部分适配 | 🟡 中 ROI |
| conversation-list.tsx | current/非 current 会话行 + Button 单 className | 部分适配 | 🟡 中 ROI |
| message-list.tsx | 空态 + 列表分支 (无 className 拼接) | 不适配 | ❌ |
| thinking-trace.tsx | finished/started 2 状态, 简单 if/else 切换 className | 低适配 | 🟢 低 ROI |
| voice-recorder.tsx | isRecording 切 icon + button variant (已用 CVA-Button) | 不适配 | ❌ |
| chat-header.tsx | isAccount 显隐按钮 (1 条件) | 不适配 | ❌ |
| chat-shell.tsx | 纯编排 | 不适配 | ❌ |
| chat-api-provider.tsx | 无 className | 不适配 | ❌ |
| memory-management-dialog.tsx | 编辑态/查看态分支, 单 className per branch | 低适配 | 🟢 低 ROI |
| message-feedback.tsx | open=true/false 切换整个子组件, 内部 className 单一 | 不适配 | ❌ |
| share-dialog.tsx | shares.length===0 渲染空态, 单 className | 不适配 | ❌ |
| shared-chat-view.tsx | model/createdAt 显隐, 单 className | 不适配 | ❌ |

### knowledge/ (5 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| schema-field-renderer.tsx | 2 个函数导出 (RelationPicker/LabelPicker), 都包装 AppSelect, 无条件 className | 不适配 | ❌ |
| knowledge-tabs.tsx | active=true/false 切 nav 链接 className | 低适配 | 🟢 低 ROI |
| schema-browser.tsx | schema 加载中/已加载切换 | 不适配 | ❌ |
| dataset-switcher.tsx | 纯 Switcher 包装 | 不适配 | ❌ |
| domain-switcher.tsx | 纯 Switcher 包装 | 不适配 | ❌ |

### evaluate/ (1 file)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| status-badge.tsx | 5 状态 (cancelled/completed/failed/pending/running), **已经在用 record map 方式映射 variant + customStyle**, 完全契合 CVA 模式 | **高适配** | 🔴 高 ROI |

### motion/ (13 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| animated.tsx | barrel, 无样式 | 不适配 | ❌ |
| animate-up.tsx | motion.div 包装, 1-2 条件 (reduced/effectiveLift) | 不适配 | ❌ |
| button-lift.tsx | motion.div 包装, reduced 条件 | 不适配 | ❌ |
| count-up.tsx | motion.span, className 透传 | 不适配 | ❌ |
| fade-presence.tsx | AnimatePresence 包装, 无样式 | 不适配 | ❌ |
| fade-up.tsx | motion.div, reduced 条件 | 不适配 | ❌ |
| hover-lift.tsx | motion.div, reduced 条件 + shadow 替代 | 不适配 | ❌ |
| pressable.tsx | motion.button, reduced/disabled 条件 | 不适配 | ❌ |
| pulse.tsx | motion.span, reduced 二元 | 不适配 | ❌ |
| reveal.tsx | motion.div, reduced 条件 | 不适配 | ❌ |
| stagger-item.tsx | variant 查找表 (VARIANT_MAP), 单 className | 不适配 | ❌ |
| stagger.tsx | motion.div, reduced 条件 | 不适配 | ❌ |
| use-reduced-motion-safe.ts | hook, 无样式 | 不适配 | ❌ |

**motion/ 总结**: 全部是 motion 原子组件, 样式极少 (大多单一 className 或透传). CVA 不适用.

### auth/ (4 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| auth-bootstrap.tsx | 副作用组件, 无 className | 不适配 | ❌ |
| guard-client.tsx | 无样式 | 不适配 | ❌ |
| guard-page.tsx | RSC, 无样式 | 不适配 | ❌ |
| permission-hydrate.tsx | 副作用, 无样式 | 不适配 | ❌ |

### json/ (4 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| json-view.tsx | RSC, 单一容器 className | 不适配 | ❌ |
| json-diff.tsx | RSC, 单一容器 className | 不适配 | ❌ |
| diff-row.tsx | **3 type (add/remove/none) + 3 BG_MAP + 3 GUTTER_COLOR_MAP + 3 GUTTER_SIGN_MAP**, 已用 record map 模式 | **高适配** | 🔴 高 ROI |
| types.ts | 类型定义 | 不适配 | ❌ |
| utils.ts | 工具函数 | 不适配 | ❌ |

### decode/ (1 file)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| chunks-preview.tsx | 单一 className, motion.span 列表 | 不适配 | ❌ |

### settings/ (2 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| settings-dialog.tsx | 2 行模板 (主题/语言), 都用 AppSelect, 单 className | 不适配 | ❌ |
| theme-toggle.tsx | 单 Button, variant 已是 CVA | 不适配 | ❌ |

### i18n/ (1 file)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| localized-link.tsx | Link 包装, className 透传 | 不适配 | ❌ |

### layout/ (2 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| header.tsx | 布局组件, NavLink 子组件单 className | 不适配 | ❌ |
| footer.tsx | 单层 RSC, 单 className | 不适配 | ❌ |

### 顶层 (3 files)

| 文件 | 当前模式 | CVA 适配 | 判定 |
|---|---|---|---|
| theme-provider.tsx | Context Provider, 无样式 | 不适配 | ❌ |
| user-menu.tsx | 1 条件 (anon/account), Button 已在 CVA | 不适配 | ❌ |
| page-guard.tsx | RSC, 无样式 | 不适配 | ❌ |

---

## 🔴 高 ROI（建议重写）

### 1. `components/json/diff-row.tsx`

**当前实现** (55 行):
```tsx
const BG_MAP: Record<DiffLineType, string> = {
  add: "bg-green-950/20 dark:bg-green-950/40",
  remove: "bg-red-950/20 dark:bg-red-950/40",
  none: "",
};

const GUTTER_COLOR_MAP: Record<DiffLineType, string> = {
  add: "text-green-500",
  remove: "text-red-500",
  none: "text-muted-foreground",
};

const GUTTER_SIGN_MAP: Record<DiffLineType, string> = {
  add: "+",
  remove: "-",
  none: " ",
};

export const DiffRow = ({ line }: DiffRowProps) => (
  <tr className={BG_MAP[line.type]}>
    <td className={cn("w-8 select-none text-right", GUTTER_COLOR_MAP[line.type])}>
      {GUTTER_SIGN_MAP[line.type]}
    </td>
    ...
  </tr>
);
```

**CVA 重写** (约 50 行):
```tsx
import { cva, type VariantProps } from "class-variance-authority";

const diffRowVariants = cva("", {
  variants: {
    type: {
      add: "bg-green-950/20 dark:bg-green-950/40",
      remove: "bg-red-950/20 dark:bg-red-950/40",
      none: "",
    },
  },
});

const gutterColorVariants = cva("w-8 select-none text-right", {
  variants: {
    type: {
      add: "text-green-500",
      remove: "text-red-500",
      none: "text-muted-foreground",
    },
  },
});

const gutterSignVariants = cva("", {
  variants: {
    type: {
      add: "+",
      remove: "-",
      none: " ",
    },
  },
});

export const DiffRow = ({ line }: { line: { type: VariantProps<typeof diffRowVariants>["type"]; tokens: ... } }) => (
  <tr className={diffRowVariants({ type: line.type })}>
    <td className={gutterColorVariants({ type: line.type })}>{gutterSignVariants({ type: line.type })}</td>
    ...
  </tr>
);
```

**对比**:
- 当前: 3 个 Record map + 2 次 cn 拼接 + 1 处 GUTTER_SIGN_MAP 字符查表
- CVA: 3 个 cva() 函数, 类型自动推导
- **净变化**: 约 -2 行 (CVA 类型声明 + 函数定义, vs Record 简写)
- **收益**: 字符 (+/-/空格) 实际上不适合放 className, CVA 用法上不优雅; 仅 BG/color 是真正的样式变体
- **建议**: 只把 BG_MAP + GUTTER_COLOR_MAP 合并成 1 个 cva (tr + td 共用 type 变体), 保留符号查表. 实操仅净省 1 行, **价值低**, 但 **类型化改善显著** (VariantProps 推出 type union, 避免字符串拼错)

**实际判定**: 🟡 中 ROI 偏下. 收益是类型推导, 不是行数. 推荐度: **可改可不改**.

### 2. `components/evaluate/status-badge.tsx`

**当前实现** (44 行):
```tsx
const CUSTOM_STYLE: Record<string, string> = {
  completed: "bg-moss/10 text-moss border-moss/30",
  running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
};
const LABEL: Record<EvaluationStatus, string> = { ... };
const VARIANT: Record<EvaluationStatus, BadgeProps["variant"]> = { ... };

export const StatusBadge = ({ status, className = "" }: Props) => (
  <Badge variant={VARIANT[status]} className={`${CUSTOM_STYLE[status] ?? ""} ${className}`.trim()}>
    {LABEL[status]}
  </Badge>
);
```

**CVA 重写** (约 50 行):
```tsx
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const statusBadgeVariants = cva("", {
  variants: {
    status: {
      cancelled: "",
      completed: "bg-moss/10 text-moss border-moss/30",
      failed: "",
      pending: "",
      running: "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
    },
  },
});

type Status = NonNullable<VariantProps<typeof statusBadgeVariants>["status"]>;

// LABEL 不变 (中文映射)
// VARIANT 不变 (shadcn Badge 内建 variant)
export const StatusBadge = ({ status, className }: Props) => (
  <Badge variant={VARIANT[status]} className={cn(statusBadgeVariants({ status }), className)}>
    {LABEL[status]}
  </Badge>
);
```

**对比**:
- 当前: 3 个 Record map + 字符串模板拼接
- CVA: 1 个 cva() 推导 status 联合类型, VariantProps 自动约束
- **净变化**: 约 +3 行 (cva 模板 + 注释)
- **收益**:
  1. 类型自动推导 (新加状态时, BadgeProps/LABEL/CUSTOM_STYLE 都要同步, 易漏)
  2. **LANGUAGE_TYPE_SAFETY**: 当前 CUSTOM_STYLE 是 `Record<string, string>`, 不受 EvaluationStatus 类型约束 — 加新状态时漏写 CUSTOM_STYLE 不会报错
  3. cn() 比模板字符串更安全 (trim 边界处理)
- **建议**: **建议重写**, 核心收益是类型化兜底 + 扩展性, 行数差可忽略

**实际判定**: 🔴 高 ROI. 5 状态 + 未来可能加 (e.g. queued / retrying), 类型安全价值 > 行数成本.

---

## 🟡 中 ROI（可选重写）

### 3. `components/chat/message-bubble.tsx`

**当前实现** (3 处 if/三元):
```tsx
const bubbleClass: string = (() => {
  if (isUser) {
    return `${MAX_WIDTH_CLASS} rounded-2xl bg-ink px-4 py-2.5 text-paper`;
  }
  return `${MAX_WIDTH_CLASS} rounded-2xl border border-border/60 bg-card px-4 py-2.5`;
})();
// ... 第 121 行: className={isUser ? "flex justify-end" : "flex justify-start"}
// ... 第 86 行: bodyContent: React.ReactNode = isUser ? ...
```

**CVA 重写** (约 8 行):
```tsx
const bubbleVariants = cva(`${MAX_WIDTH_CLASS} rounded-2xl px-4 py-2.5`, {
  variants: {
    role: {
      user: "bg-ink text-paper",
      assistant: "border border-border/60 bg-card",
    },
  },
});

const containerVariants = cva("flex", {
  variants: {
    role: { user: "justify-end", assistant: "justify-start" },
  },
});
```

**对比**:
- 当前: IIFE + 2 处三元拼接
- CVA: 2 个 cva, 类型化
- **净变化**: 约 -3 行 (省 IIFE + 三元)
- **收益**: 边际. 如果未来加 system/error 角色 (4 种), CVA 扩展更清晰

**实际判定**: 🟡 中 ROI. 仅在确认要加 system/error 角色时改. 当前 2 状态不痛.

### 4. `components/chat/composer-attachments.tsx`

**当前模式**:
- `ActivePanel`: 3 slot 用 if/else 渲染 (image/file/voice)
- `ThumbnailList`: 单层 className
- `SlotButtons`: 3 个相同结构 Button (variant/aria 略不同)

**CVA 适用点**: `SlotButtons` 的 3 个 Button 几乎同型, 但差异是 icon + testid + aria-label, 不是 className 变体 — **不是 CVA 的用例**. CVA 管样式, 不管 icon / testid.

**ActivePanel** 的 if/else 是**渲染分支**, 不是 className 拼接 — CVA 不适用.

**实际判定**: ❌ 不建议. CVA 不解决这种结构差异.

### 5. `components/chat/conversation-list.tsx`

**当前模式** (1 处三元):
```tsx
className={cn(
  "group flex cursor-pointer items-baseline gap-2 rounded-md border border-transparent px-2.5 py-2 transition-colors hover:bg-muted/40",
  isCurrent && "border-clay/40 bg-clay/5",
)}
```

**CVA 重写**:
```tsx
const conversationItemVariants = cva(
  "group flex cursor-pointer items-baseline gap-2 rounded-md border px-2.5 py-2 transition-colors hover:bg-muted/40",
  {
    variants: {
      active: {
        true: "border-clay/40 bg-clay/5",
        false: "border-transparent",
      },
    },
    defaultVariants: { active: false },
  },
);
```

**对比**:
- 当前: 1 行 cn 拼接
- CVA: 8 行 cva 定义
- **净变化**: +5 行, 复杂度上升

**实际判定**: ❌ 不建议. 单条件分支, cn 拼接已经是最简形式.

---

## 🟢 低 ROI（不建议重写）

### 6. `components/chat/thinking-trace.tsx`

```tsx
if (isFinished) {
  statusClass = FINISHED_CLASS;
} else {
  statusClass = STARTED_CLASS;
}
```

**判定**: ❌ 2 状态, 1 条件, CVA 模板 8 行 vs 当前 3 行. 不划算.

### 7. `components/knowledge/knowledge-tabs.tsx`

```tsx
let linkClass = "text-muted-foreground hover:text-foreground";
if (active) {
  linkClass = "border-b-2 border-clay text-foreground";
}
```

**判定**: ❌ 1 条件, 简单变量替换. 不需要 CVA.

### 8. `components/chat/memory-management-dialog.tsx`

`MemoryListItem` 内部 `if (isEditing) return ...` 是**渲染分支**, 不是 className. 不适用 CVA.

---

## ❌ 明确不做（违反 YAGNI / 不适用 CVA）

### motion/ (13 files)

所有 motion 原子组件:
- 单一 className 透传, 或
- reduced motion 二态 (const 替换 already)
- 多 variant 选择 (stagger-item 的 VARIANT_MAP 已用查找表, 类型安全)

CVA 在 motion 域的**唯一可能价值**是统一 variant API, 但 framer-motion 自身已有 variants prop. **不要替换为 CVA**.

### 大部分 layout / auth / i18n / decode / settings / 顶层文件

**根因**: 这些组件是**业务编排**或**单一职责**, 不需要 className 变体管理.

### ui/common/ 不在本报告范围

按要求仅扫描业务组件.

---

## 总体结论

| 类别 | 数量 | 文件 |
|---|---|---|
| 🔴 高 ROI 建议改 | 1 | evaluate/status-badge.tsx |
| 🟡 中 ROI 可选 | 1 | json/diff-row.tsx (类型化收益, 非行数) |
| ❌ 不建议 | 45 | 全部 chat/knowledge/motion/auth/layout/settings/i18n/decode/顶层 |

**总净省行数**: 接近 0 (CVA 模板成本与节省抵消).
**真正价值**: 在 evaluate/status-badge 和 json/diff-row, **类型安全** + **扩展性兜底** 是 ROI 来源, 不是行数.

### 推荐执行顺序

1. **`components/evaluate/status-badge.tsx`** — 5 状态变体, EvaluationStatus 类型已定义, 改 CVA 加 `VariantProps` 强约束, 防止漏加状态.
2. **`components/json/diff-row.tsx`** — 3 类型共用, 已用 Record map 模式, CVA 收益在类型化; 同时注意: GUTTER_SIGN_MAP (字符 + / -) 不属于 className 变体, **不应迁 CVA**, 保留查表.

**其它业务组件不要为用 CVA 而用 CVA**.

---

## 扫描方法说明

1. **范围**: `packages/web/components/` 下, 排除 `common/` 和 `ui/` 子目录, 排除 `.test.tsx` / `.test.ts` / `index.ts` (47 个文件实际扫描).
2. **方法**:
   - 用 Read 逐个读完所有候选文件 (本报告涵盖全部 47 个).
   - 用 Grep 验证 CVA 已使用位置 (确认仅 `ui/` 8 个文件).
   - 用 Grep 找 `cn(...)` 三元 / `if/else` 拼接 className 模式.
3. **判定标准**:
   - 数 if/三元拼接 className 的分支数 (≥3 高 ROI, 2 中 ROI, 1 低 ROI)
   - 评估 Record map → CVA 转换的类型化收益
   - 排除渲染分支 (if 返回 JSX) 和单一 className
4. **CVA 模板行数参考**: 标准 cva() 函数约 8-10 行 (含 types/comments). 重写必须节省 ≥5 行才算正向 ROI, 否则以类型化收益为准.
5. **未扫描**: `common/` 和 `ui/` 目录下的组件封装 (项目规范要求封装统一, CVA 已在 `ui/` 内建).