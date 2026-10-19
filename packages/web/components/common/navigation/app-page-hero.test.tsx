import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { PageHero } from "./app-page-hero";

describe("PageHero", () => {
  it("渲染 eyebrow + display title", () => {
    render(<PageHero eyebrow="Knowledge" title="知识库" />);
    expect(screen.getByText("Knowledge")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库" })).toBeInTheDocument();
  });

  it("支持右侧 meta slot (refresh 间隔等)", () => {
    render(<PageHero eyebrow="Knowledge" title="知识库" meta={<span>30s 刷新</span>} />);
    expect(screen.getByText("30s 刷新")).toBeInTheDocument();
  });

  it("渲染 description 副标题", () => {
    render(
      <PageHero
        eyebrow="Decoder"
        title="产品订货号·解码"
        description="把完整订货号丢进来按配置拆成字段"
      />,
    );
    expect(screen.getByText("把完整订货号丢进来按配置拆成字段")).toBeInTheDocument();
  });

  it("允许 title 为 ReactNode (含 inline 元素)", () => {
    render(
      <PageHero
        eyebrow="Decoder"
        title={
          <>
            产品订货号<span>·</span>解码
          </>
        }
      />,
    );
    expect(screen.getByRole("heading", { name: /产品订货号.*解码/ })).toBeInTheDocument();
  });
});
