// AppSelect 单元测试 (2026-06-14)
//   替 shadcn Select 6-行模板 (Root/Trigger/Value/Content/Item/Icon) → 1 行 options + value + onChange
//   测试范围: trigger 渲染 + 受控值 + placeholder, 不 click open dropdown
//   (jsdom 测不到 Radix portal, 跟现有 DatasetSwitcher.test.tsx 同型)
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { AppSelect } from "./app-select";

const options = [
  { label: "全部", value: "all" },
  { label: "账号", value: "account" },
  { label: "anon", value: "anon" },
];

describe("AppSelect", () => {
  it("render trigger with dataTestid", () => {
    render(<AppSelect options={options} dataTestid="kind" />);
    expect(screen.getByTestId("kind")).toBeInTheDocument();
  });

  it("respect value prop as controlled (display selected label)", () => {
    render(<AppSelect options={options} value="anon" onChange={() => {}} dataTestid="kind" />);
    expect(screen.getByText("anon")).toBeInTheDocument();
  });

  it("show placeholder when value undefined", () => {
    render(<AppSelect options={options} placeholder="选类型" dataTestid="kind" />);
    expect(screen.getByText("选类型")).toBeInTheDocument();
  });

  it("disabled disable trigger", () => {
    render(<AppSelect options={options} disabled dataTestid="kind" />);
    expect(screen.getByTestId("kind")).toBeDisabled();
  });

  it("onChange prop accepted (smoke test, jsdom 测不到 portal)", () => {
    const onChange = vi.fn();
    render(<AppSelect options={options} value="all" onChange={onChange} dataTestid="kind" />);
    // 只能确认 prop 不抛, 真交互靠 Playwright
    expect(screen.getByTestId("kind")).toBeInTheDocument();
  });
});
