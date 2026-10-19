// /api/auth/anon BFF: POST 创建匿名 token, 透传后端 Set-Cookie
// (2026-06-14) 修复 BFF 缺失: 之前浏览器 fetch /api/auth/anon 拿到 404 (Next dev server 找不到 route),
//   Cookie 永远没设上 → 后续 /api/ingest/* 全部 401 "缺少 x-user-token"
//
// 流程:
// 1. 浏览器 → POST /api/auth/anon (AuthBootstrap 触发)
// 2. BFF → POST ${API_BASE}/api/auth/anon (直连后端, 不走 apiProxy 是因为 Set-Cookie 透传是核心副作用)
// 3. 后端生成 token + Set-Cookie rag_user_token (HttpOnly, 7d)
// 4. BFF 透传 status + body + set-cookie 给浏览器
// 5. 浏览器拿到 Set-Cookie, 后续 /api/* 自动带 token
import { API_BASE } from "@/lib/api/config";
import type { NextRequest } from "next/server";
import { proxyAuthResponse } from "./proxy";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 创建匿名 token BFF: 透传后端 Set-Cookie
 * @param _req - 请求对象 (未使用)
 * @returns Response
 * @client-bff */
export const POST = async (_req: NextRequest) => {
  const upstream = await fetch(`${API_BASE}/api/auth/anon`, {
    cache: "no-store",
    method: "POST",
  });
  return proxyAuthResponse(upstream);
};
