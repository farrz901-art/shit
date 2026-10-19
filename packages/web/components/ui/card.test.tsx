import { describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Card, CardContent, CardHeader, CardTitle } from "./card";

describe("Card", () => {
  it("渲染无报错", () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>标题</CardTitle>
        </CardHeader>
        <CardContent>内容</CardContent>
      </Card>,
    );
    expect(container.firstChild).toBeInTheDocument();
  });
});
