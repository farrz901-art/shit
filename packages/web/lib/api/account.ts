/**
 * 账号系统 API wrapper (2026-06-29) — login / logout / profile / avatar / email / password / deletion / invite
 * 调用方: client 组件 + server action (`@/app/[locale]/_actions/account.ts` 调 login/logout/resetPassword 等)
 * 全部走 apiFetch, 不直接 fetch
 */
import { apiFetch } from "./config";

/**
 * 登录账号
 * @param body    登录请求体 (邮箱 + 密码)
 * @param headers 可选请求头
 * @returns       包含 token 的响应
 *
 * @server-only
 */
export const login = (
  body: { email: string; password: string },
  headers?: Record<string, string>,
) => apiFetch<{ token: string }>("/api/account/login", { body, headers, method: "POST" });

/**
 * 退出登录
 * @param headers 可选请求头
 *
 * @server-only
 */
export const logout = (headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/logout", { headers, method: "POST" });

/**
 * 发送密码重置邮件
 * @param email   用户邮箱
 * @param headers 可选请求头
 * @returns       reset_url (调试环境返)
 *
 * @server-only
 */
export const forgotPassword = (email: string, headers?: Record<string, string>) =>
  apiFetch<{ reset_url?: string }>("/api/account/forgot-password", {
    body: { email },
    headers,
    method: "POST",
  });

/**
 * 重置用户密码 (含 token 验证)
 * @param body    重置请求体 (token + 新密码)
 * @param headers 可选请求头
 *
 * @server-only
 */
export const resetUserPassword = (
  body: { token: string; password: string },
  headers?: Record<string, string>,
) => apiFetch<void>("/api/account/reset-password", { body, headers, method: "POST" });

/**
 * 获取当前用户资料
 * @param headers 可选请求头
 * @returns       用户资料对象
 *
 * @server-only
 */
export const getProfile = (headers?: Record<string, string>) =>
  apiFetch("/api/account/me", { headers });

/**
 * 更新用户资料
 * @param body    更新请求体 (display_name)
 * @param headers 可选请求头
 *
 * @server-only
 */
export const updateProfile = (body: { display_name: string }, headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/profile", { body, headers, method: "PATCH" });

/**
 * 上传头像
 * @param fd      头像 FormData
 * @param headers 可选请求头
 * @returns       包含 avatar_url 的响应
 *
 * @server-only
 */
export const uploadAvatar = (fd: FormData, headers?: Record<string, string>) =>
  apiFetch<{ avatar_url: string }>("/api/account/avatar", { body: fd, headers, method: "POST" });

/**
 * 删除头像
 * @param headers 可选请求头
 *
 * @server-only
 */
export const deleteAvatar = (headers?: Record<string, string>) =>
  apiFetch<void>("/api/account/avatar", { headers, method: "DELETE" });

/**
 * 查询账号删除状态
 * @param headers 可选请求头
 * @returns       删除申请信息
 *
 * @server-only
 */
export const getDeletion = (headers?: Record<string, string>) =>
  apiFetch("/api/account/deletion", { headers });

/**
 * 提交账号删除申请
 * @param body    删除请求体 (当前密码 + 确认文本)
 * @param headers 可选请求头
 * @returns       恢复链接 + 过期时间
 *
 * @server-only
 */
export const requestDeletion = (
  body: { current_password: string; confirm_text: string },
  headers?: Record<string, string>,
) =>
  apiFetch<{ restore_url: string; expires_at: string }>("/api/account/deletion", {
    body,
    headers,
    method: "POST",
  });

/**
 * 取消账号删除申请
 * @param body    取消请求体 (当前密码)
 * @param headers 可选请求头
 *
 * @server-only
 */
export const cancelDeletion = (
  body: { current_password: string },
  headers?: Record<string, string>,
) => apiFetch<void>("/api/account/deletion", { body, headers, method: "DELETE" });

/**
 * 更改邮箱
 * @param body    更改请求体 (新邮箱 + 当前密码)
 * @param headers 可选请求头
 * @returns       验证链接
 *
 * @server-only
 */
export const changeEmail = (
  body: { new_email: string; current_password: string },
  headers?: Record<string, string>,
) =>
  apiFetch<{ verification_url: string }>("/api/account/email", {
    body,
    headers,
    method: "PATCH",
  });

/**
 * 更改密码
 * @param body    更改请求体 (当前密码 + 新密码 + 确认)
 * @param headers 可选请求头
 *
 * @server-only
 */
export const changePassword = (
  body: { current_password: string; new_password: string; confirm: string },
  headers?: Record<string, string>,
) => apiFetch<void>("/api/account/password", { body, headers, method: "PATCH" });

/** 查询邀请信息 — GET /api/invites/{token} */
export const getInvite = (token: string, headers?: Record<string, string>) =>
  apiFetch<{ email: string }>(`/api/invites/${token}`, { headers });

/** 兑换邀请 — POST /api/invites/{token}/redeem */
export const redeemInvite = (
  token: string,
  body: { display_name: string; password: string },
  headers?: Record<string, string>,
) => apiFetch<{ token: string }>(`/api/invites/${token}/redeem`, { body, headers, method: "POST" });
