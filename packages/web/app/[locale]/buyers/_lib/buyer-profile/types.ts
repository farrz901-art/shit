// 客户画像系统 前端类型 (2026-06-22 buyer-profile spec)
// (2026-06-24) 全 snake_case 对齐后端 FastAPI schemas (buyer_profile/schemas.py),
// 前端不再额外做 camelCase 转换 — 后端权威, 字段名直接对应.

/** 客户画像数据
 * @property id - 画像 ID
 * @property buyer_key - 客户标识键
 * @property buyer_name - 客户名称
 * @property status - 状态
 * @property profile_data - 画像字段数据 (字段编码 → 字段值)
 * @property tags - 标签列表
 * @property notes - 备注
 * @property first_seen_at - 首次出现时间
 * @property last_contact_at - 最后联系时间
 * @shared
 */
export interface BuyerProfile {
  id: string;
  buyer_key: string;
  buyer_name: string | null;
  status: string;
  profile_data: Record<string, ProfileFieldValue>;
  tags: string[];
  notes: string | null;
  first_seen_at: string | null;
  last_contact_at: string | null;
}

/** 画像字段值 (值 + 置信度 + 来源)
 * @property value - 字段值
 * @property confidence - 置信度 (高/中/低)
 * @property source - 来源 (自动/手动)
 * @property updated_at - 更新时间
 * @shared
 */
export interface ProfileFieldValue {
  value: unknown;
  confidence: "high" | "medium" | "low";
  source: "auto" | "manual";
  updated_at: string | null;
}

/** 画像字段配置
 * @property id - 配置 ID
 * @property code - 字段编码
 * @property label - 字段标签
 * @property field_type - 字段类型
 * @property extraction_prompt - 提取提示词
 * @property options - 选项列表
 * @property is_required - 是否必填
 * @property is_active - 是否激活
 * @property sort_order - 排序序号
 * @property notify_on_change - 变更通知配置
 * @shared
 */
export interface ProfileFieldConfig {
  id: number;
  code: string;
  label: string;
  field_type: string;
  extraction_prompt: string | null;
  options: (string | Record<string, unknown>)[];
  is_required: boolean;
  is_active: boolean;
  sort_order: number;
  notify_on_change: Record<string, unknown>[];
}

/** 画像变更日志
 * @property id - 日志 ID
 * @property profile_id - 画像 ID
 * @property field_code - 字段编码
 * @property old_value - 旧值
 * @property new_value - 新值
 * @property source - 来源 (自动/手动)
 * @property conv_id - 会话 ID
 * @property created_at - 创建时间
 * @shared
 */
export interface ChangeLog {
  id: number;
  profile_id: string;
  field_code: string;
  old_value: unknown;
  new_value: unknown;
  source: "auto" | "manual";
  conv_id: string | null;
  created_at: string | null;
}

/** 客户画像列表响应
 * @property items - 画像列表
 * @property total - 总数
 * @shared
 */
export interface BuyerProfileListResponse {
  items: BuyerProfile[];
  total: number;
}
