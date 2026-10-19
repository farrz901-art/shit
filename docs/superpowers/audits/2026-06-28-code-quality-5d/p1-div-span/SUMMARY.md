# P1 维度审计总报告 — ① div/span 提取样式组件

**审计日期**: 2026-06-28
**范围**: `packages/web/` 全量源文件（排除 `.test.tsx`/`.test.ts`/`.stories.tsx`/`e2e/`/`tests/`/`messages/`）
**模式**: 4 个 agent 并行扫描（A=common+ui, B=业务组件, C=页面+API, D=lib+其它）

---

## 1. 总体扫描概览

| 维度 | 数值 |
| --- | --- |
| 总源文件数 | **568** (.tsx) + 88 (.ts, lib/api/store 等) = ~656 个非测试源文件 |
| 含 div/span 的文件 | **237** (业务 UI) |
| 纯逻辑/配置文件（无 UI） | **419** (D 报告全 0；C 报告 API routes 25 个；其余 hooks/api/store/theme) |
| 发现重复 pattern（跨文件 / 同文件 ≥2） | **44 类** |
| 可直接替换为已有封装 | **30 处** |
| 建议新封装组件 | **11 个** |
| 已正确使用 `<PageHero>` 的页面 | 9 |
| 已正确使用 `<DataTable>` 的页面 | 9 |
| 已正确使用 `<ErrorBanner>` 的页面 | 9 |
| 仍手写失败/告警条幅的页面 | 5 |

---

## 2. 各 Agent 报告位置

| Agent | 范围 | 文件数 | 报告 |
| --- | --- | --- | --- |
| A | common + ui 封装实现层 | 78 | [`A-common-ui-report.md`](p1-div-span/A-common-ui-report.md) |
| B | 业务组件（chat/knowledge/motion/auth/json/...） | 60 | [`B-business-components-report.md`](p1-div-span/B-business-components-report.md) |
| C | app/ 全部页面+API | 154 | [`C-pages-api-report.md`](p1-div-span/C-pages-api-report.md) |
| D | lib/ + const/ + i18n/ + scripts/ + proxy + next.config | 76 | [`D-lib-others-report.md`](p1-div-span/D-lib-others-report.md) |

---

## 3. 严重度分布（汇总）

| 严重度 | 数量 | 说明 |
| --- | --- | --- |
| 🔴 严重（高频重复 5+） | **6 类** | 跨多文件 / 多处出现的固定 pattern |
| 🟡 中等（重复 3-4） | **12 类** | 跨 3-4 处或特定模块内的重复 |
| 🟢 建议（重复 2） | **26 类** | 同文件重复或独有但值得封装 |

---

## 4. Top-10 高频重复模式（全项目汇总，按 ROI 重排）

> ⚠️ **Top-3 模式 (`space-y-N` / `h-full overflow-y-auto` / `<h1 display>`) 不建议抽组件**：单 className 包组件反而增加复杂度。仅 5/9/4 处仍手写的错误条/PageHero/BackLink 直接迁现有封装即可。

| # | 模式 | 文件数 | 出现次数 | 现有封装 | 建议方案 | ROI |
| --- | --- | --- | --- | --- | --- | --- |
| 🔴 1 | `<div ... border-destructive bg-destructive/5>` 错误条 | 5 | 5 | `<ErrorBanner>` 已存在 | 直接迁 5 处 | 🔴 极高 |
| 🔴 2 | `<h1 className="display text-Nxl">` 手写标题 | 15 | 18 | `<PageHero>` 9 处 | 4 处仍手写迁 PageHero | 🔴 高 |
| 🔴 3 | `<div className="flex justify-end gap-2 pt-2">` 弹框底部 | 8 | 9 | 无 | 新增 `<DialogFooter>` | 🔴 高 |
| 🟡 4 | `<div className="rounded ... border ... bg-muted/30">` 信息块 | 4 | 4 | 无 | 新增 `<AppSubtleCard>` | 🟡 中 |
| 🟡 5 | `<div className="flex items-center gap-2 ... border">` 列表项 | 4 | 6 | 无 | 新增 `<AppListItem>` | 🟡 中 |
| 🟡 6 | `<div ... border-warning bg-warning/5>` 状态容器 | 3 | 3 | 无 | 新增 `<Callout>` | 🟢 低 |
| ⚪ 7 | `<div className="space-y-2/4/6">` 堆叠 | 23 | 35 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 8 | `<div className="h-full overflow-y-auto">` 滚动容器 | 15 | 15 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 9 | `<div className="space-y-6 p-6">` 页面外容器 | 8 | 8 | 无 | **不抽**，保留 div | ⚪ N/A |
| ⚪ 10 | `<p className="text-sm text-muted-foreground">加载中…</p>` | 12 | 12 | `<DataEmpty>` 部分 | DataEmpty 已支持 loading | ⚪ N/A |

---

## 5. 建议新增的封装组件清单（10 个，按 ROI 排序）

