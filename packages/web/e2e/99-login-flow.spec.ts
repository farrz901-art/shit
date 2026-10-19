// 登录流程 E2E (2026-06-17 自测)
// 验证: 登录后 UserMenu 从 anon "登录" 按钮 → display_name (账号用户下拉).
// 修复核心: loginAction 走 server-side redirect() 强制 layout 重跑 /me 拿用户信息.
// (2026-06-17) 历史 bug: client router.push/refresh 不会重跑 [locale] layout 的 apiFetch("/me").
import { expect, test } from "@playwright/test";

const TEST_EMAIL = "fengkai@citws.com";
const TEST_PASSWORD = "deyuan888";

test("登录成功 → 跳到 /zh + UserMenu 显示 display_name (Deyuan) + 不再显示登录按钮", async ({
  page,
}) => {
  // 1. 进 /zh/login, 应该看到登录按钮 (anon)
  await page.goto("/zh/login");
  await expect(page.getByTestId("user-menu-login"), "匿名时应有登录按钮").toBeVisible();

  // 2. 填表
  await page.getByTestId("email-input").fill(TEST_EMAIL);
  await page.getByTestId("password-input").fill(TEST_PASSWORD);

  // 3. 点击登录 (server action 走 server-side redirect, 全页 reload)
  await page.getByTestId("login-submit").click();

  // 4. 等导航完成 (redirect 目标 = next, 默认 /, 走 next-intl 变 /zh)
  await page.waitForURL(/\/zh(?:\/|$)/, { timeout: 15_000 });

  // 5. UserMenu 应该不再显示 "登录" 按钮, 改显示 user-menu (display_name 下拉)
  await expect(page.getByTestId("user-menu-login"), "登录后不应再有登录按钮").not.toBeVisible({
    timeout: 5000,
  });
  await expect(page.getByTestId("user-menu"), "登录后应显示用户下拉菜单").toBeVisible({
    timeout: 5000,
  });

  // 6. user-menu 的按钮文字应该是 display_name (后端 accounts 表里 Deyuan) 或 email
  const userMenuText = await page.getByTestId("user-menu").textContent();
  expect(userMenuText, `user-menu 应包含 display_name 或 email, 实际: ${userMenuText}`).toMatch(
    /Deyuan|fengkai@citws\.com/,
  );
});
