// RequestDeletionDialog 单元测试 (2026-06-18) T4.1 — 替 T3.3 stub 测试
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { RequestDeletionDialog } from "./request-deletion-dialog";

describe("RequestDeletionDialog", () => {
  it("renders form fields when open", () => {
    render(
      <IntlWrapper locale="zh">
        <RequestDeletionDialog onOpenChange={() => {}} open={true} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("request-deletion-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-current-password")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-confirm-text")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-submit")).toBeInTheDocument();
  });
});
