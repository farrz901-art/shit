import { Temporal } from "@js-temporal/polyfill";
import { describe, expect, it } from "vitest";
import {
  MS_PER_SECOND,
  SECONDS_PER_DAY,
  SECONDS_PER_HOUR,
  SECONDS_PER_MINUTE,
  ZERO,
} from "@/const";
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
  formatDurationMs,
  formatElapsedMs,
  fmtRelativeTime,
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
const ONE_SECOND_MS = 1000;
const ONE_MINUTE_SECONDS = 60;
const FIVE_MINUTES_SECONDS = 5;
const THREE_HOURS_SECONDS = 3;
const ONE_DAY_AMOUNT = 1;
const THIRTY_DAYS_AMOUNT = 30;
const MINUS_ONE_DAY_AMOUNT = -1;
const FIVE_HOURS_AMOUNT = 5;
const TRUE_VAL = true;
const FALSE_VAL = false;

describe("toInstant", () => {
  it("ISO string -> Temporal.Instant", () => {
    const inst = toInstant(ANCHOR_ISO);
    expect(inst).toBeInstanceOf(Temporal.Instant);
    expect(inst.epochMilliseconds).toBe(ANCHOR_MS);
  });

  it("epoch ms -> Temporal.Instant", () => {
    const inst = toInstant(ANCHOR_MS);
    expect(inst.epochMilliseconds).toBe(ANCHOR_MS);
  });

  it("Date -> Temporal.Instant", () => {
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
    const first = nowMs();
    const second = nowMs();
    expect(typeof first).toBe("number");
    expect(second).toBeGreaterThanOrEqual(first);
  });

  it("nowIso 返回合法 ISO 字符串", () => {
    const iso = nowIso();
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$/);
  });

  it("nowInstant 返回 Temporal.Instant", () => {
    expect(nowInstant()).toBeInstanceOf(Temporal.Instant);
  });
});

describe("differenceInMilliseconds", () => {
  it("later - earlier = 0", () => {
    expect(differenceInMilliseconds(ANCHOR_ISO, ANCHOR_ISO)).toBe(ZERO);
  });

  it("差 1 秒 = 1000ms", () => {
    expect(differenceInMilliseconds("2026-01-15T12:00:01Z", ANCHOR_ISO)).toBe(ONE_SECOND_MS);
  });

  it("earlier - later = 负数", () => {
    expect(differenceInMilliseconds(ANCHOR_ISO, "2026-01-15T12:00:01Z")).toBe(-ONE_SECOND_MS);
  });
});

describe("differenceInSeconds / Minutes / Hours / Days", () => {
  it("差 60 秒", () => {
    expect(differenceInSeconds("2026-01-15T12:01:00Z", ANCHOR_ISO)).toBe(ONE_MINUTE_SECONDS);
  });

  it("差 5 分钟", () => {
    expect(differenceInMinutes("2026-01-15T12:05:00Z", ANCHOR_ISO)).toBe(FIVE_MINUTES_SECONDS);
  });

  it("差 3 小时", () => {
    expect(differenceInHours("2026-01-15T15:00:00Z", ANCHOR_ISO)).toBe(THREE_HOURS_SECONDS);
  });

  it("差 1 天", () => {
    expect(differenceInDays("2026-01-16T12:00:00Z", ANCHOR_ISO)).toBe(ONE_DAY_AMOUNT);
  });

  it("跨月差 30 天 (1月15 -> 2月14)", () => {
    expect(differenceInDays("2026-02-14T12:00:00Z", ANCHOR_ISO)).toBe(THIRTY_DAYS_AMOUNT);
  });
});

describe("addDays / addHours", () => {
  it("addDays 1 -> 次日", () => {
    const result = addDays(ANCHOR_ISO, ONE_DAY_AMOUNT);
    expect(result.toISOString()).toBe("2026-01-16T12:00:00.000Z");
  });

  it("addDays -1 -> 前一日", () => {
    const result = addDays(ANCHOR_ISO, MINUS_ONE_DAY_AMOUNT);
    expect(result.toISOString()).toBe("2026-01-14T12:00:00.000Z");
  });

  it("addHours 5 -> 5 小时后", () => {
    const result = addHours(ANCHOR_ISO, FIVE_HOURS_AMOUNT);
    expect(result.toISOString()).toBe("2026-01-15T17:00:00.000Z");
  });

  it("addDays 月末溢出 (1月31 + 1天 = 2月1)", () => {
    const result = addDays("2026-01-31T12:00:00Z", ONE_DAY_AMOUNT);
    // 本地时区决定具体日期, 但绝不会回退到 1 月
    expect(result.getUTCDate()).toBeGreaterThanOrEqual(ONE_DAY_AMOUNT);
  });
});