> **ROI 判定标准**:
> - **高 ROI**: 单个抽取能省 ≥5 行 OR 集中设计 token OR 跨 ≥3 文件
> - **中 ROI**: 跨 2-3 文件，未来扩展
> - **低 ROI**: 仅 1-2 文件，未来不一定扩展 — **不推荐做**
>
> **明确不推荐**: `<Stack>` `<PageContainer>` `<PageScrollArea>` `<RowActions>` `<FilterBar>` `<PaginationBar>` 这些"把 1-2 个 Tailwind className 包成组件"的提议，**反而增加复杂度**，违反 YAGNI。

### ✅ 推荐做（高 ROI）

| 组件 | 调用方 | 收益 | 来源 |
| --- | --- | --- | --- |
| `<AppDataEmpty variant="destructive">` 扩展 | json-view/diff 5 处 | 加 1 个 prop 省 15 行，统一视觉 | B |
| `<DialogFooter primary destructive cancelLabel>` | 9+ 个 dialog | 集中 cancel/save/destructive 模式，省 ~30 行 | C |
| `<AppListItem>` | chat 列表 4 文件 / 6 处 | 跨组件复用，节省 ~20 行 | B |
| `<AppSubtleCard>` | chat 信息块 4 文件 / 4 处 | 颜色 token 统一，省 ~15 行 | B |
| `<AuthFormContainer>` | login/forgot/reset/invite 4 处 | 同模板复用，省 ~10 行 | C |
| `<Callout variant="warning\|error\|info">` | 3 处 status 容器 | 状态容器统一，省 ~10 行 | C |

### ⚠️ 可选（中 ROI，单文件/小扩展）

| 组件 | 调用方 | 收益 | 来源 |
| --- | --- | --- | --- |
| `<AppSettingsRow>` | settings-dialog 2 处 | 单文件重复但模式稳定，未来可能扩 | B |
| `<AppCodeBlock>` | json-view/diff 2 处 | 同上 | B |

### ❌ 不推荐做（低 ROI，违反 YAGNI）

| 提议 | 原因 |
| --- | --- |
| `<Stack size="sm\|md\|lg">` | `<div className="space-y-N">` 仅 1 个 className，抽组件增加 prop+import+抽象，省 0 行 |
| `<PageContainer>` | 同上，`<div className="space-y-6 p-6">` 1 个 className 没必要包 |
| `<PageScrollArea>` | `<div className="h-full overflow-y-auto">` 1 个 className 包组件是过度抽象 |
| `<RowActions>` | `<div className="flex justify-end gap-2">` 1 个 className |
| `<FilterBar>` | 单调用方 |
| `<PaginationBar>` | 单调用方 |
| `<SettingsCard>` | shadcn `<Card>` 已存在，1 调用方 |

---

## 5.5 真正可节省的代码量（重写 ROI 重新计算）

| 类别 | 文件数 | 节省行数 |
| --- | --- | --- |
| **5 处错误条 → ErrorBanner** | 5 | -25 |
| **4 处 PageHero + 2 处 BackLink 迁移** | 6 | -50 |
| **json-view/diff 5 处 → AppDataEmpty** | 2 | -15 |
| **9 处 DialogFooter 抽取** | 9 | -30 |
| **6 处 AppListItem** | 4 | -20 |
| **4 处 AppSubtleCard** | 4 | -15 |
| **4 处 AuthFormContainer** | 4 | -10 |
| **3 处 Callout** | 3 | -10 |
| **1 处 message-bubble Badge** | 1 | -3 |
| **总计** | **~38 文件** | **~-178 行** |

---

## 6. 可直接替换为已有封装的清单（30 处）

### 6.1 错误条（5 处仍手写）

| 文件 | 当前代码 | 替换为 |
| --- | --- | --- |
| `app/[locale]/health/_components/health-client.tsx` | `<div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-destructive">` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/batch/page.tsx` | `<div className="rounded border ... bg-destructive/10 p-3">` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/triples/_components/triples-form.tsx` | `<div ... border-destructive/30 bg-destructive/5>` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx` | `<div ... border-destructive/30 bg-destructive/5 p-3>` | `<ErrorBanner variant="destructive">` |
| `app/[locale]/evaluate/new/_components/evaluate-new-form.tsx` | `<div ... border-destructive/30 bg-destructive/5>` | `<ErrorBanner variant="destructive">` |

### 6.2 PageHero 仍未迁移（4 处）

| 文件 | 现状 |
| --- | --- |
| `app/[locale]/output/new/page.tsx` | 手写 `<span className="eyebrow">Output</span> + <h1 className="display text-4xl">` |
| `app/[locale]/output/_components/output-list-client.tsx` | 手写 hero |
| `app/[locale]/admin/users/page.tsx` | 手写 `<h1 className="display text-3xl">` |
| `app/[locale]/admin/invites/page.tsx` | 手写 `<h1 className="display text-3xl">` |

### 6.3 BackLink 仍未迁移（2 处）

| 文件 | 现状 |
| --- | --- |
| `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 手写返回链 |
| `app/[locale]/output/[task_id]/[file]/page.tsx` | 手写返回链 |

### 6.4 AppDataEmpty 可直接替换（5 处，json-view/diff）

