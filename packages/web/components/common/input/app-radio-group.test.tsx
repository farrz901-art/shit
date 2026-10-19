// AppRadioGroup 单元测试 (2026-07-07)
//   替 shadcn RadioGroup + RadioGroupItem 2 行模板 (Root/Item/Indicator) → 1 行 options + value + onChange
//   测试范围: 默认 label 渲染 + renderLabel 复合 + 受控值 + dataTestid Item 级透传 + disabled
//   (jsdom 测 Radix radio 选中状态, 跟 AppSelect 模式一致)
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

import { AppRadioGroup } from "./app-radio-group";

const options = [
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "camelot", label: "Camelot" },
  { value: "pdfplumber", label: "pdfplumber" },
];

describe("AppRadioGroup", () => {
  it("render root with dataTestid", () => {
    render(<AppRadioGroup options={options} dataTestid="backend" />);
    expect(screen.getByTestId("backend")).toBeInTheDocument();
  });

  it("render default label for each option", () => {
    render(<AppRadioGroup options={options} value="pymupdf" onChange={() => {}} />);
    expect(screen.getByText("PyMuPDF")).toBeInTheDocument();
    expect(screen.getByText("Camelot")).toBeInTheDocument();
    expect(screen.getByText("pdfplumber")).toBeInTheDocument();
  });

  it("renderLabel override default label", () => {
    render(
      <AppRadioGroup
        options={options}
        value="pymupdf"
        onChange={() => {}}
        renderLabel={(opt) => (
          <span data-testid={`custom-${opt.value}`}>{`custom-${opt.label}`}</span>
        )}
      />,
    );
    expect(screen.getByTestId("custom-pymupdf")).toHaveTextContent("custom-PyMuPDF");
    expect(screen.queryByText("PyMuPDF")).not.toBeInTheDocument();
  });

  it("onValueChange called with new value (controlled)", () => {
    const onChange = vi.fn();
    render(<AppRadioGroup options={options} value="pymupdf" onChange={onChange} />);
    // RadioGroupItem 的 click 触发 onValueChange (Radix 标准)
    screen.getByRole("radio", { name: "Camelot" }).click();
    expect(onChange).toHaveBeenCalledWith("camelot");
  });

  it("Item dataTestid composed as dataTestid + dash + value", () => {
    render(<AppRadioGroup options={options} dataTestid="backend" />);
    expect(screen.getByTestId("backend-pymupdf")).toBeInTheDocument();
    expect(screen.getByTestId("backend-camelot")).toBeInTheDocument();
    expect(screen.getByTestId("backend-pdfplumber")).toBeInTheDocument();
  });

  it("disabled option disable radio", () => {
    render(
      <AppRadioGroup
        options={[{ value: "a", label: "A", disabled: true }]}
        value="a"
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("radio", { name: "A" })).toBeDisabled();
  });
});
