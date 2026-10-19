// Reject BFF: POST /api/approvals/{id}/reject
// (2026-06-14) 改走 apiProxy(): 鉴权 + 拼 API_BASE + 透传 body + 透传 content-type
// (2026-06-13) Task 23: admin 用 BFF
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 审批拒绝 BFF: 透传 POST /api/approvals/{id}/reject
 * @param req - 请求对象
 * @param params - 路由参数, 含审批 id
 * @returns Response
 * @client-bff */
export const POST = async (req: NextRequest, { params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  const resp = await apiProxy(`/api/approvals/${encodeURIComponent(id)}/reject`, {
    body: await req.text(),
    cache: "no-store",
    headers: {
      ...(await serverAuthHeaders()),
      [HEADER_CONTENT_TYPE]: req.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON,
    },
    method: "POST",
  });
  return bffProxyResponse(resp);
};
