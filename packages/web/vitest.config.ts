import { defineConfig } from "vitest/config";
import path from "node:path";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      // Server-only 是个 marker module, 在测试环境 (jsdom/client) 引入会抛错.
      // RSC prefetch 工具的测试需要导入它, 所以在 vitest 把它 alias 成空模块.
      "server-only": path.resolve(__dirname, "test-shims/server-only-empty.ts"),
      // Zod v4 ESM 在 vitest jsdom 下 re-export 为 undefined, 强制走 CJS 入口
      zod: path.resolve(__dirname, "node_modules/zod/index.cjs"),
    },
  },
  test: {
    // RSC 测试慢, coverage 模式 instrumentation 让默认 5s 超时, 提到 15s
    // 2026-06-19 code-quality spec: 加 vitest coverage 起始基线 (不强制门禁, 仅采集)
    coverage: {
      exclude: [
        "node_modules/**",
        ".next/**",
        "**/*.test.{ts,tsx}",
        "**/*.spec.{ts,tsx}",
        "**/*.config.{ts,mjs}",
        "**/types.ts",
        "**/*.d.ts",
        "test-shims/**",
        "e2e/**",
      ],
      include: [
        "app/**/*.{ts,tsx}",
        "components/**/*.{ts,tsx}",
        "hooks/**/*.{ts,tsx}",
        "lib/**/*.{ts,tsx}",
        "i18n/**/*.{ts,tsx}",
      ],
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      thresholds: {
        // 起始不强制门禁, 仅采集; 后续 spec 加 thresholds
        branches: 0,
        functions: 0,
        lines: 0,
        statements: 0,
      },
    },
    environment: "happy-dom",
    // 排除 Playwright E2E 文件, 避免 vitest 当单测跑
    exclude: ["node_modules", "e2e/**", "dist/**", ".next/**"],
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    testTimeout: 15_000,
  },
});
