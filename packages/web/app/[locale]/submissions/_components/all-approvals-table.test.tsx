// AllApprovalsTable 单元测试 — TDD red phase
// 覆盖: 1) 渲染 initialData 列表 (ApprovalRow, isAdmin=true)
//       2) admin 看到批准/拒绝按钮 (仅 pending)
//       3) 空列表返 Empty

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// UseQuery mock — 返 initialData, 不发请求
const { useQueryMock, invalidateMock } = vi.hoisted(() => ({
  invalidateMock: vi.fn(),
  useQueryMock: vi.fn(),
}));
vi.mock("@tanstack/react-query", () => ({
  // ApprovalRow 内部用 — 空 stub, 不影响当前测试断言
  useMutation: () => ({ isPending: false, mutate: vi.fn() }),
  useQuery: useQueryMock,
  useQueryClient: () => ({ invalidateQueries: invalidateMock }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { AllApprovalsTable } from "./all-approvals-table";
import type { Approval } from "@/lib/api/approvals";

const mockAll: Approval[] = [
  {
    applied_at: null,
    apply_status: "none",
    created_at: "2026-06-13T10:00:00Z",
    error_msg: null,
    id: 10,
    kind: "qa",
    rejection_note: null,
    rejection_reason: null,
    review_status: "pending",
    reviewed_at: null,
    reviewer_id: null,
    submitter_id: 5,
  },
];

describe("AllApprovalsTable", () => {
  beforeEach(() => useQueryMock.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("渲染 initialData 列表 (每项 ApprovalRow, isAdmin=true)", () => {
    useQueryMock.mockReturnValue({ data: mockAll });
    render(<AllApprovalsTable initialData={mockAll} />);
    expect(screen.getByText("#10")).toBeInTheDocument();
  });

  it("admin 看到批准/拒绝按钮 (仅 pending)", () => {
    useQueryMock.mockReturnValue({ data: mockAll });
    render(<AllApprovalsTable initialData={mockAll} />);
    expect(screen.getByTestId("btn-approve")).toBeInTheDocument();
    expect(screen.getByTestId("btn-reject")).toBeInTheDocument();
  });

  it("空列表返 Empty", () => {
    useQueryMock.mockReturnValue({ data: [] });
    render(<AllApprovalsTable initialData={[]} />);
    expect(screen.getByText(/暂无/)).toBeInTheDocument();
  });
});
