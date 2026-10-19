// 评估批 BFF: 列表 / 上传
// - GET  → 透传到 FastAPI /api/evaluate/runs
// - POST → 透传 multipart (file + concurrency) 到 FastAPI
// (2026-06-14) 改走 apiProxy()
import { type NextRequest, NextResponse } from "next/server";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";

/** 评估批列表 BFF: 透传 GET /api/evaluate/runs
 * @param _req - 请求对象 (未使用)
 * @returns Response
 * @client-bff */
export const GET = async (_req: NextRequest) => {
  const resp = await apiProxy("/api/evaluate/runs", {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return bffProxyResponse(resp);
};

/** 创建评估批 BFF: 透传 multipart POST /api/evaluate/runs
 * @param req - 请求对象
 * @returns Response
 * @client-bff */
export const POST = async (req: NextRequest) => {
  const form = await req.formData();
  const file = form.get("file");
  const concurrency = form.get("concurrency") ?? "5";
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "缺少 file 字段" }, { status: 400 });
  }

  // 构造 multipart 给 FastAPI
  const fd = new FormData();
  fd.append("file", file);
  fd.append("concurrency", String(concurrency));

  const resp = await apiProxy("/api/evaluate/runs", {
    body: fd,
    headers: await serverAuthHeaders(),
    method: "POST",
  });
  return bffProxyResponse(resp);
};
