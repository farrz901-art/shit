# P3 - cva 改写 spec 草稿 (2026-06-28)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D5 Frontend (cva 专项)
> 关联 checklist: [docs/audit/2026-06-28-findings.md](../../2026-06-28-findings.md)

## 范围

9 条 finding (3 high + 3 medium + 3 low):
- CVA-001 (high): ErrorBanner 5 variant lookup map
- CVA-002 (high): StatCard 5 accent lookup map (12 处调用)
- CVA-003 (high): MetricBar 3 阈值 if/else 链
- CVA-004 (medium): 3 个 StatusBadge 合并 + 状态色不一致修复
- CVA-005 (medium): BreathingDot 2 维度 cva
- CVA-006 (medium): AppTooltip 3 variant cva
- CVA-007 (medium): AppConfirm variant 暴露 cva
- CVA-008 (low): KnowledgeTabs active 二元
- CVA-009 (low): DecodeField rich/suffix 二元

## 修复策略

### 前置 (跨 finding 关联修复, 必须先做)

1. **扩 themes.ts** (`packages/web/lib/theme/themes.ts`):
   - 加 `--color-status-info` (蓝, hex 蓝 `border-blue-500/50` 替代)
   - 加 `--color-status-muted` (灰, hex 灰替代)
   - Tailwind v4 同步: `tailwind.config.ts` 加 `status-info: "var(--color-status-info)"` 等
   - 关联: CVA-001 (info) / CVA-004 (cancelled/archived 灰) / CVA-005 (muted)

2. **修 app-status-badge.tsx hex 颜色**:
   - `bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400` → `bg-status-error/10 text-status-error`
   - 关联: CVA-004 (合并前提)

### P0 (3 条 high, 必做)

按 ROI 排序:
- **CVA-002 (StatCard)** — 12 处调用, ROI 最高, 1 文件 1 cva 模板, 推荐先做
- **CVA-001 (ErrorBanner)** — 注释自己承认 lookup 模式, 16 处调用 (全项目 ErrorBanner), ROI 极高
- **CVA-003 (MetricBar)** — 1 文件 56 行, 改完 80 行, ROI 中等

### P1 (3 条 medium, 应该做)

- **CVA-004 (3 StatusBadge 合并)** — 重要! 修 hex 颜色不一致 + 合并重复 lookup
- **CVA-005 (BreathingDot)** — 2 维度, cva compoundVariants 教科书用例
- **CVA-007 (AppConfirm)** — 补 default variant 显式声明 (避免 "中性确认" 按钮变 primary 蓝)

### P2 (3 条 low, 可选)

- **CVA-006 (AppTooltip)** — 单文件, 改完跟项目风格统一
- **CVA-008 (KnowledgeTabs)** — 跟 SettingsDialog 等其他 active tab 一起做才划算
- **CVA-009 (DecodeField)** — 单文件 53 行, 改完 ROI 负, 建议保留

## 实施顺序 (推荐)

1. 前置: 扩 themes.ts (status-info / status-muted) + 修 app-status-badge hex 颜色
2. P0: CVA-002 → CVA-001 → CVA-003 (按 ROI 排序)
3. P1: CVA-004 (最大, 合并 + 修不一致) → CVA-005 → CVA-007
4. P2: CVA-006 → (跟 SettingsDialog 一起) CVA-008 → (评估 ROI 后决定) CVA-009
5. 每个 finding 改完跑 `bun run lint / typecheck / test` + commit `refactor(<scope>): cva 改写 <component> (<ID>)`

## cva 改写标准模式 (项目惯例)

跟 [components/ui/button.tsx](../../packages/web/components/ui/button.tsx) 对齐:

```ts
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// 1. 定义 cva 模板
const xxxVariants = cva(
  "base classes 永远会加",
  {
    defaultVariants: { variant: "default", size: "default" },
    variants: {
      variant: { /* ... */ },
      size: { /* ... */ },
    },
  },
);

// 2. TS props 类型
export interface XxxProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof xxxVariants> {
  // 自定义 props
}

// 3. 组件 (forwardRef)
const Xxx = React.forwardRef<HTMLDivElement, XxxProps>(
  ({ className, variant, size, ...props }, ref) => (
    <div ref={ref} className={cn(xxxVariants({ variant, size, className }))} {...props} />
  ),
);
Xxx.displayName = "Xxx";

export { Xxx, xxxVariants };
```

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- 其他 P 维度 finding (P0 security / P1 error / P2 data / P4 arch) — 本 audit 只扫 cva
- 项目 cva 升级 (v0.7+ 新增的 `compoundVariants` 改进) — 当前 v0.7 够用
- 第三方库 (motion Variants) cva 化 — 完全不属 cva 范畴 (Variants 是 JS 对象)

## 风险 & 缓解

| 风险 | 缓解 |
|------|------|
| cva 改写后 className 顺序变化, 影响 Tailwind 优先级 | 测试覆盖 9 个组件都有 .test.tsx, 跑 `bun run test` |
| hex 换 status token 后暗色模式破 | 视觉回归测试 (manual, 跑 `bun run dev` 看 dark/light) |
| StatCard 12 处调用, 改 cva 后 prop 兼容性 | cva VariantProps 是 string union, 传错编译报错, 比原来更安全 |
| AppConfirm 改 cva 后, 调用方 `variant` prop 名冲突 | cva 暴露同名 `variant`, 跟 shadcn Button variant 对齐, 无冲突 |
| themes.ts 扩 status-info / status-muted 后, 已有的 16 处 ErrorBanner 调用方要不要改 | 渐进迁移: 加 token 不删 hex, 新 cva 模板用 token, 老 lookup map 用 hex 保持兼容 (后续清理) |

## 验证清单 (修复后跑)

```bash
cd packages/web
bun run lint         # 必须 0 warning
bun run typecheck    # 必须 0 error
bun run test         # 全部通过 (测试覆盖已有, 不用新加)
bun run format:check # 0 报错
```

## 关联文档

- 完整 finding 列表: [d5-cva-audit.md](../d5-cva-audit.md) §Findings
- 审计汇总: [AUDIT-REPORT.md](../AUDIT-REPORT.md)
- 项目 cva 范例: [components/ui/button.tsx](../../packages/web/components/ui/button.tsx)
- 项目封装约定: [packages/web/CLAUDE.md §封装组件](../../packages/web/CLAUDE.md)
- 已知跳过清单: [d5-cva-audit.md §已知跳过](../d5-cva-audit.md#已知跳过--不建议改-cva-的-清单)
