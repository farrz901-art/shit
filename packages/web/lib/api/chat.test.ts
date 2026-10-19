// ChatApi 测试只覆盖**行为** (token 读取 + 流式返回 + 错误归一),
// 不重复测 apiProxy 内部 (URL/headers 注入)
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sendMessage, uploadFile } from "./chat";

const FIRST_ARG_IDX = 0;

describe("sendMessage / uploadFile", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sendMessage 返上游 stream", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(ctrl) {
        ctrl.enqueue(new TextEncoder().encode("chunk"));
        ctrl.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ body: stream, ok: true }));
    const body = await sendMessage({ inputs: {}, query: "hi", user: "u-1" });
    expect(body).toBe(stream);
  });

  it("sendMessage 非 2xx 抛 Error 含 status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => "boom",
      }),
    );
    await expect(sendMessage({ query: "hi", user: "u-1" })).rejects.toThrow(/500/);
  });

  it("sendMessage body 为空抛 Error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ body: null, ok: true }));
    await expect(sendMessage({ query: "hi", user: "u-1" })).rejects.toThrow(/无 body/);
  });

  it("uploadFile 调 apiFetch 上传文件", async () => {
    // Mock global fetch 让 apiFetch 内调用的 fetch 返回 200 JSON
    const mockResponse = { uploadFileId: "file_abc", uri: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify(mockResponse),
      }),
    );
    const file = new File(["content"], "test.txt", { type: "text/plain" });
    const result = await uploadFile(file);
    expect(result).toEqual(mockResponse);
    // 验证 fetch 被调用: 路径含 /api/chat/files, method POST
    const [firstArg, secondArg] = (fetch as ReturnType<typeof vi.fn>).mock.calls[FIRST_ARG_IDX];
    expect(firstArg).toContain("/api/chat/files");
    expect(secondArg?.method).toBe("POST");
    // Body 是 FormData
    expect(secondArg?.body).toBeInstanceOf(FormData);
  });
});
