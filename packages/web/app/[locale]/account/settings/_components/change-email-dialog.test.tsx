// ChangeEmailDialog 单元测试 (2026-06-18) T4.1 — 替 T3.3 stub 测试
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ChangeEmailDialog } from "./change-email-dialog";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("ChangeEmailDialog", () => {
  it("renders form fields when open", () => {
    render(
      <IntlWrapper locale="zh">
        <ChangeEmailDialog onOpenChange={() => {}} open={true} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("change-email-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("email-new")).toBeInTheDocument();
    expect(screen.getByTestId("email-current-password")).toBeInTheDocument();
    expect(screen.getByTestId("email-submit")).toBeInTheDocument();
  });
});
