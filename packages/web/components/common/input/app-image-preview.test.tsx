// ImagePreview 单元测试 (2026-06-16 Task 4) — shadcn Dialog 包原图,
// 消息内点击放大 + 发送前缩略图共用. 验证:
// 1) open=true 渲染 src 对应的 <img>
// 2) 点击 overlay (外部) 关闭
// 3) ESC 键关闭
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { ImagePreview } from "./app-image-preview";

describe("ImagePreview", () => {
  it("open=true 渲染 src 对应的 <img>", () => {
    render(
      <ImagePreview open={true} onOpenChange={vi.fn()} src="https://x.test/img.png" alt="测试图" />,
    );
    const img = screen.getByAltText("测试图");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "https://x.test/img.png");
  });

  it("点击 overlay (外部) → onOpenChange(false)", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<ImagePreview open={true} onOpenChange={onOpenChange} src="x.png" alt="" />);
    // Radix Dialog overlay 是 data-state="open" 且带 bg-black/80 class 的全屏遮罩
    const overlay = document.querySelector(String.raw`[data-state="open"].bg-black\/80`);
    expect(overlay).toBeInTheDocument();
    // 用 userEvent 触发完整 pointerdown/click 序列, 让 Radix 识别为外部点击
    await user.click(overlay as Element);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("ESC 键 → onOpenChange(false)", () => {
    const onOpenChange = vi.fn();
    render(<ImagePreview open={true} onOpenChange={onOpenChange} src="x.png" alt="" />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
