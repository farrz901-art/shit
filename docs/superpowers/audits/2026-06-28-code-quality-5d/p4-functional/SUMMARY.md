# P4 维度审计总报告 — ④ 函数式写法 (curry / cond / pipe / compose / es-toolkit)

**审计日期**: 2026-06-28
**范围**: `packages/web/` 全量源文件（排除 `.test.tsx`/`.test.ts`/`.stories.tsx`）
**模式**: 4 个 agent 并行扫描（A=common+ui, B=业务组件, C=app/页面+API, D=lib+其它）
**FP 库现状**: es-toolkit ^1.48.1 **已装**（仅 1 处使用：`lib/chat/migration.ts:10` groupBy）；Ramda **未装**

---

## 1. 总体扫描概览

| 维度 | 数值 |
| --- | --- |
| 总扫描文件 | **~371** (86 common+ui + 49 业务组件 + 153 app + 83 lib+其它) |
| **es-toolkit 当前使用** | **1 处** (lib/chat/migration.ts groupBy) |
| **CLAUDE.md §优先使用纯函数强制要求** | 严重偏差（项目实际几乎没用 FP） |
| 🔴 高 ROI 建议重写 | **5** (净省 ~245 行 + 单点修改价值) |
| 🟡 中 ROI 可选 | **10+** (净省 ~80 行) |
| ❌ 不建议 | 多数（shadcn 原语 + React 组件本身 + 真副作用 + idiomatic ES） |

**核心结论**: P4 不是"挑刺找机会"，而是**发现项目架构层（lib/api + app/api）有 2 个真高 ROI 集中区**，合计净省 ~245 行。

---

## 2. 各 Agent 报告位置

| Agent | 范围 | 文件数 | 报告 |
| --- | --- | --- | --- |
| A | common + ui 封装实现层 | 86 | [A-common-ui-report.md](p4-functional/A-common-ui-report.md) |
| B | 业务组件（chat/knowledge/...） | 49 | [B-business-components-report.md](p4-functional/B-business-components-report.md) |
| C | app/ 页面+API+_actions | 153 | [C-pages-report.md](p4-functional/C-pages-report.md) |
| D | lib/ + const/ + i18n/ + scripts/ | 83 | [D-lib-report.md](p4-functional/D-lib-report.md) |

---

## 3. 现有 FP 资产（已正确使用，不要重复建议）

### 3.1 lib/chat/ — 项目 FP 化最彻底的样板（D 报告）
- `lib/chat/migration.ts:10` — **全项目唯一** es-toolkit 使用点（`groupBy`）
- `lib/chat/chat-utils.ts:30-55` — `computeEffectiveConversations` / `getNextConversationId` / `newId` 全部是显式 deps/state 注入的纯函数
- `lib/chat/dify.ts:87-128` — `normalize()` 用 switch dispatcher + generator（每个 case 抽成独立函数）
- `lib/chat/storage.ts` — Dexie adapter Facade（封装 IDB CRUD 为纯函数式 API）

### 3.2 lib/api/ — 内部函数式纯化（D 报告）
- `lib/api/config.ts:84-93, 99-117` — `resolveUrl` / `serializeRequest` / `parseErrorDetail` / `parseResponseBody` 全部纯函数
- `lib/api/query-client.ts:17-25` — `errorMessage()` 已有完整 private 版本（区分 ApiError/NetworkError/Error/fallback）

### 3.3 其它（D 报告）
- `lib/motion.ts` — `stagger(delay) => variant` 工厂 FP 风格
- `lib/theme/themes.ts:71-77` — `getThemeConfig()` 查表
- `lib/log.ts` — `COLOR_BY_LEVEL` 教科书级查表 dispatch
- `lib/buyer-profile/hooks.ts` — TanStack Query 标准化封装

**结论**: lib/chat/ 是项目 FP 化的样板，`chat-utils.ts` 的"显式 deps 注入 + 纯函数"是其他模块应参考的范式。

---

## 4. 🔴 高 ROI 建议（5 个，净省 ~245 行）

### 4.1 🏆 `app/api/*` 抽 `bffProxyResponse()` 工厂 — 净省 ~180 行（C 报告）

**问题**: **17 个 BFF route** 重复 12 行模板（修正 P3 估计的 9 处）

```ts
// 17 个 route 重复这个 12 行模板
return new NextResponse(await resp.text(), {
  headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
  status: resp.status,
});
```

**重构**: 在 `lib/api/config.ts` 加 `bffProxyResponse(resp: Response): NextResponse` 工厂（~6 行）

```ts
// lib/api/config.ts 新增
export const bffProxyResponse = async (resp: Response): Promise<NextResponse> =>
  new NextResponse(await resp.text(), {
    headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
    status: resp.status,
  });
```

