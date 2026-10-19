// CancelDeletionDialog 单元测试 (2026-06-18) T4.1 — 新增, 给 RestoreDeletionBanner (T4.3) 用
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { CancelDeletionDialog } from "./cancel-deletion-dialog";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("CancelDeletionDialog", () => {
  it("renders form fields when open", () => {
    render(
      <IntlWrapper locale="zh">
        <CancelDeletionDialog onOpenChange={() => {}} open={true} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("cancel-deletion-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-deletion-password")).toBeInTheDocument();
    expect(screen.getByTestId("cancel-deletion-submit")).toBeInTheDocument();
  });
});
