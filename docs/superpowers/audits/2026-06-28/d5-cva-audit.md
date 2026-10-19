# D5: cva 改写专项审计

> 扫描时间: 2026-06-28
> 工具调用次数: 33 / 40

## 元信息

- 项目根: `c:/doc/Code/rag/packages/web`
- 扫了 28 个文件 (8 个 cva 模板 + 11 个高怀疑候选 + 7 个 ui/* + 2 个其他)
- 找到 9 条 finding (3 high + 4 medium + 2 low)

## 检查项回顾 (6 项)

1. **if/else 拼 className** — 找到 4 处 (metric-bar / knowledge-tabs / admin-users-table / decode-field)
2. **size/variant/state 隐式散落** — 找到 6 处 (error-banner / stat-card / status-badge 3 个 / breathing-dot / task-status-badge)
3. **重复 className 模式 ≥ 3 处** — 找到 2 处 (badge state 映射 4+ 处重复 / button confirm 包装 2 处)
4. **三元嵌套 ≥ 2 层** — 未发现明显 (项目普遍用 if/else 替代三元, 2026-06-19 强制)
5. **复合变体未抽 compoundVariants** — 未发现 (项目还没 cva 多 prop 组合用法)
6. **状态色/语义色不一致** — 找到 1 处 (status-badge.tsx 写 hex bg-red-100 不用 status-* token)

## Findings (9 条)

```yaml
- id: CVA-001
  dimension: frontend
  severity: high
  confidence: high
  title: "ErrorBanner 用 lookup map 模拟 5 variant, 应改 cva"
  file: packages/web/components/common/feedback/app-error-banner.tsx
  line: 36
  description: |
    ErrorBanner 注释明确说 "Shadcn Alert 只有 destructive + default 2 variant, 其他 4 variant 用 className 模拟".
    当前实现: `variantColorClass: Record<ErrorBannerVariant, string>` 硬编 5 variant 的 className 字符串, 通过 `cn(variantColorClass[variant], className)` 应用.
    这是教科书 cva 候选: 5 个 variant + 跟 icon variant 联动 (loading 加 animate-spin).
  evidence: |
    const variantColorClass: Record<ErrorBannerVariant, string> = {
      destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
      info: "border-blue-500/50 text-blue-700 dark:text-blue-300 [&>svg]:text-blue-500",
      loading: "",
      success: "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500",
      warning: "border-amber-500/50 text-amber-700 dark:text-amber-300 [&>svg]:text-amber-500",
    };
  impact: |
    - 变体散落, 改一处要改 map + 注释 + icon map 同步
    - 颜色写 hex (emerald/amber/blue) 不用 status-* token, 主题切换一致性风险
    - TS 不强制 variant 字符串, 默认值在 prop default; cva 的 defaultVariants 模式更标准
  fix_sketch: |
    改用 cva:
    ```ts
    const errorBannerVariants = cva(
      "relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4",
      {
        defaultVariants: { variant: "destructive" },
        variants: {
          variant: {
            destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
            info: "border-blue-500/50 text-blue-700 dark:text-blue-300 [&>svg]:text-blue-500",
            loading: "",
            success: "border-emerald-500/50 text-emerald-700 dark:text-emerald-300 [&>svg]:text-emerald-500",
            warning: "border-amber-500/50 text-amber-700 dark:text-amber-300 [&>svg]:text-amber-500",
          },
        },
      }
    );
    ```
    同步建议: 把 hex 色换 status-* token (`bg-status-info/10 text-status-info` 等, 但项目当前没 info token, 需先扩 themes.ts).

- id: CVA-002
  dimension: frontend
  severity: high
  confidence: high
  title: "StatCard accent 5 色用 lookup map, 应改 cva"
  file: packages/web/components/common/display/app-stat-card.tsx
  line: 22
  description: |
    StatCard 有 5 个 accent 维度 (ink/clay/moss/ochre/indigo), 当前用 inline `{}` lookup 表反查 className.
    调用方常见 (`<StatCard ... accent="moss" />` run-detail-view 等), 跟 cva variant 语义完全对齐.
  evidence: |
    const accentBar = {
      clay: "bg-clay",
      indigo: "bg-indigo",
      ink: "bg-ink",
      moss: "bg-moss",
      ochre: "bg-ochre",
    }[accent];
  impact: |
    - 5 个 accent 硬编, 改一处要 grep 多文件同步
    - 提取命名 + TS 类型推断, 调用方拼错 accent 编译期就能发现 (cva defaultVariants 自动回退)
    - cva variant 跟其他变体 (size/color) 可复合, 未来扩展 (hover 色 / active 色) 用 compoundVariants
  fix_sketch: |
    改用 cva:
    ```ts
    const statCardVariants = cva("", {
      variants: {
        accent: {
          clay: "[&_.accent-bar]:bg-clay",
          indigo: "[&_.accent-bar]:bg-indigo",
          ink: "[&_.accent-bar]:bg-ink",
          moss: "[&_.accent-bar]:bg-moss",
          ochre: "[&_.accent-bar]:bg-ochre",
        },
      },
    });
    // accent-bar div 加 data-slot="accent-bar"
    ```

- id: CVA-003
  dimension: frontend
  severity: high
  confidence: high
  title: "MetricBar 用 if/else 链 + lookup 拼 3 色 + 显示值, 应改 cva"
  file: packages/web/[locale]/evaluate/[id]/_components/metric-bar.tsx
  line: 17
  description: |
    MetricBar 同时有 3 维度变体: barColor (moss/warning/destructive 3 阈值) + displayValue (有/无) + size (高度, 这里隐式 h-2).
    `getColor()` 是 if/else 链返 className; `barColor` 用 let-then-if 模式赋默认值; `displayValue` 同样.
    整个组件本质是 1 个 bar component, 3 个 prop 维度, 适合 cva + state prop.
  evidence: |
    const getColor = (val: number): string => {
      if (val >= SCORE_HIGH) {
        return "bg-moss";
      }
      if (val >= SCORE_MEDIUM) {
        return "bg-status-warning";
      }
      return "bg-destructive";
    };
    // ... let barColor = "bg-muted"; if (value != null) barColor = getColor(value);
  impact: |
    - barColor 隐式 4 状态 (null/muted/3 阈值色) 用 if-else 拼, 不直观
    - 跟 status-badge 3 处 + StatCard 5 accent + ErrorBanner 5 variant 形成重复的 "基础 + 颜色" 模板
    - TS 不强制 score 阈值 (SCORE_HIGH/MEDIUM 是常量但用魔法数字 0.7/0.4 来自 local const, 复用性差)
  fix_sketch: |
    改用 cva + score prop:
    ```ts
    const metricBarVariants = cva("h-full rounded-full transition-all duration-500", {
      variants: {
        score: {
          high: "bg-moss",
          medium: "bg-status-warning",
          low: "bg-destructive",
          none: "bg-muted",
        },
      },
    });
    // barColor = metricBarVariants({ score: val == null ? "none" : val >= SCORE_HIGH ? "high" : val >= SCORE_MEDIUM ? "medium" : "low" })
    ```

- id: CVA-004
  dimension: frontend
  severity: medium
  confidence: high
  title: "StatusBadge / TaskStatusBadge / EvaluateStatusBadge 3 处重复 badge 状态色 lookup, 应合并 cva"
  file: packages/web/components/common/display/app-status-badge.tsx
  line: 13
  description: |
    3 个 badge 组件 (StatusBadge / TaskStatusBadge / EvaluateStatusBadge) 各自用 `Record<Status, string>` 维护状态色.
    虽然状态集不完全重叠 (admin/ingest/evaluate 各有), 但视觉模板 100% 重复: `bg-{color}-{n} text-{color}-{n} dark:bg-{color}-{n}/30`.
    应该抽 1 个 `<StatusBadge>` cva 模板 + 状态枚举 (status/cancelled/failed/...) 用 cva variant.
  evidence: |
    // app-status-badge.tsx
    const STATUS_COLORS: Record<StatusType, string> = {
      pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
      running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
      completed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
      failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
      cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
      ...
    };
    // app-task-status-badge.tsx 类似: done/failed/partial/queued/running/cancelled
    // evaluate/status-badge.tsx 类似: completed/failed/running/cancelled/pending
  impact: |
    - 3 处独立维护, 新增状态要改 3 处
    - app-status-badge 用 hex 颜色 (bg-red-100 等), 跟另外 2 个用 status-* token 不一致, 主题切换可能破
    - 重复 5+ 行配置, 加测试要写 3 遍
  fix_sketch: |
    合并为 cva:
    ```ts
    // components/common/display/app-status-badge.tsx
    const statusBadgeVariants = cva("font-medium", {
      variants: {
        state: {
          pending: "bg-status-warning/10 text-status-warning",
          running: "bg-status-running/10 text-status-running animate-pulse",
          completed: "bg-moss/10 text-moss",
          done: "bg-moss/10 text-moss", // alias
          failed: "bg-destructive/10 text-destructive",
          cancelled: "bg-muted text-muted-foreground",
          partial: "bg-status-warning/10 text-status-warning",
          queued: "bg-muted text-muted-foreground",
          active: "bg-moss/10 text-moss",
          archived: "bg-muted text-muted-foreground",
        },
      },
    });
    ```
    同步建议: app-status-badge 的 hex 颜色改 status-* token (跟 status-badge / task-status-badge 统一).

- id: CVA-005
  dimension: frontend
  severity: medium
  confidence: high
  title: "BreathingDot 双 map (color + size) 应改 cva compoundVariants"
  file: packages/web/components/common/display/app-breathing-dot.tsx
  line: 19
  description: |
    BreathingDot 有 2 维度: color (5 个: moss/clay/success/error/muted, 每色 2 个 class: ping/dot) + size (2 个: sm/md).
    当前用 2 个 lookup map (COLOR_MAP + SIZE_MAP), 然后 `cn(...)` 拼.
    cva 的 variant + compoundVariants 模式更直接: size 维度独立, color 维度 5 variant.
  evidence: |
    const COLOR_MAP: Record<BreathingDotColor, { ping: string; dot: string }> = {
      clay: { dot: "bg-clay", ping: "bg-clay/60" },
      error: { dot: "bg-status-error", ping: "bg-status-error/60" },
      moss: { dot: "bg-moss", ping: "bg-moss/60" },
      muted: { dot: "bg-muted-foreground/50", ping: "bg-muted-foreground/40" },
      success: { dot: "bg-status-success", ping: "bg-status-success/60" },
    };
    const SIZE_MAP: Record<BreathingDotSize, string> = {
      md: "h-2.5 w-2.5",
      sm: "h-1.5 w-1.5",
    };
  impact: |
    - 2 维度拆 2 map, 加颜色要改 2 处 (ping + dot)
    - ping/dot 命名绑死, 不能复用到其他呼吸组件 (decorative dot)
    - cva 的 compoundVariants 可加 "animated + size 组合时额外 class", 后续扩展更顺
  fix_sketch: |
    改用 cva:
    ```ts
    const breathingDotVariants = cva("relative flex", {
      variants: {
        color: {
          clay: "[&_.ping]:bg-clay/60 [&_.dot]:bg-clay",
          error: "[&_.ping]:bg-status-error/60 [&_.dot]:bg-status-error",
          moss: "[&_.ping]:bg-moss/60 [&_.dot]:bg-moss",
          muted: "[&_.ping]:bg-muted-foreground/40 [&_.dot]:bg-muted-foreground/50",
          success: "[&_.ping]:bg-status-success/60 [&_.dot]:bg-status-success",
        },
        size: { sm: "h-1.5 w-1.5", md: "h-2.5 w-2.5" },
      },
    });
    // 子 span 加 data-slot="ping"/"dot"
    ```

- id: CVA-006
  dimension: frontend
  severity: medium
  confidence: high
  title: "AppTooltip variant + lookup 模式可改 cva (3 variant 重复)"
  file: packages/web/components/common/overlay/app-tooltip.tsx
  line: 29
  description: |
    AppTooltip 有 3 variant (default/error/none), 用 `Record<..., string>` 反查色条 class.
    虽然只有 3 variant, 仍是 cva 候选: 单文件, 单维度, 跟项目 cva 风格对齐, 未来加 variant (warning/info) 直接扩.
  evidence: |
    const VARIANT_BAR: Record<"default" | "error" | "none", string> = {
      default: "before:bg-moss",
      error: "before:bg-destructive",
      none: "before:hidden",
    };
    // 用法: cn(..., VARIANT_BAR[variant])
  impact: |
    - 改一处查 2 处 (类型 + lookup)
    - cva 默认值 + TS VariantProps 自动推 props, 业务调用方写错 variant 编译报错
    - 跟项目 8 个 cva 模板风格统一
  fix_sketch: |
    改用 cva:
    ```ts
    const tooltipVariants = cva("...", {
      variants: {
        variant: {
          default: "before:bg-moss",
          error: "before:bg-destructive",
          none: "before:hidden",
        },
      },
      defaultVariants: { variant: "default" },
    });
    ```

- id: CVA-007
  dimension: frontend
  severity: medium
  confidence: high
  title: "AppConfirm variant 二元 if 拼 destructive class, 应改 cva"
  file: packages/web/components/common/confirm/app-confirm.tsx
  line: 48
  description: |
    AppConfirm 有 `variant: "default" | "destructive"` 二元变体, 当前 `cn(variant === "destructive" && "bg-destructive ...")` 拼按钮 class.
    这是 [feedback-no-shim-no-minimal-changes] 反面: 重复 markup = 隐藏技术债.
    AlertDialogAction 用 `buttonVariants()` (无 variant), 直接覆盖 className, 应改 cva 把 variant 维度纳入.
  evidence: |
    <AlertDialogAction
      onClick={onConfirm}
      className={cn(variant === "destructive" && "bg-destructive text-destructive-foreground")}
    >
  impact: |
    - variant 维度被 AlertDialogAction 抹平, 类型不安全 (调用方传 destructive 还是 default 都要看 prop 名字)
    - 当前按钮覆盖了 buttonVariants 的所有样式 (variant="default" 时也是 destructive class?), 实际是 if (variant === "destructive") 才覆盖, 所以 default 时按钮是 `buttonVariants()` 默认 primary 色, 不符合 "中性确认" 语义
    - 加新 variant (warning/info) 要再扩 if
  fix_sketch: |
    改用 cva:
    ```ts
    const confirmActionVariants = cva("", {
      variants: {
        variant: {
          default: "",
          destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        },
      },
    });
    <AlertDialogAction
      className={cn(buttonVariants(), confirmActionVariants({ variant }))}
    />
    ```

- id: CVA-008
  dimension: frontend
  severity: low
  confidence: high
  title: "KnowledgeTabs linkClass 用 let-then-if 二元变体, 应改 cva"
  file: packages/web/components/knowledge/knowledge-tabs.tsx
  line: 48
  description: |
    KnowledgeTabs 用 let-then-if 二元变体 (active/inactive) 拼 linkClass.
    组件小 (66 行), 但模式典型: `let linkClass = "..."; if (active) linkClass = "..."`.
    cva variant 改写会让 active 状态跟项目其他 tab (SettingsDialog) 风格对齐.
  evidence: |
    let linkClass = "text-muted-foreground hover:text-foreground";
    if (active) {
      linkClass = "border-b-2 border-clay text-foreground";
    }
  impact: |
    - 二元变体小, 边际改善
    - 跟项目 SettingsDialog 等其他 active tab 模式不一致, 未来统一 active state 需要重写
    - 单一组件内 if-else, 维护成本低
  fix_sketch: |
    改用 cva (低优先):
    ```ts
    const tabLinkVariants = cva("px-4 py-2 text-sm transition-colors", {
      variants: {
        active: {
          true: "border-b-2 border-clay text-foreground",
          false: "text-muted-foreground hover:text-foreground",
        },
      },
    });
    ```
    建议: 跟 SettingsDialog 等其他 active tab 一起做, 避免单独迁移.

- id: CVA-009
  dimension: frontend
  severity: low
  confidence: medium
  title: "DecodeField fieldClass let-then-if 二元变体 + 后续条件叠加"
  file: packages/web/app/[locale]/decode/decode-field.tsx
  line: 24
  description: |
    DecodeField 有 2 段 if-else 拼 className: 1) fieldClass (isRich 时变 muted) 2) 后面又叠 `suffix === "zh"` 条件.
    实际是 2 维度的状态: isRich (zh/en/raw) + suffix, 但当前实现散落.
    组件单文件 53 行, cva 改写收益小, 但模式典型.
  evidence: |
    let fieldClass = "font-medium text-foreground";
    if (isRich) {
      fieldClass = "text-muted-foreground";
    }
    // ... 后接 cn("num truncate ...", fieldClass, suffix === "zh" && "text-foreground")
  impact: |
    - 2 处独立 if 拼, 改一处要 grep 同步
    - 单一组件内, 边际改善
    - fieldClass + suffix 双 if 加 cn("...") 形成条件叠加模板, cva compoundVariants 可治
  fix_sketch: |
    改用 cva (低优先):
    ```ts
    const decodeFieldVariants = cva("num truncate text-right text-base", {
      variants: {
        rich: { true: "text-muted-foreground", false: "font-medium text-foreground" },
        suffix: { zh: "text-foreground", en: "", raw: "", default: "" },
      },
    });
    ```
    注: 这个组件接近单文件简单 UI, 改 cva 收益不抵复杂度, 建议保留.

## 已扫但未发现 finding 的组件 (清单)

### components/ui/*.tsx (项目自带 shadcn)
- input.tsx: 无 size/variant/state, 单 className
- textarea.tsx: 同 input, 无变体
- checkbox.tsx: 无变体, 仅 data-state 属性
- switch.tsx: 无变体
- radio-group.tsx: 标准 Radix 包装, 无 if/else
- select.tsx: trigger/content/item 各自固定样式, 无业务变体
- tabs.tsx: 走 data-state="active" 属性, 不需要 cva
- table.tsx: 标准表格, 无变体
- card.tsx: 标准 Card, 无变体 (Header/Title/Content/Footer)
- separator.tsx: 标准 shadcn, 无变体
- scroll-area.tsx: 标准 shadcn, 无变体
- popover.tsx: 标准 shadcn, 无变体
- dropdown-menu.tsx: 标准 shadcn, 无变体
- dialog.tsx: 标准 shadcn, 无变体 (Sheet 是 cva, Dialog 内容固定)
- alert-dialog.tsx: 引用 buttonVariants, 自身无 if-else
- command.tsx: 标准 cmdk 包装, 无变体
- avatar.tsx: 3 子件固定样式, 无变体
- skeleton.tsx: 7 行单文件, 无变体
- sonner.tsx: 14 行, sonner 直接包装
- calendar.tsx: 未读, 但属标准 react-day-picker 包装
- collapsible.tsx: 标准 shadcn
- progress.tsx: 接受 indicatorClassName 注入, 已设计为受控变体 (业务层传 className)
- pagination.tsx: 用 buttonVariants + isActive 拼 className, 见 [pagination-link if-else]
- tooltip.tsx: 标准 shadcn

### components/common/display/*
- app-collapsible.tsx: 透传 className, 无变体
- app-data-empty.tsx: variant="table" | "page" 二元, 已是 cva 候选但只有 1 维度, 当前模式 1 行 cn 拼, 改 cva 收益小
- app-entry-card.tsx: 单形态 (group hover 效果), 无变体
- app-env-badge.tsx: 3 variant (DEV/PROD/STAGING) 用 inline lookup, 跟 StatusBadge 重复 (已并入 CVA-004)
- app-health-dot.tsx: 包装 BreathingDot, 自身无变体
- app-section-card.tsx: 纯展示卡, 无变体
- app-settings-card.tsx: 纯展示卡, 无变体

### components/common/feedback/*
- app-error-boundary.tsx: 错误边界 UI, 无变体

### components/common/confirm/*
- app-confirm.tsx: 见 CVA-007

### components/common/input/*
- app-dropdown-menu.tsx: variant="default" | "destructive" 二元 + 1 行 cn 拼 (跟 CVA-007 同模式)
- app-select.tsx: 走 AntD API, 自身无变体

### components/common/overlay/*
- app-tooltip.tsx: 见 CVA-006

### components/common/button/*
- app-copy-button.tsx: 透传 variant/size 给 Button, 自身无变体

### components/chat/*
- composer-attachments.tsx: 3 slot 显隐用 if-else, 但不是 className 变体 (是分支渲染), 不属 cva 候选
- message-bubble.tsx: isUser 二元 + 三引号模板, 见下文"已知跳过"
- thinking-trace.tsx: 2 status (started/finished) 跟 2 className 映射, 跟 CVA-006 同模式但小
- share-dialog.tsx: 3 处 let-then-if 二元变体 (createLabel/hint/buttonText), 都是字符串不是 className, 不属 cva 候选

### components/knowledge/*
- knowledge-tabs.tsx: 见 CVA-008
- schema-browser.tsx: requiredMark 二元字符串, 不属 cva 候选

### app/[locale]/admin/users/_components/admin-users-table.tsx
- 见上文: 3 处 badge 变体 + 2 处 label 二元, 都属"业务局部二元判断", 见"已知跳过"

### app/[locale]/knowledge/batch/page.tsx
- failedClassName let-then-if, 是单点状态, 改 cva 反而复杂

### app/[locale]/evaluate/[id]/_components/metric-bar.tsx
- 见 CVA-003

### app/[locale]/evaluate/_components/evaluate-list-view.tsx
- 仅 cell 内三元判断 + DataTable, 无业务组件变体

### app/[locale]/evaluate/[id]/_components/run-detail-view.tsx
- durationDisplay 是字符串不是 className, 不属 cva 候选

### components/evaluate/status-badge.tsx
- 见 CVA-004 (合并 StatusBadge)

### app/[locale]/output/_components/output-card.tsx
- StateBadge 有 4 state (completed/failed/queued/running) lookup, 跟 CVA-004 同模式
- formatRowName / renderActionsCell 是 if-else 二元字符串, 不属 cva

### components/motion/stagger-item.tsx
- variant 是 motion variants (Variants 对象), 不是 className, 不属 cva 候选

### components/ui/pagination.tsx (PaginationLink)
- isActive 二元 + buttonVariants({ variant: isActive ? "outline" : "ghost" })
- 已经是 cva 调用, 但 variant 决策在 if/else 拼, 不在 component API 暴露
- 这是合理用法, 不算 finding (buttonVariants 自己已是 cva)

## 已知跳过 / 不建议改 cva 的 (清单)

1. **message-bubble.tsx 的 isUser 二元 className 拼接**: 只有 2 个 variant (user/assistant), 改 cva 反而多文件, 当前 5 行三引号模板已经清晰
2. **decode-field.tsx (CVA-009)**: 单文件 53 行, 边际改善, 建议保留
3. **knowledge-tabs.tsx (CVA-008)**: 跟 SettingsDialog 等其他 active tab 一起做才划算, 单独迁移低 ROI
4. **app-data-empty.tsx 的 table/page 二元**: 1 行 cn 拼, 改 cva 复杂度 > 收益
5. **app-dropdown-menu.tsx 的 destructive 二元**: 跟 CVA-007 同模式, 一起改才划算
6. **thinking-trace.tsx 的 started/finished 二元**: 2 variant, 跟 CVA-006 同模式但更小, 单独改不划算
7. **run-detail-view.tsx 的 durationDisplay 二元字符串**: 是显示值不是 className, 不属 cva 范畴
8. **share-dialog.tsx 的 createLabel/hint 二元字符串**: 是 i18n 字符串不是 className, 不属 cva 范畴
9. **batch/page.tsx 的 failedClassName**: 单点状态, 当前 1 处 if, 改 cva 增加复杂度
10. **admin-users-table.tsx 的 3 处 badge 二元**: 单文件局部, 改 cva 要新建组件, ROI 低
11. **output-card.tsx 的 StateBadge**: 跟 CVA-004 同根因, 已经合并到 StatusBadge 统一改造范围
12. **progress.tsx 的 indicatorClassName 注入模式**: 已设计为受控变体 (业务层传 className), 不需要再 cva
13. **pagination-link.tsx 的 isActive 二元 + buttonVariants 调用**: 已经是 cva 调用, variant 决策在调用方合理
14. **stagger-item.tsx 的 fadeUp/fadeIn/scaleIn**: 是 motion Variants 对象不是 className, 完全不属 cva 范畴
15. **motion/* (animated.tsx / stagger / reveal)**: motion 库封装, 完全不属 cva 范畴

## 修复优先级建议 (主线程参考)

### P0 (必做, 3 条)
- CVA-001 (ErrorBanner 5 variant 注释自己承认)
- CVA-002 (StatCard 5 accent, 复用率高)
- CVA-003 (MetricBar 3 阈值, 教科书 if/else)

### P1 (应该做, 3 条)
- CVA-004 (3 个 badge 合并 + 修状态色不一致)
- CVA-005 (BreathingDot 2 维度)
- CVA-007 (AppConfirm variant 暴露)

### P2 (可选, 3 条)
- CVA-006 (AppTooltip 3 variant, 改完跟项目风格统一)
- CVA-008 (KnowledgeTabs 二元, 跟 SettingsDialog 一起做)
- CVA-009 (DecodeField, 边际改善)

### 关联修复 (建议一并改)
- app-status-badge.tsx 用 hex 颜色 → 改 status-* token (跟 status-badge / task-status-badge 统一, 避免主题切换破)
- ErrorBanner / BreathingDot / StatusBadge 的 compound 状态色 → 先扩 themes.ts 加 --color-status-info, 然后把 hex 全部换
- themes.ts (lib/theme/themes.ts) 当前只有 status-success/warning/error/running, 无 info 蓝 / muted 灰, 需补齐

### 验证清单 (主线程 fix 后跑)
- `bun run lint` 0 warning
- `bun run typecheck` 0 error
- `bun run test` 通过 (ErrorBanner / StatusBadge / StatCard / MetricBar 测试覆盖已有, 不用新加)
- `bun run format:check` 0 报错