**调用方简化**: 17 个 route 从 12 行 → 1 行 `return bffProxyResponse(resp)`

**收益**: **净省 ~180 行 + 单点修改价值**（改 Content-Type 默认值只改 1 处）

**风险**: 低（API 透传语义不变，每个 route 还有 params 解析等独立逻辑）

**判定**: 🔴 **强烈推荐** — P3 估计的"9 处"是低估，实际 **17 处**

---

### 4.2 🏆 `lib/api/errors.ts` 抽 `getErrorMessage(error: unknown)` helper — 净省 ~30 行（D + C 报告）

**问题**: 9 处重复的 `errorMessage(error: unknown)`：
- `lib/api/query-client.ts:17-25` — 最完整版本（区分 ApiError/NetworkError/Error/fallback）但未导出
- `lib/api/config.ts:43` — inline 简化版
- `lib/api/ingest.ts:72-76` — inline 简化版
- `lib/api/rsc-queries.ts:58` — inline
- `lib/api/chat.ts:36` — 包 fetch 错误
- `lib/dify-datasets.ts:57` — 包 fetch 错误
- `app/admin/invites/_components/admin-invites-table.tsx:31` — 组件内 helper
- `app/admin/dicts/_components/dict-item-create-dialog.tsx:35` — 组件内 helper
- `app/evaluate/new/_components/evaluate-new-form.tsx:67` — 组件内 helper
- `components/common/form/app-field.tsx:78` — 组件内 helper

**重复估算**: 5 处 lib/api 内 + 5 处组件内 = **10 处重复 helper**，平均 5-10 行/处 = **50-100 行重复**

**重构**: `lib/api/errors.ts` 导出 `getErrorMessage`，把 `query-client.ts:17-25` private 版提升为公共 API

```ts
// lib/api/errors.ts (新增 export)
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
};
```

**收益**: **净省 ~30 行 + 未来加错误归一逻辑只改 1 处**

**风险**: 低（语义统一，只升不降）

**判定**: 🔴 **强烈推荐** — P3 估计的"6+ 处"是低估，实际 **10 处**

---

### 4.3 🏆 `_actions/*` 抽 `errMsg(err)` helper — 净省 ~40 行（C 报告）

**问题**: `_actions/*.ts` 错误归一严重重复：
- `evaluate.ts` + `output.ts` 字字相同的 9 行 `errMsg()` helper
- `knowledge.ts` 5 处 inline `error instanceof Error ? .message : String(error)`
- `account.ts` 5 处 inline try/catch
- `account-settings.ts` 5 处 `handle*Error` 函数 + 7 处调用

**重复估算**: **17 处**（修正 P3 估计的 6+ 处），平均 7 行/处 = **119 行重复**

**重构**: 复用 4.2 的 `getErrorMessage` + 在 `app/[locale]/_actions/_utils.ts` 加 server-only `actionError(err)`

**收益**: **净省 ~40 行**

**风险**: 低（已有 query-client.ts 模板）

**判定**: 🔴 **强烈推荐** — 与 4.2 合并实施

---

### 4.4 `chat/thinking-trace.tsx:12-29` `renderStep` 改 Record lookup（B 报告）

**问题**: `renderStep` 内 2-branch if + `let statusClass` 模式

```tsx
const renderStep = (step: TraceStep, idx: number) => {
  let statusClass = "";
  if (step.status === "completed") statusClass = "bg-status-success/20 text-status-success";
  else if (step.status === "running") statusClass = "bg-status-running/20 text-status-running animate-pulse";
  return <div ...>...</div>;
};
```

**改法**: 抽 Record lookup

```tsx
const STATUS_CLASS: Record<TraceStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-status-running/20 text-status-running animate-pulse",
  completed: "bg-status-success/20 text-status-success",
  failed: "bg-status-error/20 text-status-error",
};
```

**收益**: 净省 5 行 + 满足 CLAUDE.md §业务 enum 走 lookup

**风险**: 低

**判定**: 🔴 **强烈推荐**

---

### 4.5 `theme-provider.tsx:115/202/209/257` 抽 `isValidTheme` type predicate（B 报告）

**问题**: 4 处散落的 `LIGHT/DARK/SYSTEM` 校验表达式（看 `enableSystem` 不同分支）

```tsx
// 4 处形如
if (theme === "light" || theme === "dark" || (!enableSystem && theme === "system")) { ... }
```

**改法**: 抽 type predicate

```tsx
const isValidTheme = (val: string, enableSystem: boolean): val is ThemeName => {
  if (val === "light" || val === "dark") return true;
  return enableSystem && val === "system";
};
```

**收益**: 净省 8 行 + 类型安全升级 + 单一事实源

**风险**: 低

**判定**: 🔴 **强烈推荐**

