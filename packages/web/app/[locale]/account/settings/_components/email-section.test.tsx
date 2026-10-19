// EmailSection 单元测试 (2026-06-18) T3.3
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { EmailSection } from "./email-section";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("EmailSection", () => {
  it("shows email + change button", () => {
    render(
      <IntlWrapper locale="zh">
        <EmailSection email="test@example.com" />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("email-value")).toHaveTextContent("test@example.com");
    expect(screen.getByTestId("email-change-button")).toBeInTheDocument();
  });

  it("does not render dialog stub by default", () => {
    render(
      <IntlWrapper locale="zh">
        <EmailSection email="test@example.com" />
      </IntlWrapper>,
    );
    expect(screen.queryByTestId("change-email-dialog-stub")).not.toBeInTheDocument();
  });
});
