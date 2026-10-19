import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AppConfirm } from "./app-confirm";

describe("AppConfirm", () => {
  it("open=true 渲染 title + description + 按钮", () => {
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="删除"
        description="不可撤销"
        confirmText="删除"
        cancelText="取消"
        onConfirm={vi.fn()}
      />,
    );
    // Title 出现在 h2
    expect(screen.getByRole("heading", { name: "删除" })).toBeInTheDocument();
    expect(screen.getByText("不可撤销")).toBeInTheDocument();
    // 取消按钮 (确认按钮也叫 "删除", 用 role 区分)
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除" })).toBeInTheDocument();
  });

  it("点确认触发 onConfirm", async () => {
    const userEventModule = await import("@testing-library/user-event");
    const userEvent = userEventModule.default;
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="删除"
        confirmText="删除"
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByRole("button", { name: "删除" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("description 可选, 不传时不渲染", () => {
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="删除"
        confirmText="删除"
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: "删除" })).toBeInTheDocument();
  });

  it("variant=destructive 确认按钮用破坏色", () => {
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="危险操作"
        variant="destructive"
        confirmText="确认删除"
        onConfirm={vi.fn()}
      />,
    );
    const confirmBtn = screen.getByRole("button", { name: "确认删除" });
    expect(confirmBtn.className).toContain("bg-destructive");
  });

  it("onCancel 被调用", async () => {
    const userEventModule = await import("@testing-library/user-event");
    const user = userEventModule.default.setup();
    const onCancel = vi.fn();
    render(
      <AppConfirm
        open={true}
        onOpenChange={vi.fn()}
        title="测试"
        confirmText="确认"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
