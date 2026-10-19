// SubmissionsTabs 单元测试 — TDD red phase
// 覆盖: 1) admin 渲染 2 tab 2) 非 admin 渲染 1 tab 3) 点 tab 调 router.push
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

const { useRouterPushMock, useRouterRefreshMock } = vi.hoisted(() => ({
  useRouterPushMock: vi.fn(),
  useRouterRefreshMock: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

// submissions-tabs 用 @/i18n/navigation 的 useRouter (next-intl 4.x createNavigation)
// 不走 importOriginal: 会拉真 next-intl/navigation → next/navigation 在 vitest ESM 下解析失败
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: useRouterPushMock, refresh: useRouterRefreshMock }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// 子组件 MySubmissionsList / AllApprovalsTable 内部 useQuery — 返空数据, 不让真实 RQ 找不到 QueryClient
vi.mock("@tanstack/react-query", () => ({
  useMutation: () => ({ isPending: false, mutate: vi.fn() }),
  useQuery: () => ({ data: undefined }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

import { SubmissionsTabs } from "./submissions-tabs";
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
];

describe("SubmissionsTabs", () => {
  beforeEach(() => {
    useRouterPushMock.mockReset();
    useRouterRefreshMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("admin: 渲染 2 tab (mine / all), 默认 active=mine", () => {
    render(<SubmissionsTabs activeTab="mine" isAdmin initialMine={mockMine} initialAll={[]} />);
    expect(screen.getByText("我提交的")).toBeInTheDocument();
    expect(screen.getByText("全部待审")).toBeInTheDocument();
  });

  it("非 admin: 仅渲染 mine tab, 不渲染 all", () => {
    render(
      <SubmissionsTabs activeTab="mine" isAdmin={false} initialMine={mockMine} initialAll={null} />,
    );
    expect(screen.getByText("我提交的")).toBeInTheDocument();
    expect(screen.queryByText("全部待审")).toBeNull();
  });

  it("点 all tab 调 router.push('/submissions?tab=all')", async () => {
    const userEventModule = await import("@testing-library/user-event");
    const userEvent = userEventModule.default;
    const user = userEvent.setup();
    render(<SubmissionsTabs activeTab="mine" isAdmin initialMine={mockMine} initialAll={[]} />);
    // 改用 userEvent (Radix Tabs onValueChange 需真实点击, fireEvent.click 不可靠)
    await user.click(screen.getByText("全部待审"));
    expect(useRouterPushMock).toHaveBeenCalledWith("/submissions?tab=all");
  });
});
