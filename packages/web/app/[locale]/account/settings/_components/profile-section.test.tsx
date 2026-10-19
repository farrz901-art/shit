// ProfileSection 单元测试 (2026-06-18) T3.3
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { ProfileSection } from "./profile-section";

describe("ProfileSection", () => {
  it("renders display_name input with initial value", () => {
    render(
      <IntlWrapper locale="zh">
        <ProfileSection me={{ avatar_url: null, display_name: "Alice" }} />
      </IntlWrapper>,
    );
    const input = screen.getByTestId("profile-display-name") as HTMLInputElement;
    expect(input.value).toBe("Alice");
  });

  it("falls back to empty when display_name is null", () => {
    render(
      <IntlWrapper locale="zh">
        <ProfileSection me={{ avatar_url: null, display_name: null }} />
      </IntlWrapper>,
    );
    const input = screen.getByTestId("profile-display-name") as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("renders avatar with data-testid", () => {
    render(
      <IntlWrapper locale="zh">
        <ProfileSection me={{ avatar_url: null, display_name: "Bob" }} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("profile-avatar")).toBeInTheDocument();
    expect(screen.getByTestId("profile-save")).toBeInTheDocument();
  });
});
