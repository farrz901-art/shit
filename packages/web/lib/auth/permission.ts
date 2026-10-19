/**
 * Server 端读权限 (P1-8, 2026-06-29 补 JSDoc + can() 短路 + DEFAULT_PERMISSION 兜底)
 *
 * RSC layout / Server Action / route.ts 用. React `cache()` 同 request 单例.
 * 失败降级为 anon DEFAULT (role="user", 仅能 chat).
 *
 * 跟 client 端 lib/hooks/use-permissions.ts 区别: server 端带 auth headers 直连 FastAPI,
 *                                                       client 端只读 zustand store (RSC 灌入)
 *
 * super_admin 短路: 跟 usePermissions.client 同语义 (跨 RSC/Client 一致).
 */
import "server-only"; // 防止 client 组件误引（headers/can 不可序列化）
import { cache } from "react";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { getMyPermissions } from "@/lib/api/permissions";
import type { PermissionData } from "./permission-types";
export type { PermissionData, PageMeta } from "./permission-types";

/**
 * 权限结果扩展 (含 can() 判断 + headers + admin 标识)
 * @shared
 */
export interface PermissionResult extends PermissionData {
  isAdminLevel: boolean;
  isSuperAdmin: boolean;
  /**
   * 判断当前用户能否访问某页面. super_admin 短路 true, 否则看 allowed.
   * @param pageKey 跟后端 PageMeta.key 对齐 (e.g. "chat" / "admin" / "submissions")
   */
  can: (pageKey: string) => boolean;
  headers: Record<string, string>;
}

// anon 降级: role=user (非 admin), allowed 只含 chat, can 只对 "chat" 返 true
// 目的: 即使 auth 失败 (cookie 过期 / 后端 5xx), 用户仍能进 chat 页, 其他页被静默隐藏
const DEFAULT_PERMISSION: PermissionResult = {
  role: "user",
  accountId: null,
  allowed: ["chat"],
  pages: [],
  isAdminLevel: false,
  isSuperAdmin: false,
  can: (pageKey: string) => pageKey === "chat",
  headers: {},
};

/**
 * 获取当前用户权限 (React cache per-request 单例, 失败降级 anon)
 * @returns 权限结果 (含 can 判断函数 + 服务端鉴权头)
 *
 * @server-only
 */
// React cache() 包: per-request 单例, 同一次 render 多次调只 fetch 1 次
export const getPermissions = cache(async (): Promise<PermissionResult> => {
  try {
    const headers = await serverAuthHeaders();
    const data = await getMyPermissions(headers);
    return {
      role: data.role,
      accountId: data.account_id ?? null,
      allowed: data.allowed,
      pages: data.pages,
      isAdminLevel: data.role !== "user",
      isSuperAdmin: data.role === "super_admin",
      // super_admin 短路 — 不管 allowed 包不包含 pageKey, 直接 true
      can: (pageKey: string) => data.role === "super_admin" || data.allowed.includes(pageKey),
      headers,
    };
  } catch {
    // 失败兜底: 用 anon DEFAULT (允许访问 chat), 不抛错避免 SSR 整个挂掉
    return DEFAULT_PERMISSION;
  }
});
