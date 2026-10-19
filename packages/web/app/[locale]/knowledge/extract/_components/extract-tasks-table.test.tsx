// kg_extract 表格测试 (2026-07-03) — happy-dom 17 + TanStack Table 行 click 测试
/* eslint-disable id-length, no-magic-numbers, max-statements -- 测试 fixture */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import ExtractTasksTable from "./extract-tasks-table";
import { startExtract, type ExtractTaskRow } from "@/lib/api/knowledge";

const mockRouter = { back: vi.fn(), push: vi.fn(), refresh: vi.fn(), replace: vi.fn() };
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/api/knowledge", () => ({
  startExtract: vi.fn(),
}));

const ROW_DONE: ExtractTaskRow = {
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
  task_id: "task-done-001",
  uri: "s3://bucket/key.pdf",
};

const ROW_RUNNING: ExtractTaskRow = {
  created_at: 1_720_000_000,
  dataset: "motor",
  extractor: "llm_pydantic",
  failed: 0,
  finished_at: null,
  kind: "kg_extract",
  splitter: "heading",
  started_at: 1_720_000_100,
  state: "running",
  success: 5,
  task_id: "task-running-001",
  uri: "s3://bucket/key2.pdf",
};

const ROW_INVALID: ExtractTaskRow = {
  created_at: 1_720_000_000,
  dataset: undefined,
  extractor: undefined,
  failed: 0,
  finished_at: null,
  kind: "kg_extract",
  splitter: undefined,
  started_at: null,
  state: "failed",
  success: 0,
  task_id: "task-invalid-001",
  uri: undefined,
};

describe("ExtractTasksTable", () => {
  it("点 done 行 → push preview 路径", () => {
    mockRouter.push.mockClear();
    render(
      <ExtractTasksTable
        error={null}
        loading={false}
        onPageChange={() => {}}
        onRetry={() => {}}
        page={0}
        pageSize={20}
        rows={[ROW_DONE]}
        total={1}
        totalFailed={0}
        totalSuccess={10}
      />,
    );
    const [row] = screen.getAllByTestId("data-table-row");
    fireEvent.click(row);
    expect(mockRouter.push).toHaveBeenCalledWith(
      "/knowledge/extract/task-done-001/preview?dataset=motor",
    );
  });

  it("点 running 行 → push 进度页", () => {
    mockRouter.push.mockClear();
    render(
      <ExtractTasksTable
        error={null}
        loading={false}
        onPageChange={() => {}}
        onRetry={() => {}}
        page={0}
        pageSize={20}
        rows={[ROW_RUNNING]}
        total={1}
        totalFailed={0}
        totalSuccess={5}
      />,
    );
    const [row] = screen.getAllByTestId("data-table-row");
    fireEvent.click(row);
    expect(mockRouter.push).toHaveBeenCalledWith(
      "/knowledge/extract/task-running-001?dataset=motor",
    );
  });

  it("点重跑按钮弹 AppConfirm, 确认后调 startExtract + 跳进度页", async () => {
    vi.mocked(startExtract).mockResolvedValue({ task_id: "task-rerun-001", state: "queued" });
    mockRouter.push.mockClear();
    render(
      <ExtractTasksTable
        error={null}
        loading={false}
        onPageChange={() => {}}
        onRetry={() => {}}
        page={0}
        pageSize={20}
        rows={[ROW_DONE]}
        total={1}
        totalFailed={0}
        totalSuccess={10}
      />,
    );
    const rerunBtn = screen.getByTestId("rerun-task-done-001");
    fireEvent.click(rerunBtn);
    const confirmBtn = await screen.findByRole("button", { name: /确定|确认|重跑/ });
    fireEvent.click(confirmBtn);
    await waitFor(() => {
      expect(startExtract).toHaveBeenCalledWith({
        dataset: "motor",
        extractor: "llm_pydantic",
        splitter: "heading",
        uri: "s3://bucket/key.pdf",
      });
    });
    await waitFor(() => {
      expect(mockRouter.push).toHaveBeenCalledWith(
        "/knowledge/extract/task-rerun-001?dataset=motor",
      );
    });
  });

  it("重跑按钮 → uri 缺失时不弹 confirm, 直接 toast.error", async () => {
    const toast = await import("sonner");
    const errorSpy = vi.spyOn(toast.toast, "error").mockImplementation(() => "");
    render(
      <ExtractTasksTable
        error={null}
        loading={false}
        onPageChange={() => {}}
        onRetry={() => {}}
        page={0}
        pageSize={20}
        rows={[ROW_INVALID]}
        total={1}
        totalFailed={0}
        totalSuccess={0}
      />,
    );
    const rerunBtn = screen.getByTestId("rerun-task-invalid-001");
    fireEvent.click(rerunBtn);
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith("重跑参数缺失");
    });
  });
});
