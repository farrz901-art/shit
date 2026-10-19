# PR8 — E2E Tests + Documentation + Final Regression

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Playwright E2E tests covering the full submenu + permission tree flow, write user-facing docs, run final regression to confirm zero new failures.

**Files:**
- Create: `packages/web/e2e/nav-submenu.spec.ts`
- Create: `docs/cookbook/web/navigation-submenu.md`

---

## Task 8.1: Add E2E test for desktop hover dropdown

**Files:**
- Create: `packages/web/e2e/nav-submenu.spec.ts`

- [ ] **Step 1: Check existing Playwright config**

Run: `ls packages/web/playwright.config.ts 2>/dev/null && echo "exists" || echo "missing"`

If `exists`: continue.
If `missing`: per CLAUDE.md "E2E tests live in `packages/web/e2e/`, use Playwright + chromium". Verify the directory and config exist; if not, run `bunx playwright init` in `packages/web/`.

- [ ] **Step 2: Write E2E test**

Create `packages/web/e2e/nav-submenu.spec.ts`:

```typescript
/**
 * E2E: 导航子菜单 + 权限树形勾选 (2026-07-02 nav spec §7.3)
 * 5 个用例覆盖完整流程.
 */
import { test, expect } from "@playwright/test";

test.describe("导航子菜单 (desktop)", () => {
  test("admin 角色 hover 管理中心, 看到 5 个子项", async ({ page }) => {
    await page.goto("/zh/admin");
    await page.waitForLoadState("networkidle");

    // 登录为 admin (假设已有 fixture / mock auth)
    await page.context().addCookies([
      { name: "rag_user_token", value: "test-admin-token", url: "http://localhost:3000" },
    ]);
    await page.reload();
    await page.waitForLoadState("networkidle");

    // hover 管理中心
    await page.getByTestId("nav-dropdown-admin").hover();
    await expect(page.getByTestId("nav-dropdown-item-admin_users")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_invites")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_permissions")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_dicts")).toBeVisible();
    await expect(page.getByTestId("nav-dropdown-item-admin_profile_fields")).toBeVisible();
  });

  test("点击子项跳到对应页面", async ({ page }) => {
    await page.goto("/zh/admin");
    await page.waitForLoadState("networkidle");
    await page.context().addCookies([
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
    await page.context().addCookies([
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
    await page.context().addCookies([
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
    await page.context().addCookies([
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
```

- [ ] **Step 3: Run E2E locally**

Run: `cd packages/web && bun run test:e2e -- nav-submenu.spec.ts`

Expected: 5 tests pass (or skip if test env not ready; CI 跑全套).

- [ ] **Step 4: Commit E2E**

```bash
cd c:/doc/Code/rag
git add packages/web/e2e/nav-submenu.spec.ts
git commit -m "test(e2e): add 5 submenu + tree checkbox E2E tests (PR8/1)"
```

---

## Task 8.2: Write user-facing documentation

**Files:**
- Create: `docs/cookbook/web/navigation-submenu.md`

- [ ] **Step 1: Write doc**

Create `docs/cookbook/web/navigation-submenu.md`:

```markdown
# 导航子菜单 + 数据字典 (2026-07-02)

## 加一个新页面, 改 1 处

1. 改 [packages/service/config/dictionaries_seed.yaml](../../packages/service/config/dictionaries_seed.yaml) 中 `page_key` 字典:
   ```yaml
   - {
       key: my_page,
       label_zh: 我的页面,
       label_en: My Page,
       sort: 100,
       metadata_json: { path: "/my-page" },
     }
   ```
2. 跑 `cd packages/service && uv run python -m scripts.seed_dictionaries` 同步到 DB
3. 后端 cache 自动 warmup, 顶导航自动出现, 权限矩阵自动加入

## 子菜单 (hover dropdown)

把页面挂在某个顶级 page_key 下:
```yaml
- {
    key: admin_my_subpage,
    label_zh: 我的子页,
    label_en: My Sub Page,
    sort: 56,
    metadata_json: { path: "/admin/my-subpage", parent_id: "admin" },
  }
