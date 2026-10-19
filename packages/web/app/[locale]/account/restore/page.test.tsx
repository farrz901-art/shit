// /account/restore page 测试 (2026-06-18) T4.3
// 测 RestoreForm 客户端组件 (跳过 RSC + redirect, 太难直接测)
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { RestoreForm } from "./restore-form";

describe("RestoreForm", () => {
  it("renders password input + submit button", () => {
    render(
      <IntlWrapper locale="zh">
        <RestoreForm />
      </IntlWrapper>,
    );
    expect(screen.getByTestId("restore-password")).toBeInTheDocument();
    expect(screen.getByTestId("restore-submit")).toBeInTheDocument();
  });
});
