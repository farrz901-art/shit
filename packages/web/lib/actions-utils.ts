// Server actions 共享工具 (2026-06-28 P4 refactor)
//
// 替 17 处重复的错误归一:
// - 9 处 errMsg() helper (evaluate.ts + output.ts 字字相同)
// - 5 处 inline error instanceof Error (knowledge.ts)
// - 5 处 try/catch (account.ts + account-settings.ts)
// - 7 处 handle*Error 函数 (account-settings.ts)
//
// 注意: 本文件不在 _actions/ 下, 没有 "use server" 标记.
// 这些是纯同步工具函数, 被各个 Server Action 文件 import 后在 async 函数内部使用.
import { getErrorMessage } from "@/lib/api/errors";

/**
 * Server action 错误归一: 返 { ok: false, error: "可读消息" }
 *
 * @param error 从 try/catch 捕获的任意 error
 * @returns 结构化错误对象, 客户端用 .error 展示 toast / inline
 *
 * @example
 *   try { await apiFetch("/api/x") }
 *   catch (e) { return actionError(e) }
 */
export const actionError = (error: unknown): { ok: false; error: string } => ({
  error: getErrorMessage(error),
  ok: false,
});

/**
 * Server action 错误归一 + 兜底中文 (2026-06-29 P4 §4.3 增补).
 *
 * 跟 actionError 区别: `getErrorMessage(error)` 返非空时直接用, 返空串时走 fallback.
 * 替 account-settings.ts 5 处 `getErrorMessage(error) || "保存失败"` 模板.
 *
 * @param error 从 try/catch 捕获的任意 error
 * @param fallback getErrorMessage 返空时的兜底中文 (客户端看)
 * @returns 结构化错误对象, 客户端用 .error 展示 toast / inline
 *
 * @example
 *   catch (e) { return actionErrorWithFallback(e, "保存失败") }
 */
export const actionErrorWithFallback = (
  error: unknown,
  fallback: string,
): { ok: false; error: string } => ({
  error: getErrorMessage(error) || fallback,
  ok: false,
});
