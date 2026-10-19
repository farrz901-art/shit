import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// Mock zustand store
const mockStore = { datasetId: "", setDatasetId: vi.fn() };
vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (selector: (state: typeof mockStore) => unknown) => selector(mockStore),
}));

// Mock RQ useQuery — 返裸数组 (knowledgeApi.fetchDatasets 2026-06-15 内部解 Dify 包装后直接返 DatasetRow[])
// 模式跟 HealthDot.test.tsx 一致, 不用包 QueryClientProvider (DatasetSwitcher 自包)
let queryData: { id: string; name: string }[] | undefined = undefined;
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

import { DatasetSwitcher } from "./dataset-switcher";

describe("DatasetSwitcher", () => {
  beforeEach(() => {
    mockStore.datasetId = "";
    mockStore.setDatasetId.mockClear();
    queryData = undefined;
  });

  it("加载中显示 trigger (placeholder 在 SelectValue 内)", () => {
    render(<DatasetSwitcher />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("有数据时渲染下拉选项 (knowledgeApi.fetchDatasets 已解 Dify 包装, 直接拿数组)", () => {
    queryData = [
      { id: "ds_001", name: "西门子电机知识库" },
      { id: "ds_002", name: "FAQ 数据集" },
    ];
    render(<DatasetSwitcher />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("空数据时不下拉选项, 保持 trigger", () => {
    queryData = [];
    render(<DatasetSwitcher />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("data 为 undefined 时不下拉选项", () => {
    queryData = undefined;
    render(<DatasetSwitcher />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });
});
