// MySubmissionsList 单元测试 — TDD red phase
// 覆盖: 1) 渲染 initialData 列表 (ApprovalRow, isAdmin=false)
//       2) 空列表返 Empty
//       3) 非 admin: 不渲染批准/拒绝/重试按钮

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// UseQuery mock — 返 initialData, 不发请求 (避免 ApprovalRow 内部 useQuery 干扰)
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

import { MySubmissionsList } from "./my-submissions-list";
import type { Approval } from "@/lib/api/approvals";

const mockMine: Approval[] = [
  {
    applied_at: null,
    apply_status: "none",
    created_at: "2026-06-13T10:00:00Z",
    error_msg: null,
    id: 1,
    kind: "qa",
    rejection_note: null,
    rejection_reason: null,
    review_status: "pending",
    reviewed_at: null,
    reviewer_id: null,
    submitter_id: 1,
  },
  {
    applied_at: null,
    apply_status: "none",
    created_at: "2026-06-12T10:00:00Z",
    error_msg: null,
    id: 2,
    kind: "qa",
    rejection_note: "跟 doc-12 重复",
    rejection_reason: "duplicate",
    review_status: "rejected",
    reviewed_at: "2026-06-12T11:00:00Z",
    reviewer_id: 9,
    submitter_id: 1,
  },
];

describe("MySubmissionsList", () => {
  beforeEach(() => useQueryMock.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("渲染 initialData 列表 (每项 ApprovalRow, isAdmin=false)", () => {
    // Mock useQuery 返 initialData (不调 fetch)
    useQueryMock.mockReturnValue({ data: mockMine });
    render(<MySubmissionsList initialData={mockMine} />);
    // 2 个 approval row (ApprovalRow 渲染 #1, #2)
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
  });

  it("空列表返 Empty", () => {
    useQueryMock.mockReturnValue({ data: [] });
    render(<MySubmissionsList initialData={[]} />);
    expect(screen.getByText(/暂无/)).toBeInTheDocument();
  });

  it("不渲染批准/拒绝/重试按钮 (非 admin)", () => {
    useQueryMock.mockReturnValue({ data: mockMine });
    render(<MySubmissionsList initialData={mockMine} />);
    expect(screen.queryByTestId("btn-approve")).toBeNull();
    expect(screen.queryByTestId("btn-reject")).toBeNull();
    expect(screen.queryByTestId("btn-retry")).toBeNull();
  });
});
