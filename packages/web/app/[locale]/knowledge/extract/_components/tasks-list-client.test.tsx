// 列表容器测试 (2026-07-03)
// happy-dom 17 + TanStack Table 行渲染正常, T11 E2E 不再需要
/* eslint-disable id-length, max-statements -- 测试 fixture */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import TasksListClient from "./tasks-list-client";
import type { ExtractTaskRow } from "@/lib/api/knowledge";

const { mockFetchExtractTasks } = vi.hoisted(() => ({
  mockFetchExtractTasks: vi.fn(),
}));

vi.mock("@/lib/api/knowledge", () => ({
  fetchExtractDatasets: vi.fn().mockResolvedValue([]),
  fetchExtractors: vi.fn().mockResolvedValue([]),
  fetchExtractTasks: mockFetchExtractTasks,
  fetchSplitters: vi.fn().mockResolvedValue([]),
  startExtract: vi.fn(),
}));

const mockUseRouter = { back: vi.fn(), push: vi.fn(), refresh: vi.fn(), replace: vi.fn() };
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => mockUseRouter,
  usePathname: () => "/",
}));

const ROW_EXTRACT: ExtractTaskRow = {
  created_at: 1_720_000_000,
  dataset: "motor",
  extractor: "llm_pydantic",
  failed: 0,
  finished_at: 1_720_010_000,
  kind: "kg_extract",
  splitter: "heading",
  started_at: 1_720_000_100,
  state: "done",
  success: 10,
  task_id: "task-extract-1",
  uri: "s3://bucket/a.pdf",
};

const MOCK_RESPONSE = {
  items: [ROW_EXTRACT],
  limit: 20,
  offset: 0,
  total: 1,
  total_failed: 0,
  total_success: 10,
};

const renderWithProviders = (ui: React.ReactElement): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

beforeEach(() => {
  mockFetchExtractTasks.mockReset();
});

describe("TasksListClient", () => {
  it("render 抽取 tab 显示 kg_extract 行", async () => {
    mockFetchExtractTasks.mockResolvedValue(MOCK_RESPONSE);
    renderWithProviders(<TasksListClient />);
    expect(await screen.findByTestId("data-table-row")).toBeInTheDocument();
  });

  it("切到批量 tab 触发新 query", async () => {
    mockFetchExtractTasks.mockResolvedValue(MOCK_RESPONSE);
    renderWithProviders(<TasksListClient />);
    await screen.findByTestId("data-table-row");
    const batchTab = await screen.findByTestId("tasks-tab-kg_batch");
    fireEvent.click(batchTab);
    await waitFor(() => {
      expect(mockFetchExtractTasks).toHaveBeenCalledTimes(2);
    });
    expect(mockFetchExtractTasks).toHaveBeenNthCalledWith(2, {
      kind: "kg_batch",
      limit: 20,
      offset: 0,
    });
  });

  it("点新建提取按钮弹 ExtractCreateDialog", async () => {
    mockFetchExtractTasks.mockResolvedValue({ ...MOCK_RESPONSE, items: [] });
    renderWithProviders(<TasksListClient />);
    const btn = await screen.findByTestId("new-extract-btn");
    fireEvent.click(btn);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
  });
});
