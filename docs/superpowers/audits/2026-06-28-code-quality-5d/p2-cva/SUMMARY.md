# P2 维度审计总报告 — ② CVA 重写机会

**审计日期**: 2026-06-28
**范围**: `packages/web/` 全量源文件（排除 `.test.tsx`/`.test.ts`/`.stories.tsx`）
**模式**: 4 个 agent 并行扫描（A=common+ui, B=业务组件, C=页面+API, D=lib+其它）

---

## 1. 总体扫描概览

| 维度 | 数值 |
| --- | --- |
| 总扫描文件 | ~365 (78 common+ui + 47 业务组件 + 153 app + 89 lib+其它) |
| 已用 CVA 的文件 | **7** (全部在 `components/ui/` shadcn 标准件) |
| `app/` 目录 CVA 使用 | **0** |
| `common/` 目录 CVA 使用 | **0** |
| 业务组件 CVA 使用 | **0** |
| 🔴 高 ROI 建议重写 | **3** |
| 🟡 中 ROI 可选重写 | **6** |
| ❌ 不建议重写 | **356+** |
| 净省代码量 | **接近 0**（CVA 模板成本 ≈ 节省） |

---

## 2. 各 Agent 报告位置

| Agent | 范围 | 文件数 | 报告 |
| --- | --- | --- | --- |
| A | common + ui 封装实现层 | ~75 | [`A-common-ui-report.md`](p2-cva/A-common-ui-report.md) |
| B | 业务组件（chat/knowledge/...） | 47 | [`B-business-components-report.md`](p2-cva/B-business-components-report.md) |
| C | app/ 页面+API+_components | 153 | [`C-pages-report.md`](p2-cva/C-pages-report.md) |
| D | lib/ + const/ + i18n/ + scripts/ + proxy | 89 | [`D-lib-others-report.md`](p2-cva/D-lib-others-report.md) |

---

## 3. 已用 CVA 的文件（现状）

| 文件 | variants | 备注 |
| --- | --- | --- |
| `components/ui/button.tsx` | size(4) + variant(6) | shadcn 标准 |
| `components/ui/badge.tsx` | variant(4) | shadcn 标准 |
| `components/ui/alert.tsx` | variant(2) | shadcn 标准 |
| `components/ui/toggle.tsx` | size(3) + variant(2) | shadcn 标准 |
| `components/ui/sheet.tsx` | side(4) | shadcn 标准 |
| `components/ui/label.tsx` | (无 variant, 仅 base) | shadcn 标准 |
| `components/ui/empty.tsx` | variant(2) | shadcn 标准 |

**结论**: ui/ 7 个文件已用 CVA，common/ 与业务组件 0 个用 CVA，**app/ 0 个用 CVA**。

---

## 4. 🔴 高 ROI 建议（3 个）

### 4.1 `components/evaluate/status-badge.tsx` — 5 状态强类型化

- **当前**: 3 个 Record map（`CUSTOM_STYLE` / `LABEL` / `VARIANT`）+ 字符串模板拼接
- **问题**: `CUSTOM_STYLE: Record<string, string>` 是**弱类型**，加新状态时漏写不报错
- **CVA 重写**: 1 个 cva() + VariantProps 推导 status union
- **收益**: 类型安全 + 新增 variant 成本从 3 处降到 1 处
- **行数变化**: +3 行（CVA 模板），但类型化收益显著
- **判定**: 🔴 **强烈建议**

### 4.2 `components/feedback/app-error-banner.tsx` — 5 variant × 2 lookup table

- **当前**: `defaultIcon: Record<Variant, LucideIcon>` + `variantColorClass: Record<Variant, string>` + 内联三元
- **问题**: 新增 variant 需同步 3 处（icon map / color class / 三元）
- **CVA 重写**: 1 个 cva() + CompoundVariants 处理 loading 的 animate-spin
- **收益**: 新增 variant 成本 3 处 → 1 处
- **行数变化**: +5 行（CVA 模板）
- **判定**: 🔴 **建议重写**

### 4.3 `app/[locale]/health/_components/system-resources.tsx` — 4 个独立 if 链生成颜色

- **当前**: `cpuProgressColor` / `memProgressColor` / `gpuProgressColor` / `statusTextColor` 都是 if 链返回 className
- **问题**: 4 个函数同模式（阈值 → className），重复实现
- **CVA 重写**: 1 个 `resourceLevelVariants` cva()，4 处复用
- **收益**: 净省 ~25 行（4 个 if 链消除为 1 个 cva）
- **判定**: 🔴 **净省代码量最高**

---

## 5. 🟡 中 ROI 可选（6 个）

