// TC39 Temporal wrapper, date-fns 4.x 风格 API
// (2026-07-07) 替代原生 Date API + date-fns 调用.
// 内部用 @js-temporal/polyfill (Bun 1.3.14 当前无原生 Temporal).
// @shared
import { Temporal } from "@js-temporal/polyfill";
import {
  MS_PER_SECOND,
  ONE,
  SECONDS_PER_DAY,
  SECONDS_PER_HOUR,
  SECONDS_PER_MINUTE,
  ZERO,
} from "@/const";

/**
 * 24 小时/天的换算常量.
 * 用于 differenceInDays 将小时差转成天数.
 */
const HOURS_PER_DAY = 24;

/**
 * Temporal.Instant.since 接受的 largestUnit 类型.
 * Instant 是绝对时间点, 没有日历概念, 所以不支持 day / week / month / year.
 * @internal
 */
type InstantUnit =
  | "auto"
  | "hour"
  | "minute"
  | "second"
  | "millisecond"
  | "microsecond"
  | "nanosecond"
  | "hours"
  | "minutes"
  | "seconds"
  | "milliseconds"
  | "microseconds"
  | "nanoseconds";

/** Wrapper 函数接受的输入类型 */
export type DateInput = string | number | Date | Temporal.Instant;

/**
 * 输入值归一为 Temporal.Instant.
 * @param input ISO 字符串 / epoch ms / Date / Temporal.Instant
 * @returns Temporal.Instant
 * @throws RangeError 当 input 非法时 (替代 Date.parse 返回 NaN 的静默 fail)
 *
 * @shared
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

// ──────────── 当前时间 ────────────

/**
 * 当前时间 -> Temporal.Instant. 仅 client / 事件 handler 调用 (SSR root 会有 hydration mismatch).
 * @returns Temporal.Instant
 *
 * @client-bff
 */
export const nowInstant = (): Temporal.Instant => Temporal.Now.instant();

/**
 * 当前时间 -> epoch ms. 替 Date.now().
 * @returns number (ms since epoch)
 *
 * @shared
 */
export const nowMs = (): number => Temporal.Now.instant().epochMilliseconds;

/**
 * 当前时间 -> ISO 8601 字符串. 替 new Date().toISOString().
 * @returns string (形如 2026-07-07T07:15:30.123Z)
 *
 * @shared
 */
export const nowIso = (): string => Temporal.Now.instant().toString();

// ──────────── 差值 (date-fns 4.x 风格签名) ────────────

/**
 * later - earlier 的 Temporal.Duration.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @param largestUnit 最大单位 (Instant 不支持 day/weeks/months/years)
 * @returns Temporal.Duration
 * @internal
 */
const durationOf = (later: DateInput, earlier: DateInput, largestUnit: InstantUnit) =>
  toInstant(later).since(toInstant(earlier), { largestUnit });

/**
 * later - earlier 的毫秒数.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 毫秒差 (可为负)
 *
 * @shared
 */
export const differenceInMilliseconds = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "milliseconds").milliseconds;

/**
 * later - earlier 的秒数.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 秒差 (可为负)
 *
 * @shared
 */
export const differenceInSeconds = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "seconds").seconds;

/**
 * later - earlier 的分钟数.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 分钟差 (可为负)
 *
 * @shared
 */
export const differenceInMinutes = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "minutes").minutes;

/**
 * later - earlier 的小时数.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 小时差 (可为负)
 *
 * @shared
 */
export const differenceInHours = (later: DateInput, earlier: DateInput): number =>
  durationOf(later, earlier, "hours").hours;

/**
 * later - earlier 的天数 (按 24 小时天计, 跨月/跨年自动归一化).
 * 内部用小时差 / 24 取整, 不涉及时区.
 * @param later 较晚时间
 * @param earlier 较早时间
 * @returns 天数差 (可为负)
 *
 * @shared
 */
export const differenceInDays = (later: DateInput, earlier: DateInput): number =>
  Math.trunc(durationOf(later, earlier, "hours").hours / HOURS_PER_DAY);

// ──────────── 加减 (返回 Date 跟现有代码兼容) ────────────

/**
 * date + Temporal.DurationLike 后的 Date.
 * 内部用 ZonedDateTime.add 处理月末溢出 (如 1月31 + 1天 = 2月1日).
 * @param date 起始时间
 * @param duration 时长对象 (days, hours, minutes, seconds, milliseconds)
 * @returns 新的 Date
 * @internal
 */
const shift = (date: DateInput, duration: Temporal.DurationLike): Date => {
  const zdt = toInstant(date).toZonedDateTimeISO(Temporal.Now.timeZoneId());
  return new Date(zdt.add(duration).epochMilliseconds);
};

