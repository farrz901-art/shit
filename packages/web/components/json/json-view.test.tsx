import { HUNDRED, ONE } from "@/const";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JsonView } from "./json-view";

const mockCodeToHtml = vi.hoisted(() => {
  const MOCK_HTML = '<pre><code><span style="color:#fff">{"key":1}</span></code></pre>';
  return vi.fn().mockResolvedValue(MOCK_HTML);
});

vi.mock("shiki", () => ({
  codeToHtml: mockCodeToHtml,
}));

describe("JsonView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("data=null 应渲染占位符 (--)", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: null });
    render(container);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("data=undefined 应渲染占位符 (--)", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: undefined });
    render(container);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("空对象应调 codeToHtml + 渲染 shiki HTML", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: {} });
    const { container: domContainer } = render(container);
    expect(domContainer.querySelector("pre")).toBeInTheDocument();
    expect(domContainer.querySelector("code")).toBeInTheDocument();
    expect(mockCodeToHtml).toHaveBeenCalledTimes(ONE);
    expect(mockCodeToHtml).toHaveBeenCalledWith("{}", {
      lang: "json",
      theme: "github-dark",
    });
  });

  it("theme 应透传给 codeToHtml", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    await JsonView({ data: { key: ONE }, theme: "github-light" });
    expect(mockCodeToHtml).toHaveBeenCalledWith(expect.any(String), {
      lang: "json",
      theme: "github-light",
    });
  });

  it("maxHeight 数字应转为 px 样式", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: {}, maxHeight: HUNDRED });
    const { container: domContainer } = render(container);
    const outerDiv = domContainer.firstChild as HTMLElement;
    expect(outerDiv.style.maxHeight).toBe("100px");
  });

  it("maxHeight 字符串应原样传递", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: {}, maxHeight: "600px" });
    const { container: domContainer } = render(container);
    const outerDiv = domContainer.firstChild as HTMLElement;
    expect(outerDiv.style.maxHeight).toBe("600px");
  });

  it("className 应透传到容器", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonView({ data: {}, className: "custom-class" });
    const { container: domContainer } = render(container);
    const outerDiv = domContainer.firstChild as HTMLElement;
    expect(outerDiv.className).toContain("custom-class");
  });
});
