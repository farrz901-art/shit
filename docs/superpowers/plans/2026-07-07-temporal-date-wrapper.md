# Temporal Date Wrapper 实施 Plan (2026-07-07)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用单文件 `packages/web/lib/date.ts` (TC39 Temporal + `@js-temporal/polyfill` 实现, date-fns 4.x 风格签名) 替换项目里全部 68 处原生 `Date` API + 1 处 `date-fns` 调用.

**Architecture:**
- 单文件 `lib/date.ts` < 300 行, 集中所有 wrapper
- `import { Temporal } from "@js-temporal/polyfill"` (Bun 1.3.14 当前无原生 Temporal)
- 输入类型 union `DateInput = string | number | Date | Temporal.Instant`, 业务调用零改动
- `tsconfig.json` `lib` 字段 `"ES2023"` → `"ES2025"` 提供 Temporal 类型

**Tech Stack:**
- TC39 Temporal (Stage 3) via `@js-temporal/polyfill` (latest)
- TypeScript 6 (ES2025 lib for Temporal types)
- Vitest 3.x + jsdom (业务测试不动)
- 项目其它栈不变: Next.js 16 / React 19 / bun 1.3.14 / oxlint 1.x / oxfmt 1.x

---

## Global Constraints

来自 [spec §3, §5, §8](../specs/2026-07-07-temporal-date-wrapper-design.md):

- **版本**: bun 1.3.14, TS 6, Next.js 16 — 锁版本不升级
- **依赖**: 不引第三方 UI 库, 不动后端, 不动 `packages/service` / `packages/workflow`
- **范围**: 单次 commit < 500 行 (本 plan 单 task < 250 行), 6 phase 拆分
- **测试**: vitest + jsdom 默认环境, 业务测试 0 新 fail (baseline 719 passed + 8 deferred)
- **lint/format**: oxlint 0 warning, oxfmt 0 diff, tsc 0 error
- **JSDoc**: 所有 export 必须中文 JSDoc + `@param` + `@returns` (spec §11)
- **import 排序**: oxlint sort-imports 强制
- **commit prefix**: `chore:` / `feat:` / `refactor:` / `test:` / `docs:`
- **commit 策略**: 批量提交, 单个 commit ≥ 10 文件
  - Phase 1: 保持原计划 5 个独立 commit (基建)
  - Phase 2: 所有 Task 完成后 1 个批量 commit
  - Phase 3: 1 个批量 commit
  - Phase 4: 1 个批量 commit  
  - Phase 5: 1 个批量 commit
  - Phase 6: 1 个批量 commit (不逐文件提交)
- **不引全局** `useState` 等复杂 hook 模板 — 已有封装优先 (`<DataTable>` / `<AppDialog>` 等)

---

## File Structure

**新增**:
- `packages/web/lib/date.ts` (~280 行, wrapper 模块)
- `packages/web/lib/date.test.ts` (~250 行, 单元测试)

**修改**:
- `packages/web/tsconfig.json` (lib 字段 +1 行)
- `packages/web/package.json` (+1 dep `@js-temporal/polyfill`, -1 dep `date-fns`)
- `packages/web/bun.lock` (自动更新)
- 18 个业务文件 (Phase 2-5, 见 [spec §6](../specs/2026-07-07-temporal-date-wrapper-design.md))

---

## Phase 1 — 基建 (lib/date.ts + tsconfig + tests)

### Task 1.1: 升级 tsconfig lib 字段

**Files:**
- Modify: `packages/web/tsconfig.json:4`

**Context:** Phase 1 引入 Temporal 类型, 必须先把 ES2025 lib 加上.
否则 `lib/date.ts` 写 `Temporal.Instant` 会报 "Cannot find name 'Temporal'".

- [ ] **Step 1: 修改 tsconfig.json**

Edit `packages/web/tsconfig.json`, 第 4 行:

```diff
   "compilerOptions": {
     "target": "ES2022",
-    "lib": ["dom", "dom.iterable", "ES2023"],
+    "lib": ["dom", "dom.iterable", "ES2025"],
     "allowJs": false,
```

- [ ] **Step 2: 跑 typecheck 验证 (临时跳过, 还没引入 Temporal)**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -5`
Expected: 当前 baseline 0 error. 不引入新 error (因为只改了 lib, 没改 source).

- [ ] **Step 3: Commit**

```bash
git add packages/web/tsconfig.json
git commit -m "chore(web): bump tsconfig lib to ES2025 for Temporal types"
```

---

### Task 1.2: 安装 @js-temporal/polyfill

**Files:**
- Modify: `packages/web/package.json` (deps)
- Modify: `packages/web/bun.lock` (auto)

**Context:** Bun 1.3.14 没有原生 Temporal. `@js-temporal/polyfill` 跟 spec 完全对齐 (Stage 3 冻结版本), 提供 `Temporal` 全局对象.

- [ ] **Step 1: 安装依赖**

Run: `cd packages/web && bun add @js-temporal/polyfill`
Expected: `package.json` 加 `"@js-temporal/polyfill": "^0.5.1"` (具体版本以 bun 输出为准), `bun.lock` 自动更新.

- [ ] **Step 2: 验证 import 可用**

Run: `cd packages/web && bun -e 'import("@js-temporal/polyfill").then(m => console.log(m.Temporal.Now.instant().toString()))'`
Expected: 输出形如 `2026-07-07T07:15:30.123Z`. 不抛错.

- [ ] **Step 3: Commit**

```bash
git add packages/web/package.json packages/web/bun.lock
git commit -m "chore(web): add @js-temporal/polyfill dependency"
```

---

### Task 1.3: 创建 lib/date.ts skeleton + 基础类型

**Files:**
- Create: `packages/web/lib/date.ts`

**Context:** 先建空模块 + `DateInput` 类型 + 内部 `toInstant` 私有函数,
后续 task 增量加 wrapper. 这样 Task 1.4 的 test 有最小可测目标.

- [ ] **Step 1: 创建 lib/date.ts 初始骨架**

Write `packages/web/lib/date.ts`:

```typescript
// TC39 Temporal wrapper, date-fns 4.x 风格 API
// (2026-07-07) 替代原生 Date API + date-fns 调用.
// 内部用 @js-temporal/polyfill (Bun 1.3.14 当前无原生 Temporal).
// @shared
import { Temporal } from "@js-temporal/polyfill";

