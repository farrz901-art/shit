// Ingest zip 下载 BFF: GET /api/ingest/tasks/{id}/download
// 流式透传 FastAPI StreamingResponse, 不读 body
// (2026-06-14) 改走 apiProxy() (apiProxy 不读 body, 直接传 Response 透传)
import type { NextRequest } from "next/server";
import { apiProxy } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HEADER_CONTENT_TYPE } from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** Ingest Zip 下载 BFF: 流式透传 GET /api/ingest/tasks/{id}/download
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id
 * @returns Response (流式)
 * @client-bff */
export const GET = async (_req: NextRequest, ctx: { params: Promise<{ id: string }> }) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/ingest/tasks/${encodeURIComponent(id)}/download`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  // 流式透传: 直接 new Response(res.body, ...), 不 await .text()
  return new Response(resp.body, {
    headers: {
      "content-disposition":
        resp.headers.get("content-disposition") ?? `attachment; filename="${id}.zip"`,
      [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? "application/zip",
    },
    status: resp.status,
  });
};
