// Ingest 单任务 BFF: GET /api/ingest/tasks/{id}
// (2026-06-14) 改走 apiProxy()
// (2026-06-16) 加 serverAuthHeaders
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Ingest 单任务 BFF: 透传 GET /api/ingest/tasks/{id}
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id
 * @returns Response
 * @client-bff */
export const GET = async (_req: NextRequest, ctx: { params: Promise<{ id: string }> }) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/ingest/tasks/${encodeURIComponent(id)}`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return bffProxyResponse(resp);
};
