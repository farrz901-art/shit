// Server-only 鉴权工具. 仅 server component / RSC / BFF route / server action 用.
// "server-only" 是 Next.js marker, 防止 client 端误 import 进来
// (在 vitest 里被 alias 成空模块, 见 vitest.config.ts)
import "server-only";
import { cookies } from "next/headers";
import { COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN } from "@/const";

/** Server 端: 从 cookie 读 user token (admin 已废弃, 统一走 user token). */
export const getServerToken = async (): Promise<string> => {
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_USER_TOKEN)?.value ?? "";
};

/** Server 端: 构造透传给后端的鉴权头.
 *
 * 注意 (2026-06-24): 后端 resolve_user 不识别 `x-admin-token` (auth.py:10-12
 * 砍掉了 bootstrap admin 路径), 注入会被 401. 这里统一注 `x-user-token`.
 * admin 优先读 cookie 是历史的, 现在统一走 user token, admin 通过账号 role 区分.
 */
export const authHeaders = async (): Promise<Record<string, string>> => {
  const cookieStore = await cookies();
  const user = cookieStore.get(COOKIE_USER_TOKEN)?.value;
  const out: Record<string, string> = {};
  const tokenValue = user ?? "";
  if (tokenValue) {
    out[HEADER_X_USER_TOKEN] = tokenValue;
  }
  return out;
};

/** Server 端: 返回一个 headers 对象, 调用方传给 apiFetch() 当 headers.
 *
 * 用法 (server action / RSC 页面 / BFF route):
 *   const data = await apiFetch<Response>("/api/kg/datasets", {
 *     headers: await serverAuthHeaders(),
 *   });
 *
 * 客户端不要用: 浏览器 /api/* 走 BFF 同源, cookie 由浏览器自动带, BFF 内部读.
 */
export const serverAuthHeaders = async (): Promise<Record<string, string>> => authHeaders();
