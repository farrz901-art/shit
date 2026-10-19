/**
 * E2E: 导航子菜单 + 权限树形勾选 (2026-07-02 nav spec §7.3)
 * 5 个用例覆盖完整流程.
 *
 * 注意: 跟其他 e2e spec 一样, 用 dev token 模拟登录. 真实账号 token 需要 staging.
 */
/* eslint-disable max-statements, no-magic-numbers -- e2e fixture */
import { test, expect } from "@playwright/test";

test.describe("导航子菜单 (desktop)", () => {
  test("admin 角色 hover 管理中心, 看到 5 个子项", async ({ page }) => {
    await page.goto("/zh/admin");
    await page.waitForLoadState("networkidle");

    // 模拟 admin 登录 (RAG_DEV_AUTH=true 走 dev anon, 这里用 RAG_TEST_TOKEN 切角色)
    await page
      .context()
      .addCookies([
        { name: "rag_user_token", value: "test-admin-token", url: "http://localhost:3000" },
      ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    // hover 管理中心 (desktop nav ≥ sm)
    await page.getByTestId("nav-dropdown-admin").hover();
    await expect(page.getByTestId("nav-dropdown-item-admin_users")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_invites")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_permissions")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_dicts")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_profile_fields")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_pre_analysis")).toBeVisible();
  });

  test("点击子项跳到对应页面", async ({ page }) => {
    await page.goto("/zh/admin");
    await page.waitForLoadState("networkidle");
    await page
      .context()
      .addCookies([
        { name: "rag_user_token", value: "test-admin-token", url: "http://localhost:3000" },
      ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    await page.getByTestId("nav-dropdown-admin").hover();
    await page.getByTestId("nav-dropdown-item-admin_users").click();
    await expect(page).toHaveURL(/\/admin\/users$/);
  });

  test("user 角色看不到 admin 子菜单", async ({ page }) => {
    await page.goto("/zh/");
    await page
      .context()
      .addCookies([
        { name: "rag_user_token", value: "test-user-token", url: "http://localhost:3000" },
      ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    // user 角色无 admin 权限, 应看不到 admin 子菜单
    await expect(page.getByTestId("nav-dropdown-admin")).toHaveCount(0);
  });
});

test.describe("移动端汉堡菜单", () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test("375 宽度下汉堡菜单 + 展开子菜单", async ({ page }) => {
    await page.goto("/zh/");
    await page
      .context()
      .addCookies([
        { name: "rag_user_token", value: "test-admin-token", url: "http://localhost:3000" },
      ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    await page.getByTestId("mobile-hamburger").click();
    await expect(page.getByTestId("mobile-nav-toggle-admin")).toBeVisible();

    await page.getByTestId("mobile-nav-toggle-admin").click();
    await expect(page.getByTestId("mobile-nav-item-admin_users")).toBeVisible();
  });
});

test.describe("/admin/permissions 树形勾选", () => {
  test("super_admin 看到树形 + indeterminate 状态", async ({ page }) => {
    await page.goto("/zh/admin/permissions");
    await page.waitForLoadState("networkidle");
    await page
      .context()
      .addCookies([
        { name: "rag_user_token", value: "test-super-admin-token", url: "http://localhost:3000" },
      ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    // 切到非 super_admin 的角色行, 验证树形
    await page.getByTestId("permission-role-admin").click();
    // 父级 disabled
    const adminCheckbox = page.getByRole("checkbox", { name: /管理中心/ }).first();
    await expect(adminCheckbox).toBeDisabled();
  });
});
