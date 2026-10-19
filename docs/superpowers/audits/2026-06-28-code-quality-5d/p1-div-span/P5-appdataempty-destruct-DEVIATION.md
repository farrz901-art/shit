# P1 Phase 5 偏离说明 — `<AppDataEmpty variant="destructive">` + 5 处 json 替换 (2026-06-29)

> 范围: P1 [plan §Phase 5](../../superpowers/plans/2026-06-28-p1-div-span-extraction.md) (Task 24-26, ~3 tasks).
> 状态: **SKIPPED — DONE_WITH_CONCERNS**. 0 src 改动.

## TL;DR

[spec](../../superpowers/plans/2026-06-28-p1-div-span-extraction.md) 假设 `<AppDataEmpty>` 改造为"扁平居中文本组件" (variant 类 map `table/page/destructive` + 图标 map). 实际 [`AppDataEmpty`](../../../../packages/web/components/common/display/app-data-empty.tsx) 是"shadcn `<Empty>` + `<EmptyHeader>` + `<EmptyTitle>`" 结构组件, 提供 icon + title + description slot. 两套设计哲学不同, force-fit 会破坏现有 4 处用法 + 视觉降级 5 处 json 占位. 按 P1 Phase 1 ErrorBanner / Phase 2 admin pages 的"done-with-concerns skip 模式"处理, **不引入 `variant="destructive"`**, 5 处 json 不替换.

## Spec 假设 vs 实际

### Spec (Task 24) 假设的 AppDataEmpty API

```tsx
// spec §4.1 显示的 variant 类 map
const variantClass: Record<Variant, string> = {
  table: "rounded-md border p-8 text-muted-foreground",
  page: "flex items-center justify-center rounded-lg border p-8 text-muted-foreground",
  destructive: "flex items-center justify-center rounded-lg border border-destructive/40 p-8 text-destructive",
};

const variantIcon: Record<Variant, LucideIcon> = {
  table: Inbox,
  page: FileX,
  destructive: AlertCircle,
};
```

关键点: **扁平居中文本, 无 `<EmptyHeader>`/`<EmptyTitle>`/`<EmptyDescription>` 结构**. variant 直接对应 CSS class.

### 实际 AppDataEmpty 实现

