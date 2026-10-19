import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { MarkdownStream } from "./markdown-stream";

// 避免 streamdown 内 lucide-react 图标在 jsdom 下渲染报错
vi.mock("lucide-react", async () => ({}));

describe("MarkdownStream", () => {
  it("渲染纯文本不崩", () => {
    render(<MarkdownStream>hello world</MarkdownStream>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("渲染 GFM 表格", () => {
    render(
      <MarkdownStream>
        {`| a | b |
| - | - |
| 1 | 2 |`}
      </MarkdownStream>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("渲染代码块带 Shiki 高亮 class", () => {
    const md = "```ts\nconst x = 1;\n```";
    render(<MarkdownStream>{md}</MarkdownStream>);
    // shiki 通常加 'shiki' class 或 data 属性
    const pre = document.querySelector("pre");
    expect(pre).toBeInTheDocument();
    expect(pre?.className ?? "").toMatch(/shiki|streamdown/);
  });

  it("不完全代码块 (```ts\\nconst) 自动闭合不抛错", () => {
    expect(() => {
      render(<MarkdownStream>{"```ts\nconst x"}</MarkdownStream>);
    }).not.toThrow();
  });

  it("img 点击触发 onPreview 回调", () => {
    const onPreview = vi.fn();
    render(
      <MarkdownStream onPreview={onPreview}>{"![alt](https://example.com/a.png)"}</MarkdownStream>,
    );
    const img = screen.getByRole("img");
    fireEvent.click(img);
    expect(onPreview).toHaveBeenCalledWith("https://example.com/a.png");
  });

  it("无 onPreview 时渲染不崩, src 属性正确", () => {
    render(<MarkdownStream>![alt](https://example.com/a.png)</MarkdownStream>);
    const img = screen.getByRole("img");
    // MarkdownImg 内部 safeSrc 守卫, onClick 在 safeSrc 缺失时不会调 onPreview
    // 这里只验渲染不崩 + src 属性正确
    expect(img).toHaveAttribute("src", "https://example.com/a.png");
  });
});
