// TriggerBrowserDownload 额外单测 (document 完整 mock)
import { afterEach, describe, expect, it, vi } from "vitest";
import { ZERO } from "@/const";
import { triggerBrowserDownload } from "./download";

describe("triggerBrowserDownload", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("完整流程: 创建 a → click → removeChild → revoke", async () => {
    const clickFn = vi.fn();
    const revokeFn = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn().mockReturnValue("blob:url"),
      revokeObjectURL: revokeFn,
    });
    vi.stubGlobal("document", {
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
      createElement: vi.fn().mockReturnValue({ click: clickFn, href: "", download: "", style: {} }),
    });
    triggerBrowserDownload(new Blob(["x"]), "test.txt");
    expect(clickFn).toHaveBeenCalled();
    // Settimeout 内 revoke
    await new Promise((resolve) => setTimeout(resolve, ZERO));
    expect(revokeFn).toHaveBeenCalledWith("blob:url");
  });
});
