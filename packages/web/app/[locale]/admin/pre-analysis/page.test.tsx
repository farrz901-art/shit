// pre-analysis 列表页测试 (mode 1 mock + DataTable 渲染验证)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisClient } from "./_components/admin-pre-analysis-client";

afterEach(() => {
  vi.restoreAllMocks();
});

/**
 * 包装 QueryClientProvider 让 useQuery 不报 "No QueryClient set".
 * 每个测试用新 QueryClient, 避免状态泄漏.
 */
const renderWithProviders = (ui: React.ReactElement): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

const FAKE_ELAPSED_MS = 28_421;

const mockTasks = [
  {
    id: "pa-1",
    state: "completed" as const,
    user_hash: "hash",
    pdf_filename: "D81.pdf",
    pdf_uri: "local://x",
    started_at: "2026-07-02T10:00:00Z",
    finished_at: "2026-07-02T10:01:00Z",
    task_config_json: {},
    summary: {
      total_chapters: 6,
      total_tables: 12,
      total_flagged_paragraphs: 11,
      elapsed_ms: FAKE_ELAPSED_MS,
      cross_page_candidates: 1,
    },
    error: null,
  },
];

describe("admin pre-analysis list page", () => {
  it("renders DataTable with tasks", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({ tasks: mockTasks }, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisClient />);
    await waitFor(() => {
      expect(screen.getByText("D81.pdf")).toBeTruthy();
    });
  });

  it("renders upload button", () => {
    renderWithProviders(<AdminPreAnalysisClient />);
    expect(screen.getByText("上传 PDF")).toBeTruthy();
  });

  it("shows empty state when no tasks", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({ tasks: [] }, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisClient />);
    await waitFor(() => {
      expect(screen.getByText("无预分析任务")).toBeTruthy();
    });
  });
});
