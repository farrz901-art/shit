import { screen } from "@testing-library/react";
import { useTranslations } from "next-intl";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "./render-with-intl";

const GreetingComponent = () => {
  const translate = useTranslations();
  return <div data-testid="greeting">{translate("加载中…")}</div>;
};

describe("renderWithIntl", () => {
  it("提供 NextIntlClientProvider context 让 useTranslations 工作", () => {
    renderWithIntl(<GreetingComponent />);
    expect(screen.getByTestId("greeting")).toHaveTextContent("加载中…");
  });

  it("允许 override messages 测试 i18n fallback", () => {
    renderWithIntl(<GreetingComponent />, { messages: { "加载中…": "Loading..." } });
    expect(screen.getByTestId("greeting")).toHaveTextContent("Loading...");
  });
});
