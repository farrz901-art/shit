// 客户端入口子组件测试 (2026-06-12) — 接 RSC 灌的 stats, 测 datasetId 交互.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

// 可变 store state, 供单测按需切 datasetId
const appStoreState: { datasetId: string } = { datasetId: "ds1" };

vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (state: { datasetId: string }) => string) => sel(appStoreState),
}));

import { DocumentsEntry } from "./documents-entry";

const renderInI18n = (ui: React.ReactNode) => render(<IntlWrapper locale="zh">{ui}</IntlWrapper>);

describe("DocumentsEntry (client)", () => {
  beforeEach(() => {
    appStoreState.datasetId = "ds1";
  });

  it("渲染 PageHero title=向量库", () => {
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    expect(screen.getByRole("heading", { name: /向量库/ })).toBeInTheDocument();
  });

  it("不渲染上传区 (已搬到 /documents/import)", () => {
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    expect(screen.queryByTestId("file-dropzone")).not.toBeInTheDocument();
  });

  it("展示录入入口卡: 录 QA 对 + 批量导入 (仿老 Dify tab 2 张卡)", () => {
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    // EntryCard 渲染为 article + Link, 用 title 找
    expect(screen.getByRole("heading", { name: "录 QA 对" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "批量导入" })).toBeInTheDocument();
    // 入口 href 正确 (LocalizedLink 自动加 /zh 前缀)
    expect(screen.getByRole("link", { name: /录 QA 对/ }).getAttribute("href")).toBe(
      "/zh/knowledge/qa",
    );
    expect(screen.getByRole("link", { name: /批量导入/ }).getAttribute("href")).toBe(
      "/zh/knowledge/documents/import",
    );
  });

  it("数据集数卡可点, 跳 /knowledge/datasets", () => {
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    const link = screen.getByRole("link", { name: /数据集/ });
    expect(link).toHaveAttribute("href", "/zh/knowledge/datasets");
  });

  it("文档数卡在 datasetId 存在时可点, 跳 /knowledge/dataset-documents/:id", () => {
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    const link = screen.getByRole("link", { name: /文档数/ });
    expect(link).toHaveAttribute("href", "/zh/knowledge/dataset-documents/ds1");
  });

  it("datasetId 缺失时文档数卡不可点, 显示提示", () => {
    // 切到空 datasetId 模拟未选状态
    appStoreState.datasetId = "";
    renderInI18n(<DocumentsEntry stats={{ datasets: 7, documents: 42 }} />);
    expect(screen.getByText("请先选 dataset →")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /文档数/ })).not.toBeInTheDocument();
  });
});
