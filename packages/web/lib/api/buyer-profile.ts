/**
 * Buyer profile 客户画像 HTTP client (P1-4, 2026-06-29 补 JSDoc + calling-boundary)
 *
 * ============================================================
 * 调用边界 (calling-boundary, 2026-06-19 audit)
 * ============================================================
 *   - 所有函数: @server-only (admin 操作, 需 server-side auth headers 注入)
 *
 * 注意: 全部是 admin 操作 (列 / 改 / 归档 客户档案), 不是 user 自己 profile
 *        user 自己 profile 用 /api/buyer-profiles/my-profile (见 lib/api/buyer-profile/my-profile.ts)
 *        field config (字段定义) 仅 super_admin 可写, admin 可读
 */

import { apiFetch } from "./config";

const BASE = "/api/buyer-profiles";

/** 列出所有客户档案 (admin) — 可传查询参数 (e.g. status=active)
 * @param opts 查询参数
 * @returns 客户档案列表
 * @server-only */
export const listProfiles = (opts?: Record<string, string>) => {
  const queryString = opts ? `?${new URLSearchParams(opts).toString()}` : "";
  return apiFetch(`${BASE}${queryString}`);
};

/** 获取单个客户档案详情 (admin)
 * @param id 档案 ID
 * @returns 客户档案详情
 * @server-only */
export const getBuyerProfile = (id: string) => apiFetch(`${BASE}/${id}`);
/** 更新客户档案 (admin)
 * @param id 档案 ID
 * @param body 更新内容
 * @server-only */
export const updateBuyerProfile = (id: string, body: Record<string, unknown>) =>
  apiFetch(`${BASE}/${id}`, { method: "PATCH", body });
/** 归档客户档案 (admin) — 软删, 数据保留
 * @param id 档案 ID
 * @server-only */
export const archiveProfile = (id: string) => apiFetch(`${BASE}/${id}`, { method: "DELETE" });
/** 获取客户档案变更历史 (admin)
 * @param id 档案 ID
 * @returns 变更历史列表
 * @server-only */
/** 获取客户档案变更历史 (admin)
 * @param id 档案 ID
 * @returns 变更历史列表
 * @server-only */
export const getProfileChanges = (id: string) => apiFetch(`${BASE}/${id}/changes`);
/** 列出字段定义配置 (admin / super_admin)
 * @returns 字段定义列表
 * @server-only */
export const listProfilesFieldConfigs = () => apiFetch(`${BASE}/fields`);
/** 创建字段定义 (super_admin only) — 新字段后端会校验唯一性
 * @param body 字段定义 payload
 * @server-only */
export const createFieldConfig = (body: Record<string, unknown>) =>
  apiFetch(`${BASE}/fields`, { method: "POST", body });
/** 更新字段定义 (super_admin only) — code 是字段唯一标识不可改
 * @param code 字段 code
 * @param body 更新内容
 * @server-only */
export const updateProfileFieldConfig = (code: string, body: Record<string, unknown>) =>
  apiFetch(`${BASE}/fields/${code}`, { method: "PATCH", body });
/** 删除字段定义 (super_admin only) — 有 profile 在用会被后端 400 拒绝
 * @param code 字段 code
 * @server-only */
export const deleteFieldConfig = (code: string) =>
  apiFetch(`${BASE}/fields/${code}`, { method: "DELETE" });
