// EnvBadge 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { EnvBadge } from "./app-env-badge";

describe("EnvBadge", () => {
  it("渲染环境名", () => {
    render(<EnvBadge />);
    const badge = screen.getByText(/DEV|PROD|STAGING/);
    expect(badge).toBeInTheDocument();
  });
});
