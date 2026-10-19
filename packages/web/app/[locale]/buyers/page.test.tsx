// 买家列表页动态画像列测试 (2026-06-25 buyer-profile dynamic columns spec)
// 9 个 it, 全部 mock hook, 0 真实后端连接.

import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import BuyersPage from "./page";

// Mock hooks — 不连真后端
vi.mock("@/app/[locale]/buyers/_lib/buyer-profile/hooks", () => ({
  useBuyerProfiles: vi.fn(),
  useFieldConfigs: vi.fn(),
  useCreateFieldConfig: vi.fn(),
  useUpdateFieldConfig: vi.fn(),
}));

import { useBuyerProfiles, useFieldConfigs } from "@/app/[locale]/buyers/_lib/buyer-profile/hooks";

const TEST_PROFILE_COUNT = 2;
const ZERO_INDEX = 0;
const MISSING_FIELD_COUNT = 4;
const NOT_FOUND_INDEX = -1;

const mockProfiles = [
  {
    buyer_key: "k1",
    buyer_name: "张三",
    first_seen_at: null,
    id: "1",
    last_contact_at: null,
    notes: null,
    profile_data: {
      budget: { confidence: "high", source: "auto", updated_at: null, value: 50_000 },
      region: { confidence: "high", source: "auto", updated_at: null, value: "华东" },
      products: { confidence: "medium", source: "auto", updated_at: null, value: ["云屏", "数显"] },
      active: { confidence: "high", source: "auto", updated_at: null, value: true },
    },
    status: "active",
    tags: [],
  },
  {
    buyer_key: "k2",
    buyer_name: "李四",
    first_seen_at: null,
    id: "2",
    last_contact_at: null,
    notes: null,
    profile_data: {
      budget: { confidence: "high", source: "auto", updated_at: null, value: 80_000 },
      region: { confidence: "high", source: "auto", updated_at: null, value: "华北" },
      products: { confidence: "medium", source: "auto", updated_at: null, value: ["仪表"] },
      active: { confidence: "high", source: "auto", updated_at: null, value: false },
    },
    status: "archived",
    tags: [],
  },
];

const mockFieldConfigs = [
  {
    code: "budget",
    extraction_prompt: null,
    field_type: "number",
    id: 1,
    is_active: true,
    label: "预算",
    notify_on_change: [],
    options: [],
    sort_order: 1,
  },
  {
    code: "region",
    extraction_prompt: null,
    field_type: "select",
    id: 2,
    is_active: true,
    label: "区域",
    notify_on_change: [],
    options: [],
    sort_order: 2,
  },
  {
    code: "products",
    extraction_prompt: null,
    field_type: "tags",
    id: 3,
    is_active: true,
    label: "产品",
    notify_on_change: [],
    options: [],
    sort_order: 3,
  },
  {
    code: "active",
    extraction_prompt: null,
    field_type: "boolean",
    id: 4,
    is_active: true,
    label: "活跃",
    notify_on_change: [],
    options: [],
    sort_order: 4,
  },
  {
    code: "disabled_field",
    extraction_prompt: null,
    field_type: "text",
    id: 5,
    is_active: false,
    label: "停用字段",
    notify_on_change: [],
    options: [],
    sort_order: 5,
  },
];

const renderPage = () =>
  render(
    <IntlWrapper locale="zh">
      <BuyersPage />
    </IntlWrapper>,
  );

describe("BuyersPage 动态画像列", () => {
  it("基础渲染: 表格 + 列头 + 行数", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    expect(screen.getAllByTestId("data-table-row")).toHaveLength(TEST_PROFILE_COUNT);
  });

  it("按 sort_order 升序渲染动态列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = [...container.querySelectorAll("th")].map((th) => th.textContent);
    const budgetIdx = headers.indexOf("预算");
    const productsIdx = headers.indexOf("产品");
    const activeIdx = headers.indexOf("活跃");
    expect(budgetIdx).toBeGreaterThan(NOT_FOUND_INDEX);
    expect(activeIdx).toBeGreaterThan(productsIdx);
  });

  it("is_active=false 字段不渲染列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    expect(screen.queryByText("停用字段")).not.toBeInTheDocument();
  });

  it("buyer_key 列已删除", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = [...container.querySelectorAll("th")].map((th) => th.textContent);
    expect(headers).not.toContain("标识");
  });

  it("select 字段画 Badge", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      const cells = screen.getAllByText("华东");
      expect(cells.length).toBeGreaterThan(ZERO_INDEX);
    });
    expect(screen.getByText("华东").closest('[class*="rounded"]')).toBeTruthy();
  });

  it("tags 字段画多个 Badge", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("云屏")).toBeInTheDocument();
    });
    expect(screen.getByText("云屏")).toBeInTheDocument();
    expect(screen.getByText("数显")).toBeInTheDocument();
    expect(screen.getByText("仪表")).toBeInTheDocument();
  });

  it("boolean 字段画 是/否", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const yesCells = screen.getAllByText("是");
    const noCells = screen.getAllByText("否");
    expect(yesCells.length).toBeGreaterThan(ZERO_INDEX);
    expect(noCells.length).toBeGreaterThan(ZERO_INDEX);
  });

  it("缺失 profile_data 字段渲染 —", async () => {
    const profilesMissingField = [
      {
        buyer_key: "k1",
        buyer_name: "王五",
        first_seen_at: null,
        id: "1",
        last_contact_at: null,
        notes: null,
        profile_data: {},
        status: "active",
        tags: [],
      },
    ];
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: profilesMissingField, total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("王五")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(MISSING_FIELD_COUNT);
  });

  it("useFieldConfigs 失败回退基础 5 列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("network error"),
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = [...container.querySelectorAll("th")].map((th) => th.textContent);
    expect(headers).not.toContain("预算");
    expect(headers).not.toContain("区域");
    expect(headers).not.toContain("产品");
    expect(headers).not.toContain("活跃");
    expect(screen.getByText("network error")).toBeInTheDocument();
  });
});
