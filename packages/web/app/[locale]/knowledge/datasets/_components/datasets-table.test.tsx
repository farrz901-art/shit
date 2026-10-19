// 客户端表格组件测试 (2026-06-12) — 接 RSC 灌的 Promise, 用 use() 解包
// (2026-06-14) use(promise) 模式: 用 act + flushMicrotasks 解决 Suspense
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it } from "vitest";
import type { DatasetRow } from "@/lib/api/knowledge";
import { DatasetsTable } from "./datasets-table";
import userEvent from "@testing-library/user-event";

const sample: DatasetRow[] = [
  { document_count: 5, id: "1", name: "DS1", word_count: 100 },
  { document_count: 3, id: "2", name: "DS2", word_count: 60 },
];

// Use(promise) 在 jsdom 中需要 flush microtasks 才能解包
const renderWithPromise = async (ui: React.ReactElement) => {
  let result: ReturnType<typeof render> = null as unknown as ReturnType<typeof render>;
  await act(async () => {
    result = render(ui);
    // 让 Promise.resolve() 的 microtask 执行完
    await Promise.resolve();
  });
  return result!;
};

describe("DatasetsTable", () => {
  it("渲染所有 dataset 名称", async () => {
    await renderWithPromise(<DatasetsTable datasetsPromise={Promise.resolve(sample)} />);
    expect(screen.getByText("DS1")).toBeInTheDocument();
    expect(screen.getByText("DS2")).toBeInTheDocument();
  });

  it("客户端分页: 25 条数据第 1 页 20 条", async () => {
    const arr: DatasetRow[] = Array.from({ length: 25 }, (_unused, idx) => ({
      id: String(idx),
      name: `DS${idx}`,
    }));
    await renderWithPromise(<DatasetsTable datasetsPromise={Promise.resolve(arr)} />);
    expect(screen.getByText("DS0")).toBeInTheDocument();
    expect(screen.queryByText("DS20")).not.toBeInTheDocument();
    expect(screen.getByText(/第 1 \/ 2 页/)).toBeInTheDocument();
  });

  it("点下一页, 显示第 2 页", async () => {
    const arr: DatasetRow[] = Array.from({ length: 25 }, (_unused, idx) => ({
      id: String(idx),
      name: `DS${idx}`,
    }));
    const user = userEvent.setup();
    await renderWithPromise(<DatasetsTable datasetsPromise={Promise.resolve(arr)} />);
    // DataTable 分页按钮文案走 i18n, zh locale 渲染 "下一页"
    await user.click(screen.getByText("下一页"));
    expect(screen.getByText("DS20")).toBeInTheDocument();
    expect(screen.queryByText("DS0")).not.toBeInTheDocument();
  });

  it("空数据时显示 '暂无数据集' (DataEmpty)", async () => {
    await renderWithPromise(<DatasetsTable datasetsPromise={Promise.resolve([])} />);
    expect(screen.getByText(/暂无数据集/)).toBeInTheDocument();
  });
});
