# AUDIT-REPORT — cva 改写专项审计 (2026-06-28)

> 专项审计, 不是 6 维度全栈 audit. 范围: `packages/web/` 内可用 class-variance-authority (cva) 改写的代码.
> 来源: 1 个 D5 Frontend subagent 扫描 + 3 条 high finding adversarial verify + 主线程独立 reconnaissance 交叉验证.
> 工具调用: subagent 33/40, verifier 14/15.

## 元信息

- 项目根: c:/doc/Code/rag/packages/web
- 扫描范围: 28 个文件 (8 个 cva 模板 + 11 个高怀疑候选 + 9 个 ui/* 未 cva 化组件)
- 总 finding 数: **9 条** (3 high + 3 medium + 3 low)
- 已 verify (high): 3 / 3 = 100% verified
- 已 refuted: 0
- 误报率: 0%
- 已知跳过: 15 条 (单文件简单 / 字符串不是 className / 已是 cva 调用 / motion Variants 对象)

## 汇总表

| ID | 维度 | Severity | Confidence | Verified | 标题 | file:line |
|----|------|----------|------------|----------|------|-----------|
| CVA-001 | frontend | high | high | ✅ | ErrorBanner 用 lookup map 模拟 5 variant | components/common/feedback/app-error-banner.tsx:36 |
| CVA-002 | frontend | high | high | ✅ | StatCard accent 5 色用 lookup map (12 处调用) | components/common/display/app-stat-card.tsx:22 |
| CVA-003 | frontend | high | high | ✅ | MetricBar 用 if/else 链 + 3 阈值拼 4 状态 | app/[locale]/evaluate/[id]/_components/metric-bar.tsx:17 |
| CVA-004 | frontend | medium | high | - | 3 处 StatusBadge 重复 + 状态色不一致 | components/common/display/app-status-badge.tsx:13 |
| CVA-005 | frontend | medium | high | - | BreathingDot 双 map (color + size) 应改 cva | components/common/display/app-breathing-dot.tsx:19 |
| CVA-006 | frontend | medium | high | - | AppTooltip 3 variant lookup | components/common/overlay/app-tooltip.tsx:29 |
| CVA-007 | frontend | medium | high | - | AppConfirm variant 二元 if 拼 destructive class | components/common/confirm/app-confirm.tsx:48 |
| CVA-008 | frontend | low | high | - | KnowledgeTabs linkClass let-then-if 二元 | components/knowledge/knowledge-tabs.tsx:48 |
| CVA-009 | frontend | low | medium | - | DecodeField fieldClass let-then-if 二元 | app/[locale]/decode/decode-field.tsx:24 |

## 6 维度详情

### D5 Frontend (cva 改写专项)

**现状**:

- 项目 cva 使用率 8/231 = **3.5%** (8 个 ui/* 组件, 全部 shadcn 标准模板)
- 业务组件 (`components/common/*`, `app/[locale]/**`) 大量用 `Record<Variant, string>` lookup map 或 `let ... = ...; if (...) ... = ...` 模式
- 项目 themes.ts (`lib/theme/themes.ts`) 当前只有 status-success / warning / error / running token, **缺 status-info (蓝) / status-muted (灰)**

**典型反模式** (跟项目 i18n 风格一致: 中文 key + identity value, 反例: 直接拼字符串):

```ts
// 反例 1: lookup map (CVA-001 / CVA-002 / CVA-004 / CVA-006)
const variantColorClass: Record<ErrorBannerVariant, string> = {
  destructive: "border-destructive/50 text-destructive ...",
  info: "border-blue-500/50 text-blue-700 ...",
  ...
};
return <Alert className={cn(variantColorClass[variant], className)}>...</Alert>;

// 反例 2: let-then-if (CVA-007 / CVA-008 / CVA-009)
let linkClass = "text-muted-foreground hover:text-foreground";
if (active) {
  linkClass = "border-b-2 border-clay text-foreground";
}

// 反例 3: 颜色硬编不一致 (CVA-004 子项)
const STATUS_COLORS = {
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",  // ❌ 不用 status-* token
};
```

**正向 (项目 cva 标准模板)**:

```ts
// 正例 1: button.tsx (8 个 cva 之一)
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 ... [&_svg]:size-4",
  {
    defaultVariants: { size: "default", variant: "default" },
    variants: {
      size: { default: "h-10 px-4 py-2", icon: "h-10 w-10", lg: "...", sm: "..." },
      variant: { default: "bg-primary ...", destructive: "bg-destructive ...", ... },
    },
  },
);
```

**Spec 草稿映射**:

- **P3-frontend-cva.md** ← 本 audit 所有 9 条 finding (3 high + 3 medium + 3 low)
- 实施顺序: P0 (3 high) → P1 (3 medium) → P2 (3 low), 关联修复先做 themes.ts 扩 token

## 关键关联修复 (跨 finding)

实施任意 P0 改写前, 必须先做这些**前置改动**:

1. **扩 themes.ts** (`packages/web/lib/theme/themes.ts`):
   - 加 `--color-status-info` (蓝, 当前 hex 蓝 `border-blue-500/50` 用)
   - 加 `--color-status-muted` (灰, 当前 hex 灰 `border-gray-100` 用)
   - 关联 finding: CVA-001 (info) / CVA-004 (cancelled/archived 灰) / CVA-005 (muted 灰)

2. **修 app-status-badge.tsx hex 颜色** (跟其他 2 个 StatusBadge 统一):
   - `bg-red-100 text-red-800` → `bg-status-error/10 text-status-error`
   - 关联 finding: CVA-004 子项

3. **AppConfirm 补 default variant 显式声明** (避免 "中性确认" 按钮变 primary 蓝):
   - 关联 finding: CVA-007

## 详细 Findings (YAML)

完整 finding 列表在 [`d5-cva-audit.md`](d5-cva-audit.md) §Findings (9 条 YAML). 高 / 中 / 低优先级和修复 sketch 都在那里.

## Spec 草稿

- [P3-frontend-cva.md](P3-frontend-cva.md) — 9 条 finding 改写 spec 草稿 (未实施)

## 验证清单 (修复后跑)

```bash
cd packages/web
bun run lint         # 0 warning
bun run typecheck    # 0 error
bun run test         # 全部通过 (ErrorBanner / StatusBadge / StatCard / MetricBar 测试覆盖已有, 不用新加)
bun run format:check # 0 报错
```

## 关联文档

- [d5-cva-audit.md](d5-cva-audit.md) — 完整扫描报告 (含元信息 / 9 条 finding / 已扫但未发现清单 / 已知跳过清单)
- [P3-frontend-cva.md](P3-frontend-cva.md) — 实施 spec 草稿
- 项目 cva 模板: [components/ui/button.tsx](../../packages/web/components/ui/button.tsx) / [badge.tsx](../../packages/web/components/ui/badge.tsx) / [toggle.tsx](../../packages/web/components/ui/toggle.tsx) / [sheet.tsx](../../packages/web/components/ui/sheet.tsx)
- 项目封装约定: [packages/web/CLAUDE.md §封装组件](../../packages/web/CLAUDE.md) / §反模式
