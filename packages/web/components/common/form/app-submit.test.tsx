// AppSubmit 测试 — TDD 红绿循环 (2026-06-25)
import { AppForm } from "./app-form";
import { AppSubmit } from "./app-submit";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it } from "vitest";

const TEST_TEXT = "提交";
const TEST_CLASS = "custom-class";
const TEST_ID = "submit-btn";

describe("AppSubmit", () => {
  it("渲染 children 文本", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={async () => {}}>
        <AppSubmit>{TEST_TEXT}</AppSubmit>
      </AppForm>,
    );
    expect(screen.getByText(TEST_TEXT)).toBeInTheDocument();
  });

  it("透传 className 和 data-testid", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={async () => {}}>
        <AppSubmit className={TEST_CLASS} data-testid={TEST_ID}>
          {TEST_TEXT}
        </AppSubmit>
      </AppForm>,
    );
    const button = screen.getByTestId(TEST_ID);
    expect(button.className).toContain(TEST_CLASS);
  });

  it("按钮 type 为 submit", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={async () => {}}>
        <AppSubmit data-testid={TEST_ID}>{TEST_TEXT}</AppSubmit>
      </AppForm>,
    );
    expect(screen.getByTestId(TEST_ID)).toHaveAttribute("type", "submit");
  });
});