`components/json/json-view.tsx:31+46` 和 `components/json/json-diff.tsx:46` 共 5 处：
- 空态：`<div className="flex items-center justify-center rounded-lg border p-8 text-muted-foreground">` → `<AppDataEmpty>`
- 错误态：`<div ... text-destructive>` → 给 AppDataEmpty 加 `variant="destructive"`

### 6.5 Badge 替换手写徽章（1 处）

`components/chat/message-bubble.tsx:105` interrupted badge → shadcn `<Badge variant="outline" className="bg-status-warning/10 text-status-warning">`

---

## 7. 不建议改动的 Pattern（A 报告的 6 类 shadcn 标准模板）

shadcn/ui 标准实现层（`components/ui/`）的以下 pattern 是上游设计，**不建议改**：

1. 弹框 close 按钮（X）— Dialog/Sheet 重复 2 处（破坏 shadcn 升级）
2. 弹框 Header 三件套 — Dialog/Sheet/AlertDialog 3 文件
3. 弹框 Footer 三件套 — 3 文件
4. Overlay 遮罩层 — 3 文件
5. Table 容器 — 1 文件
6. animate-in / animate-out Radix state — 6 文件 10 处

---

## 8. lib/ 区无任何发现（D 报告）

- **76 个 lib/ const/ i18n/ scripts/ proxy/ next.config 文件全部 0 div/span**
- lib/hooks/* 9 个 hooks 全是纯逻辑（TanStack Query + zustand + useState）
- lib/chat/* 15 个文件是 fetch/storage/类型定义
- lib/motion.ts 是 framer-motion variants object，不是 JSX
- 仅 `lib/store/app-data.tsx` 和 `lib/test-utils/intl-wrapper.tsx` 是 React Provider，无包装 div

**结论**: P2-P5 维度扫描时可跳过 lib/，除非是函数式写法扫描。

---

## 9. 已合规的使用模式（鼓励保持）

以下封装使用率较高的项目，需要保持：

- ✅ `<PageHero>` — 9 处（Phase3 Task3.5 完成度）
- ✅ `<DataTable>` — 9 处（4 个旧表格已迁移）
- ✅ `<ErrorBanner>` — 9 处（但仍有 5 处手写需迁）
- ✅ `<AppDialog>` / `<AppConfirm>` — 9 处
- ✅ `<EntryCardGrid>` — 4 处（Phase3 Task3.5）
- ✅ `<Reveal>` — knowledge 仪表盘等

---

## 10. 实施优先级建议（按 ROI 重排）

| 优先级 | 行动 | ROI | 估算 |
| --- | --- | --- | --- |
| **P0 本周** | 5 处手写错误条 → `<ErrorBanner>` | 🔴 极高 | 5 文件 × 5 行 = 25 行 |
| **P0 本周** | 4 处 PageHero + 2 处 BackLink 迁移 | 🔴 高 | 6 文件 × 8 行 = 50 行 |
| **P0 本周** | message-bubble interrupted → `<Badge>` | 🔴 高 | 1 文件 × 3 行 |
| **P1 下 sprint** | `<DialogFooter>` 新增 + 9 处替换 | 🔴 高 | 9 文件 × 4 行 = 36 行 |
| **P1 下 sprint** | `<AppDataEmpty variant="destructive">` 扩展 + 5 处替换 | 🟡 中 | 2 文件 |
| **P2 后续** | `<AppListItem>` + `<AppSubtleCard>` 抽封装 | 🟡 中 | 8 文件 / 10 处 |
| **P2 后续** | `<AuthFormContainer>` 抽封装 | 🟡 中 | 4 文件 |
| **P2 后续** | `<Callout>` 抽封装 | 🟢 低 | 3 文件 |
| **P3 可选** | `<AppSettingsRow>` `<AppCodeBlock>` 单文件/小扩展 | 🟢 低 | 2-3 文件 |

**总计**: ~178 行节省（净减少），覆盖 ~38 文件，~2 人天

> ⚠️ **明确不做**（违反 YAGNI）：`<Stack>` `<PageContainer>` `<PageScrollArea>` `<RowActions>` `<FilterBar>` `<PaginationBar>` `<SettingsCard>` —— 这些是把 1-2 个 className 包成组件，**净增复杂度**。

---

## 11. 后续建议

1. **先验证 ROI**: 抽样 1-2 个新封装（如 `<Stack>`），确认收益符合预期后再批量
2. **保持封装层纯净**: components/common/ 和 components/ui/ 不必再拆
3. **统一视觉语言**: 优先用项目 token（`bg-status-*/10` 而非 `bg-{emerald/amber/rose}-100`），如 message-bubble 徽章
4. **后续审计维度 (P2-P5)**:
   - P2 CVA: 重点扫业务组件（chat/knowledge/admin）
   - P3 设计模式: 重点扫 lib/api/, lib/store/, lib/chat/ 业务编排
   - P4 函数式: 重点扫 lib/hooks/, lib/chat/, lib/api/ 工具函数
   - P5 注释: 全项目统一扫描（lib/ 也需注释）