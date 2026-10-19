import { ONE, TWO, ZERO } from "@/const";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JsonDiff } from "./json-diff";

const mockDiffLines = vi.hoisted(() => vi.fn());
const mockCodeToTokens = vi.hoisted(() => vi.fn());

vi.mock("diff", () => ({
  diffLines: mockDiffLines,
}));

vi.mock("shiki", () => ({
  codeToTokens: mockCodeToTokens,
}));

const TOKEN_A = { content: '{"alpha": 1}', color: "#fff" };
const TOKEN_B = { content: '{"alpha": 2}', color: "#fff" };

describe("JsonDiff", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("oldData=null 且 newData=null 应渲染占位符", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({ oldData: null, newData: null });
    render(container);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("相同 JSON 应渲染无差异提示", async () => {
    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({ oldData: { key: ONE }, newData: { key: ONE } });
    render(container);
    expect(screen.getByText("无差异")).toBeInTheDocument();
  });

  it("不同 JSON 应调 diffLines 并渲染 table 行", async () => {
    mockDiffLines.mockReturnValue([
      { value: '{"alpha": 1}\n', removed: true, count: ONE },
      { value: '{"alpha": 2}\n', added: true, count: ONE },
    ]);
    mockCodeToTokens.mockResolvedValue({
      tokens: [[TOKEN_A], [TOKEN_B]],
    });

    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({
      oldData: { key: ONE },
      newData: { key: TWO },
    });
    const { container: domContainer } = render(container);

    expect(domContainer.querySelector("table")).toBeInTheDocument();
    expect(mockDiffLines).toHaveBeenCalledTimes(ONE);
    expect(mockDiffLines).toHaveBeenCalledWith('{\n  "key": 1\n}', '{\n  "key": 2\n}');
  });

  it("theme 应透传给 codeToTokens", async () => {
    mockDiffLines.mockReturnValue([{ value: '{"alpha": 1}\n', removed: true, count: ONE }]);
    mockCodeToTokens.mockResolvedValue({
      tokens: [[TOKEN_A]],
    });

    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    await JsonDiff({
      oldData: { key: ONE },
      newData: { key: TWO },
      theme: "github-light",
    });
    expect(mockCodeToTokens).toHaveBeenCalledWith(expect.any(String), {
      lang: "json",
      theme: "github-light",
    });
  });

  it("序列化失败应渲染错误提示", async () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;

    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({ oldData: circular, newData: { key: ONE } });
    render(container);
    expect(screen.getByText("JSON 序列化失败")).toBeInTheDocument();
  });

  it("maxHeight 字符串应透传到容器", async () => {
    mockDiffLines.mockReturnValue([
      { value: '{"alpha": 1}\n', removed: true, count: ONE },
      { value: '{"alpha": 2}\n', added: true, count: ONE },
    ]);
    mockCodeToTokens.mockResolvedValue({
      tokens: [[TOKEN_A], [TOKEN_B]],
    });

    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({
      oldData: { key: ONE },
      newData: { key: TWO },
      maxHeight: "500px",
    });
    const { container: domContainer } = render(container);
    const outerDiv = domContainer.firstChild as HTMLElement;
    expect(outerDiv.style.maxHeight).toBe("500px");
  });

  it("不同 JSON 的 gutter 应包含 +/- 符号", async () => {
    mockDiffLines.mockReturnValue([
      { value: '{"old": 1}\n', removed: true, count: ONE },
      { value: '{"new": 2}\n', added: true, count: ONE },
    ]);
    mockCodeToTokens.mockResolvedValue({
      tokens: [[TOKEN_A]],
    });

    // eslint-disable-next-line new-cap -- RSC 组件在测试中作为 async 函数调用
    const container = await JsonDiff({
      oldData: { key: ONE },
      newData: { key: TWO },
    });
    const { container: domContainer } = render(container);

    const rows = domContainer.querySelectorAll("tr");
    expect(rows.length).toBe(TWO);
    expect(rows[ZERO].textContent).toContain("-");
    expect(rows[ONE].textContent).toContain("+");
  });
});
