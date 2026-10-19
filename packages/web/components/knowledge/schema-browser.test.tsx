import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { SchemaBrowser } from "./schema-browser";
import { useState } from "react";

// 测行为: 打开 dialog → 调 schema 端点 → 渲染 schema 内容
// 不再断言 URL/headers (apiFetch 内部实现)
// eslint-disable-next-line arrow-body-style -- 需要显式 return 配合 as 类型转换
const okResponse = (data: unknown): Response => {
  const resp = {
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  };
  return resp as unknown as Response;
};

const mockSchema = {
  nodes: [
    { fields: [{ key: "model", label: "型号", required: true, type: "string" }], name: "Product" },
  ],
  relations: [{ cardinality: "many_to_one", from: "Product", name: "BELONGS_TO", to: "Series" }],
};

const Wrapper = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} data-testid="schema-browser-trigger">
        ?
      </button>
      <SchemaBrowser open={open} onOpenChange={setOpen} />
    </>
  );
};

describe("SchemaBrowser", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(okResponse(mockSchema)) as unknown as typeof fetch;
  });

  it("点击 trigger 后加载并渲染 schema", async () => {
    render(<Wrapper />);
    fireEvent.click(screen.getByTestId("schema-browser-trigger"));
    await waitFor(() => expect(screen.getByText(/Schema 浏览器/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Product")).toBeInTheDocument());
    expect(screen.getByText(/BELONGS_TO/)).toBeInTheDocument();
  });
});
