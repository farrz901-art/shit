// kg_batch 表格测试 (2026-07-03) — happy-dom 17 + TanStack Table 行 click 不响应测试
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import BatchTasksTable from "./batch-tasks-table";
import type { ExtractTaskRow } from "@/lib/api/knowledge";

const mockRouter = { back: vi.fn(), push: vi.fn(), refresh: vi.fn(), replace: vi.fn() };
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => mockRouter,
}));

const ROW_BATCH: ExtractTaskRow = {
  created_at: 1_720_000_000,
  dataset: "motor",
  extractor: undefined,
  failed: 0,
  finished_at: null,
  kind: "kg_extract",
  splitter: undefined,
  started_at: null,
  state: "done",
  success: 10,
  task_id: "task-batch-1",
  uri: "s3://bucket/batch.pdf",
};

describe("BatchTasksTable", () => {
  it("render batch 行, 行 click 不触发 router.push (无详情页)", () => {
    mockRouter.push.mockClear();
    render(
      <BatchTasksTable
        error={null}
        loading={false}
        onPageChange={() => {}}
        onRetry={() => {}}
        page={0}
        pageSize={20}
        rows={[ROW_BATCH]}
        total={1}
        totalFailed={0}
        totalSuccess={10}
      />,
    );
    const [row] = screen.getAllByTestId("data-table-row");
    fireEvent.click(row);
    expect(mockRouter.push).not.toHaveBeenCalled();
  });
});
