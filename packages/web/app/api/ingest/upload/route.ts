// Ingest 上传 BFF: 优先 BFF v2 (presign+finalize), 老走 multipart fallback
// (2026-06-16) 改走 presign/finalize, 保留 multipart fallback 兼容旧前端
import { type NextRequest, NextResponse } from "next/server";
import { HEADER_CONTENT_TYPE, MIME_JSON, ZERO } from "@/const";
import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/**
 * handleFallbackUpload - multipart fallback 上传
 * @param req - 请求对象
 * @returns Response
 */
const handleFallbackUpload = async (req: NextRequest): Promise<NextResponse> => {
  const form = await req.formData();
  const files = form.getAll("files");
  if (files.length === ZERO) {
    return NextResponse.json({ detail: "缺少 files 字段" }, { status: 400 });
  }
  const fd = new FormData();
  for (const file of files) {
    if (file instanceof File) {
      fd.append("files", file);
    }
  }
  const resp = await apiProxy("/api/ingest/upload", {
    body: fd,
    headers: await serverAuthHeaders(),
    method: "POST",
  });
  return bffProxyResponse(resp);
};

/**
 * Ingest 上传 BFF: 优先 presign/finalize v2, 回到 multipart fallback
 * @param req - 请求对象
 * @returns Response
 * @client-bff
 */
export const POST = async (req: NextRequest) => {
  const version = req.headers.get("x-bff-version");
  if (version === "2") {
    const body = await req.json();
    const presignResp = await apiProxy("/api/ingest/upload/presign", {
      body: JSON.stringify(body),
      headers: { ...(await serverAuthHeaders()), [HEADER_CONTENT_TYPE]: MIME_JSON },
      method: "POST",
    });
    return bffProxyResponse(presignResp);
  }
  return handleFallbackUpload(req);
};
