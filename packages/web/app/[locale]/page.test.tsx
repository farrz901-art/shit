// /[locale] Landing RSC 测试 (2026-06-29):
//   未登录 (isAccount=false) → redirect 到 /chat
//   账号用户 (isAccount=true) → 渲染 ENTRIES (对话 / 知识库 / 评估)
//
// 实现细节:
//   - mock @/i18n/navigation 的 redirect (项目 CLAUDE.md 强制, 禁 next/navigation)
//   - mock next/headers 的 cookies (走 serverAuthHeaders 读 COOKIE_USER_TOKEN)
//   - mock next-intl/server 的 getTranslations + getLocale (page + redirect 都要)
//   - mock globalThis.fetch → /api/account/me 返 is_account
//
// 参照模板:
//   - chat/page.test.tsx (fetch + cookies mock)
//   - account/settings/page.test.tsx (redirectMock 抛 NEXT_REDIRECT 走 try/catch)
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { HTTP_UNAUTHORIZED, ONE } from "@/const";

const { redirectMock, fetchMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  redirectMock: vi.fn((args: { href: string; locale: string }) => {
    // 真实 redirect() 抛 NEXT_REDIRECT 终止后续执行. 测试吞掉异常
    // (跟 account/settings/page.test.tsx:11-17 一致模式).
    const err = new Error(`NEXT_REDIRECT: ${args.href}`);
    (err as Error & { digest?: string }).digest = "NEXT_REDIRECT";
    throw err;
  }),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    // 跟 chat/page.test.tsx 一致: anon 场景给个假 token 让 serverAuthHeaders 不返空,
    //   真正 isAccount=false 由 /api/account/me 401 兜底.
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

vi.mock("@/i18n/navigation", () => ({
  redirect: redirectMock,
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  getPathname: () => "/",
}));

vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
  getLocale: vi.fn(async () => "zh"),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errorResponse = (status: number): Response =>
  ({
    ok: false,
    status,
    statusText: "Unauthorized",
    text: async () => "",
  }) as unknown as Response;

globalThis.fetch = fetchMock as never;

import landingPage from "./page";

describe("LandingPage (RSC)", () => {
  beforeEach(() => {
    redirectMock.mockClear();
    fetchMock.mockReset();
  });

  it("anon (/api/account/me 401) → redirect /chat", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(HTTP_UNAUTHORIZED));
    await landingPage().catch(() => {});
    expect(redirectMock).toHaveBeenCalledTimes(ONE);
    expect(redirectMock).toHaveBeenCalledWith({ href: "/chat", locale: "zh" });
  });

  it("账号用户 (/api/account/me 200 is_account=true) → 渲染对话 / 知识库 / 评估 3 入口", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ is_account: true }));
    const Page = await landingPage();
    // IntlWrapper: LocalizedLink 内部 useLocale 必须在 Provider 内
    render(
      <IntlWrapper locale="zh">
        <>{Page}</>
      </IntlWrapper>,
    );
    // 3 入口标题 (跟 page.tsx ENTRIES 数组对齐)
    expect(screen.getByText("对话")).toBeInTheDocument();
    expect(screen.getByText("知识库")).toBeInTheDocument();
    expect(screen.getByText("评估")).toBeInTheDocument();
    // 入口描述 (跟 page.tsx ENTRIES 数组对齐)
    expect(screen.getByText("跟产品智能体聊")).toBeInTheDocument();
    expect(screen.getByText("录 QA / 文档 / 三元组")).toBeInTheDocument();
    expect(screen.getByText("RAG 评估报告")).toBeInTheDocument();
    // 账号态不应触发 redirect
    expect(redirectMock).not.toHaveBeenCalled();
  });
});
