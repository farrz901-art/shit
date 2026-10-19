import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nProvider } from "./provider";
import { useTranslations } from "next-intl";

const messages = { common: { loading: "加载中" } } as any;

const Consumer = () => {
  const translate = useTranslations("common");
  return <div data-testid="translated">{translate("loading")}</div>;
};

describe("I18nProvider", () => {
  it("传入 messages 后子组件能用 useTranslations", () => {
    render(
      <I18nProvider locale="zh" messages={messages} timeZone="Asia/Shanghai">
        <Consumer />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("加载中");
  });
});
