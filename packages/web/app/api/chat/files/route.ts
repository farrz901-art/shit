// Chat files multipart fallback BFF: POST /api/chat/files
// (2026-06-17) Task 9: 浏览器直传 MinIO 走 presign/finalize 优先, multipart fallback
// 走标准 multipart 透传到后端, 后端调 Dify Files API
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** Chat 文件上传 BFF (multipart fallback): 透传 POST /api/chat/files
 * @param req - 请求对象
 * @returns Response
 * @client-bff */
export const POST = async (req: NextRequest) => {
  const form = await req.formData();
  const fd = new FormData();
  for (const [key, value] of form.entries()) {
    fd.append(key, value);
  }
  const resp = await apiProxy("/api/chat/files", {
    body: fd,
    headers: await serverAuthHeaders(),
    method: "POST",
  });
  return bffProxyResponse(resp);
};
