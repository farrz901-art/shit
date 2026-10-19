/**
 * 鉴权端点 HTTP client (P1-1, 2026-06-29 补 JSDoc)
 *
 * ============================================================
 * 调用边界 (calling-boundary, 2026-06-19 audit)
 * ============================================================
 *   - createAnonToken: @client-bff (浏览器端调, 走 /api/auth/anon BFF 路由)
 */

import { apiFetch } from "./config";

/**
 * 创建匿名访问 token — anon user chat 用
 * anon 用户调此端点拿临时 token, 后续 chat BFF 调 sendMessage 时 Header 注入.
 * 跟登录 token 区别: anon token 短期有效 (anon chat 过期清空)
 * @returns 返 { token: string } — 临时 anon token
 * @throws NetworkError / ApiError 4xx/5xx
 * @example
 *   const { token } = await createAnonToken();
 *   localStorage.setItem(ANON_TOKEN_KEY, token);
 */
export const createAnonToken = () =>
  apiFetch<{ token: string }>("/api/auth/anon", { method: "POST" });
