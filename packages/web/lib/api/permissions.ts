/**
 * 权限 / 角色 HTTP client (P1-3, 2026-06-29 补 JSDoc + calling-boundary)
 *
 * ============================================================
 * 调用边界 (calling-boundary, 2026-06-19 audit)
 * ============================================================
 *   - getMyPermissions: @server-only (auth 注入 headers, RSC layout / Server Action 用)
 *   - getAllPermissions / patchPermissions / listRoles / createRole /
 *     updateRole / deleteRole: @server-only (admin 操作, 需 server-side auth headers)
 *
 * RBAC 权限级别:
 *   - super_admin: 全部 page 短路, 可改角色 / 改 page 权限
 *   - admin: 可读 / 改 user-level 权限 (不能改 super_admin 专属)
 *   - regular admin: 只读 + 自己页权限
 */

import { apiFetch } from "./config";
import type { PageMeta } from "@/lib/auth/permission-types";

/**
 * 权限更新 payload (角色 + 页面 + allowed)
 * @shared
 */
export interface PermissionUpdate {
  role_name: string;
  page_key: string;
  allowed: boolean;
}

/**
 * 获取当前用户权限 — RSC layout 必调, 结果灌进 client store
 * @param headers 服务端 auth headers (从 cookies 解出)
 * @returns { role, account_id, allowed, pages } 跟 PermissionData 同构
 */
export const getMyPermissions = (headers?: Record<string, string>) =>
  apiFetch<{ role: string; account_id: number | null; allowed: string[]; pages: PageMeta[] }>(
    "/api/permissions/me",
    { headers },
  );

/** 获取所有角色的 page 权限矩阵 (super_admin 用)
 * @param headers 服务端鉴权头
 * @returns 权限矩阵数据
 * @server-only */
export const getAllPermissions = <TData = unknown>(headers?: Record<string, string>) =>
  apiFetch<TData>("/api/permissions", { headers });

/** 批量更新 page 权限 (super_admin 用, 改 allowed=true/false)
 * @param updates 权限更新列表
 * @param headers 服务端鉴权头
 * @server-only */
export const patchPermissions = (updates: PermissionUpdate[], headers?: Record<string, string>) =>
  apiFetch("/api/permissions", { body: { updates }, headers, method: "PATCH" });

/** 创建自定义角色
 * @param data 角色数据 (name, label, permissions)
 * @server-only */
export const createRole = (data: {
  name: string;
  label_zh: string;
  label_en: string;
  permissions: Record<string, boolean>;
}) => apiFetch("/api/roles", { body: data, method: "POST" });

// (2026-06-26) RBAC wire: 补 GET /api/roles + PATCH/DELETE /api/roles/{name}
/**
 * 角色列表项 (含系统标记 / 可删性 / 用户数)
 * @shared
 */
export interface RoleListItem {
  name: string;
  label_zh: string;
  label_en: string;
  /** 系统角色 (super_admin / admin / user) 不可删除 / 改 name */
  is_system: boolean;
  /** 是否允许 DELETE — is_system=false 时才 true */
  is_deletable: boolean;
  /** 使用该角色的用户数 — 删除前检查必须为 0 */
  user_count: number;
  created_at: string | null;
  updated_at: string | null;
}

/** 列出所有角色 (含系统 + 自定义)
 * @param headers 服务端鉴权头
 * @returns 角色列表
 * @server-only */
export const listRoles = (headers?: Record<string, string>) =>
  apiFetch<{ roles: RoleListItem[] }>("/api/roles", { headers });

/** 改角色 label (中英文) — 不可改 name (主键)
 * @param name 角色名 (主键)
 * @param data 更新数据
 * @param headers 服务端鉴权头
 * @returns 更新后的角色
 * @server-only */
export const updateRole = (
  name: string,
  data: { label_zh?: string; label_en?: string },
  headers?: Record<string, string>,
) =>
  apiFetch<RoleListItem>(`/api/roles/${name}`, {
    body: data,
    headers,
    method: "PATCH",
  });

/** 删除自定义角色 — 系统角色 / 有用户的角色会被后端 400 拒绝
 * @param name 角色名
 * @param headers 服务端鉴权头
 * @server-only */
export const deleteRole = (name: string, headers?: Record<string, string>) =>
  apiFetch<void>(`/api/roles/${name}`, { headers, method: "DELETE" });
