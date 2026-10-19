# Temporal Date Wrapper 设计 (2026-07-07)

> 模仿 `date-fns` API 封装 TC39 [Temporal](https://tc39.es/proposal-temporal/docs/),
> 用单文件 `packages/web/lib/date.ts` 替换项目里全部 68 处原生 `Date` API + 1 处 `date-fns`.

## 1. 背景与动机

- `packages/web` 当前用 `date-fns@^4.4.0` 仅 1 处 (`restore-deletion-banner.tsx:12`),
  业务代码大量直接调原生 `Date` (`new Date()` / `Date.now()` / `Date.parse()` / `.toISOString()` / `.getTime()`).
- TC39 Temporal 已进入 Stage 3, Node.js 22+ 内置 (`globalThis.Temporal`),
  Chromium / Safari / Firefox 最新版均原生支持.
- ⚠️ **2026-07-07 实测**: 本机 Bun 1.3.14 没有原生 Temporal (`Temporal is not defined`),
  调整方案见 §13 — 改用 `@js-temporal/polyfill` 包保证 dev/test/prod 一致.
- 痛点:
  1. **时区陷阱**: `new Date(iso)` 在 SSR / 客户端行为不一致, 月份/日期溢出 (`new Date(2024, 1, 31)`).
  2. **API 碎片化**: 同一仓库里同时存在 `date-fns`, `Intl.DateTimeFormat`, 原生 `Date`,
     三套写法, 新人 onboarding 成本高.
  3. **类型不安全**: `Date.parse` 返回 `NaN` 时静默 fail, `getMonth()` 月份 0-indexed 易错.
  4. **测试 fragile**: 大量 `Date.now()` mock 注入, 业务代码里有 `Math.max(ZERO, differenceInDays(exp, new Date()))` 重复模式.

## 2. 目标

1. **统一 API**: 业务代码只 import `@/lib/date`, 不用 `date-fns`, 不用原生 `Date`.
2. **零行为破坏**: 现有 156 个 test file / 719 passing test 必须不新增 fail.
3. **零 bundle 增长**: 不引 polyfill, 全靠原生 Temporal.
4. **小范围提交**: 单次 PR < 500 行, 5 个 phase 独立 commit.

## 3. 非目标 (YAGNI)

- ❌ 不实现 locale-aware fmtDate / fmtRelativeTime (已在 `docs/todo/i18n-deferred-tasks.md`)
- ❌ 不实现完整 date-fns API (仅补齐项目实际用到的 ~20 个函数)
- ❌ 不引 `@js-temporal/polyfill` / `proposal-temporal` 包
- ❌ 不动 `packages/service` (后端 Python)
- ❌ 不动 `packages/workflow`
- ❌ 不改 ESLint/oxlint 规则 (除非新增 `no-restricted-globals` 禁用原生 `Date`)

## 4. 架构

### 4.1 模块位置

```
packages/web/lib/
├── date.ts          ← 新增, 单文件 < 300 行
├── date.test.ts     ← 新增, vitest 覆盖
├── format.ts        ← 已有, fmtSize / fmtRelativeTime 保留
└── format.test.ts   ← 已有, 不动
```

### 4.2 API 签名 (date-fns 4.x 风格)

```typescript
// 输入联合类型 — 业务调用零改动
export type DateInput = string | number | Date | Temporal.Instant;

// ──────────── 解析 / 当前 ────────────

/** ISO 字符串 / epoch ms / Date / Temporal.Instant → Temporal.Instant
 * @param input 时间输入
 * @returns Temporal.Instant
 * @throws RangeError 当 input 非法时 (替代 Date.parse 返回 NaN)
 */
export const toInstant = (input: DateInput): Temporal.Instant;

/** 当前时间 → Temporal.Instant (顶层调用, 仅 client / 非 SSR root) */
export const nowInstant = (): Temporal.Instant;

/** 当前时间 → epoch ms (替 Date.now()) */
export const nowMs = (): number;

/** 当前时间 → ISO 字符串 (替 new Date().toISOString()) */
export const nowIso = (): string;

// ──────────── 差值 ────────────

export const differenceInMilliseconds = (later: DateInput, earlier: DateInput): number;
export const differenceInSeconds      = (later: DateInput, earlier: DateInput): number;
export const differenceInMinutes      = (later: DateInput, earlier: DateInput): number;
export const differenceInHours        = (later: DateInput, earlier: DateInput): number;
export const differenceInDays         = (later: DateInput, earlier: DateInput): number;

// ──────────── 加减 ────────────

export const addMilliseconds = (date: DateInput, amount: number): Date;
export const addSeconds      = (date: DateInput, amount: number): Date;
export const addMinutes      = (date: DateInput, amount: number): Date;
export const addHours        = (date: DateInput, amount: number): Date;
export const addDays         = (date: DateInput, amount: number): Date;

// ──────────── 比较 ────────────

export const isAfter  = (date: DateInput, dateToCompare: DateInput): boolean;
export const isBefore = (date: DateInput, dateToCompare: DateInput): boolean;
export const isEqual  = (date: DateInput, dateToCompare: DateInput): boolean;

// ──────────── 格式化 ────────────

/** ISO → 本地化日期字符串 (替 Intl.DateTimeFormat + new Date(iso).toLocaleDateString)
 * @param iso ISO 8601 字符串
 * @param locale 'zh-CN' | 'en-US' (项目只用这俩)
 * @returns yyyy/M/d 风格本地化日期
 */
export const formatDate = (iso: string, locale: string): string;

/** ISO → 本地化日期+时间 (替 new Date(iso).toLocaleString()) */
export const formatDateTime = (iso: string, locale: string): string;
```

### 4.3 内部实现要点

```typescript
const toInstant = (input: DateInput): Temporal.Instant => {
  if (input instanceof Temporal.Instant) return input;
  if (input instanceof Date) return Temporal.Instant.fromEpochMilliseconds(input.getTime());
  if (typeof input === "number") return Temporal.Instant.fromEpochMilliseconds(input);
  // string — Temporal.Instant.from 内部走 ISO 8601 parser, 比 Date.parse 严格
  return Temporal.Instant.from(input);
};

const differenceInDays = (later: DateInput, earlier: DateInput): number => {
  const dur = toInstant(later).until(toInstant(earlier), { largestUnit: "days" });
  return dur.days;  // Temporal.Duration 已规范化, 自动处理 DST / 月末
};

const addDays = (date: DateInput, amount: number): Date => {
  const zdt = toInstant(date).toZonedDateTimeISO(Temporal.Now.timeZoneId());
  return new Date(zdt.add({ days: amount }).epochMilliseconds);
};
```

**时区**: `add*` 用 `Temporal.Now.timeZoneId()` (运行时机时区),
跟现有 `new Date(... + 86400000)` 行为一致 (本地时间). 如未来需要 UTC 严格,
加 `addDaysUtc` 后缀函数 (YAGNI, 暂不加).

**SSR 安全**: `differenceIn*` / `add*` / `is*` / `formatDate*` 全是纯函数, RSC 可用.
`nowInstant` / `nowMs` / `nowIso` 顶层调 `Temporal.Now.instant()`, 仅在 client 组件 / 事件 handler 调用.

## 5. tsconfig 改动

`packages/web/tsconfig.json`:

```diff
   "compilerOptions": {
     "target": "ES2022",
-    "lib": ["dom", "dom.iterable", "ES2023"],
+    "lib": ["dom", "dom.iterable", "ES2025"],
```

- **不改 target** (Next.js 16 transpile 仍 ES2022, runtime 走 Node 22)
- **不改 moduleResolution** (bundler)
- **ES2025 lib** 提供 `Temporal` 全局类型 + `Iterator` 增强, 跟现有类型无冲突
- 验证: `bun run typecheck` 必须 0 error (现有 baseline 0 error, 不引入 regression)

## 6. 迁移清单

### Phase 1 — 基建 (无业务改动)

| 文件 | 改动 | 行数 |
| --- | --- | --- |
| `tsconfig.json` | lib 加 ES2025 | +1 / -1 |
| `lib/date.ts` | 新增 wrapper 模块 | +200 |
| `lib/date.test.ts` | 新增 vitest 覆盖 | +200 |

预估 +400 行, 1 commit, `chore(deps): upgrade tsconfig lib + add temporal wrapper`.

### Phase 2 — date-fns + Intl 替换 (~10 处)

| 文件 | 旧调用 | 新调用 |
| --- | --- | --- |
| `restore-deletion-banner.tsx` | `differenceInDays/Hours` from date-fns | `differenceInDays/Hours` from `@/lib/date` |
| `change-timeline.tsx` | `new Intl.DateTimeFormat("zh-CN", ...).format(new Date(iso))` | `formatDate(iso, "zh-CN")` |
| `evaluate-list-view.tsx` | 同上 | `formatDate(iso, locale)` |
| `buyers/page.tsx` | 同上 | `formatDate(iso, "zh-CN")` |
| `admin/invites/.../admin-invites-table.tsx` | `new Date(value).toLocaleDateString()` | `formatDate(value, locale)` |
| `admin/dicts/.../dict-audit-log.tsx` | `new Date(entry.ts).toLocaleString()` | `formatDateTime(entry.ts, locale)` |
| `admin/pre-analysis/...` | 同上 | `formatDateTime(value, locale)` |
| `admin/users/.../admin-users-table.tsx` | `toLocaleDateString()` × 2 | `formatDate(value, locale)` × 2 |

预估 +30 / -30 行, 1 commit, `refactor(web): replace date-fns + Intl.DateTimeFormat with lib/date`.

### Phase 3 — `lib/` 工具层 (~15 处)

| 文件 | 改动 |
| --- | --- |
| `lib/log.ts` | `new Date().toISOString().slice(...)` → `nowIso().slice(...)` |
| `lib/rate-limiter.ts` | `Date.now()` × 2 → `nowMs()` × 2 |
| `lib/format.ts` | `Date.now() / MS_PER_SECOND` default → `nowMs() / MS_PER_SECOND` |
| `lib/chat/use-chat-state.ts` | `Date.parse / Date.now` × 6 → `toInstant / nowMs` |
| `lib/chat/ui-message-adapter.ts` | `Date.parse` × 2 → `toInstant` |
| `lib/chat/migration.ts` | `Date.now / toISOString` × 3 → `nowMs / nowIso` |

预估 +25 / -25 行, 1 commit, `refactor(web): migrate lib/ to temporal wrapper`.

### Phase 4 — `components/` (~9 处)

| 文件 | 改动 |
| --- | --- |
| `components/chat/share-dialog.tsx` | `new Date(message.createdAt).toISOString()` → `nowIso()` |
| `components/chat/shared-chat-view.tsx` | `Date.parse(msg.timestamp)` + `toLocaleDateString` → `toInstant` + `formatDate` |
| `components/chat/use-composer-attachments.ts` | `Date.now()` → `nowMs()` |
| `components/chat/voice-recorder.tsx` | `Date.now()` × 3 → `nowMs()` × 3 |
| `health/_components/hero-section.tsx` | `Date.now() / new Date(iso).getTime()` × 2 → `nowMs() / toInstant(iso).epochMilliseconds` |

预估 +15 / -15 行, 1 commit, `refactor(web): migrate components/ to temporal wrapper`.

### Phase 5 — `app/` 业务层 (~10 处)

| 文件 | 改动 |
| --- | --- |
| `app/api/knowledge/batch/route.ts` | `Date.now()` → `nowMs()` |
| `scripts/duplication-report.ts` | `new Date().toISOString()` → `nowIso()` |
| (已包含在 Phase 2/4 的 `app/[locale]/...` 文件) | — |

预估 +10 / -10 行, 1 commit, `refactor(web): migrate app/ + scripts/ to temporal wrapper`.

### Phase 6 — package.json + 清理

- `package.json` 删除 `"date-fns": "^4.4.0"` 依赖 (业务已不引用)
- 跑 `bun install` 更新 `bun.lock`
- 跑 `bun run lint && bun run typecheck && bun run test` 完整验证
- 跑 `bun pm ls | grep date-fns` 确认 0 引用

预估 +1 / -1 行, 1 commit, `chore(web): remove date-fns dep`.

## 7. 测试策略

### 7.1 `lib/date.test.ts` 覆盖

每个 export 函数 1+ case:

| 函数 | 测试用例 |
| --- | --- |
| `toInstant` | ISO 字符串 / epoch ms / Date / Temporal.Instant / 非法字符串抛错 |
| `nowMs / nowIso / nowInstant` | 返回值类型 + 单调性 (a < b) |
| `differenceInDays` | 同一天 = 0 / 跨天 / 跨月 / 跨年 / DST 边界 |
| `differenceInHours/Minutes/Seconds/Ms` | 同上粒度 |
| `addDays/Hours/Minutes/Seconds/Ms` | 正常 / 月末溢出 (1月31+1月=2月28) / DST |
| `isAfter/Before/Equal` | 三态 |
| `formatDate / formatDateTime` | zh-CN / en-US 输出快照 (用 toMatchInlineSnapshot) |

**不 mock Temporal** — vitest 跑在 Node 22 / bun runtime 下, Temporal 原生可用.

### 7.2 业务测试

- `restore-deletion-banner.test.tsx` 现有 5 case 必须继续 pass
- `format.test.ts` 现有 case 必须继续 pass (Date.now 注入参数化, 现在 wrapper 也支持)
- `lib/chat/*` 现有 chat state tests 必须 pass

### 7.3 不做的事

- ❌ 不 mock `Temporal` (Vitest fake timers 跟 Temporal 集成不深, mock 会失真)
- ❌ 不写 E2E 新 case (现有 18 case 已覆盖时间显示)

## 8. 风险与缓解

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| Node 22+ 才能用原生 Temporal | 中 | Next.js 16 默认 Node 22, `package.json` engines 锁 `>=22`, CI / prod 都满足 |
| tsconfig 升级引入 ES2025 类型 regression | 低 | 现有 typecheck baseline 0 error, 升级后必须仍 0 error, 否则 revert |
| 单次 commit 超 500 行 | 中 | 拆 6 phase, 单次 < 250 行 |
| 现有测试用 `Date.now() + FIVE_DAYS_MS` 写 fixture | 低 | 测试 fixture 不强制替换, 保留 `new Date(Date.now() + FIVE_DAYS_MS)` 写法 (test 数据生成, 不是生产代码) |
| Temporal 在某些 Linux 旧版 glibc 下异常 | 低 | 项目用 Bun + Next.js 16, Docker 镜像基于 node:22-alpine, glibc 无关 |
| oxlint 报 `no-restricted-globals` 冲突 | 低 | 当前 0 全局禁用规则, 暂不引入 (可选后续 PR 加 `Date` / `Math.floor(Date.now())` 禁用规则) |

## 9. 验收标准

1. `bun run lint && bun run typecheck && bun run test` 全 0 error / 0 fail (跟 baseline 持平)
2. `grep -rEn "Date\\.now|new Date\\(|Date\\.parse" packages/web/{app,components,lib} --include="*.ts" --include="*.tsx"` 0 命中 (生产代码)
3. `grep -rEn "date-fns" packages/web --include="*.ts" --include="*.tsx"` 0 命中
4. `package.json` 无 `date-fns` 依赖
5. `lib/date.ts` < 300 行, 单文件单职责
6. 每个 phase commit 后 `git diff --stat` < 250 行

## 10. 文档同步

完成后更新:

- `packages/web/CLAUDE.md` 「封装组件」段补 `lib/date` 条目 (date-fns 替身, Temporal 底层)
- `docs/todo/i18n-deferred-tasks.md` 删 `fmtDate` 项 (现在已通过 `formatDate(locale)` 实现)
- 新增 `docs/superpowers/plans/2026-07-07-temporal-date-wrapper.md` (writing-plans skill 输出)

## 11. 关联规范

- [[CLAUDE.md]] §工具链 — format / lint / typecheck / test 顺序
- [[CLAUDE.md]] §范围控制 — 单次 < 500 行, 6 phase 拆分
- [[CLAUDE.md]] §JSDoc 注释规约 — 所有 export 必须中文 JSDoc + `@param` + `@returns`
- [[CLAUDE.md]] §零 lint warning — 不引入新 warning

## 12. 设计变更记录 (Delta)

### 2026-07-07: 改用 `@js-temporal/polyfill` 替代原生 Temporal

**原因**: 实测本机 Bun 1.3.14 不支持原生 Temporal (`Temporal is not defined`).
项目 `vitest` 默认跑在 Bun runtime, 测试会全部 fail. 即使生产 Node 22+ 支持, dev/test 一致性更重要.

**影响**:

- 引入依赖: `@js-temporal/polyfill` (latest, ~25KB gzip, tree-shake friendly)
- `lib/date.ts` 内部 `import { Temporal } from "@js-temporal/polyfill"`, 不直接用 globalThis
- 业务调用零变化, 仍是 `import { differenceInDays } from "@/lib/date"`
- Vitest 配置: 不需要 mock, polyfill 在 jsdom + bun 双 runtime 下都加载
- 生产 bundle 增长 ~25KB gzip, 可接受 (date-fns 4.x 自身 ~13KB, 用法比 polyfill 少)
- §5 tsconfig 仍加 ES2025 lib (类型), 不依赖 runtime polyfill
- §6 Phase 6 删 `date-fns` 同时**不删** `@js-temporal/polyfill` (新增依赖)

**保留的 ES2025 lib 升级**: Temporal 的 TypeScript 类型来自 `lib.es2025.temporal.d.ts`,
即使 runtime 用 polyfill, 类型仍走原生 ES2025 lib 声明 (更准, polyfill 跟 spec 完全对齐).