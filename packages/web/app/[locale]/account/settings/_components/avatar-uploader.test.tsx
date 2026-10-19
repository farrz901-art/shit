// AvatarUploader 单元测试 (2026-06-18) T4.2
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AvatarUploader } from "./avatar-uploader";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

describe("AvatarUploader", () => {
  it("renders upload button when no current avatar", () => {
    render(
      <IntlWrapper locale="zh">
        <AvatarUploader currentUrl={null} />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("avatar-uploader")).toBeInTheDocument();
    expect(screen.getByTestId("avatar-upload-button")).toBeInTheDocument();
    expect(screen.queryByTestId("avatar-remove-button")).not.toBeInTheDocument();
  });

  it("renders remove button when current avatar exists", () => {
    render(
      <IntlWrapper locale="zh">
        <AvatarUploader currentUrl="s3://test/avatar.webp" />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("avatar-upload-button")).toBeInTheDocument();
    expect(screen.getByTestId("avatar-remove-button")).toBeInTheDocument();
  });

  it("renders file input with correct accept attribute", () => {
    render(
      <IntlWrapper locale="zh">
        <AvatarUploader currentUrl={null} />
      </IntlWrapper>,
    );
    const fileInput = screen.getByTestId("avatar-file-input");
    expect(fileInput).toHaveAttribute("accept", "image/png,image/jpeg,image/webp");
  });
});
