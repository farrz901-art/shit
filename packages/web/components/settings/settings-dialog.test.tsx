import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { SettingsDialog } from "./settings-dialog";
import { TWO } from "@/const";

vi.mock("@/components/theme-provider", () => ({
  useTheme: () => ({ setTheme: vi.fn(), theme: "light" }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/zh",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const renderDialog = (props: { open: boolean; onOpenChange: (val: boolean) => void }) =>
  render(
    <IntlWrapper locale="zh">
      <SettingsDialog open={props.open} onOpenChange={props.onOpenChange} />
    </IntlWrapper>,
  );

describe("SettingsDialog", () => {
  it("受控: open=true 时弹框可见", () => {
    renderDialog({ onOpenChange: vi.fn(), open: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("受控: open=false 时弹框不可见", () => {
    renderDialog({ onOpenChange: vi.fn(), open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("主题 Select 存在且可交互", () => {
    renderDialog({ onOpenChange: vi.fn(), open: true });
    // 弹框里有 主题 + 语言 两个 combobox
    expect(screen.getAllByRole("combobox").length).toBeGreaterThanOrEqual(TWO);
  });

  it("语言行可交互", () => {
    renderDialog({ onOpenChange: vi.fn(), open: true });
    expect(screen.getByText("中文")).toBeInTheDocument();
  });
});
