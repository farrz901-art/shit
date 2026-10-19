// Composer 单测
// (2026-06-14) Composer 改受控 (value + onChange), test 用 Controlled wrapper
// 模拟 ChatShell 的 useState + setDraft 模式
// (2026-06-16) Composer 拆 + 接 ComposerAttachments: 用 NextIntlClientProvider 包
//   OnSend 签名扩为 (text, files), 文件列表从 attachments state 传过去
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Composer } from "./compose";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import zhMessages from "@/messages/zh.json";

const Controlled = (props: Omit<React.ComponentProps<typeof Composer>, "value" | "onChange">) => {
  const [value, setValue] = useState("");
  return (
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <Composer {...props} value={value} onChange={setValue} />
    </NextIntlClientProvider>
  );
};

describe("Composer", () => {
  it("空字符串按 Enter 不触发 onSend", () => {
    const onSend = vi.fn();
    render(<Controlled onSend={onSend} disabled={false} />);
    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("有内容按 Enter 触发 onSend", () => {
    const onSend = vi.fn();
    render(<Controlled onSend={onSend} disabled={false} />);
    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "1LE 电机?" } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("1LE 电机?", []);
    // 发送后清空由父组件 (ChatShell) 负责 — Composer 自身不清 (受控组件)
  });

  it("Shift+Enter 不发送, 加换行", () => {
    const onSend = vi.fn();
    render(<Controlled onSend={onSend} disabled={false} />);
    const textarea = screen.getByTestId("composer-textarea");
    fireEvent.change(textarea, { target: { value: "line1" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("streaming 时显示停止按钮 (替代发送)", () => {
    const onSend = vi.fn();
    const onStop = vi.fn();
    render(<Controlled onSend={onSend} onStop={onStop} disabled={false} streaming={true} />);
    expect(screen.queryByTestId("composer-send")).not.toBeInTheDocument();
    expect(screen.getByTestId("composer-stop")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("composer-stop"));
    expect(onStop).toHaveBeenCalled();
  });

  it("非 streaming 时显示发送按钮", () => {
    render(<Controlled onSend={vi.fn()} disabled={false} />);
    expect(screen.getByTestId("composer-send")).toBeInTheDocument();
    expect(screen.queryByTestId("composer-stop")).not.toBeInTheDocument();
  });

  // (2026-06-16) 拆 + 3 类入口集成测试: 渲染 Composer 时, ComposerAttachments 同时存在
  it("拆后集成: Composer 渲染时同时挂 ComposerAttachments (3 个入口)", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <Composer value="" onChange={() => {}} onSend={vi.fn()} disabled={false} />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId("composer-attachments")).toBeInTheDocument();
    expect(screen.getByTestId("composer-attach-image")).toBeInTheDocument();
    expect(screen.getByTestId("composer-attach-file")).toBeInTheDocument();
    expect(screen.getByTestId("composer-attach-voice")).toBeInTheDocument();
  });
});
