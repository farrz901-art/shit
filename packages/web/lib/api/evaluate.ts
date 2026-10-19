// 评估页业务客户端 (2026-06-10)
// 跟 lib/evaluate/headers.ts 共用 localStorage 鉴权 key
// 走 BFF: createRun (multipart) / cancelRun (admin-cancellable)
// SWR/RQ 用 URL 工厂直接喂 queryFn
// (2026-06-14) 改走 apiFetch()
//
// ============================================================
// 调用边界 (calling-boundary, 2026-06-19 audit)
// ============================================================
// 标注约定 (跟 lib/api/ 全局对齐):
//   - `@client-bff`    浏览器端调用, 必须从 'use client' 组件用;
//                       走 Next.js BFF (/api/* catch-all 或专用 route), cookie 自动带.
//   - `@server-only`   仅 RSC / server action / route.ts 可用, 必须显式传 `headers` (auth token).
//                       直连 FastAPI, 绕过 BFF.
//   - `@shared`        浏览器或 server 都可用. 浏览器走 BFF catch-all, server 直连 FastAPI.
// URL 工厂函数 (runCancelUrl / runDetailUrl / runsUrl / templateUrl) 都是
// `@shared` — 返字符串不发起请求, 调用方决定何时用 + 是否注入 auth.
import { apiFetch } from "./config";
import type { EvaluationRun } from "@/lib/evaluate/types";

/** 评估运行行摘要 (列表页用)
 * @shared */
export interface EvalRunSummary {
  id: number;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_samples: number;
  created_at: string;
}

/** 创建评估运行的响应
 * @shared */
export interface CreateRunResponse {
  id: number;
  status: string;
}

/** 取消评估的响应
 * @shared */
export interface CancelResponse {
  cancelled: boolean;
}

/** 取消评估 — 走 BFF, 鉴权后多用户数据 */
/** @client-bff */
export const cancelRun = (id: number): Promise<CancelResponse> =>
  apiFetch<CancelResponse>(`/api/evaluate/runs/${id}/cancel`, { method: "POST" });

/** 启动评估 — multipart 走 BFF */
/** @client-bff */
export const createRun = (file: File, concurrency: number): Promise<CreateRunResponse> => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("concurrency", String(concurrency));
  return apiFetch<CreateRunResponse>("/api/evaluate/runs", { body: fd, method: "POST" });
};

/** 创建评估批 — JSON 体 (用于 server action / RSC) */
/** @server-only */
export const createRunJson = <TData = unknown>(
  body: unknown,
  headers?: Record<string, string>,
): Promise<TData> => apiFetch<TData>("/api/evaluate/runs", { body, headers, method: "POST" });

// (2026-06-27) deleteRun 已搬到 lib/server/evaluate.ts:deleteRunById
// Server Action 直连后端不走 BFF. BFF 仅 serve 客户端表单.

/** URL 工厂: 给 RQ queryFn 用 */
/** @shared */
export const runCancelUrl = (id: number): string => `/api/evaluate/runs/${id}/cancel`;
/** @shared */
export const runDetailUrl = (id: number): string => `/api/evaluate/runs/${id}`;
/** @shared */
export const runsUrl = (): string => "/api/evaluate/runs";
/** @shared */
export const templateUrl = (): string => "/api/evaluate/template";

/** 获取评估批详情 — GET /api/evaluate/runs/{id} */
/** @server-only */
export const getEvaluationRun = (
  id: string,
  headers?: Record<string, string>,
): Promise<EvaluationRun> => apiFetch<EvaluationRun>(`/api/evaluate/runs/${id}`, { headers });
