// Approval HTTP client — 跟 lib/api/knowledge.ts 风格一致 (走 apiFetch)
//
// (2026-06-13) Task 9: 5 端点 wrapper (submit / getDetail / approve / reject / retry)
// (2026-06-13) Task 23: approve / reject / retry 改走 BFF /api/approvals/{id}/*
//   (admin 端点, RQ useMutation 走 client side, 跟 RSC 直连解耦)
// Submit / getDetail 仍直连 FastAPI (走 server action / useQuery + authHeaders)
// 列表 (list / pending) 走 SWR + URL 工厂模式 — 留待后续 task
// (2026-06-14) 全部 fetch 改走 apiFetch()
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
// 函数选择依据: 取 `headers` 参数 = 必须 server 注入 token → server-only;
//               无 headers + URL 是 /api/approvals/... (无专用 BFF) = shared;
//               无 headers + URL 是 /api/approvals/{id}/{action} (专用 BFF) = client-bff.

import { apiFetch } from "./config";
import { DEFAULT_PAGE_SIZE, DEFAULT_SKIP } from "../../const";

/** Approval 类型枚举 (跟后端 approvals.kind / review_status / apply_status 对齐) */
export type ApprovalKind = "qa" | "triple" | "batch" | "optimize" | "like";
/** 审核状态枚举 (跟后端 review_status 对齐) */
export type ReviewStatus = "pending" | "approved" | "rejected";
/** 申请状态枚举 (跟后端 apply_status 对齐) */
export type ApplyStatus = "none" | "applied" | "failed";

/** 拒绝原因 key — 跟后端 Pydantic Literal 对齐 */
export type RejectReasonKey =
  | "duplicate"
  | "low_quality"
  | "incomplete"
  | "wrong_category"
  | "format_issue"
  | "other";

/** Approval 完整响应. payload 仅 getDetail 返 (其它端点可选). */
export interface Approval {
  id: number;
  kind: ApprovalKind;
  review_status: ReviewStatus;
  apply_status: ApplyStatus;
  submitter_id: number;
  reviewer_id: number | null;
  rejection_reason: RejectReasonKey | null;
  rejection_note: string | null;
  error_msg: string | null;
  created_at: string;
  reviewed_at: string | null;
  applied_at: string | null;
  payload?: Record<string, unknown>;
}

/** 审核通过 — POST BFF /api/approvals/{id}/approve (走 BFF 鉴权 cookie 透传) */
/** @client-bff */
export const approve = (id: number): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/approve`, { method: "POST" });

/** 查详情 — GET FastAPI /api/approvals/{id} (RSC / server action / useQuery) */
/** @shared */
export const getDetail = (id: number): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}`);

/** 审核拒绝 — POST BFF /api/approvals/{id}/reject */
/** @client-bff */
export const reject = (id: number, reason: RejectReasonKey, note?: string): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/reject`, {
    body: { note, reason },
    method: "POST",
  });

/** 重试执行 — POST BFF /api/approvals/{id}/retry */
/** @client-bff */
export const retry = (id: number): Promise<Approval> =>
  apiFetch<Approval>(`/api/approvals/${id}/retry`, { method: "POST" });

/** 提交 approval — POST FastAPI /api/approvals (server action) */
/** @server-only */
export const submit = (kind: ApprovalKind, payload: Record<string, unknown>): Promise<Approval> =>
  apiFetch<Approval>("/api/approvals", { body: { kind, payload }, method: "POST" });

/** 查当前用户提交的 approval 列表 — GET FastAPI /api/approvals/me (RSC) */
/** @server-only */
export const getMyApprovals = (
  headers: Record<string, string>,
  skip = DEFAULT_SKIP,
  limit = DEFAULT_PAGE_SIZE,
): Promise<Approval[]> =>
  apiFetch<Approval[]>(`/api/approvals/me?skip=${skip}&limit=${limit}`, { headers });

/** 查待审 approval 列表 — GET FastAPI /api/approvals?review=pending (RSC) */
/** @server-only */
export const getPendingApprovals = (
  headers: Record<string, string>,
  skip = DEFAULT_SKIP,
  limit = DEFAULT_PAGE_SIZE,
): Promise<Approval[]> =>
  apiFetch<Approval[]>(`/api/approvals?review=pending&skip=${skip}&limit=${limit}`, { headers });

/** 按 review 状态查审批列表 (客户端 BFF, 走 cookie 鉴权) */
/** @client-bff */
export const fetchApprovalsByReview = (review: string): Promise<Approval[]> =>
  apiFetch<Approval[]>(`/api/approvals?review=${review}`);

/** 查当前用户提交的审批列表 (客户端 BFF, 走 cookie 鉴权) */
/** @client-bff */
export const fetchMyApprovals = (params?: string): Promise<Approval[]> =>
  apiFetch<Approval[]>(`/api/approvals/me${params ? `?${params}` : ""}`);