---

## 5. 🟡 中 ROI 可选（10+ 处，净省 ~80 行）

### 5.1 `Array.from({length}).map` 改 es-toolkit `range`（A 报告）

**位置**:
- `components/common/button/app-loading-skeleton.tsx:17`
- `components/common/table/data-table-skeleton.tsx:18,23,25`

**改法**:
```tsx
import { range } from "es-toolkit";
{range(rows).map((idx) => <Skeleton key={idx} ... />)}
```

**收益**: 净省 ~10 行 + es-toolkit 使用从 1 处升到 5 处

**风险**: 极低（行为完全等价）

**判定**: 🟡 **可顺手做**

### 5.2 `composer-attachments.tsx:258-280` 抽 `updateById` helper（B 报告）

**问题**: 2 处 `prev.map(item => if (item.id === tempId) ...)` 完全同型

**收益**: 净省 6 行

**判定**: 🟡

### 5.3 `lib/api/config.ts` 导出 `parseErrorDetail(res)` 给 `lib/api/ingest.ts:79-95` 复用（D 报告）

**问题**: 完全同形的 detail 提取逻辑（"4xx body 优先 .detail, 兜底 statusText"）复制了一份

**收益**: 净省 ~9 行

**判定**: 🟡

### 5.4 `lib/chat/chat-utils.ts:applyEvent` 改对象 dispatch（D + P3 已知）

**已知 P3 报告**: 3 个 if 链 → 对象 dispatch

**FP 角度升级**: 行数差不多但**扩展性 + 测试性显著提升**（dispatch 表可独立测试）

**判定**: 🟡 — **P5 合并 `computeEffectiveConversations` pipe 时一起做**

### 5.5 `share-dialog.tsx:79-106` `let + if/else` 反模式改 ternary（B 报告）

**收益**: 净省 4 行

**判定**: 🟡

### 5.6 `memory-management-dialog.tsx:55-65` `useMemoryFilter` IIFE 改 ternary（B 报告）

**收益**: 净省 1 行 + 可读性

**判定**: 🟡

### 5.7 `voice-recorder.tsx:34-39` `getFileExtension` 改 Record lookup（B 报告）

**判定**: 🟡

### 5.8 `use-chat-state.ts:185` role adapter 改 dispatch（D 报告）

**判定**: 🟡 — 净省 6 行

### 5.9 `use-lookup.ts:44` `Object.fromEntries` 改 es-toolkit `keyBy`（D 报告）

**判定**: 🟡 — 净 0 行，风格统一

### 5.10 `CopyButton` try-catch 改 es-toolkit `attempt`（A 报告）

**判定**: 🟡 — 净省 ~5 行，但当前 try-catch 清晰

---

## 6. ❌ 明确不做（违反 YAGNI / 不适合 FP 化）

### 6.1 shadcn ui/* 整目录 36 文件禁止改（A 报告）
shadcn cli 重新生成会覆盖。**整目录归 ❌**

### 6.2 React 组件本身
返回 JSX 的函数本质上不纯（与 React model 耦合），**不要为了 FP 化拆组件**

### 6.3 React hooks
- useState / useEffect / useMemo / useCallback — 本身是 React 抽象，**不要为了 FP 化拆 hook**
- zustand create() — 已合理
- React `cache()` 包装（lib/auth/permission.ts）— 已合理

### 6.4 真副作用函数（不可纯化）
- `navigator.clipboard` + `setTimeout`（CopyButton）— 业务需要
- `fetchDifyHealth` + `setInterval`（HealthDot）— 业务需要
- `router.back` + `globalThis.history`（BackLink）— 业务需要
- `localStorage` / `sessionStorage` / `cookies()` — IO 边界

### 6.5 idiomatic ES（不要套 FP）
- `for-of` 数组遍历 — 已是 ES2017+ 标准
- 顺序 `await X → await Y → combine` — RSC 数据预取原生写法

### 6.6 拆 pure 反而难懂的场景（B + A 报告）
- `theme-provider.tsx:resolveTheme` 3 if → cond — 基座组件，风险 > 收益
- `conversation-list.tsx:formatRelativeTime` 4 if → cond — **真问题是 `Date.now()` 副作用**，清理 if 不解决核心
- `composer-attachments.tsx:inferType` 3 if → cond — 3 行已清晰，cond wrapper 会变成 5-7 行
- `newId` 强制 `crypto.randomUUID` — 现有 SSR 安全回退链已最优
- `processStream` pipe 评估 — async generator + abort 透传麻烦（D 报告）
- `parse-*` curry — 抽不出真公共参数（D 报告）

### 6.7 es-toolkit `tryCatch` 不适合现有模式（C 报告）
返回 tuple `[result, error]` 跟现有 `{ ok, error }` / throw 模式不兼容，**helper 函数更优**