/** Wrapper 函数接受的输入类型 */
export type DateInput = string | number | Date | Temporal.Instant;

/**
 * 输入值归一为 Temporal.Instant.
 * @param input ISO 字符串 / epoch ms / Date / Temporal.Instant
 * @returns Temporal.Instant
 * @throws RangeError 当 input 非法时 (替代 Date.parse 返回 NaN 的静默 fail)
 */
export const toInstant = (input: DateInput): Temporal.Instant => {
  if (input instanceof Temporal.Instant) {
    return input;
  }
  if (input instanceof Date) {
    return Temporal.Instant.fromEpochMilliseconds(input.getTime());
  }
  if (typeof input === "number") {
    return Temporal.Instant.fromEpochMilliseconds(input);
  }
  // string — Temporal.Instant.from 内部走 ISO 8601 parser, 比 Date.parse 严格
  return Temporal.Instant.from(input);
};
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -5`
Expected: 0 error. (类型来自 ES2025 lib, runtime 来自 polyfill.)

- [ ] **Step 3: Commit**

```bash
git add packages/web/lib/date.ts
git commit -m "feat(web): add lib/date.ts skeleton with toInstant helper"
```

---

### Task 1.4: 写 lib/date.test.ts (TDD red)

**Files:**
- Create: `packages/web/lib/date.test.ts`

**Context:** 先写失败测试 (针对 toInstant + 即将添加的全部 wrapper),
后续 task 增量实现让测试绿. 测试不 mock polyfill, 真实跑.

- [ ] **Step 1: 写测试文件**

Write `packages/web/lib/date.test.ts`:

```typescript
import { Temporal } from "@js-temporal/polyfill";
import { describe, expect, it } from "vitest";
import {
  addDays,
  addHours,
  differenceInDays,
  differenceInHours,
  differenceInMilliseconds,
  differenceInMinutes,
  differenceInSeconds,
  formatDate,
  formatDateTime,
  isAfter,
  isBefore,
  isEqual,
  nowInstant,
  nowIso,
  nowMs,
  toInstant,
} from "./date";

// 固定锚点: 2026-01-15T12:00:00Z (避免 Date.now() flaky)
const ANCHOR_ISO = "2026-01-15T12:00:00Z";
const ANCHOR_MS = Date.parse(ANCHOR_ISO);

describe("toInstant", () => {
  it("ISO string → Temporal.Instant", () => {
    const inst = toInstant(ANCHOR_ISO);
    expect(inst).toBeInstanceOf(Temporal.Instant);
    expect(inst.epochMilliseconds).toBe(ANCHOR_MS);
  });

  it("epoch ms → Temporal.Instant", () => {
    const inst = toInstant(ANCHOR_MS);
    expect(inst.epochMilliseconds).toBe(ANCHOR_MS);
  });

  it("Date → Temporal.Instant", () => {
    const inst = toInstant(new Date(ANCHOR_MS));
    expect(inst.epochMilliseconds).toBe(ANCHOR_MS);
  });

  it("Temporal.Instant 直通", () => {
    const original = Temporal.Instant.from(ANCHOR_ISO);
    expect(toInstant(original)).toBe(original);
  });

  it("非法 string 抛 RangeError", () => {
    expect(() => toInstant("not-a-date")).toThrow(RangeError);
  });
});

describe("nowMs / nowIso / nowInstant", () => {
  it("nowMs 返回 number 且单调递增", () => {
    const a = nowMs();
    const b = nowMs();
    expect(typeof a).toBe("number");
    expect(b).toBeGreaterThanOrEqual(a);
  });

  it("nowIso 返回合法 ISO 字符串", () => {
    const iso = nowIso();
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });

  it("nowInstant 返回 Temporal.Instant", () => {
    expect(nowInstant()).toBeInstanceOf(Temporal.Instant);
  });
});

describe("differenceInMilliseconds", () => {
  it("later - earlier = 正数", () => {
    expect(differenceInMilliseconds(ANCHOR_ISO, ANCHOR_ISO)).toBe(0);
    expect(differenceInMilliseconds("2026-01-15T12:00:01Z", ANCHOR_ISO)).toBe(1000);
  });

  it("earlier - later = 负数", () => {
    expect(differenceInMilliseconds(ANCHOR_ISO, "2026-01-15T12:00:01Z")).toBe(-1000);
  });
});

describe("differenceInSeconds / Minutes / Hours / Days", () => {
  it("差 60 秒", () => {
    expect(differenceInSeconds("2026-01-15T12:01:00Z", ANCHOR_ISO)).toBe(60);
  });
  it("差 5 分钟", () => {
    expect(differenceInMinutes("2026-01-15T12:05:00Z", ANCHOR_ISO)).toBe(5);
  });
  it("差 3 小时", () => {
    expect(differenceInHours("2026-01-15T15:00:00Z", ANCHOR_ISO)).toBe(3);
  });
  it("差 1 天", () => {
    expect(differenceInDays("2026-01-16T12:00:00Z", ANCHOR_ISO)).toBe(1);
  });
  it("跨月差 30 天 (1月15 → 2月14)", () => {
    expect(differenceInDays("2026-02-14T12:00:00Z", ANCHOR_ISO)).toBe(30);
  });
});

describe("addDays / addHours", () => {
  it("addDays 1 → 次日", () => {
    const result = addDays(ANCHOR_ISO, 1);
    expect(result.toISOString()).toBe("2026-01-16T12:00:00.000Z");
  });
  it("addDays -1 → 前一日", () => {
    const result = addDays(ANCHOR_ISO, -1);
    expect(result.toISOString()).toBe("2026-01-14T12:00:00.000Z");
  });
  it("addHours 5 → 5 小时后", () => {
    const result = addHours(ANCHOR_ISO, 5);
    expect(result.toISOString()).toBe("2026-01-15T17:00:00.000Z");
  });
  it("addDays 月末溢出 (1月31 + 1天 = 2月1)", () => {
    const result = addDays("2026-01-31T12:00:00Z", 1);
    // 本地时区决定具体日期, 但绝不会回退到 1 月
    expect(result.getUTCDate()).toBeGreaterThanOrEqual(1);
  });
});

