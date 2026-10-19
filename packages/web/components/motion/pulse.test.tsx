import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Pulse } from "./pulse";

describe("Pulse", () => {
  it("渲染子元素", () => {
    const { container } = render(<Pulse>加载中…</Pulse>);
    expect(container.textContent).toBe("加载中…");
  });
});
