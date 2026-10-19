/**
 * Admin 用户/邀请管理 API wrapper (2026-06-26 RBAC) — listUsers / createInvite / resetPassword / patchUser
 * 调用方: client 组件 (`@/app/[locale]/admin/users/*`) + server action (`@/app/[locale]/_actions/account.ts`)
 * 全部走 apiFetch; createUser DEPRECATED 走 createInvite + role
 */
import { apiFetch } from "./config";

/** 获取用户列表
 * @param params 查询筛选参数
 * @param headers 服务端鉴权头
 * @returns 用户列表
 * @server-only */
// (2026-06-26) 加可选 params (query string), 允许调用方传筛选参数
export const listUsers = <TData = unknown>(
  params?: string,
  headers?: Record<string, string>,
): Promise<TData> => {
  const query = params ? `?${params}` : "";
  return apiFetch<TData>(`/api/admin/users${query}`, { headers });
};

/** 创建邀请
 * @param email 邀请邮箱
 * @param headers 服务端鉴权头
 * @server-only */
export const createInvite = (email: string, headers?: Record<string, string>) =>
  apiFetch("/api/admin/invites", { body: { email }, headers, method: "POST" });

/** 创建用户（含管理员） — DEPRECATED since 2026-06-17
 * @param body 用户信息 (email + 可选 role)
 * @param headers 服务端鉴权头
 * @returns 邀请链接
 * @server-only */
// 后端早就不接 is_admin: bool (Pydantic 校验失败), 保留函数仅为向后兼容, 新代码走 createInvite 传 role.
export const createUser = (
  body: { email: string; role?: string },
  headers?: Record<string, string>,
) => apiFetch<{ invite_url: string }>("/api/admin/users", { body, headers, method: "POST" });

/** 重置用户密码
 * @param userId 用户 ID
 * @param headers 服务端鉴权头
 * @returns 临时密码
 * @server-only */
export const resetPassword = (userId: number, headers?: Record<string, string>) =>
  apiFetch<{ temp_password: string }>(`/api/admin/users/${userId}/reset-password`, {
    headers,
    method: "POST",
  });

/** 修改用户字段 (is_active / role / display_name)
 * @param userId 用户 ID
 * @param body 修改字段
 * @param headers 服务端鉴权头
 * @server-only */
// (2026-06-26) RBAC wire: 后端 PatchUserRequest 接 role: str (替原 is_admin: bool).
export const patchUser = (
  userId: number,
  body: { is_active?: boolean; role?: string; display_name?: string },
  headers?: Record<string, string>,
) =>
  apiFetch<{ id: number; ok: true }>(`/api/admin/users/${userId}`, {
    body,
    headers,
    method: "PATCH",
  });

/**
 * 列出邀请 — GET /api/admin/invites
 * @param headers 服务端鉴权头
 * @returns 邀请列表
 * @server-only
 */
export const listInvites = <TData = unknown>(headers?: Record<string, string>): Promise<TData> =>
  apiFetch<TData>("/api/admin/invites", { headers });

/** 撤销邀请 — DELETE /api/admin/invites/{token}
 * @param token 邀请 token
 * @param headers 服务端鉴权头
 * @server-only */
export const deleteInvite = (token: string, headers?: Record<string, string>) =>
  apiFetch<{ ok: true }>(`/api/admin/invites/${encodeURIComponent(token)}`, {
    headers,
    method: "DELETE",
  });
