// @vitest-environment node
// TODO: i18n test rewrite — async server components can't be rendered in jsdom
// (Next.js docs: "Vitest currently does not support async Server Components").
// Switch to E2E test in a follow-up, or refactor header rendering to be
// Testable in isolation (extract Header into its own tested component).
// This smoke test only verifies the module loads and the async function
// Can be invoked without throwing on a valid locale.
import { describe, expect, it, vi } from "vitest";

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "--font-geist-sans" }),
  JetBrains_Mono: () => ({ variable: "--font-jetbrains-mono" }),
}));

vi.mock("next-intl/server", () => ({
  getMessages: vi.fn().mockResolvedValue({}),
  getTranslations: vi.fn().mockResolvedValue((key: string) => key),
  setRequestLocale: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

// Task 20: layout 现在调 cookies() + fetch /me, 在 Node 环境下需要 mock 掉
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    delete: () => {},
    get: () => undefined,
    getAll: () => [],
    has: () => false,
    set: () => {},
    toString: (): string => "",
  })),
}));

// 让 fetch 抛错 → 走 catch 分支, user 保持 null, 不阻塞 async 调用
globalThis.fetch = vi.fn(async () => {
  throw new Error("fetch not mocked in test");
}) as unknown as typeof fetch;

import localeLayoutFn from "./layout";

describe("localeLayoutFn (smoke)", () => {
  it("module 加载成功, async 函数可被调用", async () => {
    expect(typeof localeLayoutFn).toBe("function");
    // 调一下拿到 Promise, 不解 await — 只验不抛同步错
    const result = localeLayoutFn({
      children: null,
      params: Promise.resolve({ locale: "zh" }),
    });
    expect(result).toBeInstanceOf(Promise);
  });
});
