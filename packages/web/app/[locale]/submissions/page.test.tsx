// /submissions RSC 单元测试 — TDD red phase
// 覆盖: 1) 无 token → redirect /login  2) 普通用户不调 all 端点  3) admin 同时调 mine + all

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

const { cookiesMock, fetchMock } = vi.hoisted(() => ({
  cookiesMock: vi.fn(),
  fetchMock: vi.fn(),
}));

// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("next/headers", () => ({
  cookies: cookiesMock,
}));
// (2026-06-17) cookies mock 返有 .get() 方法的对象 (v2 RBAC: authHeaders 调 c.get("rag_user_token"))
cookiesMock.mockResolvedValue({
  get: (key: string) => {
    if (key === "rag_user_token") {
      return { value: "t" };
    }
    return undefined;
  },
  toString: () => "rag_user_token=t",
});

vi.mock("next/navigation", () => ({
  // 真实 redirect 抛 NEXT_REDIRECT 终止后续执行 — 测试吞掉异常
  redirect: vi.fn((url: string) => {
    const err = new Error(`REDIRECT:${url}`);
    throw err;
  }),
  // SubmissionsTabs (client) 内部 useRouter
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

// RSC 测试: jsdom 不支持 next-intl/server getTranslations, mock 成回传 key 本身
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
}));

// 子组件内部 useQuery — 返空数据, 不让真实 RQ 找不到 QueryClient
vi.mock("@tanstack/react-query", () => ({
  useMutation: () => ({ isPending: false, mutate: vi.fn() }),
  useQuery: () => ({ data: undefined }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

// 客户端 next-intl useTranslations (子组件 MySubmissionsList 用)
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.stubGlobal("fetch", fetchMock);

import SubmissionsPage from "./page";

const renderPage = (searchParams: Record<string, string> = {}) => {
  const pageFactory = SubmissionsPage;
  return pageFactory({ searchParams: Promise.resolve(searchParams) });
};

describe("SubmissionsPage RSC", () => {
  beforeEach(() => {
    cookiesMock.mockReset();
    fetchMock.mockReset();
    // (2026-06-17) cookies mock 返有 .get() 方法的对象 (v2 RBAC: authHeaders 调 c.get("rag_user_token"))
    cookiesMock.mockResolvedValue({
      get: (key: string) => {
        if (key === "rag_user_token") {
          return { value: "t" };
        }
        return undefined;
      },
      toString: () => "rag_user_token=t",
    });
    // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (默认兜底, 个别 case 用 mockResolvedValueOnce 覆盖)
    fetchMock.mockImplementation(async (url: string | URL | Request) => {
      let urlString = "";
      if (typeof url === "string") {
        urlString = url;
      } else {
        urlString = url.toString();
      }
      if (urlString.includes("/api/permissions/me")) {
        return Response.json(
          {
            allowed: [
              "chat",
              "output",
              "knowledge",
              "evaluate",
              "submissions",
              "decode",
              "health",
              "admin",
            ],
            pages: [],
            role: "admin",
          },
          { headers: { "Content-Type": "application/json" }, status: 200 },
        );
      }
      return new Response("not mocked", { status: 404 });
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("无 token → redirect /login?next=/submissions", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 401 }));
    await expect(renderPage()).rejects.toThrow(/REDIRECT:.*login/);
  });

  it("普通用户 (is_admin=false) → 不渲染 all tab, 只调 /api/approvals/me", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json({ is_admin: false }, { status: 200 })) // /me
      .mockResolvedValueOnce(Response.json([], { status: 200 })); // /me (RSC 预取)
    const Page = await renderPage();
    render(<>{Page}</>);
    const urls = fetchMock.mock.calls.map(([firstArg]) => firstArg as string);
    expect(urls.some((url) => url.includes("/api/approvals/me"))).toBe(true);
    expect(urls.some((url) => url.includes("/api/approvals?review=pending"))).toBe(false);
  });

  it("admin → 调 /api/approvals/me + /api/approvals (admin 路径)", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json({ is_admin: true }, { status: 200 })) // /me
      .mockResolvedValueOnce(Response.json([], { status: 200 })) // /me (RSC 预取)
      .mockResolvedValueOnce(Response.json([], { status: 200 })); // /api/approvals
    const Page = await renderPage();
    render(<>{Page}</>);
    const urls = fetchMock.mock.calls.map(([firstArg]) => firstArg as string);
    expect(urls.some((url) => url.includes("/api/approvals/me"))).toBe(true);
    expect(urls.some((url) => url.includes("/api/approvals?review=pending"))).toBe(true);
  });
});
