// TriggerBrowserDownload 单测 (2026-06-11)
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { triggerBrowserDownload } from "./download";
import { ONE } from "@/const";

describe("triggerBrowserDownload", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // eslint-disable-next-line max-statements -- 测试需完整验证 DOM 操作链
  it("创建 object URL, 触发 <a download> 点击, setTimeout 0 释放 URL", () => {
    const createSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-1");
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    // 监听 appendChild: 拿到 a 元素, 替它的 click (jsdom click 抛 NotImplementedError)
    const seenAnchor: { anchor: HTMLAnchorElement | null } = { anchor: null };
    const origAppend = document.body.appendChild.bind(document.body);
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
      if (node instanceof HTMLAnchorElement) {
        seenAnchor.anchor = node;
        node.click = vi.fn();
      }
      return origAppend(node);
    });
    const removeSpy = vi
      .spyOn(document.body, "removeChild")
      .mockImplementation((nodeReturn) => nodeReturn);

    const blob = new Blob(["x"], { type: "application/zip" });
    triggerBrowserDownload(blob, "task.zip");

    expect(createSpy).toHaveBeenCalledWith(blob);
    expect(seenAnchor.anchor).not.toBeNull();
    expect(seenAnchor.anchor!.download).toBe("task.zip");
    expect(seenAnchor.anchor!.href).toBe("blob:mock-1");
    // eslint-disable-next-line no-magic-numbers -- 测试断言: click 被调 1 次
    expect(seenAnchor.anchor!.click as unknown as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(
      ONE,
    );
    expect(removeSpy).toHaveBeenCalled();

    // Revoke 在 setTimeout 0 之后
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(revokeSpy).toHaveBeenCalledWith("blob:mock-1");
        resolve();
      }, 10); // eslint-disable-line no-magic-numbers -- 10ms 等 setTimeout(0) 多拍
    });
  });

  it("SSR 环境 (无 window) 静默 no-op", () => {
    const orig = globalThis.window;
    (globalThis as { window?: typeof globalThis.window }).window = undefined;
    try {
      expect(() => triggerBrowserDownload(new Blob(["x"]), "x.zip")).not.toThrow();
    } finally {
      (globalThis as { window?: typeof globalThis.window }).window = orig;
    }
  });
});
