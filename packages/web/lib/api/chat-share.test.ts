// ChatShareApi 单测 (2026-06-16) — 创建 / 拉取 / 撤销 share
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./config", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "./config";
import { createShare, getShare, listShares, revokeShare } from "./chat-share";

// oxlint-disable-next-line unicorn/filename-case -- 文件名保持原样
const mocked = vi.mocked(apiFetch);

describe("chatShareApi", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("create → POST /api/chat/shares with conv_id + title", async () => {
    mocked.mockResolvedValue({
      created_at: "2026-06-16T00:00:00Z",
      expires_at: null,
      share_id: "abc123456789",
      title: "t",
      url: "http://localhost:3000/zh/chat/s/abc123456789",
    });
    await createShare({ convId: "c1", messages: [], title: "我的对话" });
    expect(mocked).toHaveBeenCalledWith(
      "/api/chat/shares",
      expect.objectContaining({
        body: { conv_id: "c1", messages: [], title: "我的对话" },
        method: "POST",
      }),
    );
  });

  it("create 缺 title → body.title=null", async () => {
    mocked.mockResolvedValue({
      created_at: "",
      expires_at: null,
      share_id: "x",
      title: "",
      url: "u",
    });
    await createShare({ convId: "c1", messages: [] });
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: mock calls 数组索引
    const body = mocked.mock.calls[0][1]?.body as Record<string, unknown>;
    expect(body).toEqual({ conv_id: "c1", messages: [], title: null });
  });

  it("get → GET /api/chat/shares/{id} (公开, anon)", async () => {
    mocked.mockResolvedValue({
      created_at: "",
      messages: [],
      model: null,
      share_id: "abc",
      title: "t",
    });
    await getShare("abc");
    expect(mocked).toHaveBeenCalledWith(
      "/api/chat/shares/abc",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("revoke → DELETE /api/chat/shares/{id}", async () => {
    mocked.mockResolvedValue(undefined);
    await revokeShare("abc");
    expect(mocked).toHaveBeenCalledWith(
      "/api/chat/shares/abc",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("createShare 携带 messages 字段 POST 到 /api/chat/shares", async () => {
    mocked.mockResolvedValue({
      created_at: "2026-06-30T00:00:00Z",
      expires_at: null,
      share_id: "x",
      title: null,
      url: "http://x",
    });
    await createShare({
      convId: "c1",
      messages: [
        { role: "user", content: "hi" },
        { role: "assistant", content: "hello" },
      ],
    });
    expect(mocked).toHaveBeenCalledWith(
      "/api/chat/shares",
      expect.objectContaining({
        body: {
          conv_id: "c1",
          title: null,
          messages: [
            { role: "user", content: "hi" },
            { role: "assistant", content: "hello" },
          ],
        },
        method: "POST",
      }),
    );
  });

  it("listShares GET /api/chat/shares?conv_id=...", async () => {
    mocked.mockResolvedValue([]);
    await listShares("c1");
    expect(mocked).toHaveBeenCalledWith(
      "/api/chat/shares?conv_id=c1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
