import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { KnowledgeTabs } from "./knowledge-tabs";

let mockPathname = "/knowledge/documents";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

describe("KnowledgeTabs", () => {
  beforeEach(() => {
    mockPathname = "/knowledge/documents";
  });

  it("渲染 2 个 tab link", () => {
    render(<KnowledgeTabs />);
    expect(screen.getByTestId("tab-documents")).toBeInTheDocument();
    expect(screen.getByTestId("tab-graph")).toBeInTheDocument();
  });

  it("当前路径对应 tab 高亮", () => {
    render(<KnowledgeTabs />);
    const tab = screen.getByTestId("tab-documents");
    expect(tab.className).toContain("border-clay");
  });

  it("非活跃 tab 没有高亮 class", () => {
    render(<KnowledgeTabs />);
    const tab = screen.getByTestId("tab-graph");
    expect(tab.className).not.toContain("border-clay");
  });

  // 子路径联动高亮 (2026-06-10 redesign)
  it("子路径 /knowledge/qa 高亮 '向量库' tab", () => {
    mockPathname = "/knowledge/qa";
    render(<KnowledgeTabs />);
    expect(screen.getByTestId("tab-documents").className).toContain("border-clay");
    expect(screen.getByTestId("tab-graph").className).not.toContain("border-clay");
  });

  it("子路径 /knowledge/documents/import 高亮 '向量库' tab", () => {
    mockPathname = "/knowledge/documents/import";
    render(<KnowledgeTabs />);
    expect(screen.getByTestId("tab-documents").className).toContain("border-clay");
  });

  it("子路径 /knowledge/triples 高亮 '知识图谱' tab", () => {
    mockPathname = "/knowledge/triples";
    render(<KnowledgeTabs />);
    expect(screen.getByTestId("tab-graph").className).toContain("border-clay");
    expect(screen.getByTestId("tab-documents").className).not.toContain("border-clay");
  });

  it("子路径 /knowledge/batch 高亮 '知识图谱' tab", () => {
    mockPathname = "/knowledge/batch";
    render(<KnowledgeTabs />);
    expect(screen.getByTestId("tab-graph").className).toContain("border-clay");
  });
});
