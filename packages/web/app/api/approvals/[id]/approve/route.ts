// Approve BFF: POST /api/approvals/{id}/approve
// (2026-06-14) 改走 apiProxy(): 鉴权 + 拼 API_BASE, BFF 透传 status + body 给 client
// (2026-06-13) Task 23: admin 用 BFF (跟 RSC 直连解耦, 走 RQ useMutation)
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 审批通过 BFF: 透传 POST /api/approvals/{id}/approve
 * @param _req - 请求对象 (未使用)
 * @param params - 路由参数, 含审批 id
 * @returns Response
 * @client-bff */
export const POST = async (_req: NextRequest, { params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  const resp = await apiProxy(`/api/approvals/${encodeURIComponent(id)}/approve`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
    method: "POST",
  });
  return bffProxyResponse(resp);
};
