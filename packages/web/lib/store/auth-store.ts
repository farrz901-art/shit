// (2026-06-23) 登录用户 auth 状态 (zustand)
// 存储 account_id 供聊天等场景使用
// (2026-06-23) setAccountId 接受 number | null — 登出/未登录时由 PermissionHydrate 传 null 清除
//   避免 localStorage persist 残留陈旧 accountId
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  accountId: number | null;
  setAccountId: (id: number | null) => void;
}

/**
 * 管理登录用户 auth 状态 (accountId)
 * @client-bff
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accountId: null,
      setAccountId: (accountId) => set({ accountId }),
    }),
    { name: "rag.auth-store.v1" },
  ),
);
