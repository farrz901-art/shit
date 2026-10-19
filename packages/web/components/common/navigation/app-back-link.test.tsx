// BackLink 测试 (2026-06-15): 覆盖两种模式 (纯 link / useHistory)
// 跟旧 knowledge/BackButton 测试对齐: 1 个 testid, 默认/自定义 label, history 行为
// 新增: useHistory=false 时不挂 onClick (纯 link); 修饰键透传不拦截
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";

import zhMessages from "@/messages/zh.json";

const mockBack = vi.fn();
const mockPush = vi.fn();
// BackLink 实际用 @/i18n/navigation 的 useRouter (next-intl 4.x createNavigation 包装),
// 不是 next/navigation. 这里 mock 实际 import 的路径.
// 不走 importOriginal: 会拉真 next-intl/navigation → next/navigation 在 vitest ESM 下解析失败
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: mockBack, push: mockPush }),
}));

import { BackLink } from "./app-back-link";

// IntlWrapper: LocalizedLink 内部 useLocale 必须在 Provider 内
const wrap = (ui: React.ReactElement) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

describe("BackLink", () => {
  beforeEach(() => {
    mockBack.mockClear();
    mockPush.mockClear();
  });

  it("默认模式 (useHistory=false) 渲染 <a href=...> + testid + 默认 label", () => {
    wrap(<BackLink href="/output" data-testid="back-link" />);
    const link = screen.getByTestId("back-link");
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe("A");
    // 渲染后 href 会被 LocalizedLink 加 /zh 前缀
    expect(link.getAttribute("href")).toContain("/output");
    expect(screen.getByText("返回")).toBeInTheDocument();
  });

  it("自定义 label 生效", () => {
    wrap(<BackLink href="/output" label="返回 Output" />);
    expect(screen.getByText("返回 Output")).toBeInTheDocument();
  });

  it("useHistory=false 时不挂 onClick — 纯 <a> 行为 (右键/中键/SEO 仍可用)", () => {
    wrap(<BackLink href="/output" data-testid="back-link" />);
    const link = screen.getByTestId("back-link");
    fireEvent.click(link);
    // 默认模式不调 router.back/push, 让浏览器走 href
    expect(mockBack).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("useHistory=true: history.length > 1 时点 back()", () => {
    globalThis.history.pushState({}, "", "/foo"); // 模拟 history 长度
    wrap(<BackLink href="/knowledge/documents" useHistory data-testid="back-link" />);
    fireEvent.click(screen.getByTestId("back-link"));
    expect(mockBack).toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("useHistory=true: history 长度为 1 时 fallback push(href)", () => {
    Object.defineProperty(globalThis, "history", {
      configurable: true,
      value: { ...globalThis.history, back: vi.fn(), length: 1, pushState: vi.fn() },
      writable: true,
    });
    wrap(<BackLink href="/knowledge/documents" useHistory data-testid="back-link" />);
    fireEvent.click(screen.getByTestId("back-link"));
    expect(mockPush).toHaveBeenCalledWith("/knowledge/documents");
    expect(mockBack).not.toHaveBeenCalled();
  });

  it("useHistory=true: ctrl/cmd/shift/middle-click 时不拦截, 让浏览器原生处理 (新标签打开)", () => {
    Object.defineProperty(globalThis, "history", {
      configurable: true,
      value: { ...globalThis.history, back: vi.fn(), length: 5, pushState: vi.fn() },
      writable: true,
    });
    wrap(<BackLink href="/output" useHistory data-testid="back-link" />);
    const link = screen.getByTestId("back-link");
    // Ctrl+click
    fireEvent.click(link, { ctrlKey: true });
    fireEvent.click(link, { metaKey: true });
    fireEvent.click(link, { shiftKey: true });
    fireEvent.click(link, { button: 1 }); // Middle-click
    // 4 次修饰键点击都不应调 router
    expect(mockBack).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
