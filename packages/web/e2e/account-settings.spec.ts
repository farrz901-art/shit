// 账号设置 e2e (5 case)
// 跟现有 e2e 同模式 (Playwright + chromium)
// 假设 dev 模式 + seed 了一个测试账号 (用 E2E_TEST_TOKEN / E2E_TEST_PASSWORD env 注入)
import { expect, test } from "@playwright/test";

test.describe("账号设置", () => {
  test.beforeEach(async ({ context }) => {
    // 假设已 seed 账号, 用 env 注入 token
    await context.addCookies([
      {
        domain: "localhost",
        name: "rag_user_token",
        path: "/",
        value: process.env.E2E_TEST_TOKEN ?? "",
      },
    ]);
  });

  test("设置页加载 + 4 section 显示", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await expect(page.getByTestId("profile-section")).toBeVisible();
    await expect(page.getByTestId("email-section")).toBeVisible();
    await expect(page.getByTestId("password-section")).toBeVisible();
    await expect(page.getByTestId("deletion-section")).toBeVisible();
  });

  test("改昵称后 UserMenu 显示新昵称", async ({ page }) => {
    await page.goto("/zh/account/settings");
    const newName = `test_${Date.now()}`;
    await page.getByTestId("profile-display-name").fill(newName);
    await page.getByTestId("profile-save").click();
    await expect(page.getByText(newName).first()).toBeVisible({ timeout: 5000 });
  });

  test("改邮箱 dialog 打开 + 显示 verification URL (dev mode)", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("email-change-button").click();
    await expect(page.getByTestId("change-email-dialog")).toBeVisible();
    await page.getByTestId("email-new").fill("newemail@example.com");
    await page.getByTestId("email-current-password").fill(process.env.E2E_TEST_PASSWORD ?? "");
    await page.getByTestId("email-submit").click();
    // Dev mode 应返 verification_url
    await expect(page.getByTestId("email-verification-url")).toBeVisible({ timeout: 5000 });
  });

  test("改密码 dialog 打开 + 3 输入框", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("password-change-button").click();
    await expect(page.getByTestId("change-password-dialog")).toBeVisible();
    await expect(page.getByTestId("password-current")).toBeVisible();
    await expect(page.getByTestId("password-new")).toBeVisible();
    await expect(page.getByTestId("password-confirm")).toBeVisible();
  });

  test("申请注销 dialog 打开 + 显示 confirm_text 提示", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("deletion-request-button").click();
    await expect(page.getByTestId("request-deletion-dialog")).toBeVisible();
    await expect(page.getByTestId("deletion-current-password")).toBeVisible();
    await expect(page.getByTestId("deletion-confirm-text")).toBeVisible();
    await expect(page.getByTestId("deletion-submit")).toBeVisible();
  });
});
