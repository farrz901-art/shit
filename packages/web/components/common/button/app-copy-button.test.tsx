// CopyButton 组件单测 (2026-06-21) — clipboard + useTransition + sonner toast
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Vi.mock 会被提升到文件顶部执行, 因此 mock 变量必须用 vi.hoisted 定义
const { mockUseTransition, startTransition, mockClipboard } = vi.hoisted(() => {
  const fnStartTransition = vi.fn((cb: () => void) => cb());
  const fnUseTransition = vi.fn(() => [false, fnStartTransition]);
  return {
    mockUseTransition: fnUseTransition,
    startTransition: fnStartTransition,
    mockClipboard: { writeText: vi.fn() },
  };
});

vi.mock("react", async (importOriginal) => {
  // oxlint-disable-next-line typescript/consistent-type-imports -- vitest importOriginal 泛型必须用 typeof import() 形式
  const actual = await importOriginal<typeof import("react")>();
  return {
    ...actual,
    useTransition: mockUseTransition,
  };
});

vi.mock("sonner", () => ({
  toast: { error: vi.fn() },
}));

import { CopyButton } from "./app-copy-button";

const CALL_ONCE = 1;

describe("CopyButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 默认 pending=false, startTransition 同步执行
    mockUseTransition.mockReturnValue([false, startTransition]);
    // Happy-dom 用 getter 暴露 navigator.clipboard, Object.assign 抛错
    mockClipboard.writeText.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: mockClipboard.writeText },
      writable: true,
    });
  });

  it("渲染默认文案", () => {
    render(<CopyButton text="hello" />);
    expect(screen.getByText("复制")).toBeInTheDocument();
  });

  it("自定义 label", () => {
    render(<CopyButton text="hello" label="拷贝" />);
    expect(screen.getByText("拷贝")).toBeInTheDocument();
  });

  it("点击触发 clipboard writeText", async () => {
    mockClipboard.writeText.mockResolvedValue(undefined);
    render(<CopyButton text="要复制的文本" />);
    await act(async () => {
      screen.getByRole("button").click();
    });
    expect(mockClipboard.writeText).toHaveBeenCalledTimes(CALL_ONCE);
    expect(mockClipboard.writeText).toHaveBeenCalledWith("要复制的文本");
  });

  it("复制成功后显示 successLabel", async () => {
    mockClipboard.writeText.mockResolvedValue(undefined);
    render(<CopyButton text="hello" successLabel="已完成" />);
    await act(async () => {
      screen.getByRole("button").click();
    });
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });

  it("复制失败时 toast.error 被调用", async () => {
    const { toast } = await import("sonner");
    mockClipboard.writeText.mockRejectedValue(new Error("权限不足"));
    render(<CopyButton text="hello" />);
    await act(async () => {
      screen.getByRole("button").click();
    });
    expect(toast.error).toHaveBeenCalledWith("权限不足");
  });

  it("onCopied 回调被调用", async () => {
    const onCopied = vi.fn();
    mockClipboard.writeText.mockResolvedValue(undefined);
    render(<CopyButton text="hello" onCopied={onCopied} />);
    await act(async () => {
      screen.getByRole("button").click();
    });
    expect(onCopied).toHaveBeenCalledTimes(CALL_ONCE);
  });

  it("pending 时按钮 disabled", () => {
    mockUseTransition.mockReturnValue([true, startTransition]);
    render(<CopyButton text="hello" />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
