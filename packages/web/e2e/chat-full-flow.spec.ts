/** E2E: 智能体聊天全流程 (2026-06-24)
 *
 * 覆盖 3 大场景:
 *   1. Anon 流程: 发消息 → IDB 落盘 → 刷新保留
 *   2. Login 流程: 登录 → 发消息 → 服务端 conv 创建 → 刷新保留
 *   3. Memory 接口: 监听 BFF 内部 fetch, 验证 /api/memory/search + /api/memory/add 被调用
 *
 * 跑法: 1 worker 串行 (复用 dev server), 预计 60-90s.
 *
 * Lint 警告集中处理: e2e 文件跨多个场景, max-statements / id-length / magic-numbers
 * 在 Playwright 串行用例里难控; file-level oxlint-disable 集中跳过, 保留 tsgo 类型保护.
 */
/* oxlint-disable */
import { expect, test, type Page } from "@playwright/test";

const TEST_EMAIL = "test123@qq.com";
const TEST_PASSWORD = "12345678";

const ZERO_COUNT = 0;
const SINGLE_COUNT = 1;
const ANON_TEXT = "E2E anon test message";
const LOGIN_TEXT = "E2E login test message";
const TIMEOUT_LONG_MS = 20000;
const TIMEOUT_NAV_MS = 15000;
const TIMEOUT_SHORT_MS = 5000;
const TIMEOUT_MEMORY_MS = 30000;
const TIMEOUT_RELOAD_MS = 10000;
const TIMEOUT_TOAST_MS = 10000;
const TIMEOUT_CLEAR_MS = 5000;
const TIMEOUT_DIFY_LONG_MS = 60000;
const MEMORY_POST_LLM_WAIT_MS = 1000;
const TYPE_DELAY_MS = 20;

type IdbConv = { id: string; messageCount: number; owner: string; title: string };
type ServerConv = { id: string; message_count: number; title: string };

const clearAnonState = async (page: Page): Promise<void> => {
  await page.goto("/zh/chat");
  await page.evaluate(async () => {
    const databases = await indexedDB.databases();
    for (const dbInfo of databases) {
      const name = dbInfo.name;
      if (name) {
        await new Promise<void>((resolve) => {
          const req = indexedDB.deleteDatabase(name);
          req.onsuccess = () => resolve();
          req.onerror = () => resolve();
          req.onblocked = () => resolve();
        });
      }
    }
    localStorage.removeItem("rag.chat.anon-user-id.v1");
    localStorage.removeItem("rag.chat.migration.last-fired.v1");
  });
};

const readIdbConversations = async (
  page: Page,
  ownerFilter: "anon" | "imported",
): Promise<IdbConv[]> => {
  return page.evaluate(async (ownerArg) => {
    return new Promise<IdbConv[]>((resolve) => {
      const req = indexedDB.open("rag-chat");
      req.onsuccess = () => {
        const db = req.result;
        const tx = db.transaction("conversations", "readonly");
        const store = tx.objectStore("conversations");
        const idx = store.index("owner");
        const getReq = idx.getAll(ownerArg);
        getReq.onsuccess = () => {
          const list = (getReq.result as IdbConv[]) ?? [];
          resolve(
            list.map((c) => ({
              id: c.id,
              messageCount: c.messageCount,
              owner: c.owner,
              title: c.title,
            })),
          );
        };
        getReq.onerror = () => resolve([]);
      };
      req.onerror = () => resolve([]);
    });
  }, ownerFilter);
};

const readServerConversations = async (page: Page): Promise<ServerConv[]> => {
  return page.evaluate(async () => {
    const r = await fetch("/api/chat/conversations", { credentials: "include" });
    if (!r.ok) {
      return [];
    }
    return (await r.json()) as ServerConv[];
  });
};

const clearServerConversations = async (page: Page): Promise<void> => {
  await page.evaluate(async () => {
    const r = await fetch("/api/chat/conversations", { credentials: "include" });
    const convs = (await r.json()) as { id: string }[];
    for (const c of convs) {
      await fetch(`/api/chat/conversations/${c.id}`, {
        credentials: "include",
        method: "DELETE",
      });
    }
  });
};

