/**
 * 客户端读权限 hook (P1-7, 2026-06-29 补 can() + super_admin 短路语义)
 *
 * 必须在 <PermissionHydrate> 之后用, 否则返默认空权限 (loaded=false).
 * 跟 server 端 lib/auth/permission.ts getPermissions() 同语义 (super_admin 短路).
 * @returns { allowed, can, isAdminLevel, isSuperAdmin, loaded, pages, role }
 *   - can(pageKey): 当前用户能否访问该页. super_admin 短路 true, 否则看 allowed.
 *   - loaded: hydration 完成标志, false 时不要渲染菜单 (会闪一下从空到填充)
 *   - role: 原始 role 字符串 ("user" / "admin" / "super_admin" / 自定义角色名)
 */
// (2026-06-23) UsePermissions: hydration-only zustand store
// RSC layout 调 getPermissions() → PermissionHydrate → store.hydrate()
// 不再 client 侧调 API fetch
import { create } from "zustand";
import type { PermissionData } from "@/lib/auth/permission-types";

interface PermissionsStoreState {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PermissionData["pages"];
  loaded: boolean;
}

interface PermissionsStore extends PermissionsStoreState {
  hydrate: (data: PermissionData) => void;
  /** (2026-07-02 nav spec §6) 清空 store 强制 RSC layout 重新 hydrate */
  reset: () => void;
}

/** Zustand store: 由 RSC PermissionHydrate 填充, 客户端只读.
 * @client-bff */
export const usePermissionsStore = create<PermissionsStore>((set) => ({
  role: "user",
  accountId: null,
  allowed: [],
  pages: [],
  loaded: false,
  hydrate: (data) => {
    try {
      set({
        role: data.role,
        accountId: data.accountId ?? null,
        allowed: data.allowed,
        pages: data.pages,
        loaded: true,
      });
    } catch {
      set({ loaded: true });
    }
  },
  reset: () => {
    set({ role: "user", accountId: null, allowed: [], pages: [], loaded: false });
  },
}));

/** 客户端读权限 hook, 在 <PermissionHydrate> 之后使用.
 * @returns {{ allowed, can, isAdminLevel, isSuperAdmin, loaded, pages, role }}
 * @client-bff */
export const usePermissions = () => {
  const store = usePermissionsStore();
  return {
    allowed: store.allowed,
    // super_admin 短路: 不管 allowed 里有没有, super_admin 直接 true (跟 server getPermissions 同语义)
    can: (pageKey: string) => store.role === "super_admin" || store.allowed.includes(pageKey),
    isAdminLevel: store.role !== "user",
    isSuperAdmin: store.role === "super_admin",
    loaded: store.loaded,
    pages: store.pages,
    role: store.role,
  };
};
