import type { DifyChatProvider as DifyChatProviderType } from "./dify";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getChatProvider } from "./factory";

vi.mock("./dify", () => {
  class FakeDify {
    name = "dify";
    sendMessage = vi.fn();
  }
  return { DifyChatProvider: FakeDify as unknown as DifyChatProviderType };
});
vi.mock("./memory-integration", () => ({
  withMemoryHooks: vi.fn().mockImplementation((inner: { name: string }) => ({
    name: `${inner.name}+memory`,
    sendMessage: vi.fn(),
  })),
}));

describe("getChatProvider", () => {
  const ORIGINAL = process.env.CHAT_PROVIDER;

  beforeEach(() => {
    delete process.env.CHAT_PROVIDER;
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (ORIGINAL === undefined) {
      delete process.env.CHAT_PROVIDER;
    } else {
      process.env.CHAT_PROVIDER = ORIGINAL;
    }
  });

  it("CHAT_PROVIDER=dify 返 name='dify+memory' (套了 withMemoryHooks)", () => {
    process.env.CHAT_PROVIDER = "dify";
    const provider = getChatProvider();
    expect(provider.name).toBe("dify+memory");
  });

  it("CHAT_PROVIDER 未设抛错 (不静默回退)", () => {
    expect(() => getChatProvider()).toThrow(/CHAT_PROVIDER/);
  });

  it("CHAT_PROVIDER=llamaindex 抛 '未实现' (v1 故意不兜底)", () => {
    process.env.CHAT_PROVIDER = "llamaindex";
    expect(() => getChatProvider()).toThrow(/llamaindex/);
  });

  it("CHAT_PROVIDER=garbage 抛 'unknown provider'", () => {
    process.env.CHAT_PROVIDER = "garbage";
    expect(() => getChatProvider()).toThrow(/unknown provider/);
  });
});
