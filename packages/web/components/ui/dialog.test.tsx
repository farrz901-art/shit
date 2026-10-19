// Dialog 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Dialog, DialogContent, DialogTrigger } from "./dialog";

describe("Dialog", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <Dialog>
        <DialogTrigger>打开</DialogTrigger>
        <DialogContent>弹窗内容</DialogContent>
      </Dialog>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
