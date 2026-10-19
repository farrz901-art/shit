// Query-client.ts 单元测试 (2026-06-14):
// 验证 QueryCache.onError 全局兜底: useQuery / fetchQuery 失败时调用 toast.error
//
// 不挂 React 树、不用 <Toaster>: 走 qc.fetchQuery 触发, 直接断言 toast.error 被调.
// 测的是 query-client.ts:42 那一行 toast.error(errorMessage(error)) 的行为,
// 跟 RQ 5 QueryCache.config.onError 实现耦合 (query-core/src/query.ts:610).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HTTP_NOT_FOUND } from "@/const";

// Mock: 必须在被 mock 模块 import 之前; vi.hoisted 让工厂能引用外层 vi.fn
const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({
  toast: { error: toastError },
}));

import { createBrowserQueryClient } from "./query-client";
import { ApiError, NetworkError } from "./errors";

describe("createBrowserQueryClient 全局错误处理", () => {
  // 注意: beforeEach 必须在 afterEach 之前定义 (sort-imports 规则只排序 import, 不影响 describe)
  beforeEach(() => {
    toastError.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("fetchQuery 抛 ApiError → toast.error 拿到后端 detail 消息", async () => {
    const qc = createBrowserQueryClient();
    toastError.mockClear();

    await expect(
      qc.fetchQuery({
        queryFn: async () => {
          throw new ApiError(HTTP_NOT_FOUND, "resource not found");
        },
        queryKey: ["test", "api-error"],
      }),
    ).rejects.toBeInstanceOf(ApiError);

    // QueryCache.config.onError 是 batch 内同步调, 等一个 microtask 让 notify 派发完
    await Promise.resolve();
    expect(toastError).toHaveBeenCalledWith("resource not found");
  });

  it("fetchQuery 抛 NetworkError → toast.error 拿到网络层消息", async () => {
    const qc = createBrowserQueryClient();
    toastError.mockClear();

    await expect(
      qc.fetchQuery({
        queryFn: async () => {
          throw new NetworkError("fetch failed");
        },
        queryKey: ["test", "network-error"],
      }),
    ).rejects.toBeInstanceOf(NetworkError);

    await Promise.resolve();
    expect(toastError).toHaveBeenCalledWith("fetch failed");
  });

  it("fetchQuery 抛普通 Error → toast.error 拿到 .message", async () => {
    const qc = createBrowserQueryClient();
    toastError.mockClear();

    await expect(
      qc.fetchQuery({
        queryFn: async () => {
          throw new Error("boom");
        },
        queryKey: ["test", "plain-error"],
      }),
    ).rejects.toThrow("boom");

    await Promise.resolve();
    expect(toastError).toHaveBeenCalledWith("boom");
  });

  it("fetchQuery 成功 → toast.error 不被调", async () => {
    const qc = createBrowserQueryClient();
    toastError.mockClear();

    const data = await qc.fetchQuery({
      queryFn: async () => ({ ok: true }),
      queryKey: ["test", "ok"],
    });

    expect(data).toEqual({ ok: true });
    expect(toastError).not.toHaveBeenCalled();
  });
});
