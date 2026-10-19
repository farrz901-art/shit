// Invite HTTP client — GET /api/invites/{token} + POST /api/invites/{token}/redeem
// (2026-06-26) 从 _actions/account.ts / invite/[token]/page.tsx 拆出,
//   避免业务代码直调 apiFetch.
import { apiFetch } from "./config";

/** 查询邀请信息 — GET /api/invites/{token} */
export const getInvite = (token: string, headers?: Record<string, string>) =>
  apiFetch<{ email: string }>(`/api/invites/${token}`, { headers });

/** 兑换邀请 — POST /api/invites/{token}/redeem */
export const redeemInvite = (
  token: string,
  body: { display_name: string; password: string },
  headers?: Record<string, string>,
) => apiFetch<{ token: string }>(`/api/invites/${token}/redeem`, { body, headers, method: "POST" });
