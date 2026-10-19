// SettingsCard 组件单测
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Settings } from "lucide-react";
import { SettingsCard } from "./app-settings-card";

describe("SettingsCard", () => {
  it("渲染 icon + title + children", () => {
    render(
      <SettingsCard icon={Settings} title="设置">
        <div data-testid="child">内容</div>
      </SettingsCard>,
    );
    expect(screen.getByText("设置")).toBeInTheDocument();
    expect(screen.getByTestId("child")).toHaveTextContent("内容");
  });

  it("透传 data-testid", () => {
    render(
      <SettingsCard icon={Settings} title="测试" data-testid="card-1">
        <span>child</span>
      </SettingsCard>,
    );
    expect(screen.getByTestId("card-1")).toBeInTheDocument();
  });
});
