// SubmitButton 测试 (2026-06-14) — useFormStatus mock 返回 { pending: false }
// (2026-06-21) 加 className 透传 + pending 状态测试
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { SubmitButton } from "./app-submit-button";
import { useFormStatus } from "react-dom";

describe("SubmitButton", () => {
  it("渲染 children 文案", () => {
    render(
      <form>
        <SubmitButton>提交</SubmitButton>
      </form>,
    );
    expect(screen.getByRole("button", { name: "提交" })).toBeInTheDocument();
  });

  it("默认 pendingLabel='提交中…'", () => {
    render(
      <form>
        <SubmitButton>保存</SubmitButton>
      </form>,
    );
    // UseFormStatus mock 返回 { pending: false }, 所以显示 children
    expect(screen.getByRole("button", { name: "保存" })).toBeInTheDocument();
  });

  it("disabled prop 透传", () => {
    render(
      <form>
        <SubmitButton disabled>提交</SubmitButton>
      </form>,
    );
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("custom className 透传", () => {
    render(
      <form>
        <SubmitButton className="my-custom-class">提交</SubmitButton>
      </form>,
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("my-custom-class");
  });

  it("pending 时显示 pendingLabel 且按钮 disabled", () => {
    // FormStatus 类型定义 pending 为 literal false, 需要 as any 绕开
    vi.mocked(useFormStatus).mockReturnValue({
      data: null,
      method: null,
      action: null,
      pending: true,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    render(
      <form>
        <SubmitButton pendingLabel="加载中…">提交</SubmitButton>
      </form>,
    );
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("加载中…");
  });
});