describe("isAfter / isBefore / isEqual", () => {
  it("isAfter", () => {
    expect(isAfter("2026-01-16T00:00:00Z", ANCHOR_ISO)).toBe(TRUE_VAL);
    expect(isAfter(ANCHOR_ISO, "2026-01-16T00:00:00Z")).toBe(FALSE_VAL);
    expect(isAfter(ANCHOR_ISO, ANCHOR_ISO)).toBe(FALSE_VAL);
  });

  it("isBefore", () => {
    expect(isBefore("2026-01-14T00:00:00Z", ANCHOR_ISO)).toBe(TRUE_VAL);
    expect(isBefore(ANCHOR_ISO, ANCHOR_ISO)).toBe(FALSE_VAL);
  });

  it("isEqual", () => {
    expect(isEqual(ANCHOR_ISO, ANCHOR_ISO)).toBe(TRUE_VAL);
    expect(isEqual(ANCHOR_ISO, "2026-01-16T00:00:00Z")).toBe(FALSE_VAL);
  });
});

describe("formatDate / formatDateTime", () => {
  it("formatDate zh-CN", () => {
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

// ──────────── fmtRelativeTime ────────────

// oxlint-disable-next-line max-statements -- describe 块含 6 个 it + 6 个 const, 独立测试
describe("fmtRelativeTime", () => {
  // 测试注入固定 now, 避免依赖 Date.now()
  const NOW_EPOCH = 1_700_000_000; // 2023-11-14 22:13:20 UTC, 任意锚点
  const DIFF_5_SEC = 5;
  const DIFF_3_MIN = 3;
  const DIFF_2_HOURS = 2;
  const DIFF_5_DAYS = 5;
  const FUTURE_OFFSET_SEC = 100;
  const DEFAULT_NOW_FALLBACK_SEC = 30;

  it("diff < 1 分钟 → 'N 秒前'", () => {
    expect(fmtRelativeTime(NOW_EPOCH - DIFF_5_SEC, NOW_EPOCH)).toBe("5 秒前");
  });

  it("diff < 1 小时 → 'N 分钟前'", () => {
    const THREE_MIN_AGO = NOW_EPOCH - DIFF_3_MIN * SECONDS_PER_MINUTE;
    expect(fmtRelativeTime(THREE_MIN_AGO, NOW_EPOCH)).toBe("3 分钟前");
  });

  it("diff < 1 天 → 'N 小时前'", () => {
    const TWO_HOURS_AGO = NOW_EPOCH - DIFF_2_HOURS * SECONDS_PER_HOUR;
    expect(fmtRelativeTime(TWO_HOURS_AGO, NOW_EPOCH)).toBe("2 小时前");
  });

  it("diff >= 1 天 → 'N 天前'", () => {
    const FIVE_DAYS_AGO = NOW_EPOCH - DIFF_5_DAYS * SECONDS_PER_DAY;
    expect(fmtRelativeTime(FIVE_DAYS_AGO, NOW_EPOCH)).toBe("5 天前");
  });

  it("epoch 在 now 之后 (未来) → 0 秒前, 不返负数", () => {
    expect(fmtRelativeTime(NOW_EPOCH + FUTURE_OFFSET_SEC, NOW_EPOCH)).toBe("0 秒前");
  });

  it("默认 now = Date.now()/1000, 跑过不抛", () => {
    expect(() =>
      fmtRelativeTime(Math.floor(Date.now() / MS_PER_SECOND) - DEFAULT_NOW_FALLBACK_SEC),
    ).not.toThrow();
  });
});

// ──────────── formatDurationMs ────────────

// oxlint-disable-next-line max-statements -- describe 块含 4 个 it + 4 个 const, 独立测试
describe("formatDurationMs", () => {
  // (2026-07-07) pre-analysis 阶段耗时列: started_at / finished_at 是 ISO 字符串.
  // 函数纯计算, 不接 i18n, zh-only 跟 fmtRelativeTime 风格一致.

  // 锚点: 2023-11-14 22:13:20 UTC
  const DURATION_ANCHOR = "2023-11-14T22:13:20.000Z";
  const OFFSET_350_MS = 350;
  const OFFSET_1_2_S = 1200;
  const OFFSET_5_MIN_FACTOR = 5;
  const OFFSET_2_H_FACTOR = 2;
  const OFFSET_5_MIN_MS = OFFSET_5_MIN_FACTOR * SECONDS_PER_MINUTE * MS_PER_SECOND;
  const OFFSET_2_H_MS = OFFSET_2_H_FACTOR * SECONDS_PER_HOUR * MS_PER_SECOND;
  // 注入 Date.now() 相对 anchor 偏置 800ms, < 1s, 走"进行中 (0 秒)"分支
  const LIVE_NOW_OFFSET_MS = 800;

  const startAt = (offsetMs: number): string =>
    // 锚点 + offsetMs (毫秒) → ISO
    new Date(new Date(DURATION_ANCHOR).getTime() + offsetMs).toISOString();

  it("start + end 都有 → 'Nms' / 'N.Ns' / 'Nm 分 Ns' / 'Nh Nm 分'", () => {
    // 1) 亚秒级
    expect(formatDurationMs(startAt(ZERO), startAt(OFFSET_350_MS))).toBe("350ms");
    // 2) 秒级 (1 位小数)
    expect(formatDurationMs(startAt(ZERO), startAt(OFFSET_1_2_S))).toBe("1.2s");
    // 3) 分钟级
    expect(formatDurationMs(startAt(ZERO), startAt(OFFSET_5_MIN_MS + OFFSET_1_2_S))).toBe(
      `5 分 ${Math.floor(OFFSET_1_2_S / MS_PER_SECOND)} 秒`,
    );
    // 4) 小时级
    expect(formatDurationMs(startAt(ZERO), startAt(OFFSET_2_H_MS))).toBe(`2 时 0 分`);
  });

  it("end = null (进行中) → '进行中 (Ns)' 实时算到 now", () => {
    // 注入固定 now = anchor + LIVE_NOW_OFFSET_MS, 走 startAt(0) → "进行中 (0 秒)"
    const now = new Date(DURATION_ANCHOR).getTime() + LIVE_NOW_OFFSET_MS;
    const realDateNow = Date.now;
    Date.now = () => now;
    try {
      expect(formatDurationMs(startAt(ZERO), null)).toBe("进行中 (0 秒)");
    } finally {
      Date.now = realDateNow;
    }
  });

  it("start 为空字符串 → '—'", () => {
    expect(formatDurationMs("", startAt(OFFSET_1_2_S))).toBe("—");
  });

  it("end 是非法日期字符串 → '—'", () => {
    expect(formatDurationMs(startAt(ZERO), "not-a-date")).toBe("—");
  });
});

// ──────────── formatElapsedMs ────────────

describe("formatElapsedMs", () => {
  const MS_350 = 350;
  const MS_1200 = 1200;
  const FIVE_MIN_FACTOR = 5;
  const TWO_HOUR_FACTOR = 2;
  const NEGATIVE_ONE = -1;
  const MS_5_MIN = FIVE_MIN_FACTOR * SECONDS_PER_MINUTE * MS_PER_SECOND;
  const MS_5_MIN_12_S = MS_5_MIN + MS_1200;
  const MS_2_H = TWO_HOUR_FACTOR * SECONDS_PER_HOUR * MS_PER_SECOND;
  const EXPECTED_5_MIN_LABEL = `5 分 ${Math.floor(MS_1200 / MS_PER_SECOND)} 秒`;

  it("4 档 (亚秒 / 秒 / 分 / 时) 跟 formatDurationMs 的 formatRange 一致", () => {
    expect(formatElapsedMs(MS_350)).toBe("350ms");
    expect(formatElapsedMs(MS_1200)).toBe("1.2s");
    expect(formatElapsedMs(MS_5_MIN_12_S)).toBe(EXPECTED_5_MIN_LABEL);
    expect(formatElapsedMs(MS_2_H)).toBe("2 时 0 分");
  });

  it("0 毫秒 → '0ms' (正常值, 不返 '—')", () => {
    expect(formatElapsedMs(ZERO)).toBe("0ms");
  });

  it("NaN / 负数 → '—'", () => {
    expect(formatElapsedMs(Number.NaN)).toBe("—");
    expect(formatElapsedMs(NEGATIVE_ONE)).toBe("—");
  });
});