const trackMemoryCalls = (page: Page): { get: () => { url: string; status: number }[] } => {
  const calls: { url: string; status: number }[] = [];
  const handler = (response: { url: () => string; status: () => number }) => {
    const url = response.url();
    if (url.includes("/api/memory/")) {
      calls.push({ status: response.status(), url });
    }
  };
  page.on("response", handler);
  return { get: () => calls };
};

const performLogin = async (page: Page): Promise<void> => {
  await page.goto("/zh/login");
  await page.getByTestId("email-input").fill(TEST_EMAIL);
  await page.getByTestId("password-input").fill(TEST_PASSWORD);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/zh(?:\/|$)/, { timeout: TIMEOUT_NAV_MS });
};

/** 等待 Dify 流回复: 消息列表出现 >1 条消息 (user 消息发送后立刻有, 等 assistant 回复). */
const waitForDifyReply = (page: Page, timeoutMs: number) =>
  page
    .locator("[data-testid='message-list'] > :nth-child(2)")
    .waitFor({ state: "visible", timeout: timeoutMs });

/** 等 composer 发送按钮可见 (流结束). */
const waitForSendBtn = (page: Page, timeoutMs: number) =>
  page.getByTestId("composer-send").waitFor({ state: "visible", timeout: timeoutMs });

