// ImportCommitCard 单元测试 (2026-06-13 Task 21) — mock commitDocuments server action,
// 验证 form action 调它 + 提交成功后 toast + router.push /submissions.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ZERO } from "@/const";
import userEvent from "@testing-library/user-event";

const { commitDocumentsMock } = vi.hoisted(() => ({
  commitDocumentsMock: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 99, review_status: "pending" },
    ok: true as const,
  })),
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  commitDocuments: commitDocumentsMock,
}));

const { routerPushMock, toastSuccessMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/knowledge/documents/import",
}));

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: routerPushMock }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: (...args: unknown[]) => toastSuccessMock(...args),
  },
}));

// Mock zustand store: datasetId 固定 ds-1
vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (state: { datasetId: string }) => string) => sel({ datasetId: "ds-1" }),
}));

import { ImportCommitCard } from "./import-commit-card";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

beforeEach(() => {
  commitDocumentsMock.mockClear();
  routerPushMock.mockClear();
  toastSuccessMock.mockClear();
});

describe("ImportCommitCard", () => {
  it("点击提交 → commitDocuments 被调 + 弹 toast + 跳 /submissions", async () => {
    const user = userEvent.setup();
    renderInI18n(
      <ImportCommitCard
        validRows={[
          { answer: "A1.", question: "Q1?", tags: "t1" },
          { answer: "A2.", question: "Q2?", tags: "t2" },
        ]}
        validCount={2}
      />,
    );
    await user.click(screen.getByTestId("docs-commit"));
    await waitFor(() => {
      expect(commitDocumentsMock).toHaveBeenCalled();
      expect(toastSuccessMock).toHaveBeenCalled();
      expect(routerPushMock).toHaveBeenCalledWith("/zh/submissions");
    });
    // Toast 文案含 approval_id=99
    const call = toastSuccessMock.mock.calls[ZERO];
    expect(String(call[ZERO])).toMatch(/99/);
  });
});
