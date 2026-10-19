// /api/auth/anon BFF 用的纯函数: 上游 Response → NextResponse
// (2026-06-14) 抽出来便于 vitest 测, route.ts 里调这个 + 真 fetch
//
// 设计:
// - Set-Cookie 必须透传 (后端 Set-Cookie HttpOnly, 浏览器要拿到)
// - status / body 全透传 (BFF 不归一, 让前端 apiFetch 处理 ApiError)
// - 4xx/5xx 不重写: 跟其他 BFF 保持一致 (bff-must-propagate-502)
import { NextResponse } from "next/server";
import { HEADER_CONTENT_TYPE } from "@/const";

/**
 * 把上游 FastAPI Response 透传给前端.
 * 关键: 拷贝 set-cookie (Headers 多个同名值不会自动合并).
 */
export const proxyAuthResponse = (upstream: Response): NextResponse => {
  const headers = new Headers();
  // 透传 content-type (application/json)
  const ct = upstream.headers.get("content-type");
  if (ct) {
    headers.set(HEADER_CONTENT_TYPE, ct);
  }
  // 透传 set-cookie (可能多个, 浏览器按顺序处理)
  // Upstream.headers.getSetCookie() 是 Node 18+ 标准 API
  for (const cookie of upstream.headers.getSetCookie()) {
    headers.append("set-cookie", cookie);
  }
  return new NextResponse(upstream.body, {
    headers,
    status: upstream.status,
  });
};
