// Server Action 直连后端的 fetch 函数 (2026-06-27)
// 不绕 BFF (/api/* route.ts), 避免额外 hop + cookie-vs-header 鉴权混乱.
// 调用方: app/[locale]/_actions/evaluate.ts deleteRun.
import "server-only";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { API_BASE } from "@/lib/api/config";

/**
 * 删除评估批 — 直连 FastAPI DELETE /api/evaluate/runs/{id}.
 * @param id 评估批 ID
 * @returns 后端响应 JSON
 * @server-only
 */
export const deleteRunById = async (id: string): Promise<unknown> => {
  const headers = await serverAuthHeaders();
  const resp = await fetch(`${API_BASE}/api/evaluate/runs/${encodeURIComponent(id)}`, {
    headers,
    method: "DELETE",
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
  }
  return resp.json() as Promise<unknown>;
};