describe("isAfter / isBefore / isEqual", () => {
  it("isAfter", () => {
    expect(isAfter("2026-01-16T00:00:00Z", ANCHOR_ISO)).toBe(true);
    expect(isAfter(ANCHOR_ISO, "2026-01-16T00:00:00Z")).toBe(false);
    expect(isAfter(ANCHOR_ISO, ANCHOR_ISO)).toBe(false);
  });
  it("isBefore", () => {
    expect(isBefore("2026-01-14T00:00:00Z", ANCHOR_ISO)).toBe(true);
    expect(isBefore(ANCHOR_ISO, ANCHOR_ISO)).toBe(false);
  });
  it("isEqual", () => {
    expect(isEqual(ANCHOR_ISO, ANCHOR_ISO)).toBe(true);
    expect(isEqual(ANCHOR_ISO, "2026-01-16T00:00:00Z")).toBe(false);
  });
});

describe("formatDate / formatDateTime", () => {
  it("formatDate zh-CN", () => {
    // 测试运行时跑在 CI (UTC), 用 snapshot 锁格式
    const result = formatDate(ANCHOR_ISO, "zh-CN");
    expect(result).toMatch(/^\d{4}\/\d{1,2}\/\d{1,2}$/);
  });
  it("formatDate en-US", () => {
    const result = formatDate(ANCHOR_ISO, "en-US");
    expect(result).toMatch(/^\d{1,2}\/\d{1,2}\/\d{4}$/);
  });
  it("formatDateTime zh-CN 含时分", () => {
    const result = formatDateTime(ANCHOR_ISO, "zh-CN");
    expect(result).toMatch(/\d{1,2}:\d{2}/);
  });
});
```

- [ ] **Step 2: 跑测试确认 RED**

Run: `cd packages/web && bun run test -- lib/date.test.ts 2>&1 | tail -20`
Expected: FAIL — 多个 test 因为 `differenceInDays` / `addDays` / `isAfter` 等函数尚未 export 而报 "is not a function".

- [ ] **Step 3: Commit red state**

```bash
git add packages/web/lib/date.test.ts
git commit -m "test(web): add lib/date.test.ts (TDD red state)"
```

---

### Task 1.5: 实现 differenceIn* / now* / add* / is* / format* (TDD green)

**Files:**
- Modify: `packages/web/lib/date.ts`

**Context:** 把 Task 1.4 的所有测试填上. 一次性加完所有 wrapper (约 200 行),
单 task 但单文件, 仍然 < 250 行 commit.

- [ ] **Step 1: 扩展 lib/date.ts**

Edit `packages/web/lib/date.ts`, 在 `toInstant` 之后追加:

```typescript
// ──────────── 当前时间 ────────────

/**
 * 当前时间 → Temporal.Instant. 仅 client / 事件 handler 调用 (SSR root 会有 hydration mismatch).
 * @returns Temporal.Instant
 */
export const nowInstant = (): Temporal.Instant => Temporal.Now.instant();

/**
 * 当前时间 → epoch ms. 替 Date.now().
 * @returns number (ms since epoch)
 */
export const nowMs = (): number => Temporal.Now.instant().epochMilliseconds;

/**
 * 当前时间 → ISO 8601 字符串. 替 new Date().toISOString().
 * @returns string (形如 2026-07-07T07:15:30.123Z)
 */
export const nowIso = (): string => Temporal.Now.instant().toString();

// ──────────── 差值 (date-fns 4.x 风格签名) ────────────

const durationOf = (later: DateInput, earlier: DateInput, largestUnit: Temporal.DateTimeUnit) =>
  toInstant(later).until(toInstant(earlier), { largestUnit });

/**
 * later - earlier 的毫秒数.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 毫秒差 (可为负)
 */
export const differenceInMilliseconds = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "milliseconds").milliseconds;

/** later - earlier 的秒数 */
export const differenceInSeconds = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "seconds").seconds;

/** later - earlier 的分钟数 */
export const differenceInMinutes = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "minutes").minutes;

/** later - earlier 的小时数 */
export const differenceInHours = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "hours").hours;

/** later - earlier 的天数 (跨月/跨年自动归一化) */
export const differenceInDays = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "days").days;

// ──────────── 加减 (返回 Date 跟现有代码兼容) ────────────

const shift = (date: DateInput, duration: Temporal.DurationLike): Date => {
  const zdt = toInstant(date).toZonedDateTimeISO(Temporal.Now.timeZoneId());
  return new Date(zdt.add(duration).epochMilliseconds);
};

/** date + N 天. 月末溢出由 Temporal 规范处理. */
export const addDays = (date: DateInput, amount: number): Date => shift(date, { days: amount });

/** date + N 小时 */
export const addHours = (date: DateInput, amount: number): Date => shift(date, { hours: amount });

/** date + N 分钟 */
export const addMinutes = (date: DateInput, amount: number): Date => shift(date, { minutes: amount });

/** date + N 秒 */
export const addSeconds = (date: DateInput, amount: number): Date => shift(date, { seconds: amount });

/** date + N 毫秒 */
export const addMilliseconds = (date: DateInput, amount: number): Date =>
  shift(date, { milliseconds: amount });

// ──────────── 比较 ────────────

const instantOf = (input: DateInput) => toInstant(input).epochMilliseconds;

/** date > dateToCompare */
export const isAfter = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) > instantOf(dateToCompare);

/** date < dateToCompare */
export const isBefore = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) < instantOf(dateToCompare);

/** date === dateToCompare */
export const isEqual = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) === instantOf(dateToCompare);

// ──────────── 格式化 ────────────

/**
 * ISO → 本地化日期 (替 `new Intl.DateTimeFormat(locale, {...}).format(new Date(iso))`).
 * @param iso ISO 8601 字符串
 * @param locale  BCP-47 locale, 项目只用 'zh-CN' / 'en-US'
 * @returns 本地化日期字符串
 */
export const formatDate = (iso: string, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "numeric",
    year: "numeric",
  }).format(new Date(iso));

/**
 * ISO → 本地化日期+时间 (替 `new Date(iso).toLocaleString()`).
 * @param iso ISO 8601 字符串
 * @param locale BCP-47 locale
 * @returns 本地化日期时间字符串
 */
