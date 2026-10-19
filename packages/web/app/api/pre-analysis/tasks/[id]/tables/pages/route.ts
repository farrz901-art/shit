// Pre-analysis 表格页列表 BFF: GET /api/pre-analysis/tasks/{id}/tables/pages
// 透传后端: GET /api/pre-analysis/tasks/{id}/tables/pages
// 跟 ingest/tasks/[id]/files/[name]/route.ts 同 pattern: apiProxy + serverAuthHeaders + bffProxyResponse.
import { type NextRequest } from "next/server";

import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Pre-analysis 表格页列表 BFF (2026-07-09 tables viewer)
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id
 * @returns Response
 * @client-bff */
export const GET = async (_req: NextRequest, ctx: { params: Promise<{ id: string }> }) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/pre-analysis/tasks/${encodeURIComponent(id)}/tables/pages`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return bffProxyResponse(resp);
};
