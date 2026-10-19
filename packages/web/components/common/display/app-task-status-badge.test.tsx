import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it } from "vitest";
import { TaskStatusBadge } from "./app-task-status-badge";

describe("TaskStatusBadge", () => {
  it("done 绿色", () => {
    render(<TaskStatusBadge state="done" />);
    expect(screen.getByTestId("task-status").className).toContain("status-success");
  });
  it("failed 红色", () => {
    render(<TaskStatusBadge state="failed" />);
    expect(screen.getByTestId("task-status").className).toContain("status-error");
  });
  it("running 蓝色 + 动画", () => {
    render(<TaskStatusBadge state="running" />);
    expect(screen.getByTestId("task-status").className).toContain("status-running");
    expect(screen.getByTestId("task-status").className).toContain("animate-pulse");
  });
});
