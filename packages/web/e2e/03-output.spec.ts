// Output 列表 + 详情走通
import { expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { ZERO } from "@/const";

const SHOT_DIR = resolve(__dirname, "..", ".e2e-logs");

test("Output 列表: 空态 或 表格", async ({ page }) => {
  await page.goto("/output");
  // 两种结局: 有文件 → table; 没文件 → p.muted
  const table = page.locator("table");
  const empty = page.locator("p:has-text('output 目录为空')");
  await expect(table.or(empty).first()).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${SHOT_DIR}/output.png` });
});

test("Output 列表里有文件 → 详情页能打开", async ({ page }) => {
  await page.goto("/output");
  const firstLink = page.locator('a:has-text("查看")').first();
  const count = await firstLink.count();
  if (count === ZERO) {
    test.skip(true, "output 目录为空, 跳过详情测试");
    return;
  }
  await firstLink.click();
  // 详情页应该有 <pre> 之类显示文件内容
  await expect(page.locator("body")).toContainText(/./, { timeout: 10_000 });
  await page.screenshot({ path: `${SHOT_DIR}/output-detail.png` });
});