/**
 * date + N 天. 月末溢出由 Temporal 规范自动处理.
 * @param date 起始时间
 * @param amount 天数 (负数向前)
 * @returns 新的 Date
 *
 * @shared
 */
export const addDays = (date: DateInput, amount: number): Date => shift(date, { days: amount });

/**
 * date + N 小时.
 * @param date 起始时间
 * @param amount 小时数
 * @returns 新的 Date
 *
 * @shared
 */
export const addHours = (date: DateInput, amount: number): Date => shift(date, { hours: amount });

/**
 * date + N 分钟.
 * @param date 起始时间
 * @param amount 分钟数
 * @returns 新的 Date
 *
 * @shared
 */
export const addMinutes = (date: DateInput, amount: number): Date =>
  shift(date, { minutes: amount });

/**
 * date + N 秒.
 * @param date 起始时间
 * @param amount 秒数
 * @returns 新的 Date
 *
 * @shared
 */
export const addSeconds = (date: DateInput, amount: number): Date =>
  shift(date, { seconds: amount });

/**
 * date + N 毫秒.
 * @param date 起始时间
 * @param amount 毫秒数
 * @returns 新的 Date
 *
 * @shared
 */
export const addMilliseconds = (date: DateInput, amount: number): Date =>
  shift(date, { milliseconds: amount });

// ──────────── 比较 ────────────

/**
 * 输入值归一为 epoch ms.
 * @param input DateInput 类型
 * @returns epoch ms
 * @internal
 */
const instantOf = (input: DateInput) => toInstant(input).epochMilliseconds;

/**
 * date > dateToCompare.
 * @param date 被比较的时间
 * @param dateToCompare 比较基准
 * @returns 是否大于
 *
 * @shared
 */
export const isAfter = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) > instantOf(dateToCompare);

/**
 * date < dateToCompare.
 * @param date 被比较的时间
 * @param dateToCompare 比较基准
 * @returns 是否小于
 *
 * @shared
 */
export const isBefore = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) < instantOf(dateToCompare);

/**
 * date === dateToCompare (严格等于, 不涉及时区).
 * @param date 被比较的时间
 * @param dateToCompare 比较基准
 * @returns 是否相等
 *
 * @shared
 */
export const isEqual = (date: DateInput, dateToCompare: DateInput): boolean =>
  instantOf(date) === instantOf(dateToCompare);

// ──────────── 格式化 ────────────

/**
 * ISO -> 本地化日期 (替 `new Intl.DateTimeFormat(locale, {...}).format(new Date(iso))`).
 * @param iso ISO 8601 字符串
 * @param locale BCP-47 locale, 项目只用 'zh-CN' / 'en-US'
 * @returns 本地化日期字符串
 *
 * @shared
 */
export const formatDate = (iso: string, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "numeric",
    year: "numeric",
  }).format(new Date(iso));

/**
 * ISO -> 本地化日期+时间 (替 `new Date(iso).toLocaleString()`).
 * @param iso ISO 8601 字符串
 * @param locale BCP-47 locale
 * @returns 本地化日期时间字符串
 *
 * @shared
 */
export const formatDateTime = (iso: string, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));

// ──────────── 相对时间 ────────────

/**
 * epoch 秒 → 相对时间字符串 ("N 秒前" / "N 分钟前" / "N 小时前" / "N 天前").
 * 用于任务列表 created_at 列渲染.
 * 未来若加 i18n, 改用 Intl.RelativeTimeFormat.
 *
 * @param epoch epoch 秒 (后端 created_at 是 time.time() 浮点)
 * @param now 当前 epoch 秒, 默认 Date.now()/1000 (测试可注入)
 * @returns 中文相对时间字符串
 *
 * @shared
 */
export const fmtRelativeTime = (
  epoch: number,
  now: number = Date.now() / MS_PER_SECOND,
): string => {
  const diff = Math.max(ZERO, now - epoch);
  if (diff < SECONDS_PER_MINUTE) {
    return `${Math.floor(diff)} 秒前`;
  }
  if (diff < SECONDS_PER_HOUR) {
    return `${Math.floor(diff / SECONDS_PER_MINUTE)} 分钟前`;
  }
  if (diff < SECONDS_PER_DAY) {
    return `${Math.floor(diff / SECONDS_PER_HOUR)} 小时前`;
  }
  return `${Math.floor(diff / SECONDS_PER_DAY)} 天前`;
};

/**
 * 毫秒级时间戳 → 中文相对时间 ("刚刚" / "N 分钟前" / "N 小时前" / "N 天前").
 * 用于业务侧就地格式化 (如会话列表 updatedAt).
 * @param timestamp 毫秒时间戳
 * @returns 中文相对时间字符串
 *
 * @shared
 */
