import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { MarkdownStatic } from "./markdown-static";

describe("MarkdownStatic", () => {
  it("渲染纯文本不崩", () => {
    render(<MarkdownStatic>hello world</MarkdownStatic>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("渲染 GFM 表格", () => {
    render(
      <MarkdownStatic>
        {`| a | b |
| - | - |
| 1 | 2 |`}
      </MarkdownStatic>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("渲染图片但 onPreview 不被调用 (output 路径无预览)", () => {
    render(<MarkdownStatic>![alt](https://example.com/a.png)</MarkdownStatic>);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/a.png");
  });
});
