// CSV 模板下载 BFF: 透传 GET /api/evaluate/template, 强制下载头
// (2026-06-14) 改走 apiProxy()
// (2026-06-29) P4 §4.1: 改用 bffDownloadResponse 工厂, 省 8 行
import { apiProxy, bffDownloadResponse } from "@/lib/api/config";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** CSV 模板下载 BFF: 透传 GET /api/evaluate/template
 * @returns Response (下载流)
 * @client-bff */
export const GET = async () => {
  const resp = await apiProxy("/api/evaluate/template");
  return bffDownloadResponse(resp, {
    filename: "eval_template.csv",
    mime: "text/csv; charset=utf-8",
  });
};