export const formatRelativeTime = (timestamp: number): string => {
  const diff = nowMs() - timestamp;
  if (diff < MILLIS_PER_MINUTE) {
    return "刚刚";
  }
  if (diff < MILLIS_PER_HOUR) {
    return `${Math.floor(diff / MILLIS_PER_MINUTE)} 分钟前`;
  }
  if (diff < HOURS_PER_DAY * MILLIS_PER_HOUR) {
    return `${Math.floor(diff / MILLIS_PER_HOUR)} 小时前`;
  }
  return `${Math.floor(diff / (HOURS_PER_DAY * MILLIS_PER_HOUR))} 天前`;
};

// ──────────── 耗时格式化 (pre-analysis) ────────────

/** 1 小时的毫秒数 */
const MILLIS_PER_HOUR = SECONDS_PER_HOUR * MS_PER_SECOND;

/** 1 分钟的毫秒数 */
const MILLIS_PER_MINUTE = SECONDS_PER_MINUTE * MS_PER_SECOND;

/** 非法占位符 */
const DURATION_DASH = "—";

/**
 * ISO 字符串 → epoch ms (NaN 表示非法).
 * @param iso ISO 8601 字符串
 * @returns epoch ms; 空串或非法返回 NaN
 * @internal
 */
const tryParseMs = (iso: string): number => {
  if (iso === "") {
    return Number.NaN;
  }
  const ms = new Date(iso).getTime();
  return Number.isFinite(ms) ? ms : Number.NaN;
};

/**
 * 纯毫秒数 → 人类可读时长 (4 档).
 *   - < 1s → "Nms"
 *   - < 1m → "N.Ns"
 *   - < 1h → "M 分 S 秒"
 *   - ≥ 1h → "H 时 M 分"
 *   入参非法 (NaN / 负数) → "—"
 *
 * @param ms 毫秒数 (后端 summary.elapsed_ms 整型)
 * @returns 形如 "350ms" / "1.2s" / "5 分 12 秒" / "2 时 0 分" / "—"
 *
 * @shared
 */
export const formatElapsedMs = (ms: number): string => {
  if (!Number.isFinite(ms) || ms < ZERO) {
    return DURATION_DASH;
  }
  return formatRange(ms);
};

/**
 * 2 个 ISO 时间戳 → 人类可读阶段耗时.
 *   - end=null → "进行中 (N 秒)"
 *   - start/end 任一非法 → "—"
 *   - < 1s → "Nms"; < 1m → "N.Ns"; < 1h → "M 分 S 秒"; ≥ 1h → "H 时 M 分"
 *
 * @param start 起始时间 (ISO 8601 字符串)
 * @param end 结束时间 (ISO 8601 字符串); null = 进行中
 * @returns 形如 "350ms" / "1.2s" / "5 分 12 秒" / "2 时 0 分" / "进行中 (8 秒)" / "—"
 *
 * @shared
 */
export const formatDurationMs = (start: string, end: string | null): string => {
  const startMs = tryParseMs(start);
  if (Number.isNaN(startMs)) {
    return DURATION_DASH;
  }
  const endMs = end === null ? nowMs() : tryParseMs(end);
  if (Number.isNaN(endMs)) {
    return DURATION_DASH;
  }
  if (end === null) {
    const liveMs = Math.max(ZERO, endMs - startMs);
    if (liveMs < MILLIS_PER_MINUTE) {
      return `进行中 (${Math.floor(liveMs / MS_PER_SECOND)} 秒)`;
    }
    return `进行中 (${formatRange(liveMs)})`;
  }
  return formatRange(Math.max(ZERO, endMs - startMs));
};

/** 毫秒数 → 4 档格式化 (无前缀/后缀, 纯数字 + 单位). @internal */
const formatRange = (ms: number): string => {
  if (ms < MS_PER_SECOND) {
    return `${ms}ms`;
  }
  if (ms < MILLIS_PER_MINUTE) {
    return `${(ms / MS_PER_SECOND).toFixed(ONE)}s`;
  }
  if (ms < MILLIS_PER_HOUR) {
    const minutes = Math.floor(ms / MILLIS_PER_MINUTE);
    const seconds = Math.floor((ms % MILLIS_PER_MINUTE) / MS_PER_SECOND);
    return `${minutes} 分 ${seconds} 秒`;
  }
  const hours = Math.floor(ms / MILLIS_PER_HOUR);
  const minutes = Math.floor((ms % MILLIS_PER_HOUR) / MILLIS_PER_MINUTE);
  return `${hours} 时 ${minutes} 分`;
};
