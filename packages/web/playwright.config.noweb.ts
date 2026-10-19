// 临时: 跳过 webServer, 直接连已运行的 next dev + uvicorn
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  expect: { timeout: 5000 },
  fullyParallel: false,
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  reporter: [["list"]],
  retries: 0,
  testDir: "./e2e",
  timeout: 15_000,
  use: {
    actionTimeout: 10_000,
    baseURL: "http://localhost:3000",
    viewport: { height: 800, width: 1280 },
  },
  // 不启动 webServer, 复用已有进程
  workers: 1,
});
