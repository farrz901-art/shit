"use client";

// pre-analysis stages 弹框 3 个独立测试 (mode 1 mock)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { PreAnalysisStagesDialog } from "./pre-analysis-stages-dialog";

const listPreAnalysisStagesMock = vi.fn();

vi.mock("@/lib/api/pre-analysis", () => ({
  listPreAnalysisStages: (...args: unknown[]) => listPreAnalysisStagesMock(...args),
}));

afterEach(() => {
  vi.restoreAllMocks();
  listPreAnalysisStagesMock.mockReset();
});

const renderDialog = (
  props: Partial<React.ComponentProps<typeof PreAnalysisStagesDialog>> = {},
): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <PreAnalysisStagesDialog taskId="pa-test-1" onOpenChange={vi.fn()} open={true} {...props} />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

const FAKE_STAGES = [
  {
    stage: "prepare_input" as const,
    status: "completed" as const,
    progress: 100,
    started_at: "2026-07-03T10:00:00Z",
    finished_at: "2026-07-03T10:00:01Z",
    message: "config ok",
  },
  {
    stage: "extract_chapters" as const,
    status: "failed" as const,
    progress: 0,
    started_at: "2026-07-03T10:00:01Z",
    finished_at: "2026-07-03T10:00:02Z",
    message: "pymupdf open failed",
  },
];

describe("PreAnalysisStagesDialog", () => {
  it("open=true 渲染 title + 5 行 stage", async () => {
    listPreAnalysisStagesMock.mockResolvedValue({ stages: [] });
    renderDialog();
    expect(screen.getByText("总体阶段: pa-test-1")).toBeInTheDocument();
    await waitFor(() => {
      // 5 行 stage 默认渲染 (waitFor 等 loading 结束)
      expect(screen.getByText("加载配置")).toBeInTheDocument();
      expect(screen.getByText("章节提取")).toBeInTheDocument();
      expect(screen.getByText("表格提取")).toBeInTheDocument();
      expect(screen.getByText("段落标记")).toBeInTheDocument();
      expect(screen.getByText("写产物")).toBeInTheDocument();
    });
  });

  it("拉到的 stages 渲染中文 status 跟 message (不渲染百分比进度列)", async () => {
    listPreAnalysisStagesMock.mockResolvedValue({ stages: FAKE_STAGES });
    renderDialog();
    await waitFor(() => {
      // status 文案走 i18n, "已完成" + "失败"
      expect(screen.getByText("已完成")).toBeInTheDocument();
      expect(screen.getByText("失败")).toBeInTheDocument();
      // message 文案不变
      expect(screen.getByText("config ok")).toBeInTheDocument();
      expect(screen.getByText("pymupdf open failed")).toBeInTheDocument();
    });
  });

  it("关闭按钮调 onOpenChange(false)", () => {
    listPreAnalysisStagesMock.mockResolvedValue({ stages: [] });
    const onOpenChange = vi.fn();
    renderDialog({ onOpenChange });
    screen.getByRole("button", { name: "关闭" }).click();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("(2026-07-09) 后端没返的 stage 显示 '未开始' (不显示 '已跳过')", async () => {
    // (2026-07-09) 防 fallback 误把未运行 stage 标 '已跳过', 用户误解成"该 stage 被跳过/跳过逻辑"
    // 现在未拉的 stage 默认 'pending' (未开始).
    listPreAnalysisStagesMock.mockResolvedValue({ stages: [] });
    renderDialog();
    await waitFor(() => {
      // 5 行都未拉到, 应该全部 '未开始' (没'已跳过')
      const pendingCells = screen.getAllByText("未开始");
      expect(pendingCells.length).toBe(5);
      expect(screen.queryByText("已跳过")).not.toBeInTheDocument();
    });
  });

  it("extract_tables 行消息列拼已提取 N 个表格 (ICU {N} 占位符 + 拼到 message 单元格)", async () => {
    // (2026-07-08) 表格数从独立列改为拼到 message 单元格, testid 保留以便 e2e 定位
    listPreAnalysisStagesMock.mockResolvedValue({
      stages: [
        {
          stage: "extract_tables" as const,
          status: "completed" as const,
          progress: 100,
          started_at: "2026-07-08T10:00:00Z",
          finished_at: "2026-07-08T10:00:05Z",
          message: "3 表 / 0 跨页候选",
        },
      ],
    });
    renderDialog();
    await waitFor(() => {
      // 拼到消息列: "已提取 3 个表格 · 3 表 / 0 跨页候选"
      const cell = screen.getByTestId("table-count-extract_tables");
      expect(cell).toHaveTextContent("已提取 3 个表格");
      expect(cell).toHaveTextContent("3 表 / 0 跨页候选");
    });
  });
});
