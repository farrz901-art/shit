// ApprovalRow 单元测试 — TDD red phase
// 覆盖: 1) 2 独立 badge 2) review/apply 状态色 3) 拒绝原因 4) 展开调 getDetail
// 5) 行内按钮按 isAdmin + 状态机显隐

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

const { getDetailMock, approveMutMock, rejectMutMock, retryMutMock, invalidateMock } = vi.hoisted(
  () => ({
    approveMutMock: vi.fn(),
    getDetailMock: vi.fn(),
    invalidateMock: vi.fn(),
    rejectMutMock: vi.fn(),
    retryMutMock: vi.fn(),
  }),
);

vi.mock("@tanstack/react-query", () => ({
  useMutation: ({ mutationFn, onSuccess }: any) => ({
    isPending: false,
    mutate: (...args: any[]) => {
      mutationFn(...args);
      onSuccess?.();
    },
  }),
  useQuery: ({ queryFn, enabled }: any) => ({
    data: enabled ? queryFn() : undefined,
    isLoading: false,
  }),
  useQueryClient: () => ({ invalidateQueries: invalidateMock }),
}));

vi.mock("@/lib/api/approvals", () => ({
  approve: (...args: any[]) => {
    approveMutMock(...args);
    return Promise.resolve({ id: 1 });
  },
  getDetail: getDetailMock,
  reject: (...args: any[]) => {
    rejectMutMock(...args);
    return Promise.resolve({ id: 1 });
  },
  retry: (...args: any[]) => {
    retryMutMock(...args);
    return Promise.resolve({ id: 1 });
  },
  submit: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { ApprovalRow } from "./approval-row";
import type { Approval } from "@/lib/api/approvals";

const MOCK_APPROVAL_ID = 142;

const baseApproval: Approval = {
  applied_at: null,
  apply_status: "none",
  created_at: "2026-06-13T10:00:00Z",
  error_msg: null,
  id: 142,
  kind: "qa",
  rejection_note: null,
  rejection_reason: null,
  review_status: "pending",
  reviewed_at: null,
  reviewer_id: null,
  submitter_id: 1,
};

describe("ApprovalRow", () => {
  beforeEach(() => {
    getDetailMock.mockReset();
    approveMutMock.mockReset();
    rejectMutMock.mockReset();
    retryMutMock.mockReset();
    invalidateMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("渲染 2 个独立 badge (review + apply), 各自色", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin={false} />);
    expect(screen.getByTestId("badge-review")).toHaveTextContent("待审");
    expect(screen.getByTestId("badge-apply")).toHaveTextContent("未写入");
  });

  it("review=approved, apply=failed → 2 badge 正确 + 错误消息展开", () => {
    render(
      <ApprovalRow
        approval={{
          ...baseApproval,
          apply_status: "failed",
          error_msg: "Dify 502",
          review_status: "approved",
        }}
        isAdmin
      />,
    );
    expect(screen.getByTestId("badge-review")).toHaveTextContent("已批");
    expect(screen.getByTestId("badge-apply")).toHaveTextContent("写库失败");
  });

  it("review=rejected, rejection_reason=duplicate, rejection_note='跟 doc-12 重复' → 显示原因", () => {
    render(
      <ApprovalRow
        approval={{
          ...baseApproval,
          rejection_note: "跟 doc-12 重复",
          rejection_reason: "duplicate",
          review_status: "rejected",
        }}
        isAdmin={false}
      />,
    );
    expect(screen.getByText(/被拒/)).toBeInTheDocument();
    expect(screen.getByText(/跟 doc-12 重复/)).toBeInTheDocument();
  });

  it("点展开调 approvalsApi.getDetail, 拉完整 payload 渲染", async () => {
    getDetailMock.mockResolvedValue({
      ...baseApproval,
      payload: { answer: "IP55", dataset_id: "ds1", question: "1LE 防护等级?" },
    });
    render(<ApprovalRow approval={baseApproval} isAdmin />);
    fireEvent.click(screen.getByTestId("expand-trigger"));
    await waitFor(() => expect(getDetailMock).toHaveBeenCalledWith(MOCK_APPROVAL_ID));
  });

  it("非 admin: 不渲染批准/拒绝/重试按钮", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin={false} />);
    expect(screen.queryByTestId("btn-approve")).toBeNull();
    expect(screen.queryByTestId("btn-reject")).toBeNull();
    expect(screen.queryByTestId("btn-retry")).toBeNull();
  });

  it("admin + review=pending: 显示批准/拒绝按钮, 不显示重试", () => {
    render(<ApprovalRow approval={baseApproval} isAdmin />);
    expect(screen.getByTestId("btn-approve")).toBeInTheDocument();
    expect(screen.getByTestId("btn-reject")).toBeInTheDocument();
    expect(screen.queryByTestId("btn-retry")).toBeNull();
  });

  it("admin + (approved, failed): 显示重试按钮, 不显示批准/拒绝", () => {
    render(
      <ApprovalRow
        approval={{
          ...baseApproval,
          apply_status: "failed",
          error_msg: "x",
          review_status: "approved",
        }}
        isAdmin
      />,
    );
    expect(screen.queryByTestId("btn-approve")).toBeNull();
    expect(screen.queryByTestId("btn-reject")).toBeNull();
    expect(screen.getByTestId("btn-retry")).toBeInTheDocument();
  });
});