### 6.8 page.tsx 顶层（RSC 强制）+ API route 顶层 export
框架约束

---

## 7. ROI 总结（严格审查）

| 类别 | 数量 | 净省代码 |
| --- | --- | --- |
| 🔴 高 ROI 推荐做 | **5** | **净省 ~245 行** |
| 🟡 中 ROI 可选 | **10+** | 合计 ~-80 行 |
| ❌ 不建议 | 多数 | 0 |

**P4 真实判断**: 不是"挑刺找机会"，而是**发现架构层有 2 个真高 ROI 集中区**（`bffProxyResponse` + `getErrorMessage`），合计净省 ~250 行。

---

## 8. P4 关键洞察

1. **es-toolkit 使用严重不足**: 项目装了 1.48.1 但仅 1 处用（groupBy），**与 CLAUDE.md §优先使用 es-toolkit 强制要求偏差巨大**
2. **P3 的"9 处 BFF proxy"是低估**: 实际 **17 处**（C 报告修正）
3. **P3 的"6+ 处错误归一"是低估**: 实际 **10+ 处**（C + D 报告合并统计）
4. **lib/chat/chat-utils.ts 是项目 FP 样板**: "显式 deps/state 注入 + 纯函数" 应推广到其他模块
5. **拆 pure 函数 ≠ 改写 if 链**: 真正的高 ROI 是**消除模板代码重复**（BFF 12 行模板、error normalize），而不是把已清晰的 if 改成 cond
6. **React 组件不能纯化**: 强行套 FP 会破坏 React 模型；只对**内部 helper 函数**做 FP 化
7. **副作用是真业务需求**: CopyButton clipboard / HealthDot fetch / BackLink router 不可纯化

---

## 9. 强烈推荐执行顺序

### ✅ 立即做（5 个，净省 ~245 行）

1. **`bffProxyResponse()` 工厂** — C 报告 🔴 高 ROI（**17 处** × 12 行 → 1 行，净省 ~180 行）
2. **`getErrorMessage(error: unknown)` helper** — D + C 报告 🔴 高 ROI（10 处重复，净省 ~30 行 + 单点修改）
3. **`errMsg(err)` 到 `_actions/_utils.ts`** — C 报告 🔴 高 ROI（17 处 server actions 错误归一，净省 ~40 行）
4. **`thinking-trace.tsx:renderStep` 改 Record lookup** — B 报告 🔴 高 ROI（5 行 + 满足 §业务 enum 走 lookup）
5. **`theme-provider.tsx` 抽 `isValidTheme` predicate** — B 报告 🔴 高 ROI（8 行 + 类型安全升级）

### ⚠️ 谨慎评估（2-3 个）

6. **`Array.from({length}).map` → es-toolkit `range`** — A 报告 🟡 中 ROI（4 处，净省 ~10 行，**顺手做可提 es-toolkit 存在感**）
7. **`applyEvent` + `computeEffectiveConversations` 合并重写** — D + P3 报告 🟡 中 ROI（行数差不多但扩展性显著提升）
8. **`updateById` helper** — B 报告 🟡 中 ROI（6 行）

### ❌ 暂不做（风险大于收益或违反 YAGNI）

- `theme-provider.tsx:resolveTheme` 改 cond（基座组件）
- `formatRelativeTime` 改 cond（真问题是 Date.now，不是分支）
- `composer-attachments.tsx:inferType` 改 cond（3 行已清晰）
- `newId` 强制 `crypto.randomUUID`（SSR 安全回退链已最优）
- `processStream` pipe（async generator + abort 透传麻烦）
- `parse-*` curry（无公共参数）
- shadcn ui/* 整目录（禁止改）

---

## 10. P4 与 P3 协同

| 场景 | P3 报告 | P4 报告 | 综合 ROI |
|------|---------|---------|---------|
| BFF proxy 模板 | 🟡 中 ROI, 9 处 | 🔴 高 ROI, **17 处** | 🔴 升级为强烈推荐 |
| `_actions/*` 错误归一 | 🟡 中 ROI, 6+ 处 | 🔴 高 ROI, **17 处** | 🔴 升级为强烈推荐 |
| `applyEvent` if 链 | 🔴 高 ROI (对象 dispatch) | 🟡 中 ROI (行数差不多但扩展性提升) | 🟡 合并实施 |
| `lib/api/errors.ts` 抽 helper | 提到 1 次 | 🔴 高 ROI (10 处) | 🔴 强烈推荐 |

---

**P4 完成。等待你审核。**

如果同意，下一步启动 **P5: 注释完整性审计**（4 个 agent 并行扫描所有 .js/.ts/.tsx 文件，检查函数注释 + 文件头注释 + 缺失位置）。