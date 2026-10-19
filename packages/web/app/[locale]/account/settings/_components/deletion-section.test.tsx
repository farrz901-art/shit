// DeletionSection 单元测试 (2026-06-18) T3.3
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { DeletionSection } from "./deletion-section";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("DeletionSection", () => {
  it("shows request button when not pending", () => {
    render(
      <IntlWrapper locale="zh">
        <DeletionSection isPending={false} expiresAt={null} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("deletion-active")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-request-button")).toBeInTheDocument();
    expect(screen.queryByTestId("deletion-pending")).not.toBeInTheDocument();
  });

  it("shows cancel form when pending", () => {
    render(
      <IntlWrapper locale="zh">
        <DeletionSection isPending={true} expiresAt="2026-06-25T00:00:00Z" />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("deletion-pending")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-cancel-password")).toBeInTheDocument();
    expect(screen.getByTestId("deletion-cancel-submit")).toBeInTheDocument();
    expect(screen.queryByTestId("deletion-active")).not.toBeInTheDocument();
  });

  it("does not render dialog stub when not pending and not opened", () => {
    render(
      <IntlWrapper locale="zh">
        <DeletionSection isPending={false} expiresAt={null} />
      </IntlWrapper>,
    );
    expect(screen.queryByTestId("request-deletion-dialog-stub")).not.toBeInTheDocument();
  });
});
