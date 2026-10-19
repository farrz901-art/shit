// 表格 viewer 客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import {
  type TablePageItem,
  type TablePageResponse,
  type TablePagesResponse,
} from "@/lib/api/pre-analysis";
import { AdminPreAnalysisTablesClient } from "./admin-pre-analysis-tables-client";

vi.mock("server-only", () => ({}));

// react-router / next-intl navigation mock
const mockPush = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// useSearchParams mock
const mockSearchParams = new Map<string, string>();
vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key) ?? null,
  }),
}));

afterEach(() => {
  vi.restoreAllMocks();
  mockSearchParams.clear();
  mockPush.mockClear();
});

const FIXTURE_PAGES: TablePagesResponse = {
  pages: [3, 9, 12, 15, 21, 31, 39, 45],
  total: 12,
};

const FIXTURE_PAGE_DATA: TablePageResponse = {
  page: 9,
  tables: [
    {
      table_index: 1,
      filename: "tables/page-9-table-1.csv",
      size_bytes: 50,
      columns: ["col_a", "col_b"],
      rows: [
        { col_a: "v1", col_b: "v2" },
        { col_a: "v3", col_b: "v4" },
      ],
    },
    {
      table_index: 2,
      filename: "tables/page-9-table-2.csv",
      size_bytes: 30,
      columns: ["col_x"],
      rows: [{ col_x: "foo" }, { col_x: "bar" }],
    },
  ] satisfies TablePageItem[],
};

const renderWithProviders = (
  ui: React.ReactElement,
  initialSearchParams: Record<string, string> = {},
) => {
  Object.entries(initialSearchParams).forEach(([k, v]) => mockSearchParams.set(k, v));
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

describe("AdminPreAnalysisTablesClient", () => {
  it("renders pagination buttons for all pages", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json(FIXTURE_PAGES, { status: 200 }),
    ) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, {
      page: "9",
    });

    await waitFor(() => {
      // 8 个页号按钮 (P3, P9, P12, P15, P21, P31, P39, P45)
      const pageButtons = screen.getAllByTestId(/^page-button-/);
      expect(pageButtons).toHaveLength(8);
    });
  });

  it("当前页高亮", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json(FIXTURE_PAGES, { status: 200 }),
    ) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, {
      page: "9",
    });

    await waitFor(() => {
      const current = screen.getByTestId("page-button-9");
      expect(current.getAttribute("aria-current")).toBe("page");
    });
  });

  it("click P12 → router.push", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json(FIXTURE_PAGES, { status: 200 }),
    ) as unknown as typeof fetch;
    globalThis.fetch = fetchMock;
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, {
      page: "9",
    });

    await waitFor(() => screen.getByTestId("page-button-12"));
    await user.click(screen.getByTestId("page-button-12"));

    expect(mockPush).toHaveBeenCalledWith("/admin/pre-analysis/pa-1/tables?page=12");
  });

  it("mock page data 2 tables → 2 DataTable 渲染", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) {
        return Response.json(FIXTURE_PAGES, { status: 200 });
      }
      return Response.json(FIXTURE_PAGE_DATA, { status: 200 });
    }) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, {
      page: "9",
    });

    await waitFor(() => {
      // 表格 1 的列名 + 表格 2 的列名
      expect(screen.getAllByText("col_a").length).toBeGreaterThan(0);
      expect(screen.getAllByText("col_x").length).toBeGreaterThan(0);
    });

    // anchor id 检查
    expect(document.getElementById("table-1")).toBeTruthy();
    expect(document.getElementById("table-2")).toBeTruthy();
  });

  it("empty pages → <DataEmpty>", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json({ pages: [], total: 0 }, { status: 200 }),
    ) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("无表格数据")).toBeTruthy();
    });
  });

  it("无效 page param (999) 自动 fallback 到 pages[0] (3)", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) {
        return Response.json(FIXTURE_PAGES, { status: 200 });
      }
      // 第 2 次调用是 page=3 (fallback)
      return Response.json({ ...FIXTURE_PAGE_DATA, page: 3 }, { status: 200 });
    }) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, {
      page: "999",
    });

    await waitFor(() => {
      const current = screen.getByTestId("page-button-3");
      expect(current.getAttribute("aria-current")).toBe("page");
    });
  });
});
