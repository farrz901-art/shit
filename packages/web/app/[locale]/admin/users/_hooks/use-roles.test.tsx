// use-roles 单元测试 (2026-06-26) RBAC wire
//   测: 1) initialData 立即可用 2) mount refetch 1 次 3) staleTime 60s
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useRoles } from "./use-roles";

const CALLED_ONCE = 1;
const SECOND_ROLE_IDX = 1;
const UPDATED_USER_COUNT = 99;

const SAMPLE_ROLES = [
  {
    created_at: "2026-06-17T00:00:00",
    is_deletable: false,
    is_system: true,
    label_en: "Super Admin",
    label_zh: "超级管理员",
    name: "super_admin",
    updated_at: "2026-06-17T00:00:00",
    user_count: 1,
  },
  {
    created_at: "2026-06-17T00:00:00",
    is_deletable: false,
    is_system: true,
    label_en: "Admin",
    label_zh: "管理员",
    name: "admin",
    updated_at: "2026-06-17T00:00:00",
    user_count: 3,
  },
];

const { listRolesMock } = vi.hoisted(() => ({ listRolesMock: vi.fn() }));

vi.mock("@/lib/api/permissions", () => ({
  listRoles: listRolesMock,
}));

const createWrapper = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
};

describe("useRoles", () => {
  beforeEach(() => {
    listRolesMock.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("initialData 立即可用, refetch 后台静默", () => {
    listRolesMock.mockResolvedValue({ roles: SAMPLE_ROLES });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    expect(result.current).toEqual(SAMPLE_ROLES);
  });

  it("mount 强制 refetch 1 次", async () => {
    listRolesMock.mockResolvedValue({ roles: SAMPLE_ROLES });
    const { wrapper } = createWrapper();
    renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    await waitFor(() => {
      expect(listRolesMock).toHaveBeenCalledTimes(CALLED_ONCE);
    });
  });

  it("refetch 后 data 替换为最新 roles", async () => {
    const FRESH = [{ ...SAMPLE_ROLES[SECOND_ROLE_IDX]!, user_count: UPDATED_USER_COUNT }];
    listRolesMock.mockResolvedValue({ roles: FRESH });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useRoles(SAMPLE_ROLES), { wrapper });
    await waitFor(() => {
      expect(result.current).toEqual(FRESH);
    });
  });
});
