"use client";

// 验证: 1) 默认弹框关闭 2) FileDropzone 不渲染 3) 点触发按钮后弹框打开 4) failed 行渲染重试按钮
// (2026-07-06) 状态列改中文 + 失败原因 AppTooltip 包裹 Badge
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisClient } from "./admin-pre-analysis-client";

const mockListPreAnalysisTasks = vi.fn();
const mockRetryPreAnalysisTask = vi.fn();

vi.mock("@/lib/api/pre-analysis", () => ({
  listPreAnalysisTasks: (...args: unknown[]) => mockListPreAnalysisTasks(...args),
  retryPreAnalysisTask: (...args: unknown[]) => mockRetryPreAnalysisTask(...args),
}));

afterEach(() => {
  vi.restoreAllMocks();
  mockListPreAnalysisTasks.mockReset();
  mockRetryPreAnalysisTask.mockReset();
});

const renderWithProviders = (): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <AdminPreAnalysisClient />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

const makeTask = (
  id: string,
  state: "pending" | "running" | "completed" | "failed",
  error: string | null = null,
) => ({
  id,
  state,
  user_hash: "h",
  pdf_filename: "D81.pdf",
  pdf_uri: "s3://x",
  started_at: "2026-07-03T10:00:00Z",
  finished_at: "2026-07-03T10:01:00Z",
  current_stage: "extract" as const,
  task_config_json: {},
  summary: {
    total_chapters: 0,
    total_tables: 0,
    total_flagged_paragraphs: 0,
    elapsed_ms: 0,
    cross_page_candidates: 0,
  },
  error,
});

describe("AdminPreAnalysisClient (button + dialog)", () => {
  it("默认弹框关闭, FileDropzone 不渲染, 点触发按钮后弹框打开", () => {
    mockListPreAnalysisTasks.mockResolvedValue({ tasks: [] });

    renderWithProviders();
    // FileDropzone 不再渲染 (改成按钮)
    expect(screen.queryByText(/拖文件到这/)).not.toBeInTheDocument();
    // 触发按钮存在
    const trigger = screen.getByTestId("pre-analysis-upload-trigger");
    expect(trigger).toBeInTheDocument();
    // AppDialog open=false 时不渲染内部 children, FileDropzone 描述不应出现
    expect(screen.queryByText("点击上传按钮开始")).not.toBeInTheDocument();
    // 点按钮
    fireEvent.click(trigger);
    // 弹框打开后, FileDropzone 描述出现
    expect(screen.getByText("点击上传按钮开始")).toBeInTheDocument();
  });

  it("failed 行渲染重试按钮, 点击触发 API 调用", async () => {
    mockListPreAnalysisTasks.mockResolvedValue({
      tasks: [makeTask("pa-failed-1", "failed", "pymupdf open failed")],
    });
    mockRetryPreAnalysisTask.mockResolvedValue({
      task_id: "pa-failed-1",
      state: "pending",
    });

    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId("retry-pa-failed-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("retry-pa-failed-1"));
    await waitFor(() => {
      expect(mockRetryPreAnalysisTask).toHaveBeenCalledWith("pa-failed-1");
    });
  });
});

describe("AdminPreAnalysisClient 状态列中文 + 失败 tooltip", () => {
  it("failed 行 Badge 渲染中文'失败'且被 AppTooltip 包裹 (Radix TooltipContent 走 portal, jsdom 验 trigger)", async () => {
    mockListPreAnalysisTasks.mockResolvedValue({
      tasks: [
        makeTask("pa-failed-zh", "failed", "edge_tol,row_tol cannot be used with flavor='lattice'"),
      ],
    });
    renderWithProviders();
    await waitFor(() => {
      // Badge 文本是 "失败" (t("失败") 走 i18n)
      expect(screen.getByText("失败")).toBeInTheDocument();
    });
    // 重试按钮仍存在, 确认这是 failed 行
    expect(screen.getByTestId("retry-pa-failed-zh")).toBeInTheDocument();
  });

  it("completed 行渲染中文'已完成'且不出现重试按钮", async () => {
    mockListPreAnalysisTasks.mockResolvedValue({
      tasks: [makeTask("pa-ok-1", "completed", null)],
    });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("已完成")).toBeInTheDocument();
    });
    // completed 行不渲染重试按钮 (避免误重试)
    expect(screen.queryByTestId("retry-pa-ok-1")).not.toBeInTheDocument();
  });

  it("failed 但 error 为 null 时仍渲染'失败' Badge (无 tooltip 包裹但不崩)", async () => {
    mockListPreAnalysisTasks.mockResolvedValue({
      tasks: [makeTask("pa-failed-noerr", "failed", null)],
    });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText("失败")).toBeInTheDocument();
    });
    // 仍渲染重试按钮 (failed 状态独立)
    expect(screen.getByTestId("retry-pa-failed-noerr")).toBeInTheDocument();
  });
});
