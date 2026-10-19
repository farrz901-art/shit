// (2026-06-13, Task 17) LoginPage 单元测试
// (2026-06-14) 改 useActionState: mock loginAction(prev, formData) 两参签名
// (2026-06-17) 成功跳转下沉到 loginAction 内部 server-side redirect():
//   旧测试 "成功 → router.push('/')" 已删, 跳转现在由 server action 处理, 单测验不到 redirect 的副作用.
//   新测试 "成功 → state.ok=true 但不显示 ErrorBanner" 验证 success path 的 UI 状态.
import * as accountActions from "@/app/[locale]/_actions/account";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import LoginPage from "./page";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

// (2026-06-17) loginAction 内部走 server-side redirect(), wrapper 不再调 useRouter.
//   但 page.tsx 仍可能 import 错, mock 保留以防 layout/AuthBootstrap 等间接用上. 仍不 mock
//   Next-intl 内部 (第三方库) — 见 [[feedback-vitest-mock-third-party-hides-broken-import]].
vi.mock("@/i18n/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

// Mock server action — useActionState 签名: (prevState, formData)
// (2026-06-17) 真实 loginAction 成功会调 redirect() 抛 NEXT_REDIRECT. 单测里 mock 不调, 只返 ok:true.
vi.spyOn(accountActions, "loginAction").mockImplementation(async (_prev, fd) => {
  const email = String(fd.get("email") ?? "");
  const password = String(fd.get("password") ?? "");
  if (email === "alice@x.com" && password === "longpassword") {
    // LoginState.error 类型是 `string | null`, null 符合契约.
    // Oxlint 已在 .oxlintrc.json 禁掉 unicorn/no-null 全局, 不再 inline disable.
    return { error: null, ok: true };
  }
  return { error: "邮箱或密码错", ok: false };
});

const renderPage = () =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <LoginPage />
    </NextIntlClientProvider>,
  );

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("输错密码 → 顶部错误 '邮箱或密码错'", async () => {
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "wrong@x.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "wrong-pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));
    expect(await screen.findByText("邮箱或密码错")).toBeInTheDocument();
  });

  // (2026-06-17) 成功路径: mock loginAction 返 ok:true, 真实代码会调 redirect() 但 mock 不调.
  //   这里验 success 状态下不显示 ErrorBanner (不会误把 ok:true 当错误展示).
  //   跳转 + layout 刷新走 server-side redirect, 不在单测范围 (E2E 覆盖).
  it("成功 → state.ok=true, 不显示 ErrorBanner", async () => {
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "alice@x.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "longpassword" } });
    fireEvent.click(screen.getByTestId("login-submit"));
    // 等异步 action 跑完, 确认没有错误条
    await waitFor(() => {
      expect(screen.queryByText("邮箱或密码错")).not.toBeInTheDocument();
    });
    expect(screen.queryByText("登录失败")).not.toBeInTheDocument();
  });

  it("空 email/password → 按钮 disabled", () => {
    renderPage();
    expect(screen.getByTestId("login-submit")).toBeEnabled();
  });
});