| 文件 | 当前实现 | CVA 收益 | 判定 |
| --- | --- | --- | --- |
| `components/common/display/app-status-badge.tsx` | 7 status colors lookup | 净省 5 行 | 🟡 |
| `components/common/display/app-task-status-badge.tsx` | 6 state colors lookup | 净增 5 行但 defaultVariants 兜底 | 🟡 |
| `components/common/display/app-stat-card.tsx` | 5 accent colors lookup | 净省 7 行 | 🟡 |
| `components/json/diff-row.tsx` | 3 Record maps（type → bg/color/sign） | 类型化收益（非行数） | 🟡 |
| `components/chat/message-bubble.tsx` | user/ai 2 状态气泡 + 容器 | 净省 3 行（仅在加 system/error 时） | 🟡 偏下 |
| `app/[locale]/evaluate/[id]/_components/metric-bar.tsx` | getColor(val) 3 档 | 单属性 overkill | 🟡 |

---

## 6. ❌ 不建议重写（大量）

### 6.1 motion/ (13 files) — 全部不适合
- 全部是 motion 原子组件，样式极少
- framer-motion 自身已有 variants prop，**不要替换为 CVA**

### 6.2 lib/ 区 (89 files) — 0 个适合
- 纯 TS 逻辑层（API 客户端 / hooks / store / 工具）
- 与 UI 样式变体管理无关
- 仅 2 个 Provider (app-data.tsx, intl-wrapper.tsx) 不含 className

### 6.3 app/ 页面层 (37 page.tsx) — 全部不适合
- 全部是 server component 组合层
- 无 variant 概念，只是 fetch + render wrapper

### 6.4 业务组件大量 — 45+ 文件不建议
- 单一 className / 单条件分支 / 渲染分支（不是 className）
- CVA 模板成本（~8 行）大于节省
- 当前 `cn()` + Record map 已是合适表达方式

### 6.5 已是 lookup map 不建议迁
- `app-breathing-dot.tsx` — 2 个 lookup (颜色+尺寸) 已清晰，CVA 化要引入 `ping`/`dot` 子选择器约定
- `entry-card-grid.tsx` / `stats-grid.tsx` — 2 项 lookup 已是最简表达
- `data-table-pagination.tsx` — 用 const `DISABLED_OPACITY` / `CURSOR_POINTER`，已是最佳实践

---

## 7. 真实 ROI 分析（重写价值）

### 7.1 项目当前 CVA 模式现状
项目已遵循**项目规约**（业务 enum 走 lookup 字典模块，详见 `packages/service/src/lookups/README.md`），用 `Record<X, string>` + `cn()` 是**约定俗成的最佳实践**。盲目 CVA 化反而破坏一致性。

### 7.2 CVA 真正的价值不在行数
- **类型安全**: `Record<string, string>` 是弱类型，VariantProps 强类型 — 加新状态时编译器兜底
- **扩展性**: 新增 variant 成本从多处同步 → 1 处添加
- **可发现性**: API 自动推导，IDE 自动补全

### 7.3 但本项目 99% 的组件不需要这些
- `cn("base", className)` 透传占大多数
- 单条件分支占大多数
- 渲染分支（if 返回 JSX）CVA 完全不适用
- 业务组件的"状态"通常映射到**多个独立元素**（颜色+图标+文案），不是单一元素的 className

---

## 8. 核心建议（推荐执行）

### ✅ 推荐做（3 个高 ROI）

1. **`components/evaluate/status-badge.tsx`** — 强类型化 5 状态，🔴 推荐
2. **`components/common/feedback/app-error-banner.tsx`** — 5 variant 抽 CVA，🔴 推荐
3. **`app/[locale]/health/_components/system-resources.tsx`** — 4 个 if 链 → 1 个 cva，🔴 推荐（净省 ~25 行）

### ⚠️ 可选（6 个中 ROI，按需选择）

不强推，触碰这些组件时顺手改即可。**不要为了 CVA 而 CVA**。

### ❌ 不动（356+ 文件）
- 全部 motion 组件
- 全部 lib/ 区
- 全部 app/ page.tsx
- 单一 className 透传组件
- 已是 lookup map 最佳实践的组件

---

## 9. 重大发现：硬编码颜色反模式（违反主题系统）🚨

**用户反馈**: status 颜色应跟主题系统结合，不应硬编码。

### 9.1 当前主题系统现状（globals.css）

项目已有 **`bg-status-*` token 系统**：
```css
--color-status-success: hsl(var(--status-success));
--color-status-warning: hsl(var(--status-warning));
--color-status-error: hsl(var(--status-error));
--color-status-running: hsl(var(--status-running));
```

亮/暗主题切换通过 CSS 变量层完成。`bg-status-warning/10` 这种透明度语法 Tailwind v4 支持。

### 9.2 反模式：硬编码 Tailwind 色阶

| 文件 | 硬编码 | 应改为 |
| --- | --- | --- |
| `components/common/display/app-status-badge.tsx` | `bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400` | `bg-status-warning/10 text-status-warning` |
| `components/common/display/app-status-badge.tsx` | `bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400` | `bg-status-running/10 text-status-running` |
| `components/common/display/app-status-badge.tsx` | `bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400` | `bg-status-success/10 text-status-success` |
| `components/common/display/app-status-badge.tsx` | `bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400` | `bg-status-error/10 text-status-error` |
| `components/json/diff-row.tsx` | `bg-green-950/20 dark:bg-green-950/40` / `text-green-500` | `bg-status-success/20` / `text-status-success` |
| `components/json/diff-row.tsx` | `bg-red-950/20 dark:bg-red-950/40` / `text-red-500` | `bg-status-error/20` / `text-status-error` |

