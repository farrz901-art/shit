import { ZERO } from "@/const";
// CitationPanel 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { CitationPanel } from "./citation-panel";

describe("CitationPanel", () => {
  it("渲染引用列表", () => {
    render(
      <CitationPanel
        citations={[
          {
            documentName: "doc1",
            content: "内容",
            score: 0.95,
            datasetName: "DS1",
            summary: "摘要",
          },
        ]}
      />,
    );
    expect(screen.getByText("doc1")).toBeInTheDocument();
    expect(screen.getByText("内容")).toBeInTheDocument();
    expect(screen.getByText(/0.95/)).toBeInTheDocument();
  });

  it("无 citations 渲染空容器", () => {
    const { container } = render(<CitationPanel citations={[]} />);
    expect(container.firstChild?.childNodes.length).toBe(ZERO);
  });

  it("score 为 null 不渲染分数", () => {
    render(<CitationPanel citations={[{ documentName: "doc2", content: "x" }]} />);
    expect(screen.getByText("doc2")).toBeInTheDocument();
    expect(screen.queryByText(/score/)).toBeNull();
  });
});
