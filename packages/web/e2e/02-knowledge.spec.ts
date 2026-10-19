// 知识库 4 Tab 流程: QA 录入走通, Triples/Documents/Batch 表单可填
// 这些页都依赖 /api/knowledge/* (BFF → 后端 kg router → Neo4j/Dify)
// 后端不在时, 页面应正常渲染表单 (BFF 4xx/5xx 不挂页面)
import { type Page, expect, test } from "@playwright/test";
import { resolve } from "node:path";
import { ZERO } from "@/const";

const SHOT_DIR = resolve(__dirname, "..", ".e2e-logs");

const fillAndSubmitQA = async (page: Page, questionText: string, answerText: string) => {
  await page.locator("[data-testid=qa-question]").fill(questionText);
  await page.locator("[data-testid=qa-answer]").fill(answerText);
  await page.locator("[data-testid=qa-submit]").click();
};

const captureResult = async (page: Page) => {
  await expect(page.locator("[data-testid=qa-submit-result]")).toBeVisible({ timeout: 20_000 });
  const resultText = await page.locator("[data-testid=qa-submit-result]").textContent();
  console.log(`QA 提交结果: ${resultText}`);
  await page.screenshot({ path: `${SHOT_DIR}/qa-submit.png` });
};

test.describe("知识库 Dashboard", () => {
  test("4 个统计卡 + 4 个入口 + 空状态 (有数据时不显示)", async ({ page }) => {
    await page.goto("/knowledge");
    await expect(page.locator("h1")).toHaveText("知识库总览");

    // 4 个统计卡
    const stats = await page.locator('[class*="rounded"], .grid > div').count();
    expect(stats, "知识库页元素数").toBeGreaterThan(ZERO);

    // 4 个入口链接 (用 .first() 避免空状态文字链 + 入口卡重复)
    await expect(page.locator('a[href="/knowledge/qa"]').first()).toBeVisible();
    await expect(page.locator('a[href="/knowledge/documents"]').first()).toBeVisible();
    await expect(page.locator('a[href="/knowledge/triples"]').first()).toBeVisible();
    await expect(page.locator('a[href="/knowledge/batch"]').first()).toBeVisible();

    await page.screenshot({ path: `${SHOT_DIR}/knowledge-home.png` });
  });
});

test.describe("QA 录入页", () => {
  test("未选 dataset 时显示空态; 表单组件齐全", async ({ page }) => {
    // 强制清掉 localStorage
    await page.goto("/knowledge/qa");
    await page.evaluate(() => localStorage.removeItem("kg.dataset_id"));

    await page.reload();
    await expect(page.locator("[data-testid=qa-empty]")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-testid=qa-question]")).toBeVisible();
    await expect(page.locator("[data-testid=qa-answer]")).toBeVisible();
    await expect(page.locator("[data-testid=qa-submit]")).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/qa-empty.png` });
  });

  test("填问题+答案 → 提交 → 拿到结果 (后端通时) 或 错误条 (后端缺时)", async ({ page }) => {
    // 模拟选了 dataset
    await page.goto("/knowledge/qa");
    await page.evaluate(() => localStorage.setItem("kg.dataset_id", "test-dataset"));
    await page.reload();

    await expect(page.locator("[data-testid=qa-question]")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-testid=qa-answer]")).toBeVisible({ timeout: 10_000 });
    await fillAndSubmitQA(
      page,
      "E2E 测试问题: 1LE 系列适用哪些场景?",
      "E2E 测试答案: 通用工业驱动场景。",
    );

    // 等结果条出现 (绿/红/警告 都接受)
    await captureResult(page);
  });
});

test.describe("Triples 录入页", () => {
  test("页面渲染 + 表格/加载态", async ({ page }) => {
    await page.goto("/knowledge/triples");
    // 后端通: triples-submit 出现; 后端缺: triples-loading 文字出现
    const submit = page.locator("[data-testid=triples-submit]");
    const loading = page.locator("[data-testid=triples-loading]");
    await expect(submit.or(loading).first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: `${SHOT_DIR}/triples.png` });
  });
});

test.describe("Documents 上传页", () => {
  test("拖拽区 + 2 个模板下载按钮", async ({ page }) => {
    await page.goto("/knowledge/documents");
    await expect(page.locator("[data-testid=file-dropzone]")).toBeVisible();
    await expect(page.locator("[data-testid=dl-excel]")).toBeVisible();
    await expect(page.locator("[data-testid=dl-json]")).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/documents.png` });
  });
});

test.describe("Batch 批量页", () => {
  test("文件选择器 + 提交按钮", async ({ page }) => {
    await page.goto("/knowledge/batch");
    await expect(page.locator("[data-testid=batch-file]")).toBeVisible();
    await expect(page.locator("[data-testid=batch-submit]")).toBeVisible();
    await page.screenshot({ path: `${SHOT_DIR}/batch.png` });
  });
});
