import { beforeEach, describe, expect, it, vi } from "vitest";

// Next-intl/server 的 getRequestConfig 在 jsdom 环境下走 react-client 入口
// (会在调用时 throw "not supported in Client Components")。
// 它的真实 server 实现就是 identity: (fn) => fn. 这里用 identity 替代,
// 让我们能直接测 request.ts 的 callback 行为, 不污染生产代码.
vi.mock("next-intl/server", () => ({
  getRequestConfig: (fn: unknown) => fn,
}));

describe("getRequestConfig", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("zh locale 加载 messages/zh.json", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    vi.doMock("../messages/en.json", () => ({ default: { common: { loading: "Loading" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("zh") });
    // Cfg.messages 类型上可能 undefined (next-intl getRequestConfig 签名), 测试用 mock 必有值, 断言
    expect(cfg.messages!.common.loading).toBe("加载中");
  });

  it("en locale 加载 messages/en.json", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    vi.doMock("../messages/en.json", () => ({ default: { common: { loading: "Loading" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("en") });
    expect(cfg.messages!.common.loading).toBe("Loading");
  });

  it("未知 locale 降级到 zh", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("fr" as any) });
    expect(cfg.locale).toBe("zh");
  });
});
