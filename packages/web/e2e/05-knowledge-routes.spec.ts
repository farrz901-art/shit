import { expect, test } from "@playwright/test";

test.describe("knowledge routes", () => {
  test("1. /knowledge 重定向到 /knowledge/documents", async ({ page }) => {
    await page.goto("/knowledge");
    await expect(page).toHaveURL(/\/knowledge\/documents/);
  });

  test("2. 点知识图谱 tab → URL 跳 /knowledge/graph, heading visible", async ({ page }) => {
    await page.goto("/knowledge/documents");
    await page.click('[data-testid="tab-graph"]');
    await expect(page).toHaveURL(/\/knowledge\/graph/);
    await expect(page.getByRole("heading", { name: /知识图谱/ })).toBeVisible();
  });

  test("3. 浏览器后退回 /knowledge/documents, 不重请求", async ({ page }) => {
    await page.goto("/knowledge/documents");
    await page.click('[data-testid="tab-graph"]');
    await page.goBack();
    await expect(page).toHaveURL(/\/knowledge\/documents/);
  });

  test("4. 直连 /knowledge/graph 显示知识图谱, 不经 redirect", async ({ page }) => {
    await page.goto("/knowledge/graph");
    await expect(page).toHaveURL(/\/knowledge\/graph/);
    await expect(page.getByRole("heading", { name: /知识图谱/ })).toBeVisible();
  });

  test("5. tab-documents active 高亮 (border-clay class)", async ({ page }) => {
    await page.goto("/knowledge/documents");
    const tab = page.getByTestId("tab-documents");
    await expect(tab).toHaveClass(/border-clay/);
  });

  test("6. 点数据集数卡 → URL 跳 /knowledge/datasets, heading visible", async ({ page }) => {
    await page.goto("/knowledge/documents");
    await page.click('a[href="/knowledge/datasets"]');
    await expect(page).toHaveURL(/\/knowledge\/datasets/);
    await expect(page.getByRole("heading", { name: /数据集/ })).toBeVisible();
  });

  test("7. 点文档数卡 → URL 跳 /knowledge/dataset-documents/:id, heading visible", async ({
    page,
  }) => {
    await page.goto("/knowledge/documents");
    const docLink = page.locator('a[href*="/knowledge/dataset-documents/"]');
    await docLink.click();
    await expect(page).toHaveURL(/\/knowledge\/dataset-documents\//);
    await expect(page.getByRole("heading")).toBeVisible();
  });
});
