// PermissionData: 可序列化的权限数据子集，跨 RSC→Client 边界传输
// 此文件不含 server-only import，可被 client 组件安全引用

/**
 * 页面元信息 (key / 中英文 label / 路径 / 图标 / 父级等)
 * @shared
 */
export interface PageMeta {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null; // (2026-07-02) 改为可空, 父级 is_group=true 可无 path
  is_active?: boolean;
  sort?: number;
  // (2026-07-02 nav spec §2.3) 透传整块 metadata_json 给前端
  // - parent_id: 父级 key (子菜单用)
  // - is_group: true = 父级容器, 不可点
  // - icon: lucide-react 图标名
  metadata?: {
    path?: string;
    parent_id?: string;
    is_group?: boolean;
    icon?: string;
    [k: string]: unknown;
  };
}

/**
 * 可序列化的权限数据子集, 跨 RSC → Client 边界传输
 * @shared
 */
export interface PermissionData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PageMeta[];
}
