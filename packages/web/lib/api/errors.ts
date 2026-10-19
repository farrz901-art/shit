// Fetch 错误类型 (2026-06-10 从 lib/api.ts 移过来)

/**
 * API 请求错误 (非 2xx 响应)
 *
 * @shared
 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * 网络请求失败错误 (fetch 抛出)
 *
 * @shared
 */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * 把任意抛出的 error 归一成可读消息 (2026-06-28 P4 refactor).
 * 替 10 处 inline 的 `error instanceof Error ? .message : String(error)`.
 *
 * - ApiError / NetworkError → .message (后端 detail 或 "fetch failed" 等)
 * - Error → .message
 * - 其它 → String()
 *
 * @example
 *   try { await apiFetch("/api/x") }
 *   catch (e) { toast.error(getErrorMessage(e)) }
 */
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};
