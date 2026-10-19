import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { AppDialog } from "./app-dialog";

describe("AppDialog 基础渲染", () => {
  it("open=true 渲染 title + description", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="编辑" description="修改信息">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("编辑")).toBeInTheDocument();
    expect(screen.getByText("修改信息")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("open=false 不渲染内容", () => {
    render(
      <AppDialog open={false} onOpenChange={vi.fn()} title="编辑">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.queryByText("内容")).not.toBeInTheDocument();
  });

  it("footer 渲染", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="编辑" footer={<button>保存</button>}>
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("保存")).toBeInTheDocument();
  });

  it("maxWidth 应用到 className", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试" maxWidth="2xl">
        <p>内容</p>
      </AppDialog>,
    );
    // 找到包住 title 的最近 [data-state=open] 元素 (DialogContent, 而非 Overlay)
    const title = screen.getByText("测试");
    let content: HTMLElement | null = title as HTMLElement;
    while (content && !content.matches("[data-state='open']")) {
      content = content.parentElement;
    }
    expect(content?.className).toContain("max-w-2xl");
  });

  // (2026-06-16) icon prop - antd Modal 风格, icon 渲染在 title 左侧
  it("icon 渲染在 title 之前", () => {
    render(
      <AppDialog
        open={true}
        onOpenChange={vi.fn()}
        title="记忆管理"
        icon={<span data-testid="title-icon">🧠</span>}
      >
        <p>内容</p>
      </AppDialog>,
    );
    const icon = screen.getByTestId("title-icon");
    // Icon 必须是 DialogTitle 内 title 文本前的兄弟节点, 跟 antd Modal 一致
    const dialogTitle = icon.parentElement;
    expect(dialogTitle).not.toBeNull();
    expect(dialogTitle?.textContent).toContain("记忆管理");
    // Icon 在 title 文本之前: icon 应该是 firstChild
    expect(dialogTitle?.firstChild).toBe(icon);
  });

  it("不传 icon → 行为不变 (向后兼容)", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="纯文本标题">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("纯文本标题")).toBeInTheDocument();
  });

  it("无 title/description 时不渲染 header", () => {
    const { container } = render(
      <AppDialog open={true} onOpenChange={vi.fn()}>
        <p>内容</p>
      </AppDialog>,
    );
    // DialogHeader 的 border-b 应该不存在
    expect(container.querySelector("[class*='border-b']")).toBeNull();
  });

  it("无 footer 时不渲染 footer", () => {
    const { container } = render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试">
        <p>内容</p>
      </AppDialog>,
    );
    // DialogFooter 有 border-t, 没有 footer 时不应有
    expect(container.querySelector("[class*='border-t']")).toBeNull();
  });

  it("dataTestid 透传", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试" dataTestid="my-dialog">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByTestId("my-dialog")).toBeInTheDocument();
  });

  it("error prop 渲染 destructive ErrorBanner", () => {
    render(
      <AppDialog
        open={true}
        onOpenChange={vi.fn()}
        title="编辑"
        error="操作失败"
        errorTestid="my-error"
      >
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByTestId("my-error")).toBeInTheDocument();
    expect(screen.getByText("操作失败")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("error=null 时不渲染 ErrorBanner", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="编辑" error={null}>
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.queryByText("操作失败")).not.toBeInTheDocument();
  });

  it("maxWidth 默认 lg", () => {
    render(
      <AppDialog open={true} onOpenChange={vi.fn()} title="测试">
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("测试")).toBeInTheDocument();
  });
});

describe("AppDialog 防误关 prop", () => {
  // (2026-07-06) closeOnOverlayClick / closeOnEscape 透传不报错
  it("closeOnOverlayClick=false + closeOnEscape=false 渲染不报错", () => {
    render(
      <AppDialog
        open={true}
        onOpenChange={vi.fn()}
        title="上传中"
        closeOnOverlayClick={false}
        closeOnEscape={false}
      >
        <p>内容</p>
      </AppDialog>,
    );
    expect(screen.getByText("上传中")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
  });

  it("closeOnEscape=false 时按 ESC 不会触发 onOpenChange(false)", () => {
    const onOpenChange = vi.fn();
    render(
      <AppDialog
        closeOnEscape={false}
        dataTestid="test-dialog"
        onOpenChange={onOpenChange}
        open={true}
        title="测试"
      >
        <p>内容</p>
      </AppDialog>,
    );
    // fire keydown Escape 到 dialog content 触发 Radix onEscapeKeyDown
    const dialogContent = screen.getByTestId("test-dialog");
    fireEvent.keyDown(dialogContent, { key: "Escape" });
    // closeOnEscape=false → onOpenChange 不该被调
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
