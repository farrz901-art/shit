// AppDataProvider 测试: RSC 灌 datasets/schemas, 客户端读 Context
// 不进 zustand: 列表数据跨请求新鲜, 只 Context 透传
import { AppDataProvider, useAppData } from "./app-data";
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

const Probe = () => {
  const data = useAppData();
  return (
    <div>
      <span data-testid="ds-count">{data.datasets.length}</span>
      <span data-testid="schema-count">{data.schemas.length}</span>
    </div>
  );
};

describe("AppDataProvider", () => {
  it("提供 datasets + schemas 给子组件", () => {
    render(
      <AppDataProvider datasets={[{ id: "1", name: "DS1" }]} schemas={[{ name: "motor" }]}>
        <Probe />
      </AppDataProvider>,
    );
    expect(screen.getByTestId("ds-count")).toHaveTextContent("1");
    expect(screen.getByTestId("schema-count")).toHaveTextContent("1");
  });

  it("不在 Provider 内调 useAppData 抛错", () => {
    // 抑制 React 错误边界日志
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/useAppData must be used/);
    spy.mockRestore();
  });
});
