// EntryCard 组件单测
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { EntryCard } from "./app-entry-card";

vi.mock("next-intl", () => ({
  useLocale: () => "zh",
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe("EntryCard", () => {
  it("渲染 title + desc", () => {
    render(<EntryCard href="/page" icon={<span>i</span>} title="标题" desc="描述" />);
    expect(screen.getByText("标题")).toBeInTheDocument();
    expect(screen.getByText("描述")).toBeInTheDocument();
  });
});
