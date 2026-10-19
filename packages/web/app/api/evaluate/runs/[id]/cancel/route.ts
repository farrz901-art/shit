// 评估批取消 BFF
// (2026-06-14) 改走 apiProxy()
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 评估批取消 BFF: 透传 POST /api/evaluate/runs/{id}/cancel
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含评估批 id
 * @returns Response
 * @client-bff */
export const POST = async (_req: NextRequest, ctx: { params: Promise<{ id: string }> }) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/evaluate/runs/${id}/cancel`, {
    headers: await serverAuthHeaders(),
    method: "POST",
  });
  return bffProxyResponse(resp);
};
