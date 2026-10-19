import { TWO, ZERO } from "@/const";
// ThinkingTrace 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ThinkingTrace } from "./thinking-trace";

describe("ThinkingTrace", () => {
  it("渲染所有步骤", () => {
    render(
      <ThinkingTrace
        steps={[
          { node: "reasoner", status: "started" },
          { node: "extractor", status: "finished", detail: "ok" },
        ]}
      />,
    );
    expect(screen.getByText("reasoner")).toBeInTheDocument();
    expect(screen.getByText("extractor")).toBeInTheDocument();
  });

  it("finished 用 moss 色, started 用 warning 色", () => {
    const { container } = render(
      <ThinkingTrace
        steps={[
          { node: "r1", status: "finished" },
          { node: "r2", status: "started" },
        ]}
      />,
    );
    const badges = container.querySelectorAll("[class*='border-']");
    expect(badges.length).toBe(TWO);
  });

  it("空 steps 渲染空容器", () => {
    const { container } = render(<ThinkingTrace steps={[]} />);
    expect(container.firstChild?.childNodes.length).toBe(ZERO);
  });
});
