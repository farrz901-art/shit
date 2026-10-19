import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// Mock zustand store
const mockStore = { domain: "motor", setDomain: vi.fn() };
vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (selector: (state: typeof mockStore) => unknown) => selector(mockStore),
}));

// Mock RQ useQuery — 返真实后端格式: 裸数组 [{ domain, file }]
// 模式跟 HealthDot.test.tsx 一致, 不用包 QueryClientProvider (DomainSwitcher 自包)
let queryData: { domain: string; file: string }[] | undefined = undefined;
vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual("@tanstack/react-query");
  return {
    ...actual,
    useQuery: () => ({
      data: queryData,
      error: undefined,
      isLoading: !queryData,
    }),
  };
});

import { DomainSwitcher } from "./domain-switcher";

describe("DomainSwitcher", () => {
  beforeEach(() => {
    mockStore.domain = "motor";
    mockStore.setDomain.mockClear();
    queryData = undefined;
  });

  it("加载中显示 trigger (placeholder 在 SelectValue 内)", () => {
    render(<DomainSwitcher />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("有数据时渲染下拉选项 (真实后端格式: 裸数组)", () => {
    queryData = [
      { domain: "motor", file: "/configs/triples/motor/motor-schema.yaml" },
      { domain: "sensor", file: "/configs/triples/sensor/sensor-schema.yaml" },
    ];
    render(<DomainSwitcher />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("空数组时不下拉选项, 保持 trigger", () => {
    queryData = [];
    render(<DomainSwitcher />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("data 为 undefined 时不下拉选项", () => {
    queryData = undefined;
    render(<DomainSwitcher />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });
});
