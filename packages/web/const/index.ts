/**
 * 全局共享常量模块
 *
 * 优先把所有魔法数字 / 字符串放这里, 业务代码 import 使用.
 *
 * 命名规范:
 * - SCREAMING_SNAKE_CASE
 * - 单位放后缀: _MS / _SECONDS / _DAYS / _BYTES / _PERCENT
 * - HTTP 状态用 HTTP_<STATUS_NAME>
 * - 时间区间用 _<UNIT>_PER_<LARGER_UNIT> (e.g. SECONDS_PER_MINUTE)
 *
 * 业务专属常量 (e.g. dataset 颜色 / 表格列宽) 留在业务模块自己的 const.ts.
 * @shared
 */
// 全局共享常量 (2026-06-19 code-quality-phase2)

// ──────────────── 基础数字 ────────────────
export const ZERO = 0;
export const ONE = 1;
export const TWO = 2;
export const THREE = 3;
export const FOUR = 4;
export const FIVE = 5;
export const SIX = 6;
export const TEN = 10;
export const FIFTEEN = 15;
export const THIRTY = 30;
export const FIFTY = 50;
export const HUNDRED = 100;
export const THOUSAND = 1000;

// ──────────────── 时间单位换算 ────────────────
export const MS_PER_SECOND = 1000;
export const SECONDS_PER_MINUTE = 60;
export const MINUTES_PER_HOUR = 60;
export const HOURS_PER_DAY = 24;
export const DAYS_PER_WEEK = 7;

export const SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR; // 3600
export const SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY; // 86400

export const ONE_SECOND_MS = MS_PER_SECOND;
export const FIVE_SECONDS_MS = FIVE * MS_PER_SECOND;
export const TEN_SECONDS_MS = TEN * MS_PER_SECOND;
export const FIFTEEN_SECONDS_MS = FIFTEEN * MS_PER_SECOND;
export const THIRTY_SECONDS_MS = THIRTY * MS_PER_SECOND;
export const ONE_MINUTE_MS = SECONDS_PER_MINUTE * MS_PER_SECOND;
export const FIVE_MINUTES_MS = FIVE * ONE_MINUTE_MS;
export const TEN_MINUTES_MS = TEN * ONE_MINUTE_MS;
export const ONE_HOUR_MS = MINUTES_PER_HOUR * ONE_MINUTE_MS;

// ──────────────── HTTP 状态码 ────────────────
export const HTTP_OK = 200;
export const HTTP_CREATED = 201;
export const HTTP_NO_CONTENT = 204;
export const HTTP_TEMPORARY_REDIRECT = 307;
export const HTTP_BAD_REQUEST = 400;
export const HTTP_UNAUTHORIZED = 401;
export const HTTP_FORBIDDEN = 403;
export const HTTP_NOT_FOUND = 404;
export const HTTP_CONFLICT = 409;
export const HTTP_UNPROCESSABLE_ENTITY = 422;
export const HTTP_PRECONDITION_FAILED = 412;
export const HTTP_TOO_MANY_REQUESTS = 429;
export const HTTP_INTERNAL_SERVER_ERROR = 500;
export const HTTP_BAD_GATEWAY = 502;

// ──────────────── 端口 / 网络 ────────────────
export const DEFAULT_DEV_PORT = 3000;
export const DEFAULT_API_PORT = 8000;

// ──────────────── 分页 ────────────────
export const DEFAULT_SKIP = 0;
export const DEFAULT_PAGE_SIZE = 20;
export const DEFAULT_PAGE_SIZE_STRING = "20";
export const ONE_KB = 1024;
export const ONE_MB = ONE_KB * ONE_KB;
export const ONE_GB = ONE_MB * ONE_KB;

// ──────────────── localStorage keys (统一前缀 rag., 便于 grep + cleanup) ────────────────
// (2026-06-23) 匿名 chat user 标识 — Dify user 字段专用, 跟 Dify 服务端 user 维度对齐
// 登录态用 accountId, anon 态用这个, 跨刷新稳定, 同一浏览器历史连续
export const ANON_USER_ID_KEY = "rag.chat.anon-user-id.v1";

// ──────────────── HTTP 协议字符串 (2026-06-25 const-cleanup spec §3.1) ────────────────
// 复用度阈值: 跨 2+ 生产文件. 单文件不抽 (避免过度设计).
export const HEADER_CONTENT_TYPE = "content-type";
export const HEADER_X_USER_TOKEN = "x-user-token";
export const HEADER_X_CHAT_TOKEN = "x-chat-token";
export const COOKIE_USER_TOKEN = "rag_user_token";
export const MIME_JSON = "application/json";
export const LS_KEY_WAS_LOGGED_IN = "rag_was_logged_in";

// ──────────────── Chat 协议 (跨 2+ 文件) ────────────────
export const SSE_DELIMITER_LENGTH = 2;
export const INDEX_NOT_FOUND = -1;

// ──────────────── 鉴权 / 业务上限 (跨 2+ 文件) ────────────────
export const MIN_PASSWORD_LENGTH = 8;
