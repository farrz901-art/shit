// Chat files finalize BFF: POST /api/chat/files/finalize
// 通知后端: 浏览器 PUT 完, 后端从 store 拉 bytes → 转 Dify
// (2026-06-17) Task 9: presign/finalize 优先, multipart fallback
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** Chat 文件上传完成通知 BFF: 透传 POST /api/chat/files/finalize
 * @param req - 请求对象
 * @returns Response
 * @client-bff */
export const POST = async (req: NextRequest) => {
  const body = await req.json();
  const resp = await apiProxy("/api/chat/files/finalize", {
    body: JSON.stringify(body),
    headers: { ...(await serverAuthHeaders()), [HEADER_CONTENT_TYPE]: MIME_JSON },
    method: "POST",
  });
  return bffProxyResponse(resp);
};
