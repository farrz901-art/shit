// BFF /api/health/system (2026-06-11) — 透传 admin-only health endpoint
// (2026-06-14) 改走 apiProxy(): 拼 API_BASE + 鉴权 (admin 走 super_admin 角色 + x-user-token) + 不归一错误
// BFF 必须透传 status + body, 错误按 [feedback-bff-must-propagate-502-not-silently-zero] 严格处理
import { NetworkError } from "@/lib/api/errors";
import { NextResponse } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 系统健康检查 BFF: 透传 GET /api/health/system
 * @returns Response
 * @client-bff */
export const GET = async () => {
  try {
    const resp = await apiProxy("/api/health/system", { cache: "no-store", method: "GET" });
    return bffProxyResponse(resp);
  } catch (error) {
    // 后端不可达 → 502 (不静默返 0)
    if (error instanceof NetworkError) {
      return NextResponse.json(
        { detail: "后端服务不可达, 请检查 main.py 是否在 8000 端口运行", error: error.message },
        { status: 502 },
      );
    }
    return NextResponse.json({ detail: String(error) }, { status: 500 });
  }
};
