// Ingest presign BFF: POST /api/ingest/upload/presign
// 透传 backend, 返 {task_id, uploads}
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/**
 * Ingest 预签名 BFF: 透传 POST /api/ingest/upload/presign
 * @param req - 请求对象
 * @returns Response
 * @client-bff
 */
export const POST = async (req: NextRequest) => {
  const body = await req.json();
  const resp = await apiProxy("/api/ingest/upload/presign", {
    body: JSON.stringify(body),
    headers: { ...(await serverAuthHeaders()), [HEADER_CONTENT_TYPE]: MIME_JSON },
    method: "POST",
  });
  return bffProxyResponse(resp);
};
