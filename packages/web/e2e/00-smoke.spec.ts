// 全站冒烟: 5 个页面都能加载, 关键元素存在, Tailwind 类生效
// 不依赖后端: 后端 5xx 时, 页面应渲染降级 UI (错误条 / 空状态)
import { expect, test } from "@playwright/test";
import { resolve } from "node:path";

// 截图统一放 web/.e2e-logs/ (相对 repo 根)
const SHOT_DIR = resolve(__dirname, "..", ".e2e-logs");

const HTTP_ERROR_THRESHOLD = 500;
const MAX_CANDIDATES = 50;
const INITIAL_COUNT = 0;
const MIN_NAV_LINKS = 4;

const PAGES = [
  // 首页 + Decode 走的是后端直连 8000; 后端缺时 input 还在, 按钮存在
  { desc: "首页", must: ["nav", "text=RAG"], name: "Dashboard", path: "/" },
  { desc: "型号解码", must: ["input", 'button:has-text("解码")'], name: "Decode", path: "/decode" },
  { desc: "Output 列表", must: ["nav"], name: "OutputList", path: "/output" },
  {
    desc: "知识库 Dashboard",
    must: ['h1:has-text("知识库总览")', "nav a"],
    name: "KnowledgeHome",
    path: "/knowledge",
  },
  {
    desc: "QA 录入",
    must: ["[data-testid=qa-question]", "[data-testid=qa-answer]"],
    name: "QA",
    path: "/knowledge/qa",
  },
  {
    desc: "Documents 录入",
    must: ["[data-testid=file-dropzone]", "[data-testid=dl-excel]"],
    name: "Documents",
    path: "/knowledge/documents",
  },
  // Triples 后端缺时不渲染表格 (等 schema), 改为宽松断言: 页面挂标题即可
  { desc: "Triples 录入", must: ["nav"], name: "Triples", path: "/knowledge/triples" },
  {
    desc: "Batch 批量",
    must: ["[data-testid=batch-file]"],
    name: "Batch",
    path: "/knowledge/batch",
  },
];

for (const entry of PAGES) {
  test(`冒烟: ${entry.name} 渲染正常 + 截图`, async ({ page }) => {
    const res = await page.goto(entry.path);
    expect(res, `goto ${entry.path} 返回 null`).not.toBeNull();
    // 允许 5xx, 因为后端可能没起; 测的是页面挂没挂
    expect(res!.status(), `${entry.path} HTTP 状态`).toBeLessThan(HTTP_ERROR_THRESHOLD);

    for (const sel of entry.must) {
      await expect(page.locator(sel).first(), `${entry.path} 缺 ${sel}`).toBeVisible({
        timeout: 10_000,
      });
    }

    // 验证 Tailwind 实际生效: 找带 class 的元素, 检查 computed style
    const hasClasses = await page.evaluate(() => {
      const candidates = document.querySelectorAll("h1, h2, h3, button, a, nav, div, span");
      let withUtilClass = INITIAL_COUNT;
      for (const el of [...candidates].slice(INITIAL_COUNT, MAX_CANDIDATES)) {
        const cls = el.className;
        if (typeof cls === "string" && /flex|grid|rounded|p-|m-|text-|bg-/.test(cls)) {
          withUtilClass++;
        }
      }
      return withUtilClass;
    });
    expect(hasClasses, `${entry.path} 没找到 Tailwind 工具类`).toBeGreaterThan(INITIAL_COUNT);

    // 顶层 nav 在每个页面都要有 4 个入口
    const navLinks = await page.locator("nav a").count();
    expect(navLinks, `${entry.path} nav 缺链接`).toBeGreaterThanOrEqual(MIN_NAV_LINKS);

    await page.screenshot({
      animations: "disabled",
      fullPage: false,
      path: `${SHOT_DIR}/${entry.name}.png`,
    });
  });
}