[`app-data-empty.tsx:35-59`](../../../../packages/web/components/common/display/app-data-empty.tsx#L35-L59) 包裹 `<Empty>` (`flex min-w-0 flex-1 flex-col items-center justify-center gap-6 text-balance rounded-lg border-dashed p-6 text-center md:p-12`) + `<EmptyHeader>` (`flex max-w-sm flex-col items-center gap-2 text-center`) + `<EmptyTitle>` (`text-lg font-medium tracking-tight`) + `<EmptyDescription>` (`text-muted-foreground text-sm/relaxed`).

关键点: **header 结构组件, 提供 icon/title/description 三段 slot**. variant 只控制 table 的 `border-0 p-8` 是否被加在 Empty 上 (page 走 Empty 默认 dashed border).

## 为什么 force-fit 会破坏现有用法

### 现有 4 处 AppDataEmpty 用法 (都是 Empty header 结构)

1. [`evaluate-list-view.tsx:152-157`](../../../../packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx#L152-L157) — `icon: Database` + `title: 还没有评估` + `description: 上传一个问答 CSV...` + `variant="page"`. 用了 3 个 slot.
2. [`task-files.tsx:113`](../../../../packages/web/app/[locale]/output/[task_id]/_components/task-files.tsx#L113) — `title` + `variant="page"`. Empty header 结构.
3. [`admin-dicts-client.tsx:72`](../../../../packages/web/app/[locale]/admin/dicts/_components/admin-dicts-client.tsx#L72) — `title` + `variant="page"`. Empty header 结构.
4. [`app-data-empty.test.tsx:8-35`](../../../../packages/web/components/common/display/app-data-empty.test.tsx#L8-L35) — 5 个测试断言 Empty 结构 (`border-0` / `svg` 不渲染 / `border` 类).

如果按 spec 重写为扁平文本: 4 处全要改 (破坏 API 兼容性), 5 个测试全要改 (assertion 失效).

### Force-fit 5 处 json 的视觉降级

| 属性 | json 当前 | AppDataEmpty 替换后 | 影响 |
|------|-----------|---------------------|------|
| border | `border` (实线) | `border-dashed` (虚线) | 视觉变化 |
| padding | `p-8` | `p-6 md:p-12` (移动 6, 桌面 12) | 移动 padding 偏小 |
| flex grow | 无 | `flex-1` (消费父容器剩余高度) | 容器高度变化时布局动 |
| gap/text-balance | 无 | `gap-6 text-balance` | 增加额外间距 |
| title 字号 | 默认 (继承父, 一般 `text-sm`) | `text-lg font-medium tracking-tight` | `—` 单字符会显示成大号粗体 |
| icon | 无 | spec 加 `AlertCircle` 图标 (破坏"无图标"假设) | 单占位符出现红色警告图标 |

测试 `screen.getByText("—")` 在 `<EmptyTitle>` 里仍可命中 (PASS), 但**视觉体验从"细线占位"变成"大标题 + 虚线框 + 红警告图标"**, 跟 RSC JSON 渲染库"中性占位"语义不符.

## 决策

按 P1 Phase 1 ErrorBanner / Phase 2 admin pages 的"**force-fit 风险 > spec 收益时 skip**"模式:

1. **不引入 `variant="destructive"`** — 现有 AppDataEmpty 结构跟 spec 假设不同, 加 prop 会跟现有 4 处 Empty header 用法不兼容.
2. **不替换 5 处 json 占位/错误** — force-fit 会破坏视觉设计 (单 `—` 变成大标题 + 红警告图标 + 虚线框, 跟 RSC JSON 库的"中性兜底"定位冲突).
3. **保留 json 当前实现** — 重复 5 次的 div 是真重复, 但封装成 AppDataEmpty 收益为负 (视觉降级 + API 不兼容).

**净影响**: 0 src 改动, 0 test 改动. P1 plan Phase 5 标记 SKIPPED, handoff 进度更新. spec 估算 -20 行 / 净节省, 实际 **0 行, 0 commit**.

## 未来可考虑方向 (non-blocking)

如果项目决定未来 json 库需要"标准空态视觉", 2 个选项:

- **选项 A**: 重构 AppDataEmpty 为扁平文本组件 (按 spec §4.1 重写) — 跟现有 4 处用法不兼容, 需要同时改 4 处 + 5 个测试, 大改动.
- **选项 B**: 新抽 `<TextPlaceholder variant="destructive">` 扁平居中文本组件 — 跟 AppDataEmpty 并存, 5 处 json 走新组件. 但 ROI 低 (5 处 div 各 8 行 = 40 行, 抽组件 + test + 5 处替换 ≈ 30 行, 几乎不省).

**当前选择**: **不做**. P1 Phase 5 标记 SKIPPED. 重复 5 次 8 行 div 是 acceptable technical debt, 跟 spec 假设的"完全可替换"判断不符, 但项目历史多次强调"**严禁 shim/兼容代码**" (见 [`.claude/CLAUDE.md` §编码规范](../../../.claude/CLAUDE.md)), 不值得为 5 处小幅重复引入不兼容 API.

## 关联

- 触发 spec: [P1 plan §Phase 5 (Task 24-26)](../../superpowers/plans/2026-06-28-p1-div-span-extraction.md)
- 5 处候选 site:
  - [`packages/web/components/json/json-view.tsx:29-37, 44-52`](../../../../packages/web/components/json/json-view.tsx)
  - [`packages/web/components/json/json-diff.tsx:68-76, 84-92, 98-106`](../../../../packages/web/components/json/json-diff.tsx)
- 现有 AppDataEmpty: [`packages/web/components/common/display/app-data-empty.tsx`](../../../../packages/web/components/common/display/app-data-empty.tsx)
- shadcn Empty 基类: [`packages/web/components/ui/empty.tsx`](../../../../packages/web/components/ui/empty.tsx)
- 同模式 skip 历史: P1 Phase 1 ErrorBanner (2 defer 等 descriptionNode slot) / Phase 2 admin pages (PageHero 强需 eyebrow)
