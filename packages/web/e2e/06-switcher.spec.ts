// Switcher E2E: 验证 DatasetSwitcher / DomainSwitcher 真实 API 对接
// 关键: 这些测试依赖后端 uvicorn 在运行, 且 Dify / Neo4j 可达
import { expect, test } from "@playwright/test";
import { ZERO } from "@/const";

const SHOT_DIR = "e2e/.e2e-logs";

test.describe("DatasetSwitcher (向量库侧)", () => {
  test("下拉框有值, 点开能看到 dataset 列表", async ({ page }) => {
    await page.goto("/knowledge/documents");

    // 等 trigger 渲染 (testid=dataset-switcher 在 layout ActiveSwitch 中)
    const trigger = page.getByTestId("dataset-switcher");
    await expect(trigger).toBeVisible({ timeout: 10_000 });

    // 点开下拉框
    await trigger.click();

    // 验证下拉列表有真实数据 (Dify 返回的 dataset 名)
    // SelectItem 渲染为 role=option
    const options = page.getByRole("option");
    const count = await options.count();
    expect(count, "dataset 下拉选项数").toBeGreaterThan(ZERO);

    // 截图记录
    await page.screenshot({ path: `${SHOT_DIR}/dataset-switcher-open.png` });
  });
});

test.describe("DomainSwitcher (知识图谱侧)", () => {
  test("下拉框有值, 点开能看到 domain 列表", async ({ page }) => {
    await page.goto("/knowledge/graph");

    // 等 trigger 渲染
    const trigger = page.getByTestId("domain-switcher");
    await expect(trigger).toBeVisible({ timeout: 10_000 });

    // 点开下拉框
    await trigger.click();

    // 验证下拉列表有真实数据 (schemas 目录下的 domain)
    const options = page.getByRole("option");
    const count = await options.count();
    expect(count, "domain 下拉选项数").toBeGreaterThan(ZERO);

    await page.screenshot({ path: `${SHOT_DIR}/domain-switcher-open.png` });
  });
});
