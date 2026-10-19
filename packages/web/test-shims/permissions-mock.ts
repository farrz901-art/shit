// 测试辅助: 模拟 /api/permissions/me 返 admin 全权限
// (2026-06-17) v2 RBAC: 各 RSC page.tsx 现在调 getMyPermissions → /api/permissions/me,
//   旧测试 mock fetch 只返业务数据, 没 mock permissions endpoint,
//   PageGuard 会拿默认 {allowed:["chat"]} 调 notFound() 让测试挂.
//   用法: 在 page.test.tsx 顶部 import { installAdminPermissionsMock } from "@/test-shims/permissions-mock";
//     BeforeEach(installAdminPermissionsMock);
import { vi } from "vitest";

const ADMIN_PERMISSIONS_PAYLOAD = {
  allowed: ["chat", "output", "knowledge", "evaluate", "submissions", "decode", "health", "admin"],
  pages: [],
  role: "admin",
};

/**
 * 装 /api/permissions/me mock (admin 全权限).
 * 必须在 beforeEach 里调, 替代测试原有的 global.fetch mock.
 * 测试里可以再覆盖 global.fetch 调整其他 endpoint 行为.
 */
export const installAdminPermissionsMock = (): void => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const urlString = typeof url === "string" ? url : url.toString();
    if (urlString.includes("/api/permissions/me")) {
      return Response.json(ADMIN_PERMISSIONS_PAYLOAD, {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    // 其他 endpoint 走原 fetch (用户可能已 mock)
    return originalFetch(url, init);
  }) as never;
};