test.describe("chat 全流程 E2E", () => {
  test.describe.configure({ mode: "serial", timeout: 90_000 });

  // ── Anon 流程 ─────────────────────────────────────

  test("anon #1 进 /zh/chat 不需要登录, 显示 anon UI", async ({ page }) => {
    await clearAnonState(page);
    await page.goto("/zh/chat");
    await expect(page.getByTestId("new-conv")).toBeVisible();
    await expect(page.getByTestId("memory-management-button")).not.toBeVisible();
  });

  test("anon #2 发消息 → IDB 落盘 owner=anon", async ({ page }) => {
    await clearAnonState(page);
    await page.goto("/zh/chat");
    const textarea = page.getByTestId("composer-textarea");
    await textarea.pressSequentially(ANON_TEXT, { delay: TYPE_DELAY_MS });
    const sendBtn = page.getByTestId("composer-send");
    await page.waitForFunction(
      () => {
        const btn = document.querySelector(
          "[data-testid='composer-send']",
        ) as HTMLButtonElement | null;
        return btn !== null && !btn.disabled;
      },
      { timeout: TIMEOUT_SHORT_MS },
    );
    await sendBtn.click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_MEMORY_MS);
    const convs = await readIdbConversations(page, "anon");
    expect(convs.length, "IDB 应有 1 个 anon conv").toBe(SINGLE_COUNT);
    expect(convs[0]?.messageCount ?? 0, "anon conv messageCount >= 1").toBeGreaterThanOrEqual(
      SINGLE_COUNT,
    );
  });

  test("anon #3 刷新页面 → anon conv 仍在", async ({ page }) => {
    await clearAnonState(page);
    await page.goto("/zh/chat");
    await page
      .getByTestId("composer-textarea")
      .pressSequentially(ANON_TEXT, { delay: TYPE_DELAY_MS });
    const sendBtn = page.getByTestId("composer-send");
    await page.waitForFunction(
      () => {
        const btn = document.querySelector(
          "[data-testid='composer-send']",
        ) as HTMLButtonElement | null;
        return btn !== null && !btn.disabled;
      },
      { timeout: TIMEOUT_SHORT_MS },
    );
    await sendBtn.click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    const beforeConvs = await readIdbConversations(page, "anon");
    expect(beforeConvs.length, "发消息后 IDB 应有 1 个 anon conv").toBe(SINGLE_COUNT);

    await page.reload();
    await page
      .locator("[data-testid^='conv-']")
      .first()
      .waitFor({ state: "visible", timeout: TIMEOUT_RELOAD_MS });
  });

  // ── Login 流程 ───────────────────────────────────

  test("login #1 登录成功 → UserMenu 显示 display_name", async ({ page }) => {
    await performLogin(page);
    await expect(page.getByTestId("user-menu"), "登录后应显示 user-menu").toBeVisible({
      timeout: TIMEOUT_SHORT_MS,
    });
  });

  test("login #2 登录态发消息 → 服务端 conv 创建", async ({ context }) => {
    const fresh = await context.browser()!.newContext();
    const page = await fresh.newPage();
    try {
      await performLogin(page);
      await page.goto("/zh/chat");
      await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});

      const meCheck = await page.evaluate(async () => {
        const r = await fetch("/api/account/me", { credentials: "include" });
        if (!r.ok) {
          return { ok: false, status: r.status };
        }
        const me = (await r.json()) as { is_account: boolean };
        return { isAccount: me.is_account, ok: true, status: r.status };
      });
      expect(meCheck.ok, "/api/account/me 应可访问").toBe(true);
      expect(meCheck.isAccount, `登录态应 is_account=true (${JSON.stringify(meCheck)})`).toBe(true);

      await clearServerConversations(page);

      await page
        .getByTestId("composer-textarea")
        .pressSequentially(LOGIN_TEXT, { delay: TYPE_DELAY_MS });
      await page.getByTestId("composer-send").click();

      await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
      await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

      const serverConvs = await readServerConversations(page);
      expect(
        serverConvs.length,
        `登录用户发消息后服务端 conv 列表应 >= 1 (当前 bug: 期望 1, 实际 ${serverConvs.length})`,
      ).toBeGreaterThanOrEqual(SINGLE_COUNT);
    } finally {
      await fresh.close();
    }
  });

  test("login #3 登录态刷新 → 服务端 conv 仍在侧栏", async ({ page }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});
    await page
      .getByTestId("composer-textarea")
      .pressSequentially(LOGIN_TEXT, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

    await page.reload();
    await page
      .locator("[data-testid^='conv-']")
      .first()
      .waitFor({ state: "visible", timeout: TIMEOUT_RELOAD_MS });
  });

  // (2026-06-24) chat-message-persistence: 验证后端真的有 messages 记录, 刷新后 GET /conversations/{id} 能拉回
  test("login #4 登录态刷新后历史消息保留", async ({ page }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});
    await clearServerConversations(page);

    const probeText = "刷新历史保留测试";
    await page
      .getByTestId("composer-textarea")
      .pressSequentially(probeText, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

    // 刷新后等首条 conv 出现 + 点击进入, 验证 user msg 文本还在 (说明后端真存了 messages)
    await page.reload();
    const firstConv = page.locator("[data-testid^='conv-']").first();
    await firstConv.waitFor({ state: "visible", timeout: TIMEOUT_RELOAD_MS });
    await firstConv.click();
    await expect(page.locator(`text=${probeText}`)).toBeVisible({ timeout: TIMEOUT_LONG_MS });
  });

  // (2026-06-24) chat-message-persistence: 验证 conv.message_count += 1
  test("login #5 登录态发消息后列表 message_count >= 1", async ({ page }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});
    await clearServerConversations(page);

    await page
      .getByTestId("composer-textarea")
      .pressSequentially(LOGIN_TEXT, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

    const serverConvs = await readServerConversations(page);
    expect(
      serverConvs.length,
      `登录用户发消息后服务端 conv 列表应 >= 1 (实际 ${serverConvs.length})`,
    ).toBeGreaterThanOrEqual(SINGLE_COUNT);
    const count = serverConvs[0]?.message_count ?? 0;
    expect(count, `message_count 应 >= 1 (实际 ${count})`).toBeGreaterThanOrEqual(SINGLE_COUNT);
  });

  // ── Memory 接口 ───────────────────────────────────

  test("memory #1 登录态发消息触发 BFF 调 /api/memory/search + /api/memory/add", async ({
    page,
  }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});

    const tracker = trackMemoryCalls(page);
    const probeText = "memory 接口探测";
    await page
      .getByTestId("composer-textarea")
      .pressSequentially(probeText, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();

    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);
    await page.waitForTimeout(MEMORY_POST_LLM_WAIT_MS);

    const calls = tracker.get();
    const searchCalls = calls.filter((c) => c.url.includes("/api/memory/search"));
    const addCalls = calls.filter((c) => c.url.includes("/api/memory/add"));
    expect(
      searchCalls.length,
      "BFF 应至少调 1 次 /api/memory/search (pre-LLM)",
    ).toBeGreaterThanOrEqual(SINGLE_COUNT);
    expect(addCalls.length, "BFF 应至少调 1 次 /api/memory/add (post-LLM)").toBeGreaterThanOrEqual(
      SINGLE_COUNT,
    );
  });

  // ── 状态切换 ──────────────────────────────────────

  test("迁移 #1 匿名发消息后登录, 弹 toast, 点击后 IDB 清空", async ({ context }) => {
    const fresh = await context.browser()!.newContext();
    const freshPage = await fresh.newPage();
    try {
      await freshPage.goto("/zh/chat");
      await freshPage
        .getByTestId("composer-textarea")
        .pressSequentially(ANON_TEXT, { delay: TYPE_DELAY_MS });
      await freshPage.getByTestId("composer-send").click();
      await waitForDifyReply(freshPage, TIMEOUT_DIFY_LONG_MS);
      await waitForSendBtn(freshPage, TIMEOUT_MEMORY_MS);

      const beforeConvs = await readIdbConversations(freshPage, "anon");
      expect(beforeConvs.length, "发消息后 IDB 应有 anon conv").toBeGreaterThanOrEqual(
        SINGLE_COUNT,
      );

      await performLogin(freshPage);
      await freshPage.goto("/zh/chat");

      await expect(freshPage.locator("text=/本地.*聊天将清除/"), "应弹迁移 toast").toBeVisible({
        timeout: TIMEOUT_TOAST_MS,
      });
      await freshPage.getByRole("button", { name: "知道了" }).click();

      await expect
        .poll(
          async () => {
            const remaining = await readIdbConversations(freshPage, "anon");
            return remaining.length;
          },
          { message: "点 '知道了' 后 IDB anon conv 应被清", timeout: TIMEOUT_CLEAR_MS },
        )
        .toBe(ZERO_COUNT);
    } finally {
      await fresh.close();
    }
  });

  // (2026-06-30 streamdown 迁移) 验证 chat 渲染 GFM + Shiki + bold
  test("streamdown 渲染 GFM 表格 + Shiki 代码块 + bold", async ({ page }) => {
    await page.goto("/zh/chat");
    await clearAnonState(page);
    await page.goto("/zh/chat");

    const MOCK_REPLY = [
      "**重要** 结论:",
      "",
      "| 参数 | 值 |",
      "| - | - |",
      "| 功率 | 1.5kW |",
      "",
      "```ts",
      "const x = 1;",
      "```",
    ].join("\n");

    // 拦截 chat 发送请求, 模拟 Dify 流式返回
    await page.route("**/api/chat/send**", async (route) => {
      const body = JSON.stringify({ event: "message", delta: MOCK_REPLY });
      await route.fulfill({
        contentType: "text/event-stream",
        body: `data: ${body}\n\ndata: ${JSON.stringify({ event: "message_end" })}\n\n`,
      });
    });

    await page.getByPlaceholder(/(说点什么|Ask something)/).fill("测试 markdown");
    await page.keyboard.press("Enter");

    // 验证 GFM 表格出现
    await expect(page.getByRole("table")).toBeVisible({ timeout: TIMEOUT_DIFY_LONG_MS });
    // 验证 bold 出现
    await expect(
      page.locator("strong, [data-streamdown='strong']", { hasText: "重要" }),
    ).toBeVisible();
    // 验证 Shiki 代码块
    await expect(page.locator("pre")).toBeVisible();
  });
});
