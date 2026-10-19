// Ingest 读文件 BFF: GET /api/ingest/tasks/{id}/files/{name}
// (2026-06-14) 改走 apiProxy()
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Ingest 读文件 BFF: 透传 GET /api/ingest/tasks/{id}/files/{name}
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id 和文件名
 * @returns Response
 * @client-bff */
export const GET = async (
  _req: NextRequest,
  ctx: { params: Promise<{ id: string; name: string }> },
) => {
  const { id, name } = await ctx.params;
  const resp = await apiProxy(
    `/api/ingest/tasks/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`,
    { cache: "no-store", headers: await serverAuthHeaders() },
  );
  return bffProxyResponse(resp);
};
