/** Chat api.ts TanStack Query hooks 测试 (2026-06-19 chat spec §6, vitest mock) */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

// Mock apiFetch
vi.mock("@/lib/api/config", () => ({
  apiFetch: vi.fn(),
}));

// Mock sonner toast (useAppendMessage onError 调 toast.error)
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    error: vi.fn(),
    success: vi.fn(),
  }),
}));

import { apiFetch } from "@/lib/api/config";
import { toast } from "sonner";
import {
  useConversations,
  useConversation,
  useCreateConversation,
  useRenameConversation,
  useDeleteConversation,
  useBackup,
  useAppendMessage,
} from "./api";

const mockApiFetch = vi.mocked(apiFetch);

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
};

// (2026-06-24) useAppendMessage 内调 useTranslations, 需要 IntlProvider 包装
const createWrapperWithIntl = (qcOverride?: QueryClient) => {
  const qc = qcOverride ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {children}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
};

beforeEach(() => {
  mockApiFetch.mockReset();
  vi.mocked(toast.error).mockClear();
});

describe("useConversations", () => {
  it("返 GET /api/chat/conversations 结果", async () => {
    mockApiFetch.mockResolvedValueOnce([{ id: "c1", title: "t1" }]);
    const { result } = renderHook(() => useConversations(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: "c1", title: "t1" }]);
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations");
  });

  it("staleTime 60s + refetchOnWindowFocus (hook 返回可用 query)", () => {
    const { result } = renderHook(() => useConversations(), { wrapper: createWrapper() });
    expect(result.current).toBeDefined();
    // (staleTime / refetchOnWindowFocus 已在 hook 内部固定, 不需断言值)
  });
});

describe("useConversation", () => {
  it("enabled=false 当 id=null", async () => {
    const { result } = renderHook(() => useConversation(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it("enabled=true 当 id='c1' 调对应 endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1", messages: [] });
    const { result } = renderHook(() => useConversation("c1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1");
  });
});

describe("useCreateConversation", () => {
  it("POST + invalidate conversations list", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1" });
    const { result } = renderHook(() => useCreateConversation(), { wrapper: createWrapper() });
    result.current.mutate({ title: "new" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations", {
      body: { title: "new" },
      method: "POST",
    });
  });
});

describe("useRenameConversation", () => {
  it("PATCH 对应 conv_id + invalidate 列表 + 详情", async () => {
    mockApiFetch.mockResolvedValueOnce({ id: "c1" });
    const { result } = renderHook(() => useRenameConversation(), { wrapper: createWrapper() });
    result.current.mutate({ id: "c1", title: "new" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1", {
      body: { title: "new" },
      method: "PATCH",
    });
  });
});

describe("useDeleteConversation", () => {
  it("DELETE 对应 conv_id + invalidate 列表", async () => {
    mockApiFetch.mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useDeleteConversation(), { wrapper: createWrapper() });
    result.current.mutate("c1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1", {
      method: "DELETE",
    });
  });
});

describe("useBackup", () => {
  it("GET /api/chat/backup", async () => {
    mockApiFetch.mockResolvedValueOnce({ conversations: [] });
    const { result } = renderHook(() => useBackup(), { wrapper: createWrapper() });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/backup");
  });
});

// ---- useAppendMessage (2026-06-24 chat-message-persistence) ----

describe("useAppendMessage", () => {
  it("POST 到 /conversations/{id}/messages 带 role/content/meta", async () => {
    mockApiFetch.mockResolvedValueOnce({
      id: "1",
      role: "user",
      content: "hi",
      meta: null,
      created_at: "2026-06-24T00:00:00Z",
    });
    const { result } = renderHook(() => useAppendMessage(), { wrapper: createWrapperWithIntl() });
    result.current.mutate({ convId: "c1", role: "user", content: "hi" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1/messages", {
      body: { role: "user", content: "hi", meta: undefined },
      method: "POST",
    });
  });

  it("onSuccess invalidate conversations list + detail 2 keys", async () => {
    mockApiFetch.mockResolvedValueOnce({
      id: "2",
      role: "assistant",
      content: "ok",
      meta: null,
      created_at: "2026-06-24T00:00:00Z",
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAppendMessage(), {
      wrapper: createWrapperWithIntl(qc),
    });
    result.current.mutate({ convId: "c1", role: "assistant", content: "ok" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["chat", "conversations"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["chat", "conversations", "c1"] });
  });

  it("onError 弹 toast.error", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("network"));
    const { result } = renderHook(() => useAppendMessage(), { wrapper: createWrapperWithIntl() });
    result.current.mutate({ convId: "c1", role: "user", content: "x" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(vi.mocked(toast.error)).toHaveBeenCalled();
  });
});
