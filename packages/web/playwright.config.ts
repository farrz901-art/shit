// Playwright E2E 配置 (2026-06-09)
// 5 个管理页面冒烟测试, dev 模式跑 (起 next dev)
import { defineConfig, devices } from "@playwright/test";

import { DEFAULT_DEV_PORT } from "@/const";

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? DEFAULT_DEV_PORT);
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  expect: { timeout: 5000 },
  // 串行避免抢端口
  fullyParallel: false,
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  reporter: [["list"], ["html", { open: "never" }]],
  // 失败重试 1 次, 减少字体加载时序等偶发
  retries: 1,
  testDir: "./e2e",
  // Dev 模式首屏慢
  timeout: 30_000,
  use: {
    // 减少动画/字体加载时序导致的 flaky screenshot
    actionTimeout: 10_000,
    baseURL: BASE_URL,
    // 后端不通是常见情形, 不让 /api/* 把页面搞挂
    ignoreHTTPSErrors: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    // 强制桌面尺寸, mobile 不在本轮范围
    viewport: { height: 800, width: 1280 },
  },
  // 自动起 next dev + 后端 uvicorn (e2e-up.sh), 复用已有进程
  webServer: {
    command: "bash scripts/e2e-up.sh",
    reuseExistingServer: true,
    stderr: "pipe",
    stdout: "pipe",
    timeout: 90_000,
    url: BASE_URL,
  },
  // 一台机器一份, 复用 next dev
  workers: 1,
});
