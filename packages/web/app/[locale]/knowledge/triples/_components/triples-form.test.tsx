// TriplesForm 单元测试 (2026-06-13 Task 21) — mock createTriples server action,
// 验证 form action 调它 + 提交成功后 toast + router.push /submissions.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";

const { createTriplesMock } = vi.hoisted(() => ({
  createTriplesMock: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 7, review_status: "pending" },
    ok: true as const,
  })),
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  createTriples: createTriplesMock,
}));

const { routerPushMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
  toastErrorMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/knowledge/triples",
}));

// triples-form 用 @/i18n/navigation 的 useRouter (next-intl 4.x createNavigation)
// 不走 importOriginal: 会拉真 next-intl/navigation → next/navigation 在 vitest ESM 下解析失败
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: routerPushMock }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    success: (...args: unknown[]) => toastSuccessMock(...args),
  },
}));

// Mock DataTable 让单行 input 暴露 testid, 简化测试填值
vi.mock("@/components/common/table/data-table", () => ({
  DataTable: <RowType,>({
    dataSource,
    columns,
  }: {
    dataSource: RowType[];
    columns: {
      id: string;
      cell: (ctx: { row: { original: RowType; index: number } }) => React.ReactNode;
    }[];
  }) => (
    <div data-testid="data-table-rows">
      {dataSource.map((row, idx) => (
        <div key={idx} data-testid={`row-${idx}`}>
          {columns.map((col) => (
            <span key={col.id} data-testid={`cell-${idx}-${col.id}`}>
              {col.cell({ row: { original: row, index: idx } })}
            </span>
          ))}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/knowledge/SchemaFieldRenderer", () => ({
  LabelPicker: () => <span data-testid="label-picker">lp</span>,
  RelationPicker: () => <span data-testid="relation-picker">rp</span>,
}));

import { TriplesForm } from "./triples-form";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import type { KnowledgeSchema } from "@/lib/schema-types";

const SCHEMA: KnowledgeSchema = {
  nodes: [
    {
      fields: [
        { key: "model", label: "型号", type: "string" },
        { key: "vendor", label: "厂商", type: "string" },
      ],
      name: "Product",
    },
  ],
  relations: [{ cardinality: "many_to_one", from: "Product", name: "MADE_BY", to: "Product" }],
};

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

beforeEach(() => {
  createTriplesMock.mockClear();
  routerPushMock.mockClear();
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
});

describe("TriplesForm", () => {
  it("点击批量提交 (填好 from/to value) → createTriples 被调 + 弹 toast + 跳 /submissions", async () => {
    const user = userEvent.setup();
    renderInI18n(<TriplesForm schema={SCHEMA} />);
    // DataTable mock 把所有 input 暴露在 cell-{i}-{key} 内; 找 from_value + to_value input
    // Properties 已默认 "{}", 故只需补 from_value + to_value
    const fromInput = screen
      .getByTestId("cell-0-from_value")
      .querySelector("input") as HTMLInputElement;
    const toInput = screen
      .getByTestId("cell-0-to_value")
      .querySelector("input") as HTMLInputElement;
    await user.type(fromInput, "1LE0001");
    await user.type(toInput, "Vendor-A");
    await user.click(screen.getByTestId("triples-submit"));
    await waitFor(() => {
      expect(createTriplesMock).toHaveBeenCalled();
      expect(toastSuccessMock).toHaveBeenCalled();
      expect(routerPushMock).toHaveBeenCalledWith("/zh/submissions");
    });
    // Toast 文案含 approval_id=7
    const [[firstArg]] = toastSuccessMock.mock.calls;
    expect(String(firstArg)).toMatch(/7/);
  });

  it("行数据空 → 不调 createTriples (客户端 zod 校验拦, 不弹 toast)", async () => {
    const user = userEvent.setup();
    renderInI18n(<TriplesForm schema={SCHEMA} />);
    await user.click(screen.getByTestId("triples-submit"));
    await waitFor(() => {
      expect(createTriplesMock).not.toHaveBeenCalled();
      expect(toastSuccessMock).not.toHaveBeenCalled();
      expect(routerPushMock).not.toHaveBeenCalled();
    });
  });
});
