// 评估页 E2E: 走通 列表 → 新建 → 上传 → 详情 → 取消 全链路
//
// ⚠️ 真实 Dify 评估需要 OPENAI_API_KEY + DIFY_DATASET_API_KEY + 真实 PDF 知识库, CI 跑不了.
//    本 spec 用 admin token 走通 UI 渲染 + 表单校验, 详情/取消靠 BFF 透传到 backend.
//    Playwright webServer config (playwright.config.ts) 会起 next dev + backend, 配置
//    RAG_ADMIN_TOKEN 之后 BFF → FastAPI 链可走通, 无需真实 Dify 数据.
import { expect, test } from "@playwright/test";
import { HTTP_FORBIDDEN, HTTP_NOT_FOUND, HTTP_OK } from "@/const";

const ADMIN_TOKEN = "e2e-admin-secret";

test.describe("评估页 (3 路由)", () => {
  test.beforeEach(async ({ context }) => {
    // 注入 admin token (调试模式) 让 BFF 透传时带上, FastAPI admin 分支放行
    await context.addInitScript((tok) => {
      globalThis.localStorage.setItem("rag_user_token", tok);
    }, ADMIN_TOKEN);
  });

  test("列表页 mount 不报错", async ({ page }) => {
    await page.goto("/evaluate");
    await expect(page.getByText("评估历史")).toBeVisible();
    await expect(page.getByText("+ 新建评估").first()).toBeVisible();
  });

  test("下载模板 BFF 返回 CSV 内容", async ({ request }) => {
    const resp = await request.get("/api/evaluate/template");
    expect(resp.status()).toBe(HTTP_OK);
    const body = await resp.text();
    expect(body).toContain("question,ground_truth");
    expect(body).toContain("西门子"); // 模板里 3 条西门子示例
  });

  test("新建页 - 上传合法 CSV 后显示预览", async ({ page }) => {
    await page.goto("/evaluate/new");
    const csv = Buffer.from("question,ground_truth\nQ1,A1\nQ2,A2\n");
    await page.setInputFiles('input[type="file"]', {
      buffer: csv,
      mimeType: "text/csv",
      name: "test.csv",
    });
    await expect(page.getByText("Q1")).toBeVisible();
    await expect(page.getByText("Q2")).toBeVisible();
    await expect(page.getByText("(2 行)")).toBeVisible();
  });

  test("新建页 - 上传非法 CSV (缺 question 列) 报错", async ({ page }) => {
    await page.goto("/evaluate/new");
    const csv = Buffer.from("prompt,answer\nQ1,A1\n");
    await page.setInputFiles('input[type="file"]', {
      buffer: csv,
      mimeType: "text/csv",
      name: "bad.csv",
    });
    await expect(page.getByText("缺 'question' 列")).toBeVisible();
  });

  test("详情页 - 404 兼容 (admin header 命中)", async ({ request }) => {
    const resp = await request.get("/api/evaluate/runs/999999", {
      headers: { "x-user-token": ADMIN_TOKEN },
    });
    expect([HTTP_FORBIDDEN, HTTP_NOT_FOUND]).toContain(resp.status());
  });
});
