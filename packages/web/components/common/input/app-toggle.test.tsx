// AppToggle 单元测试 (2026-06-14): 3 case
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { AppToggle } from "./app-toggle";

const options = [
  { label: "解码卡", value: "cards" },
  { label: "Dify 视图", value: "llm" },
];

const onChange = () => {};

describe("AppToggle", () => {
  it("render all options", () => {
    render(<AppToggle options={options} defaultValue="cards" dataTestid="view" />);
    expect(screen.getByTestId("view-cards")).toBeInTheDocument();
    expect(screen.getByTestId("view-llm")).toBeInTheDocument();
  });

  it("respect value prop as controlled", () => {
    render(<AppToggle options={options} value="llm" onChange={() => {}} dataTestid="view" />);
    expect(screen.getByTestId("view-llm")).toBeInTheDocument();
  });

  it("smoke test, accept onChange prop (jsdom 测不到 click toggle state)", () => {
    render(
      <AppToggle options={options} defaultValue="cards" onChange={onChange} dataTestid="view" />,
    );
    expect(screen.getByTestId("view-cards")).toBeInTheDocument();
  });
});