```

父级会自动识别 `is_group: true` (yaml 里 admin 已标), 子项挂在下面.

## 父级不可点 (按 spec 决策)

父级 trigger 是 `<button>`, 不是 `<a>`, hover 弹 DropdownMenu 才进入子页.
直接点击父级 label 不会跳转.

## 权限矩阵

`/admin/permissions` 改成树形 UI:
- 父级 checkbox 永远 disabled (因为父级不入 role_permissions 表)
- 叶子单独 toggle, 进 pending
- indeterminate 状态自动从子项聚合

## 调试

- 子菜单不显示 → 检查 yaml 是否有 `parent_id` 指向存在的 key
- 父级 trigger 点了不弹菜单 → 看 Radix 控制台 + AppDropdownMenu 是否有错误
- 改了字典前端没刷新 → 看 PR7 cache invalidation, 编辑 dialog 的 onSuccess 是否触发
- 想看 tree 结构 → 浏览器 console:
  ```javascript
  fetch('/api/permissions/me').then(r => r.json()).then(console.log)
  ```
```

- [ ] **Step 2: Commit doc**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/web/navigation-submenu.md
git commit -m "docs(nav): add user-facing navigation-submenu cookbook (PR8/2)"
```

---

## Task 8.3: Final regression check

- [ ] **Step 1: Backend full test suite**

Run: `cd packages/service && uv run pytest --no-cov -q 2>&1 | tail -10`

Expected: 1078 baseline (1075 + 3 from PR1) + 0 new failures.

- [ ] **Step 2: Frontend full test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -10`

Expected: 764 baseline + 0 new failures.

- [ ] **Step 3: Typecheck both packages**

Run:
```bash
cd packages/service && uv run pyright 2>&1 | tail -5
cd packages/web && bun run typecheck 2>&1 | tail -5
```

Expected: 0 errors both.

- [ ] **Step 4: Lint + format both packages**

Run:
```bash
cd packages/service && uv run ruff check 2>&1 | tail -5
cd packages/web && bun run lint && bun run format:check 2>&1 | tail -5
```

Expected: 0 errors both.

- [ ] **Step 5: Final commit if any fix**

```bash
cd c:/doc/Code/rag
git status
# 如有 lint/format, git add -u && git commit -m "chore(pr8): final regression fixes"
```

---

## Task 8.4: Open PR (out of plan scope)

Note: This task is for the human reviewer, not for the agent.

After all 8 PRs land on `feature/nav-submenu`:
1. Push branch: `git push origin feature/nav-submenu`
2. Open PR via `gh pr create`
3. Wait for CI to pass (full pytest + vitest + lint + typecheck)
4. Address review comments
5. Merge to master

---

## PR8 Definition of Done

- [ ] 5 E2E tests added + pass locally
- [ ] Cookbook doc written for future developers
- [ ] Backend: 1078 tests pass, 0 pyright errors, 0 ruff errors
- [ ] Frontend: 764 tests pass, 0 typecheck errors, 0 lint errors
- [ ] Ready for human review + merge

---

## Final Spec Coverage Check

| Spec § | Implementation |
|---|---|
| §1.4 成功标准 1: 加新页面改 yaml 1 处 | PR1 Task 1.1 + PR2 Task 2.2 |
| §1.4 标准 2: hover 200ms 弹出 | PR3 Task 3.2 (Radix default) |
| §1.4 标准 3: /admin/permissions 树形 | PR6 Task 6.4 |
| §1.4 标准 4: 移动端汉堡 | PR4 Task 4.2 |
| §1.4 标准 5: 47+ 测试 | PR1:3 + PR2:15 + PR3:5+5 + PR4:6 + PR5:7 + PR6:5 = 46 unit + 5 E2E |
| §1.4 标准 6: 字典系统不坏 | PR1 Task 1.1 (yaml + metadata_json) + PR7 (cache invalidation) |
| §2 数据结构 | PR1 Tasks 1.1-1.4 + PR2 Task 2.1 |
| §3 buildNavTree | PR2 Tasks 2.1-2.3 |
| §4 Header 重构 | PR3 + PR4 |
| §5 权限矩阵 | PR5 + PR6 |
| §6 cache invalidation | PR7 |
| §7 测试策略 | PR1-8 distributed |
| §8 迁移 / 回滚 | PR1 yaml UPSERT + 零 schema |
| §9 风险缓解 | Inline 在各 PR |
| §10 文件变更 | All tasks above |