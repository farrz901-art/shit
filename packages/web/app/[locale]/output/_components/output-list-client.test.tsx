// /output 任务列表 client 子组件测试 (Task 24, 2026-06-12)
// 模式: mock ingestApi.fetchTasks + QueryClientProvider wrap
// 真实测: RQ 接住数据 + 渲染 input_files[0].name + 多文件 +N 后缀
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import { OutputListClient } from "./output-list-client";
import { ZERO } from "@/const";
import zhMessages from "@/messages/zh.json";

vi.mock("@/lib/api/ingest", () => ({
  fetchTasks: vi.fn(async () => [
    {
      failed: 0,
      id: "t1",
      input_files: [{ mime: "application/pdf", name: "doc-A.pdf", size: 1024 }],
      processed: 1,
      started_at: new Date().toISOString(),
      state: "completed",
      total_files: 1,
    },
    {
      failed: 0,
      id: "t2",
      input_files: [
        { mime: "application/pdf", name: "doc-B.pdf", size: 1024 },
        { mime: "application/pdf", name: "doc-C.pdf", size: 2048 },
      ],
      processed: 2,
      started_at: new Date().toISOString(),
      state: "running",
      total_files: 2,
    },
  ]),
}));

const wrap = (ui: React.ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
};

describe("OutputListClient", () => {
  it("渲染 input_files[0].name 作为首列 (单文件不显示 +N)", async () => {
    wrap(<OutputListClient />);
    await waitFor(() => {
      expect(screen.getByText("doc-A.pdf")).toBeInTheDocument();
    });
    // T1 单文件: 渲染纯文件名, 不带 +N 后缀
    // 用精确的 byText 默认 strict, "doc-A.pdf" 不会匹配 "doc-B.pdf +1"
    expect(screen.queryByText("doc-A.pdf +1")).not.toBeInTheDocument();
  });

  it("多文件渲染 +N 后缀 (input_files.length - 1)", async () => {
    wrap(<OutputListClient />);
    await waitFor(() => {
      expect(screen.getByText("doc-B.pdf +1")).toBeInTheDocument();
    });
  });

  it("running 状态渲染进度百分比", async () => {
    wrap(<OutputListClient />);
    await waitFor(() => {
      // Doc-B: processed=2, total=2 → 100%
      expect(screen.getByText("100%")).toBeInTheDocument();
    });
  });

  it("completed 任务渲染 '查看产物' / '下载全部' 按钮", async () => {
    wrap(<OutputListClient />);
    await waitFor(() => {
      expect(screen.getByText("查看产物")).toBeInTheDocument();
      expect(screen.getAllByTestId("download-zip").length).toBeGreaterThan(ZERO);
    });
  });
});
