// 字典 BFF 客户端 (2026-06-19 lookup module §5.5)
// 跟 /api/lookups/* 端点对接, 返 LookupItem + LookupDict 类型.
// 跟 chat api.ts 一致, 走 apiFetch() 统一 transport (cookie 由 BFF catch-all 自动带).
import { apiFetch } from "./config";

// 单个字典项 (业务代码里用的字符串 + i18n label).
// Description / metadata_json / effective_at / deprecated_at 是可选扩展位, 后端 admin UI 写入.
/**
 * 单个字典项 (key + 中英文 label + 排序 + active 状态)
 * @shared
 */
export interface LookupItem {
  key: string;
  label_zh: string;
  label_en: string;
  sort: number;
  is_active: boolean;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
  effective_at?: string | null;
  deprecated_at?: string | null;
}

/**
 * 单个字典 (含 items 列表 + version)
 * @shared
 */
export interface LookupDict {
  code: string;
  label_zh: string;
  label_en: string;
  version: number;
  items: LookupItem[];
}

/**
 * 字典概要 (列表用, 不含 items 详情)
 * @shared
 */
export interface LookupDictSummary {
  code: string;
  label_zh: string;
  label_en: string;
  version: number;
  is_active: boolean;
}

/**
 * 字典项 patch payload (admin UI 行内编辑用, 全部字段可选)
 * @shared
 */
export interface LookupItemPatchInput {
  label_zh?: string;
  label_en?: string;
  sort?: number;
  is_active?: boolean;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

/**
 * 字典项 create payload (admin UI 新增弹窗用)
 * @shared
 */
export interface LookupItemCreateInput {
  key: string;
  label_zh: string;
  label_en: string;
  sort: number;
  is_active: boolean;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

/**
 * 二次确认 token (删字典项时必带)
 * @shared
 */
export interface LookupConfirmToken {
  token: string;
  valid_until: string;
}

/**
 * 系统 readonly 状态 (DICTIONARY_READONLY env 旗标 + 只读字典数)
 * @shared
 */
export interface LookupSystemInfo {
  readonly: boolean;
  dicts_count: number;
}

/**
 * 审计日志条目 (admin UI 抽屉展示)
 * @shared
 */
export interface LookupAuditLogEntry {
  id: number;
  ts: string;
  actor_id: number;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  target_id: string | null;
}

/**
 * 查字典的客户端选项 (lang + onlyActive)
 * @shared
 */
export interface FetchLookupOpts {
  lang?: "zh" | "en" | "both";
  onlyActive?: boolean;
}

/**
 * 查单个字典 (含 items 列表).
 * @param dictCode 字典 code (e.g. "approval_review_status" / "reject_reason")
 * @param opts lang 默认 "both" (返 label_zh + label_en), onlyActive 默认 true
 * @throws ApiError 4xx/5xx (404 = 字典不存在, 401 = 未登录)
 */
export const fetchLookup = async (
  dictCode: string,
  opts: FetchLookupOpts = {},
): Promise<LookupDict> => {
  const lang = opts.lang ?? "both";
  const onlyActive = opts.onlyActive ?? true;
  return apiFetch<LookupDict>(`/api/lookups/${dictCode}?lang=${lang}&only_active=${onlyActive}`);
};

/**
 * 列全部字典概要 (供 admin UI / 字典选择下拉框用, 不含 items 详情).
 * 后端返 { dictionaries: LookupDictSummary[] }, 这里只返 summaries 数组.
 */
export const fetchAllLookups = async (): Promise<LookupDictSummary[]> => {
  const data = await apiFetch<{ dictionaries: LookupDictSummary[] }>("/api/lookups");
  return data.dictionaries;
};

// ========== Admin API (super_admin 写操作, Task 6 §5.4) ==========
// 鉴权由 BFF catch-all + 后端 super_admin 守卫双重校验, 前端只用 apiFetch 走 cookie 自动带.

/**
 * Admin 新增字典项 (super_admin).
 * 后端会跑 SafetyGuard 6 层防御: 鉴权 + readonly + 重复 key + 引用检查 + audit + cache invalidate.
 */
export const fetchAdminCreateItem = async (
  dictCode: string,
  payload: LookupItemCreateInput,
): Promise<LookupItem> =>
  apiFetch<LookupItem>(`/api/admin/dicts/${dictCode}/items`, {
    body: payload,
    method: "POST",
  });

/**
 * Admin 改字典项 (super_admin). label_zh/label_en/sort/is_active 等可单独 patch.
 */
export const fetchAdminPatchItem = async (
  dictCode: string,
  key: string,
  payload: LookupItemPatchInput,
): Promise<LookupItem> =>
  apiFetch<LookupItem>(`/api/admin/dicts/${dictCode}/items/${key}`, {
    body: payload,
    method: "PATCH",
  });

/**
 * Admin 软删字典项 (super_admin). 必须先调 fetchAdminConfirmToken 拿 token, 带 X-Confirm-Token header.
 * 后端 SafetyGuard 第 6 层校验 token 合法 + 引用检查 → 拒绝被业务引用的 key.
 */
export const fetchAdminDeleteItem = async (
  dictCode: string,
  key: string,
  confirmToken: string,
): Promise<void> => {
  await apiFetch<void>(`/api/admin/dicts/${dictCode}/items/${key}`, {
    headers: { "X-Confirm-Token": confirmToken },
    method: "DELETE",
  });
};

/**
 * 申请一次删/改二次确认 token. 后端生成短时 (e.g. 5 分钟) 单次 token, 防 CSRF + 防误操作.
 */
export const fetchAdminConfirmToken = (): Promise<LookupConfirmToken> =>
  apiFetch<LookupConfirmToken>("/api/admin/dicts/confirm-token", {
    method: "POST",
  });

/**
 * 系统 readonly 状态: DICTIONARY_READONLY env 是否开启 + 当前只读字典数.
 * (前端默认 fallback false, 真实状态以后端返为准. 见 ReadonlyBanner.tsx 注释.)
 */
export const fetchAdminSystemInfo = (): Promise<LookupSystemInfo> =>
  apiFetch<LookupSystemInfo>("/api/admin/dicts/system-info");

/**
 * 字典审计日志 (super_admin). dictCode 可选过滤; key 可选过滤单条 item 历史.
 * 后端审计写入所有 dictionary.item.* action, 时间倒序.
 */
export const fetchAdminAuditLog = async (
  dictCode: string,
  key?: string,
): Promise<LookupAuditLogEntry[]> => {
  // 后端 endpoint 是 /api/admin/dicts/{dict_code}/audit (无 query param, key 仅 client 端过滤)
  const { entries } = await apiFetch<{ entries: LookupAuditLogEntry[] }>(
    `/api/admin/dicts/${encodeURIComponent(dictCode)}/audit`,
  );
  if (key) {
    return entries.filter((entry) => entry.target_id?.endsWith(`:${key}`));
  }
  return entries;
};
