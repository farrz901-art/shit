// RestoreDeletionBanner 单元测试 (2026-06-18) T4.3
import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { RestoreDeletionBanner } from "./restore-deletion-banner";

// 5 天对应的毫秒数
const FIVE_DAYS_MS = 432_000_000;

describe("RestoreDeletionBanner", () => {
  it("renders nothing when expiresAt is null", () => {
    const { container } = render(
      <IntlWrapper locale="zh">
        <RestoreDeletionBanner expiresAt={null} />
      </IntlWrapper>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders banner with countdown when expiresAt is set", () => {
    // 5 天后到期
    const future = new Date(Date.now() + FIVE_DAYS_MS).toISOString();
    render(
      <IntlWrapper locale="zh">
        <RestoreDeletionBanner expiresAt={future} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("restore-deletion-banner")).toBeInTheDocument();
    expect(screen.getByTestId("banner-cancel-button")).toBeInTheDocument();
  });

  it("shows password input when cancel button clicked", () => {
    const future = new Date(Date.now() + FIVE_DAYS_MS).toISOString();
    render(
      <IntlWrapper locale="zh">
        <RestoreDeletionBanner expiresAt={future} />
      </IntlWrapper>,
    );
    const cancelButton = screen.getByTestId("banner-cancel-button");
    fireEvent.click(cancelButton);
    expect(screen.getByTestId("banner-cancel-password")).toBeInTheDocument();
    expect(screen.getByTestId("banner-cancel-submit")).toBeInTheDocument();
  });
});
