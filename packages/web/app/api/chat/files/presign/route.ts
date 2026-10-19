// Chat files presign BFF: POST /api/chat/files/presign
// 透传 backend, 返 {uri, put_url, mime}
// (2026-06-17) Task 9: 浏览器直传 MinIO 走 presign/finalize 优先, multipart fallback
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** Chat 文件预签名 BFF: 透传 POST /api/chat/files/presign
 * @param req - 请求对象
 * @returns Response
 * @client-bff */
export const POST = async (req: NextRequest) => {
  const body = await req.json();
  const resp = await apiProxy("/api/chat/files/presign", {
    body: JSON.stringify(body),
    headers: { ...(await serverAuthHeaders()), [HEADER_CONTENT_TYPE]: MIME_JSON },
    method: "POST",
  });
  return bffProxyResponse(resp);
};
