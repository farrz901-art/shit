// ChangePasswordDialog 单元测试 (2026-06-18) T4.1 — 替 T3.3 stub 测试
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ChangePasswordDialog } from "./change-password-dialog";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("ChangePasswordDialog", () => {
  it("renders form fields when open", () => {
    render(
      <IntlWrapper locale="zh">
        <ChangePasswordDialog onOpenChange={() => {}} open={true} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("change-password-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("password-current")).toBeInTheDocument();
    expect(screen.getByTestId("password-new")).toBeInTheDocument();
    expect(screen.getByTestId("password-confirm")).toBeInTheDocument();
    expect(screen.getByTestId("password-submit")).toBeInTheDocument();
  });
});
