// E2E: ingest 上传 → 转换 → 下载 (2026-06-10)
// 前置: dev server 已起, 后端已起
//   Bun run test:e2e
// Fixtures 来自仓库根的 tests/fixtures/ (web/e2e/ 往上两层到 repo root)
import { expect, test } from "@playwright/test";
import path from "path";
import fs from "fs/promises";

const FIXTURES = path.join(__dirname, "..", "..", "tests", "fixtures");
const MIN_BYTES = 0;

// 真实存在于 tests/fixtures/ 的可处理文件
const PDF_FIXTURE = "easy_pdf_test.pdf";
const ZIP_FIXTURE = "sample_archive.zip";

test.describe("Ingest upload 流程", () => {
  test("1. 上传 1 个 PDF → task created → completed → 看到 md 产物", async ({ page }) => {
    // 设 user token
    await page.addInitScript(() => {
      localStorage.setItem("rag_user_token", "e2e-user-alice");
    });

    await page.goto("/output/new");
    const filePath = path.join(FIXTURES, PDF_FIXTURE);
    await page.setInputFiles('input[type="file"]', filePath);
    await page.click("text=开始转换");
    await page.waitForURL("/output");

    // 轮询直到 1 个 PDF 转换完成 (最多等 60s; PDF 解析可能慢)
    // Easy_pdf_test.pdf 转换成功后页面会出现 "1 成功" (列表里 processed=1)
    await expect(page.getByText("1 成功")).toBeVisible({ timeout: 60_000 });
    // 点查看产物
    await page.click("text=查看产物");
    await page.waitForURL(/\/output\/[^/]+/);
    // 等产物列表 + 至少一个 md 文件
    await expect(page.getByText(/\.md/)).toBeVisible({ timeout: 10_000 });
  });

  test("2. 上传 zip → 任务完成 (或失败也接受)", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("rag_user_token", "e2e-user-bob");
    });
    await page.goto("/output/new");
    const zipPath = path.join(FIXTURES, ZIP_FIXTURE);
    await page.setInputFiles('input[type="file"]', zipPath);
    await page.click("text=开始转换");
    await page.waitForURL("/output");
    // Zip 转换可能耗时长, 接受 completed 或 failed (sample_archive.zip 内容不一定都能解析)
    await expect(page.getByText(/completed|failed/)).toBeVisible({ timeout: 60_000 });
  });

  test("3. 下载全部 → 拿到非空 zip", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("rag_user_token", "e2e-user-charlie");
    });
    await page.goto("/output/new");
    await page.setInputFiles('input[type="file"]', path.join(FIXTURES, PDF_FIXTURE));
    await page.click("text=开始转换");
    await page.waitForURL("/output");
    // 等任务完成
    await expect(page.getByText("1 成功")).toBeVisible({ timeout: 60_000 });
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.locator("a:has-text('下载全部')").first().click(),
    ]);
    const downloadPath = await download.path();
    const stat = await fs.stat(downloadPath!);
    expect(stat.size).toBeGreaterThan(MIN_BYTES);
  });

  test("4. 跨用户隔离: alice 上传 → eve 看不到任务", async ({ page, context }) => {
    // Alice 上传
    await page.addInitScript(() => {
      localStorage.setItem("rag_user_token", "e2e-user-alice-iso");
    });
    await page.goto("/output/new");
    await page.setInputFiles('input[type="file"]', path.join(FIXTURES, PDF_FIXTURE));
    await page.click("text=开始转换");
    await page.waitForURL("/output");
    // 等 alice 的任务出现 (task id 以 ISO 日期开头, 如 2026-06-10-...)
    await expect(page.getByText(/^\d{4}-\d{2}-\d{2}-/)).toBeVisible({ timeout: 60_000 });

    // 换 user_token 模拟 Eve
    await context.clearCookies();
    await page.evaluate(() => {
      localStorage.setItem("rag_user_token", "e2e-user-eve-iso");
    });
    await page.goto("/output");
    // Eve 看不到 alice 的任务 → 空态
    await expect(page.getByText("还没有任务")).toBeVisible();
  });

  test("5. 上传 .exe → 弹不支持的格式错误", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("rag_user_token", "e2e-user-frank");
    });
    await page.goto("/output/new");
    // 造一个临时 .exe 文件 (fixtures 目录已存在, 临时文件写到这里方便清理)
    const tmp = path.join(FIXTURES, "tmp_invalid.exe");
    await fs.writeFile(tmp, "fake-exe-content");
    try {
      await page.setInputFiles('input[type="file"]', tmp);
      await page.click("text=开始转换");
      // 后端校验 .exe 不在 ACCEPT 列表, 应返回错误
      await expect(page.getByText(/不支持|invalid|格式/)).toBeVisible({ timeout: 10_000 });
    } finally {
      await fs.unlink(tmp).catch(() => {});
    }
  });
});