### 9.3 为什么这是真问题

1. ❌ **硬编码不响应主题切换**：dark: 前缀只覆盖 Tailwind 默认 dark mode，**不响应项目自实现的多主题系统**（明亮/暗色/未来可能加"高对比度"等）
2. ❌ **跨组件颜色不一致**：`yellow-100` / `moss` / `ochre` 等用色哲学不统一
3. ❌ **新增主题成本倍增**：每加一个主题，所有硬编码处都要改
4. ❌ **违反项目规约**：CLAUDE.md 明确"状态色: 用 `bg-status-{success|warning|error|running}/10` 替代 `bg-{emerald|amber|rose|blue}-100`"

### 9.4 正确的方案（应优先用）

**不需要 CVA**，直接在 globals.css 配合 Tailwind 主题变量：

```css
/* globals.css 已有 (line 60-63) */
--color-status-success: hsl(var(--status-success));
--color-status-warning: hsl(var(--status-warning));
--color-status-error: hsl(var(--status-error));
--color-status-running: hsl(var(--status-running));
```

```tsx
// components/common/display/app-status-badge.tsx
const STATUS_COLORS: Record<StatusType, string> = {
  pending:   "bg-status-warning/10 text-status-warning border-status-warning/30",
  running:   "bg-status-running/10 text-status-running border-status-running/40 animate-pulse",
  completed: "bg-status-success/10 text-status-success border-status-success/30",
  failed:    "bg-status-error/10 text-status-error border-status-error/30",
  cancelled: "bg-muted text-muted-foreground",
  active:    "bg-status-success/10 text-status-success border-status-success/30",
  archived:  "bg-muted text-muted-foreground",
};
```

**优势**：
1. ✅ **亮/暗主题自动切换**（CSS 变量层）
2. ✅ **未来加新主题零成本**（如"高对比度"、"护眼"）
3. ✅ **跨组件颜色一致性**
4. ✅ **不需要 CVA** — Record map 是合适的表达方式
5. ✅ **代码量减少** — 删 `dark:bg-*` 前缀每行省 1/3 长度

### 9.5 优先级（这比 CVA 更重要）

| 行动 | ROI | 备注 |
| --- | --- | --- |
| **`app-status-badge.tsx` 改用 status-* token** | 🔴 **极高** | 2 个文件 / 14 行硬编码替换 / 自动主题切换 |
| **`diff-row.tsx` 改用 status-* token** | 🔴 **极高** | JSON 视图核心组件 |
| 全项目扫描其它硬编码色阶 | 🟡 中 | 应作为后续审计 |

### 9.6 真正的优化路径（重新定义）

**之前的 CVA 建议 + lookup 字典合并都不是最优解**。**最优解是**:

1. **第一步（最优先）**: 把硬编码色阶迁到 `bg-status-*` token（自动响应主题）
2. **第二步（可选）**: 若仍想 CVA 化，在 token 化基础上做（边际收益小）
3. **第三步（不必）**: 合并 lookup 字典（如果都用 token，重复定义就消失了）

---

## 10. ROI 总结（修正版）

| 行动 | 文件数 | 净省/收益 | ROI |
| --- | --- | --- | --- |
| 🚨 **硬编码颜色 → status token** | 2 | -10 行 + 自动主题切换 | 🔴 极高 |
| 🔴 高 ROI 改 CVA（status-badge/app-error-banner/system-resources） | 3 | +8 行（类型化收益） | 🔴 高（但 token 化后边际收益小） |
| 🟡 中 ROI 按需改 | 6 | 0 | 🟡 中 |
| ❌ 不动 | 356+ | 0 | — |

---

## 11. P2 关键洞察（给后续审计参考）

1. **业务 enum 走 lookup 字典** 是项目规约 — 任何"枚举 → 样式"模式应优先用 Record map
2. **CVA 适用场景**: 跨文件复用的视觉原语 + 类型安全需求 + 高频扩展
3. **CVA 不适用**: 单一 className 透传、单条件分支、渲染分支、业务编排组件
4. **CVA 模板成本 ~8 行** — 单文件改造至少省 5 行才算正向 ROI
5. **app/ 层完全不用 CVA** — server component 组合层无 variant 概念

---

## 12. 后续审计建议

- **P3 设计模式**: 重点关注 `lookups/` 字典合并、策略模式（多 provider/多 API）、单例模式（配置/全局状态）
- **P4 函数式写法**: 重点关注 `lib/hooks/*`、`lib/api/*` 工具函数（业务逻辑层才有函数式重写机会）
- **P5 注释**: 全项目统一扫描（包括 lib/ 区）