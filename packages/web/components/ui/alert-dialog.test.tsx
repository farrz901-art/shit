// AlertDialog 组件单测
import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogTrigger,
} from "./alert-dialog";

describe("AlertDialog", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <AlertDialog>
        <AlertDialogTrigger>打开</AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogAction>确定</AlertDialogAction>
          <AlertDialogCancel>取消</AlertDialogCancel>
        </AlertDialogContent>
      </AlertDialog>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
