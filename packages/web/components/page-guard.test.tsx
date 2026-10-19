import { describe, expect, test, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { PageGuard } from "@/components/page-guard";
import { forbidden } from "next/navigation";

vi.mock("next/navigation", () => ({
  forbidden: vi.fn(),
}));

describe("PageGuard", () => {
  test("pageKey 在 allowed → 渲染 children", () => {
    render(
      <PageGuard pageKey="knowledge" role="admin" allowed={["knowledge", "chat"]}>
        <div data-testid="content">知识库内容</div>
      </PageGuard>,
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  test("pageKey 不在 allowed → 调 forbidden()", () => {
    render(
      <PageGuard pageKey="knowledge" role="admin" allowed={["chat"]}>
        <div>内容</div>
      </PageGuard>,
    );
    expect(forbidden).toHaveBeenCalled();
  });

  test("super_admin → 跳过 allowed 检查", () => {
    render(
      <PageGuard pageKey="anything" role="super_admin" allowed={[]}>
        <div data-testid="content">超级管理员</div>
      </PageGuard>,
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });
});
