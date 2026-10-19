import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("渲染无报错", () => {
    const { container } = render(<Skeleton className="h-10 w-40" />);
    expect(container.firstChild).toBeInTheDocument();
  });
});
