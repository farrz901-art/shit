// UseLookup hook 单元测试 (2026-06-19 lookup module §5.5)
// Mock fetchLookup / fetchAllLookups 直接覆盖 hook 行为, 不走 apiFetch (transport 测在 lib/api/lookups.test.ts).
// 用 vitest + @testing-library/react renderHook + TanStack Query QueryClient.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAllLookups, fetchLookup } from "@/lib/api/lookups";
import { renderHook, waitFor } from "@testing-library/react";
import { useAllLookups, useLookup } from "./use-lookup";
import type * as lookupsNS from "@/lib/api/lookups";

// Mock lookups API, hook 只用 fetchLookup / fetchAllLookups 两个函数
vi.mock("@/lib/api/lookups", async () => {
  type LookupsModule = typeof lookupsNS;
  const actual = await vi.importActual<LookupsModule>("@/lib/api/lookups");
  return {
    ...actual,
    fetchAllLookups: vi.fn(),
    fetchLookup: vi.fn(),
  };
});

const SAMPLE_ITEMS_LENGTH = 3;
const APPROVAL_DICT_VERSION = 1;
const REJECT_DICT_VERSION = 1;
const FETCH_ALL_LOOKUPS_CALL_COUNT = 1;

const mockFetchLookup = vi.mocked(fetchLookup);
const mockFetchAllLookups = vi.mocked(fetchAllLookups);

// 工厂 fixture: 一份典型字典 (approval_review_status).
const sampleDict = {
  code: "approval_review_status",
  items: [
    { is_active: true, key: "pending", label_en: "Pending", label_zh: "待审核", sort: 1 },
    { is_active: true, key: "approved", label_en: "Approved", label_zh: "已批准", sort: 2 },
    { is_active: true, key: "rejected", label_en: "Rejected", label_zh: "已拒绝", sort: 3 },
  ],
  label_en: "Review Status",
  label_zh: "审核状态",
  version: APPROVAL_DICT_VERSION,
};

// 每个测试用独立 QueryClient, 避免 cache 串扰
const createWrapper = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
};

beforeEach(() => {
  mockFetchLookup.mockReset();
  mockFetchAllLookups.mockReset();
});

describe("useLookup", () => {
  it("returns items and byKey", async () => {
    mockFetchLookup.mockResolvedValueOnce(sampleDict);
    const { result } = renderHook(() => useLookup("approval_review_status"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toHaveLength(SAMPLE_ITEMS_LENGTH);
    expect(result.current.byKey.pending).toMatchObject({ key: "pending", label_zh: "待审核" });
    expect(result.current.byKey.approved?.label_en).toBe("Approved");
  });

  it("labelFor returns label_zh by default", async () => {
    mockFetchLookup.mockResolvedValueOnce(sampleDict);
    const { result } = renderHook(() => useLookup("approval_review_status"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.labelFor("pending")).toBe("待审核");
    expect(result.current.labelFor("approved")).toBe("已批准");
  });

  it("labelFor with locale='en' returns label_en", async () => {
    mockFetchLookup.mockResolvedValueOnce(sampleDict);
    const { result } = renderHook(() => useLookup("approval_review_status"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.labelFor("pending", "en")).toBe("Pending");
    expect(result.current.labelFor("rejected", "en")).toBe("Rejected");
  });

  it("labelFor falls back to key when key not found", async () => {
    mockFetchLookup.mockResolvedValueOnce(sampleDict);
    const { result } = renderHook(() => useLookup("approval_review_status"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // 字典没这个 key, 返原 key 作兜底 (业务下拉框不会爆, 显示 raw key 提示)
    expect(result.current.labelFor("nonexistent")).toBe("nonexistent");
    expect(result.current.labelFor("nonexistent", "en")).toBe("nonexistent");
  });

  it("passes lang and onlyActive to fetchLookup", async () => {
    mockFetchLookup.mockResolvedValueOnce(sampleDict);
    const { result } = renderHook(
      () => useLookup("approval_review_status", { lang: "en", onlyActive: false }),
      { wrapper: createWrapper() },
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockFetchLookup).toHaveBeenCalledWith("approval_review_status", {
      lang: "en",
      onlyActive: false,
    });
  });

  it("handles empty data (no items)", async () => {
    const emptyDict = { ...sampleDict, items: [] };
    mockFetchLookup.mockResolvedValueOnce(emptyDict);
    const { result } = renderHook(() => useLookup("empty_dict"), {
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items).toEqual([]);
    expect(result.current.byKey).toEqual({});
    // 即使字典为空, labelFor 也要安全兜底, 不抛
    expect(result.current.labelFor("anything")).toBe("anything");
  });
});

describe("useAllLookups", () => {
  it("returns summaries from fetchAllLookups", async () => {
    const summaries = [
      {
        code: "approval_review_status",
        is_active: true,
        label_en: "Review Status",
        label_zh: "审核状态",
        version: APPROVAL_DICT_VERSION,
      },
      {
        code: "reject_reason",
        is_active: true,
        label_en: "Reject Reason",
        label_zh: "拒绝原因",
        version: REJECT_DICT_VERSION,
      },
    ];
    mockFetchAllLookups.mockResolvedValueOnce(summaries);
    const { result } = renderHook(() => useAllLookups(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(summaries);
    expect(mockFetchAllLookups).toHaveBeenCalledTimes(FETCH_ALL_LOOKUPS_CALL_COUNT);
  });
});
