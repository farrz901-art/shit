// Ingest 任务列表 BFF: GET /api/ingest/tasks
// (2026-06-14) 改走 apiProxy()
// (2026-06-16) 加 serverAuthHeaders: BFF 跨域到 FastAPI 需显式注入 cookie token
import { type NextRequest } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Ingest 任务列表 BFF: 透传 GET /api/ingest/tasks
 * @param _req - 请求对象 (未使用)
 * @returns Response
 * @client-bff */
export const GET = async (_req: NextRequest) => {
  const resp = await apiProxy("/api/ingest/tasks", {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return bffProxyResponse(resp);
};
