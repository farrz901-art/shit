// use-user-table 单元测试 (2026-06-26) RBAC wire
//   测 changeRole: 1) PATCH body 含 role 2) optimistic 更新 3) 失败 toast
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { FIRST_PAGE, useUserTable, type AdminUser } from "./use-user-table";
import { ApiError } from "@/lib/api/errors";
import { HTTP_BAD_REQUEST } from "@/const";

const { patchUserMock } = vi.hoisted(() => ({ patchUserMock: vi.fn() }));

vi.mock("@/lib/api/users", () => ({
  patchUser: patchUserMock,
}));

const USER: AdminUser = {
  account_id: 1,
  created_at: "2026-06-01T00:00:00",
  display_name: "alice",
  email: "alice@x.com",
  id: 1,
  is_active: true,
  kind: "account",
  last_login_at: null,
  last_seen_at: "2026-06-13T00:00:00",
  role: "user",
};

const INITIAL = {
  items: [USER],
  page: FIRST_PAGE,
  page_size: 20,
  total: 1,
};

const USER_ID = USER.id;
const FIRST_ITEM_IDX = 0;

describe("useUserTable.changeRole", () => {
  beforeEach(() => {
    patchUserMock.mockReset();
    vi.spyOn(toast, "success").mockImplementation(() => "");
    vi.spyOn(toast, "error").mockImplementation(() => "");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("发 PATCH /api/admin/users/{id} body 含 role", async () => {
    patchUserMock.mockResolvedValue({ id: 1, ok: true });
    const { result } = renderHook(() => useUserTable(INITIAL));
    await act(async () => {
      result.current.changeRole(USER, "admin");
    });
    expect(patchUserMock).toHaveBeenCalledWith(USER_ID, { role: "admin" });
  });

  it("optimistic 更新: items[0].role 立刻变 admin", async () => {
    patchUserMock.mockResolvedValue({ id: 1, ok: true });
    const { result } = renderHook(() => useUserTable(INITIAL));
    act(() => {
      result.current.changeRole(USER, "admin");
    });
    // 不 await, optimistic 同步应用
    expect(result.current.data.items[FIRST_ITEM_IDX]?.role).toBe("admin");
  });

  it("失败 toast error, 不抛错", async () => {
    patchUserMock.mockRejectedValue(new ApiError(HTTP_BAD_REQUEST, "cannot demote self"));
    const { result } = renderHook(() => useUserTable(INITIAL));
    await act(async () => {
      result.current.changeRole(USER, "user");
    });
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("cannot demote self");
    });
  });
});
