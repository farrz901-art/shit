import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "./intl-wrapper";
import { useTranslations } from "next-intl";

const Consumer = () => {
  const translate = useTranslations();
  return <div data-testid="translated">{translate("对话")}</div>;
};

describe("IntlWrapper", () => {
  it("zh locale 传入中文 messages", () => {
    render(
      <IntlWrapper locale="zh">
        <Consumer />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("对话");
  });

  it("en locale 传入英文 messages, '对话' 翻译为 'Chat'", () => {
    render(
      <IntlWrapper locale="en">
        <Consumer />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Chat");
  });
});
