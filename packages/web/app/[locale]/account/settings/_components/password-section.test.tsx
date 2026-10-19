// PasswordSection 单元测试 (2026-06-18) T3.3
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { PasswordSection } from "./password-section";

describe("PasswordSection", () => {
  it("shows masked password + change button", () => {
    render(
      <IntlWrapper locale="zh">
        <PasswordSection />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("password-mask")).toBeInTheDocument();
    expect(screen.getByTestId("password-change-button")).toBeInTheDocument();
  });

  it("does not render dialog stub by default", () => {
    render(
      <IntlWrapper locale="zh">
        <PasswordSection />
      </IntlWrapper>,
    );
    expect(screen.queryByTestId("change-password-dialog-stub")).not.toBeInTheDocument();
  });
});
