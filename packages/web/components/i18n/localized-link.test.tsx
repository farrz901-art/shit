import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { LocalizedLink } from "./localized-link";
import { NextIntlClientProvider } from "next-intl";

const messages = { 测试: "测试" } as any;

// Mock next/link to render plain <a> so we can test href attribute
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("LocalizedLink", () => {
  it("zh locale 自动加 /zh 前缀", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/knowledge">知识库</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("知识库").closest("a")).toHaveAttribute("href", "/zh/knowledge");
  });

  it("en locale 自动加 /en 前缀", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <LocalizedLink href="/output">Output</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Output").closest("a")).toHaveAttribute("href", "/en/output");
  });

  it("已含 locale 前缀时不去重", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/zh/knowledge">知识库</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("知识库").closest("a")).toHaveAttribute("href", "/zh/knowledge");
  });

  it("根路径 / → /zh", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/">Home</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Home").closest("a")).toHaveAttribute("href", "/zh");
  });
});
