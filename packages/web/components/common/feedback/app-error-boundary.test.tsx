import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ErrorBoundary } from "./app-error-boundary";

const Bomb = () => {
  throw new Error("boom");
};

describe("ErrorBoundary", () => {
  it("捕获子组件异常", () => {
    // Suppress React error boundary console error
    const consoleError = console.error;
    console.error = () => {};
    try {
      render(
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>,
      );
      expect(screen.getByTestId("error-boundary")).toBeInTheDocument();
      expect(screen.getByText(/boom/)).toBeInTheDocument();
    } finally {
      console.error = consoleError;
    }
  });

  it("无错时正常渲染子组件", () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">OK</div>
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
