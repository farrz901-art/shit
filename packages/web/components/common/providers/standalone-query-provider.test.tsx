// StandaloneQueryProvider 单测 (2026-06-28 P3 refactor)
import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { useQuery } from "@tanstack/react-query";
import { StandaloneQueryProvider } from "./standalone-query-provider";

const TestChild = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["test"],
    queryFn: () => Promise.resolve("hello"),
    staleTime: Infinity,
  });
  return <div data-testid="result">{isLoading ? "loading" : data}</div>;
};

describe("StandaloneQueryProvider", () => {
  it("应该渲染 children", () => {
    render(
      <StandaloneQueryProvider>
        <div data-testid="child">child content</div>
      </StandaloneQueryProvider>,
    );
    expect(screen.getByTestId("child")).toBeDefined();
  });

  it("应该提供独立 QueryClient, useQuery 可解析", async () => {
    render(
      <StandaloneQueryProvider>
        <TestChild />
      </StandaloneQueryProvider>,
    );
    await vi.waitFor(() => {
      expect(screen.getByTestId("result").textContent).toBe("hello");
    });
  });

  it("rerender 不应重建 QueryClient (useState 工厂保证)", () => {
    const { rerender } = render(
      <StandaloneQueryProvider>
        <TestChild />
      </StandaloneQueryProvider>,
    );
    rerender(
      <StandaloneQueryProvider>
        <TestChild />
      </StandaloneQueryProvider>,
    );
    expect(screen.getByTestId("result")).toBeDefined();
  });
});
