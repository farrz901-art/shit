/** 轻量 logger (2026-06-23): 替代 console.* 输出, 自动带时间戳 + 级别 + meta.
// dev 带 ANSI 颜色, prod 纯文本 + 关闭 debug. 0 依赖, 跟 CLAUDE.md 自实现约定一致.
//
// 用法:
//   import { log } from "@/lib/log";
//   log.info("user logged in", { userId: 42 });
//   log.error("fetch failed", { url, status: 500 });
//   // dev 输出: 14:23:55.123 INFO  user logged in {"userId":42}
//   // prod 输出: 14:23:55.123 INFO  user logged in {"userId":42}
//
// 升级路径: 后期要 JSON 输出 / Sentry / ELK 聚合, 只改本文件实现即可,
// 业务侧 log.info/warn/error 调用不动.
*/
import { nowIso } from "@/lib/date";
type Level = "debug" | "info" | "warn" | "error";

const ANSI_GRAY = "\x1b[90m";
const ANSI_CYAN = "\x1b[36m";
const ANSI_YELLOW = "\x1b[33m";
const ANSI_RED = "\x1b[31m";
const ANSI_RESET = "\x1b[0m";

// Dev 才用颜色, prod stdout 走容器日志不希望有 ANSI 码
// 每次调用读: vitest 等测试环境会动态改 NODE_ENV, module-load-time freeze 不友好
const isProd = (): boolean => process.env.NODE_ENV === "production";

const COLOR_BY_LEVEL: Record<Level, string> = {
  debug: ANSI_GRAY,
  error: ANSI_RED,
  info: ANSI_CYAN,
  warn: ANSI_YELLOW,
};

// HH:MM:SS.mmm 格式, 23 字符截取 ISO 8601 的时间部分
const TIME_START_INDEX = 11;
const TIME_END_INDEX = 23;
const LEVEL_PADDED_WIDTH = 5;

const format = (level: Level, message: string, meta?: object): string => {
  const isoTime = nowIso().slice(TIME_START_INDEX, TIME_END_INDEX);
  const paddedLevel = level.toUpperCase().padEnd(LEVEL_PADDED_WIDTH);
  const metaPart = meta ? ` ${JSON.stringify(meta)}` : "";
  if (isProd()) {
    return `${isoTime} ${paddedLevel} ${message}${metaPart}`;
  }
  const color = COLOR_BY_LEVEL[level];
  return `${color}${isoTime}${ANSI_RESET} ${color}${paddedLevel}${ANSI_RESET} ${message}${metaPart}`;
};

const isDebugEnabled = (): boolean => !isProd() || process.env.NEXT_PUBLIC_LOG_LEVEL === "debug";

/** 轻量 logger, 替代 console.*, 自动时间戳 / 级别 / ANSI 颜色.
 * @shared */
export const log = {
  // Debug: prod 默认关, dev 默认开 (想关可设 NEXT_PUBLIC_LOG_LEVEL=info)
  debug: (message: string, meta?: object): void => {
    if (!isDebugEnabled()) {
      return;
    }
    // eslint-disable-next-line no-console -- log facade 故意包 console
    console.log(format("debug", message, meta));
  },
  info: (message: string, meta?: object): void => {
    // eslint-disable-next-line no-console -- log facade 故意包 console
    console.log(format("info", message, meta));
  },
  warn: (message: string, meta?: object): void => {
    // eslint-disable-next-line no-console -- log facade 故意包 console
    console.warn(format("warn", message, meta));
  },
  error: (message: string, meta?: object): void => {
    // eslint-disable-next-line no-console -- log facade 故意包 console
    console.error(format("error", message, meta));
  },
};
