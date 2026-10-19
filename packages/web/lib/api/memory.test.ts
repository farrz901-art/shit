// MemoryApi 单测: 调 apiFetch 路径 + 错误归一 (2026-06-16)
import { afterEach, describe, expect, it, vi } from "vitest";
import { HTTP_INTERNAL_SERVER_ERROR } from "@/const";

vi.mock("./config", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "./config";
import { add, deleteAll, deleteMemory, list, search, update } from "./memory";

const mockedApiFetch = vi.mocked(apiFetch);

describe("记忆 API 函数", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("search", () => {
    it("POST /api/memory/search with query + limit", async () => {
      mockedApiFetch.mockResolvedValue({ memories: [] });

      await search({ limit: 3, query: "test" });

      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/search",
        expect.objectContaining({
          // oxlint-disable-next-line no-magic-numbers -- 测试数据
          body: { limit: 3, query: "test" },
          method: "POST",
        }),
      );
    });

    it("search 默认 limit=5", async () => {
      mockedApiFetch.mockResolvedValue({ memories: [] });

      await search({ query: "test" });

      // oxlint-disable-next-line no-magic-numbers -- 测试数据
      expect(mockedApiFetch.mock.calls[0][1]?.body).toEqual({
        // oxlint-disable-next-line no-magic-numbers -- 测试数据
        limit: 5,
        query: "test",
      });
    });

    it("search 4xx/5xx → 抛 ApiError (走 apiFetch 错误归一)", async () => {
      const { ApiError } = await import("./errors");
      mockedApiFetch.mockRejectedValue(new ApiError(HTTP_INTERNAL_SERVER_ERROR, "mem0 不可达"));

      await expect(search({ query: "test" })).rejects.toThrow(/mem0 不可达/);
    });
  });

  describe("add", () => {
    it("POST /api/memory/add with messages + conversationId", async () => {
      mockedApiFetch.mockResolvedValue(undefined);

      await add({
        conversationId: "c1",
        messages: [{ content: "hi", role: "user" }],
      });

      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/add",
        expect.objectContaining({
          body: {
            conversation_id: "c1",
            messages: [{ content: "hi", role: "user" }],
          },
          method: "POST",
        }),
      );
    });

    it("add 204 → 返 undefined", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      const result = await add({
        messages: [{ content: "hi", role: "user" }],
      });
      expect(result).toBeUndefined();
    });

    it("add 无 conversationId → body 不含 conversation_id", async () => {
      mockedApiFetch.mockResolvedValue(undefined);

      await add({ messages: [{ content: "hi", role: "user" }] });

      // oxlint-disable-next-line no-magic-numbers -- 测试数据: mock 调用索引
      const body = mockedApiFetch.mock.calls[0][1]?.body as Record<string, unknown>;
      expect(body).not.toHaveProperty("conversation_id");
    });
  });

  // ---- Phase 2 (2026-06-16): 记忆管理 4 方法 ----

  describe("list", () => {
    it("GET /api/memory/list 返 {memories}", async () => {
      mockedApiFetch.mockResolvedValue({
        memories: [
          { id: "m1", text: "用户叫张三" },
          { id: "m2", text: "用户住北京" },
        ],
      });
      const result = await list();
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/list",
        expect.objectContaining({ method: "GET" }),
      );
      // oxlint-disable-next-line no-magic-numbers -- 测试数据: 记忆数量
      expect(result.memories).toHaveLength(2);
      // oxlint-disable-next-line no-magic-numbers -- 测试数据: 数组索引
      expect(result.memories[0].id).toBe("m1");
    });
  });

  describe("update", () => {
    it("PATCH /api/memory/{id} with text", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      await update("m1", "新内容");
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/m1",
        expect.objectContaining({
          body: { text: "新内容" },
          method: "PATCH",
        }),
      );
    });
  });

  describe("delete", () => {
    it("DELETE /api/memory/{id}", async () => {
      mockedApiFetch.mockResolvedValue(undefined);
      await deleteMemory("m1");
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/m1",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  describe("deleteAll", () => {
    it("DELETE /api/memory/all 返 {deleted_count}", async () => {
      mockedApiFetch.mockResolvedValue({ deleted_count: 0 });
      await deleteAll();
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "/api/memory/all",
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });
});
