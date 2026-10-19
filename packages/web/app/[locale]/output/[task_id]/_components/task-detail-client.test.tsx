// /output/[task_id] 任务详情 client 子组件测试 (Task 25, 2026-06-12)
// 模式: mock ingestApi.fetchTask + cancelTask server action
// 真实测: RQ 接住数据 + 渲染产物列表 + 「取消任务」按钮调 server action
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

// Vi.hoisted 包装 mock 函数, 让 vi.mock factory (hoist 到顶部) 能引用
const { cancelTaskMock } = vi.hoisted(() => ({
  cancelTaskMock: vi.fn(async () => ({ data: { ok: true }, ok: true as const })),
}));

vi.mock("@/lib/api/ingest", () => ({
  fetchTask: vi.fn(async (_id: string) => ({
    failed: 0,
    finished_at: new Date().toISOString(),
    id: "t1",
    output_files: [
      { mime: "text/markdown", name: "report.md", size: 1024 },
      { mime: "image/svg+xml", name: "diagram.svg", size: 2048 },
    ],
    processed: 2,
    started_at: new Date().toISOString(),
    state: "completed",
    total_files: 2,
  })),
}));

vi.mock("@/app/[locale]/_actions/output", () => ({
  cancelTask: cancelTaskMock,
}));

import { TaskDetailClient } from "./task-detail-client";
import { ONE } from "@/const";

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
};

beforeEach(() => {
  cancelTaskMock.mockClear();
});

describe("TaskDetailClient", () => {
  it("completed 任务 → 渲染产物列表 (md + svg) + '查看' 链接 (只 md 有)", async () => {
    wrap(<TaskDetailClient taskId="t1" />);
    await waitFor(() => {
      expect(screen.getByText("report.md")).toBeInTheDocument();
      expect(screen.getByText("diagram.svg")).toBeInTheDocument();
      // 只 md 那行有 '查看' 链接, svg 没有
      expect(screen.getAllByRole("link", { name: /查看/ })).toHaveLength(ONE);
    });
  });

  it("completed 任务 → 渲染 '下载全部产物 zip' 按钮", async () => {
    wrap(<TaskDetailClient taskId="t1" />);
    await waitFor(() => {
      expect(screen.getByTestId("download-zip")).toBeInTheDocument();
    });
  });

  it("点 '取消任务' → 调 cancelTask server action (form action 模式)", async () => {
    wrap(<TaskDetailClient taskId="t1" />);
    await waitFor(() => {
      expect(screen.getByText("取消任务")).toBeInTheDocument();
    });
    // 「取消任务」按钮包在 form 里, form action 模式
    const btn = screen.getByText("取消任务");
    const form = btn.closest("form");
    expect(form).not.toBeNull();
    // 触发 form 提交 → 调 cancelTask("t1")
    fireEvent.submit(form!);
    await waitFor(() => {
      expect(cancelTaskMock).toHaveBeenCalledWith("t1");
    });
  });
});
