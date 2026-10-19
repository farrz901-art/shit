// Admin Users / Invites API 单测 (2026-06-30)
// 覆盖: listUsers / createInvite / resetPassword / patchUser + 新加 listInvites / deleteInvite
// (2026-06-14) 删网络断/NetworkError 路径 (apiFetch 已统一归一, 测一次在 config.ts 即可)
/* oxlint-disable no-magic-numbers -- 测试 fixture 用具体 id / status */
import { HTTP_BAD_REQUEST, HTTP_OK, HTTP_UNAUTHORIZED } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import {
  createInvite,
  deleteInvite,
  listInvites,
  listUsers,
  patchUser,
  resetPassword,
} from "./users";

const okResponse = (data: unknown, status = HTTP_OK): Response =>
  ({
    ok: true,
    status,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

describe("listUsers", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("无 params → /api/admin/users", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await listUsers();
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/users");
  });

  it("有 params → 拼 query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await listUsers("role=admin&is_active=true");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/users?role=admin&is_active=true");
  });
});

describe("createInvite", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("POST /api/admin/invites 带 email", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await createInvite("a@x.com");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/invites");
    expect(init.method).toBe("POST");
  });
});

describe("resetPassword", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("POST /api/admin/users/{id}/reset-password", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ temp_password: "tmp" }));
    vi.stubGlobal("fetch", fetchMock);
    await resetPassword(42);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/users/42/reset-password");
    expect(init.method).toBe("POST");
  });
});

describe("patchUser", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("PATCH /api/admin/users/{id} 带 body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ id: 1, ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await patchUser(1, { is_active: false, role: "user" });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/users/1");
    expect(init.method).toBe("PATCH");
  });
});

describe("listInvites", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("GET /api/admin/invites 透传 typed response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ items: [{ id: 1, email: "a@x.com" }] })),
    );
    const result = await listInvites<{ items: { id: number; email: string }[] }>();
    expect(result.items).toEqual([{ id: 1, email: "a@x.com" }]);
  });

  it("无 headers → 默认 GET (method=undefined)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await listInvites();
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/invites");
    expect(init.method).toBeUndefined();
  });

  it("4xx 抛 ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: HTTP_UNAUTHORIZED,
        statusText: "Unauthorized",
        text: async () => JSON.stringify({ detail: "未登录" }),
      } as unknown as Response),
    );
    await expect(listInvites()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("deleteInvite", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("DELETE /api/admin/invites/{token} 转义 token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await deleteInvite("a/b c");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/api/admin/invites/a%2Fb%20c");
    expect(init.method).toBe("DELETE");
  });

  it("4xx 抛 ApiError (status + detail)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: HTTP_BAD_REQUEST,
        statusText: "Bad Request",
        text: async () => JSON.stringify({ detail: "invite 不存在" }),
      } as unknown as Response),
    );
    await expect(deleteInvite("x")).rejects.toMatchObject({
      message: "invite 不存在",
      status: HTTP_BAD_REQUEST,
    });
  });
});