export const formatDateTime = (iso: string, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
```

- [ ] **Step 2: 跑测试确认 GREEN**

Run: `cd packages/web && bun run test -- lib/date.test.ts 2>&1 | tail -10`
Expected: 全部 pass. 0 fail.

- [ ] **Step 3: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -5`
Expected: 0 error.

- [ ] **Step 4: 跑 lint + format**

Run: `cd packages/web && bun run lint:fix && bun run format`
Expected: 0 error / 0 diff.

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/date.ts
git commit -m "feat(web): implement full lib/date.ts wrapper module (TDD green)"
```

---

### Task 1.6: Phase 1 完整验证

**Files:** (无文件改动, 跑命令)

- [ ] **Step 1: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致, 无新 fail.

- [ ] **Step 2: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck && bun run lint`
Expected: 全部 0 error.

- [ ] **Step 3: 报告 Phase 1 完成**

向用户报告:
- tsconfig lib 升级到 ES2025
- @js-temporal/polyfill 安装
- lib/date.ts + lib/date.test.ts 新增
- 全量测试 baseline 持平
- 准备进入 Phase 2 (业务迁移)

---

## Phase 2 — 替换 date-fns 1 处 + Intl.DateTimeFormat 4 处 (~10 处)

### Task 2.1: restore-deletion-banner.tsx 迁移 (date-fns → lib/date)

**Files:**
- Modify: `packages/web/app/[locale]/account/settings/_components/restore-deletion-banner.tsx:12,42-43`

**Context:** 唯一 date-fns 调用点. 从 `date-fns` import 改为 `@/lib/date`.

- [ ] **Step 1: Edit imports**

Edit `packages/web/app/[locale]/account/settings/_components/restore-deletion-banner.tsx`:

```diff
 import { type DeletionState, cancelDeletionAction } from "@/app/[locale]/_actions/account-settings";
 import { AppField, AppForm, AppSubmit } from "@/components/common/form";
 import { Button } from "@/components/ui/button";
 import { HOURS_PER_DAY, ZERO } from "@/const";
-import { differenceInDays, differenceInHours } from "date-fns";
+import { differenceInDays, differenceInHours } from "@/lib/date";
```

- [ ] **Step 2: 跑对应测试**

Run: `cd packages/web && bun run test -- restore-deletion-banner.test.tsx 2>&1 | tail -10`
Expected: 3 test pass (跟 baseline 一致).

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && cd packages/web && bun run lint 2>&1 | tail -3`
Expected: 0 error.

---

### Task 2.2: change-timeline.tsx 迁移 (Intl.DateTimeFormat → formatDate)

**Files:**
- Modify: `packages/web/app/[locale]/buyers/[id]/_components/change-timeline.tsx:19-29`

**Context:** 局部 `formatDateTime` 函数, 用 Intl.DateTimeFormat. 直接替换为 lib/date 的 formatDateTime.

**因原文件已有 `formatDateTime` 函数名, 用 `as` 重命名避免冲突.**

- [ ] **Step 1: Edit imports + 替换函数体**

`packages/web/app/[locale]/buyers/[id]/_components/change-timeline.tsx`:

```diff
 import { Badge } from "@/components/ui/badge";
 import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
+import { formatDateTime as formatDateTimeZh } from "@/lib/date";
 import { Clock, RefreshCw } from "lucide-react";
 import { useTranslations } from "next-intl";
 import type { ChangeLog } from "@/app/[locale]/buyers/_lib/buyer-profile/types";

 /** 空数组长度 */
 const EMPTY_LENGTH = 0;

 /**
  * 格式化 ISO 时间为中文短格式
  * @param iso - ISO 时间字符串
  * @returns 格式化后的时间字符串
  */
 const formatDateTime = (iso: string | null): string => {
   if (!iso) {
     return "—";
   }
-  return new Intl.DateTimeFormat("zh-CN", {
-    day: "2-digit",
-    hour: "2-digit",
-    minute: "2-digit",
-    month: "2-digit",
-  }).format(new Date(iso));
+  return formatDateTimeZh(iso, "zh-CN");
 };
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

---

### Task 2.3: evaluate-list-view.tsx 迁移

**Files:**
- Modify: `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx:21-26`

**Context:** 同样是 `new Intl.DateTimeFormat(locale, ...).format(new Date(iso))` 模板.

- [ ] **Step 1: Read 当前实现**

Read `packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx:15-30`.

- [ ] **Step 2: Edit import + 替换函数体**

具体步骤根据 Read 结果调整. 模板:

```diff
+import { formatDate } from "@/lib/date";
 // ...
-  new Intl.DateTimeFormat(locale, { day: "numeric", month: "numeric", year: "numeric" }).format(new Date(iso));
+  formatDate(iso, locale);
```

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx
git commit -m "refactor(web): evaluate-list-view use lib/date.formatDate"
```

---

### Task 2.4: buyers/page.tsx 迁移

**Files:**
- Modify: `packages/web/app/[locale]/buyers/page.tsx:60-72`

- [ ] **Step 1: Read 当前实现**

Read `packages/web/app/[locale]/buyers/page.tsx:58-75`.

- [ ] **Step 2: Edit import + 替换**

模板:

```diff
+import { formatDate } from "@/lib/date";
 // ...
-  return new Intl.DateTimeFormat("zh-CN", { day: "numeric", month: "numeric", year: "numeric" }).format(new Date(iso));
+  return formatDate(iso, "zh-CN");
```

- [ ] **Step 3: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/buyers/page.tsx
git commit -m "refactor(web): buyers/page use lib/date.formatDate"
```

---

### Task 2.5: admin tables 4 文件批量迁移 (toLocaleDateString → formatDate)

**Files:**
- Modify: `packages/web/app/[locale]/admin/invites/_components/admin-invites-table.tsx:29`
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-audit-log.tsx:65`
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx:36`
- Modify: `packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx:271,277`

**Context:** 4 个 admin 表格组件, 都是 `new Date(iso).toLocaleDateString()` 或 `toLocaleString()`.

- [ ] **Step 1: Read 4 个文件相关行确认 locale 来源**

```bash
grep -n "toLocaleDateString\|toLocaleString" packages/web/app/[locale]/admin/{invites/_components/admin-invites-table,dicts/_components/dict-audit-log,pre-analysis/_components/admin-pre-analysis-client,users/_components/admin-users-table}.tsx
```

确认每个文件用 `useTranslations()` 还是 hardcoded "zh-CN".

- [ ] **Step 2: 替换 admin-invites-table.tsx**

模板:

```diff
+import { formatDate } from "@/lib/date";
 // ...
-const renderDate = (value: string) => new Date(value).toLocaleDateString();
+const renderDate = (value: string) => formatDate(value, locale);
```

(如果文件已有 `locale` 变量, 直接用; 否则从 `useTranslations()` 上下文推断.)

- [ ] **Step 3: 替换 dict-audit-log.tsx (toLocaleString → formatDateTime)**

模板:

```diff
+import { formatDateTime } from "@/lib/date";
 // ...
-{new Date(entry.ts).toLocaleString()}
+{formatDateTime(entry.ts, locale)}
```

- [ ] **Step 4: 替换 admin-pre-analysis-client.tsx**

模板同上, 函数 `formatTime` 内部用 `formatDateTime(value, locale)`.

- [ ] **Step 5: 替换 admin-users-table.tsx (2 处 toLocaleDateString)**

```diff
-    cell: (ctx) => new Date(ctx.row.original.created_at).toLocaleDateString(),
+    cell: (ctx) => formatDate(ctx.row.original.created_at, locale),
-    cell: (ctx) => new Date(ctx.row.original.last_seen_at).toLocaleDateString(),
+    cell: (ctx) => formatDate(ctx.row.original.last_seen_at, locale),
```

- [ ] **Step 6: 跑 typecheck + lint + 4 文件对应测试**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 error. (这 4 个文件若无 test file, 跳过 test step.)

- [ ] **Step 7: Commit**

```bash
git add packages/web/app/[locale]/admin/{invites/_components/admin-invites-table,dicts/_components/dict-audit-log,pre-analysis/_components/admin-pre-analysis-client,users/_components/admin-users-table}.tsx
git commit -m "refactor(web): admin tables use lib/date.formatDate/formatDateTime"
```

---

### Task 2.6: Phase 2 验证 + 批量提交

- [ ] **Step 1: 批量提交 Phase 2 所有文件**

```bash
git add packages/web/app/[locale]/account/settings/_components/restore-deletion-banner.tsx packages/web/app/[locale]/buyers/[id]/_components/change-timeline.tsx packages/web/app/[locale]/evaluate/_components/evaluate-list-view.tsx packages/web/app/[locale]/buyers/page.tsx packages/web/app/[locale]/admin/invites/_components/admin-invites-table.tsx packages/web/app/[locale]/admin/dicts/_components/dict-audit-log.tsx packages/web/app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx
git commit -m "refactor(web): replace date-fns + Intl.DateTimeFormat with lib/date helpers"
```

- [ ] **Step 2: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致.

- [ ] **Step 2: 报告 Phase 2 完成**

向用户报告:
- date-fns 1 处 + Intl 4 处 + admin 表格 4 文件已迁移
- 测试 0 新 fail
- 准备进入 Phase 3 (`lib/` 工具层)

---

## Phase 3 — `lib/` 工具层 (~15 处)

### Task 3.1: lib/log.ts + lib/rate-limiter.ts + lib/format.ts

**Files:**
- Modify: `packages/web/lib/log.ts:39`
- Modify: `packages/web/lib/rate-limiter.ts:36,59`
- Modify: `packages/web/lib/format.ts:45`

**Context:** 3 个工具函数, 简单替换 `Date.now()` / `new Date().toISOString()`.

- [ ] **Step 1: Edit lib/log.ts**

```diff
+import { nowIso } from "@/lib/date";
 // ...
-  const isoTime = new Date().toISOString().slice(TIME_START_INDEX, TIME_END_INDEX);
+  const isoTime = nowIso().slice(TIME_START_INDEX, TIME_END_INDEX);
```

- [ ] **Step 2: Edit lib/rate-limiter.ts**

```diff
+import { nowMs } from "@/lib/date";
 // ...
-  const now = Date.now();
+  const now = nowMs();
```

(2 处都改, 都是 `const now = Date.now();`)

- [ ] **Step 3: Edit lib/format.ts**

```diff
+import { nowMs } from "@/lib/date";
 // ...
-  now: number = Date.now() / MS_PER_SECOND,
+  now: number = nowMs() / MS_PER_SECOND,
```

- [ ] **Step 4: 跑 lib/format.test.ts**

Run: `cd packages/web && bun run test -- lib/format.test.ts 2>&1 | tail -10`
Expected: 全 pass.

- [ ] **Step 5: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/log.ts packages/web/lib/rate-limiter.ts packages/web/lib/format.ts
git commit -m "refactor(web): lib/ tool layer use lib/date.now* helpers"
```

---

### Task 3.2: lib/chat/use-chat-state.ts (6 处)

**Files:**
- Modify: `packages/web/lib/chat/use-chat-state.ts:103,107,185,230,274,278`

- [ ] **Step 1: Read 当前实现**

Read `packages/web/lib/chat/use-chat-state.ts:100-115, 180-235, 270-285`.

- [ ] **Step 2: Edit imports**

```diff
+import { nowMs, toInstant } from "@/lib/date";
```

(若文件已有 `import { ... } from "@/lib/..."` 之类的, 合并到现有 import group.)

- [ ] **Step 3: 替换 6 处**

模板:

```diff
-  createdAt: Date.parse(server.created_at),
+  createdAt: toInstant(server.created_at).epochMilliseconds,
-  updatedAt: Date.parse(server.updated_at),
+  updatedAt: toInstant(server.updated_at).epochMilliseconds,
-  createdAt: Date.parse(msg.created_at),
+  createdAt: toInstant(msg.created_at).epochMilliseconds,
-  createdAt: Date.parse(uimsg.id) || Date.now(),
+  createdAt: toInstant(uimsg.id).epochMilliseconds || nowMs(),
-  createdAt: Date.now(),
+  createdAt: nowMs(),
-  updatedAt: Date.now(),
+  updatedAt: nowMs(),
```

注意: `createdAt` 字段类型是 `number` (ms), 所以 `.epochMilliseconds` 而不是 `Temporal.Instant`. 

- [ ] **Step 4: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -10`
Expected: 0 error. 注意检查 `createdAt: number` 类型.

- [ ] **Step 5: 跑 chat 相关测试**

Run: `cd packages/web && bun run test -- lib/chat 2>&1 | tail -10`
Expected: 全 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/chat/use-chat-state.ts
git commit -m "refactor(web): use-chat-state use lib/date.toInstant/nowMs"
```

---

### Task 3.3: lib/chat/ui-message-adapter.ts (2 处)

**Files:**
- Modify: `packages/web/lib/chat/ui-message-adapter.ts:67,88`

- [ ] **Step 1: Edit imports**

```diff
+import { nowMs, toInstant } from "@/lib/date";
```

- [ ] **Step 2: 替换 2 处**

```diff
-      (Number.isFinite(Date.parse(ui.id)) ? Date.parse(ui.id) : Date.now()),
+      (Number.isFinite(toInstant(ui.id).epochMilliseconds) ? toInstant(ui.id).epochMilliseconds : nowMs()),
```

简化版本 (用变量):

```typescript
const parsed = toInstant(ui.id).epochMilliseconds;
const createdAt = Number.isFinite(parsed) ? parsed : nowMs();
```

```diff
-  createdAt: Date.parse(server.created_at) || Date.now(),
+  createdAt: toInstant(server.created_at).epochMilliseconds || nowMs(),
```

- [ ] **Step 3: 跑测试**

Run: `cd packages/web && bun run test -- lib/chat/ui-message-adapter.test.ts 2>&1 | tail -10`
Expected: 全 pass.

- [ ] **Step 4: Commit**

```bash
git add packages/web/lib/chat/ui-message-adapter.ts
git commit -m "refactor(web): ui-message-adapter use lib/date.toInstant/nowMs"
```

---

### Task 3.4: lib/chat/migration.ts (3 处)

**Files:**
- Modify: `packages/web/lib/chat/migration.ts:46,49,99,106`

- [ ] **Step 1: Edit imports**

```diff
+import { nowIso, nowMs } from "@/lib/date";
```

- [ ] **Step 2: 替换**

```diff
-    if (Date.now() - last < DEBOUNCE_MS) {
+    if (nowMs() - last < DEBOUNCE_MS) {
-    globalThis.localStorage.setItem(DEBOUNCE_KEY, String(Date.now()));
+    globalThis.localStorage.setItem(DEBOUNCE_KEY, String(nowMs()));
-    exported_at: new Date().toISOString(),
+    exported_at: nowIso(),
-    triggerBrowserDownload(blob, `rag-chat-backup-${Date.now()}.json`);
+    triggerBrowserDownload(blob, `rag-chat-backup-${nowMs()}.json`);
```

- [ ] **Step 3: 跑 typecheck + 测试**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run test -- lib/chat/migration 2>&1 | tail -10`
Expected: 0 error, 全 pass.

- [ ] **Step 4: Commit**

```bash
git add packages/web/lib/chat/migration.ts
git commit -m "refactor(web): chat migration use lib/date.nowMs/nowIso"
```

---

### Task 3.5: Phase 3 验证 + 批量提交

- [ ] **Step 1: 批量提交 Phase 3 所有文件**

```bash
git add packages/web/lib/log.ts packages/web/lib/rate-limiter.ts packages/web/lib/chat/chat-utils.ts packages/web/lib/chat/migration.ts packages/web/lib/chat/ui-message-adapter.ts packages/web/lib/chat/use-chat-state.ts
git commit -m "refactor(web): lib/ tool layer use lib/date helpers"
```

- [ ] **Step 2: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致.

- [ ] **Step 2: 报告 Phase 3 完成**

向用户报告: lib/ 工具层全部迁移完毕, 测试 0 新 fail, 准备 Phase 4 (components/).

---

## Phase 4 — `components/` (~9 处)

### Task 4.1: components/chat/share-dialog.tsx (1 处)

**Files:**
- Modify: `packages/web/components/chat/share-dialog.tsx:82`

**Context:** `message.createdAt` 是 epoch ms, 需转为 ISO 字符串传给后端. 改用 `toInstant` 转换.

- [ ] **Step 1: Edit**

```diff
+import { toInstant } from "@/lib/date";
 // ...
-          timestamp: new Date(message.createdAt).toISOString(),
+          timestamp: toInstant(message.createdAt).toString(),
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/chat/share-dialog.tsx
git commit -m "refactor(web): share-dialog use lib/date.nowIso"
```

---

### Task 4.2: components/chat/shared-chat-view.tsx (2 处)

**Files:**
- Modify: `packages/web/components/chat/shared-chat-view.tsx:56,80`

- [ ] **Step 1: Edit imports**

```diff
+import { formatDate, toInstant } from "@/lib/date";
```

- [ ] **Step 2: 替换**

```diff
-        <span className={HEADER_MARGIN_CLASS}>{new Date(createdAt).toLocaleDateString()}</span>
+        <span className={HEADER_MARGIN_CLASS}>{formatDate(createdAt, locale)}</span>
 // ...
-              createdAt: msg.timestamp ? Date.parse(msg.timestamp) : Date.now(),
+              createdAt: msg.timestamp ? toInstant(msg.timestamp).epochMilliseconds : nowMs(),
```

需要 `nowMs` import 也加进来 (跟 `toInstant` 同一行).

- [ ] **Step 3: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 4: Commit**

```bash
git add packages/web/components/chat/shared-chat-view.tsx
git commit -m "refactor(web): shared-chat-view use lib/date helpers"
```

---

### Task 4.3: components/chat/use-composer-attachments.ts (1 处)

**Files:**
- Modify: `packages/web/components/chat/use-composer-attachments.ts:76`

- [ ] **Step 1: Edit**

```diff
+import { nowMs } from "@/lib/date";
 // ...
-    const tempId = `tmp-${Date.now()}-${Math.random().toString(RANDOM_ID_RADIX).slice(RANDOM_ID_START)}`;
+    const tempId = `tmp-${nowMs()}-${Math.random().toString(RANDOM_ID_RADIX).slice(RANDOM_ID_START)}`;
```

- [ ] **Step 2: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/chat/use-composer-attachments.ts
git commit -m "refactor(web): use-composer-attachments use lib/date.nowMs"
```

---

### Task 4.4: components/chat/voice-recorder.tsx (3 处)

**Files:**
- Modify: `packages/web/components/chat/voice-recorder.tsx:117,138,148`

- [ ] **Step 1: Edit**

```diff
+import { nowMs } from "@/lib/date";
 // ...
-      setDuration(Math.floor((Date.now() - startedAtRef.current) / MS_PER_SECOND));
+      setDuration(Math.floor((nowMs() - startedAtRef.current) / MS_PER_SECOND));
-      const fileName = `recording-${Date.now()}.${getFileExtension(supportedMime)}`;
+      const fileName = `recording-${nowMs()}.${getFileExtension(supportedMime)}`;
-    startedAtRef.current = Date.now();
+    startedAtRef.current = nowMs();
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add packages/web/components/chat/voice-recorder.tsx
git commit -m "refactor(web): voice-recorder use lib/date.nowMs"
```

---

### Task 4.5: health/_components/hero-section.tsx (2 处)

**Files:**
- Modify: `packages/web/app/[locale]/health/_components/hero-section.tsx:83,86`

- [ ] **Step 1: Edit imports**

```diff
+import { nowMs, toInstant } from "@/lib/date";
```

- [ ] **Step 2: 替换**

```diff
-  useInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
+  useInterval(() => setNow(nowMs()), POLL_INTERVAL_MS);
 // ...
-    Math.floor((now - new Date(iso).getTime()) / MS_PER_SECOND),
+    Math.floor((now - toInstant(iso).epochMilliseconds) / MS_PER_SECOND),
```

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/[locale]/health/_components/hero-section.tsx
git commit -m "refactor(web): hero-section use lib/date.nowMs/toInstant"
```

---

### Task 4.6: Phase 4 验证 + 批量提交

- [ ] **Step 1: 批量提交 Phase 4 所有文件**

```bash
git add packages/web/components/chat/share-dialog.tsx packages/web/components/chat/shared-chat-view.tsx packages/web/components/chat/use-composer-attachments.ts packages/web/components/chat/voice-recorder.tsx packages/web/app/[locale]/health/_components/hero-section.tsx
git commit -m "refactor(web): components/ use lib/date helpers"
```

- [ ] **Step 2: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致.

- [ ] **Step 2: 报告 Phase 4 完成**

向用户报告: components/ 全部迁移完毕, 测试 0 新 fail, 准备 Phase 5 (app/).

---

## Phase 5 — `app/` 业务层 (~10 处)

### Task 5.1: app/api/knowledge/batch/route.ts (1 处)

**Files:**
- Modify: `packages/web/app/api/knowledge/batch/route.ts:47`

- [ ] **Step 1: Edit**

```diff
+import { nowMs } from "@/lib/date";
 // ...
-    await DifyDatasets.createDocumentByText(datasetId, `batch-qa-${Date.now()}-${idx}`, content);
+    await DifyDatasets.createDocumentByText(datasetId, `batch-qa-${nowMs()}-${idx}`, content);
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
git add packages/web/app/api/knowledge/batch/route.ts
git commit -m "refactor(web): knowledge batch route use lib/date.nowMs"
```

---

### Task 5.2: scripts/duplication-report.ts (1 处)

**Files:**
- Modify: `packages/web/scripts/duplication-report.ts:66`

- [ ] **Step 1: Edit**

```diff
+import { nowIso } from "@/lib/date";
 // ...
-lines.push(`检测时间: ${new Date().toISOString().slice(FIRST_INDEX, DATE_SLICE_END)}`);
+lines.push(`检测时间: ${nowIso().slice(FIRST_INDEX, DATE_SLICE_END)}`);
```

注意: scripts/ 不是 tsconfig `include` 范围 (tsconfig include 是 `**/*.ts` `**/*.tsx`).
但 bun 跑 .ts 时仍走 lib config. 验证:

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error. (scripts/ 在 tsconfig include 里.)

- [ ] **Step 3: Commit**

```bash
git add packages/web/scripts/duplication-report.ts
git commit -m "refactor(web): duplication-report use lib/date.nowIso"
```

---

### Task 5.3: app/[locale]/admin/users/_hooks/use-roles.ts (注释提及 Date.now)

**Files:**
- Modify: `packages/web/app/[locale]/admin/users/_hooks/use-roles.ts:26` (仅注释, 非生产调用)

**Context:** 这一行只是注释提及 `Date.now()`, 不是实际调用. spec 严格说不在替换范围.
但保留 `Date.now` 字眼容易让 reviewer 误以为漏了. 注释改为:

```diff
-  // 用 useRef 防重复, 不用 dataUpdatedAt (initialData 下它为 Date.now(), 不是 0)
+  // 用 useRef 防重复, 不用 dataUpdatedAt (initialData 下它为当前时间 ms, 不是 0)
```

- [ ] **Step 1: Edit 注释**

- [ ] **Step 2: Commit**

```bash
git add packages/web/app/[locale]/admin/users/_hooks/use-roles.ts
git commit -m "docs(web): use-roles comment rephrase Date.now() reference"
```

---

### Task 5.4: Phase 5 全量验证 + 批量提交

- [ ] **Step 1: 批量提交 Phase 5 所有文件**

```bash
git add packages/web/app/api/knowledge/batch/route.ts packages/web/scripts/duplication-report.ts packages/web/app/[locale]/admin/users/_hooks/use-roles.ts
git commit -m "refactor(web): app/ business layer use lib/date helpers"
```

- [ ] **Step 2: 全量 grep 原生 Date API**

Run: `grep -rEn "Date\\.now|new Date\\(|Date\\.parse" packages/web/{app,components,lib} --include="*.ts" --include="*.tsx" | grep -v ".test." | grep -v ".spec."`
Expected: 0 命中 (test fixture 文件允许 `new Date(Date.now() + FIVE_DAYS_MS)`, 但本步骤只看生产代码).

如果还有命中: 检查是否在测试 fixture (`.test.ts` / `.test.tsx`), 是则忽略; 否则漏改.

- [ ] **Step 2: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致.

- [ ] **Step 3: 报告 Phase 5 完成**

向用户报告: app/ 业务层 + scripts 全部迁移, 全文 0 原生 Date 调用, 准备 Phase 6 (删 date-fns 依赖).

---

## Phase 6 — 删 date-fns 依赖 + 文档同步

### Task 6.1: 删除 date-fns 依赖

**Files:**
- Modify: `packages/web/package.json`
- Modify: `packages/web/bun.lock` (auto)

- [ ] **Step 1: 移除依赖**

Run: `cd packages/web && bun remove date-fns`
Expected: `package.json` 删 `"date-fns": "^4.4.0"`, `bun.lock` 更新.

- [ ] **Step 2: 全文 grep 确认 0 引用**

Run: `grep -rEn "date-fns" packages/web --include="*.ts" --include="*.tsx" --include="*.json" | grep -v "node_modules" | grep -v "bun.lock"`
Expected: 0 命中.

- [ ] **Step 3: 跑全量 vitest + typecheck + lint**

Run: `cd packages/web && bun run test 2>&1 | tail -5 && bun run typecheck 2>&1 | tail -3 && bun run lint 2>&1 | tail -3`
Expected: 0 fail / 0 error.

- [ ] **Step 4: Commit**

```bash
git add packages/web/package.json packages/web/bun.lock
git commit -m "chore(web): remove date-fns dependency (replaced by lib/date)"
```

---

### Task 6.2: 同步 CLAUDE.md 文档

**Files:**
- Modify: `packages/web/CLAUDE.md` (新增段)

**Context:** spec §10 要求同步文档. 在 `packages/web/CLAUDE.md` 「封装组件」段后加 `lib/date` 条目.

- [ ] **Step 1: 找到合适插入点**

Run: `grep -n "封装组件\|封装新组件流程" packages/web/CLAUDE.md`
Expected: 显示行号. 在「封装组件 (2026-06-14)」段后追加.

- [ ] **Step 2: 追加 lib/date 条目**

在 `### 新封装 (6, 2026-06-18)` 段**前**插入:

```markdown
### `lib/date` (2026-07-07 Temporal wrapper)

替代 `date-fns` + 原生 `Date` 的统一 API. date-fns 4.x 风格签名 (differenceInDays, addDays, formatDate 等),
内部用 TC39 Temporal via `@js-temporal/polyfill`. 所有业务时间计算 / 格式化走这里, 禁止直接用 `Date.now()` / `new Date()` / `Date.parse()` / `Intl.DateTimeFormat`.

- **API**: `toInstant` / `nowInstant` / `nowMs` / `nowIso` / `differenceIn*` / `add*` / `isAfter|Before|Equal` / `formatDate|DateTime`
- **输入类型**: `DateInput = string | number | Date | Temporal.Instant`, 业务调用零改动
- **测试**: `lib/date.test.ts` 覆盖所有 export (vitest, 不 mock polyfill)
- **依赖**: `@js-temporal/polyfill` (~25KB gzip), bun + Node 22 都跑得动
- **spec**: [docs/superpowers/specs/2026-07-07-temporal-date-wrapper-design.md](../../docs/superpowers/specs/2026-07-07-temporal-date-wrapper-design.md)
```

- [ ] **Step 3: Commit**

```bash
git add packages/web/CLAUDE.md
git commit -m "docs(web): add lib/date wrapper to CLAUDE.md"
```

---

### Task 6.3: 更新 i18n-deferred-tasks.md

**Files:**
- Modify: `docs/todo/i18n-deferred-tasks.md`

**Context:** spec §10 要求删 `fmtDate` 项 (已通过 `formatDate(locale)` 实现).

- [ ] **Step 1: Read 当前文件**

Read `docs/todo/i18n-deferred-tasks.md`, 找 `fmtDate` 条目.

- [ ] **Step 2: 删除 fmtDate 条目或加备注**

如果文件存在 `fmtDate` 任务项, 删除该段. 如果只提了一句, 改为:

```diff
-- locale-aware fmtDate (用 Temporal Intl, 全 zh-only)
+- locale-aware fmtDate: ✅ 已实现 (lib/date.formatDate(locale), 2026-07-07)
```

- [ ] **Step 3: Commit**

```bash
git add docs/todo/i18n-deferred-tasks.md
git commit -m "docs: mark fmtDate i18n task done (lib/date.formatDate 2026-07-07)"
```

---

### Task 6.4: 最终全量验证 (无多余 commit, Phase 6 已随 Task 6.1-6.3 分 3 次提交)

- [ ] **Step 1: 跑全量 vitest**

Run: `cd packages/web && bun run test 2>&1 | tail -5`
Expected: 跟 baseline 719 passed + 8 deferred 一致, **0 新 fail**.

- [ ] **Step 2: 跑 typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | tail -3`
Expected: 0 error.

- [ ] **Step 3: 跑 lint**

Run: `cd packages/web && bun run lint 2>&1 | tail -3`
Expected: 0 warning / 0 error.

- [ ] **Step 4: 跑 format check**

Run: `cd packages/web && bun run format:check 2>&1 | tail -3`
Expected: 0 diff.

- [ ] **Step 5: 验证 grep 0 命中**

```bash
grep -rEn "Date\\.now|new Date\\(|Date\\.parse" packages/web/{app,components,lib} --include="*.ts" --include="*.tsx" | grep -v ".test." | grep -v ".spec." | grep -v node_modules
grep -rEn "date-fns" packages/web --include="*.ts" --include="*.tsx" --include="*.json" | grep -v node_modules | grep -v bun.lock
grep -rEn "from \"date-fns\"\|from 'date-fns'" packages/web --include="*.ts" --include="*.tsx" | grep -v node_modules
```

Expected: 全部 0 命中.

- [ ] **Step 6: 报告完成**

向用户报告:
- 6 phase 全部 commit 通过
- 全量测试 baseline 持平 (719 passed + 8 deferred)
- date-fns 依赖已删, lib/date 是统一入口
- 文档同步完毕
- spec §6 Phase 1-6 + §9 验收标准 + §10 文档同步全部满足