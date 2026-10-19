// 评估批详情 BFF: 透传 GET /api/evaluate/runs/{id} 给 FastAPI
// (2026-06-14) 改走 apiProxy()
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 评估批详情 BFF: 透传 GET /api/evaluate/runs/{id}
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含评估批 id
 * @returns Response
 * @client-bff */
export const GET = async (_req: NextRequest, ctx: { params: Promise<{ id: string }> }) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/evaluate/runs/${id}`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return bffProxyResponse(resp);
};
