import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";

// BackLink 用 useRouter (useHistory 模式), mock 避免真实跳转
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));
// (2026-06-23) GuardClient 读 zustand store; mock 不再需要 globalThis.fetch
import BatchPage from "./page";

const renderInI18n = (ui: React.ReactNode) => render(<IntlWrapper locale="zh">{ui}</IntlWrapper>);

describe("BatchPage", () => {
  beforeEach(() => {
    localStorage.clear();
    usePermissionsStore.setState({
      accountId: null,
      allowed: ["knowledge"],
      loaded: true,
      pages: [],
      role: "admin",
    });
  });

  it("renders 操作 + 提交按钮", () => {
    renderInI18n(<BatchPage />);
    expect(screen.getByTestId("batch-file")).toBeInTheDocument();
    expect(screen.getByTestId("batch-submit")).toBeInTheDocument();
  });

  it("hero 含 BackLink → /knowledge/graph", () => {
    renderInI18n(<BatchPage />);
    expect(screen.getByTestId("page-hero-back-link")).toBeInTheDocument();
    // 跟 BackLink 文字匹配: 返回 + 知识图谱
    expect(screen.getByRole("link", { name: /返回知识图谱/ })).toBeInTheDocument();
  });
});
