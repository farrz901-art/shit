// (2026-06-23) 跨组件 UI 状态 (Zustand)
// 当前: sidebar 切换 (为后续 sidebar 组件预留)
// 后续: 可加 global loading, toast 队列等

import { create } from "zustand";

interface UIState {
  sidebarOpen: boolean;
  setSidebarOpen: (val: boolean) => void;
  toggleSidebar: () => void;
}

/**
 * 管理跨组件 UI 状态 (侧边栏开关)
 * @client-bff
 */
export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
