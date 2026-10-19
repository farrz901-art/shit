import { describe, expect, it } from "vitest";
import enMessages from "../en.json";
import zhMessages from "../zh.json";

const NON_EMPTY = 0;

describe("messages key consistency", () => {
  it("zh.json 不是空对象", () => {
    expect(Object.keys(zhMessages).length).toBeGreaterThan(NON_EMPTY);
  });

  it("zh.json 所有 value 跟 key 一致 (identity / 默认值模式)", () => {
    for (const [key, val] of Object.entries(zhMessages)) {
      expect(val).toBe(key);
    }
  });

  it("zh.json 所有 key 都是非空字符串", () => {
    for (const key of Object.keys(zhMessages)) {
      expect(key.length).toBeGreaterThan(NON_EMPTY);
    }
  });

  it("en.json 不是空对象", () => {
    expect(Object.keys(enMessages).length).toBeGreaterThan(NON_EMPTY);
  });

  it("en.json 覆盖了 zh.json 所有 key (防止漏翻译)", () => {
    const zhKeys = new Set(Object.keys(zhMessages));
    const enKeys = new Set(Object.keys(enMessages));
    const missing = [...zhKeys].filter((key) => !enKeys.has(key));
    expect(missing, `en.json 漏翻译 ${missing.length} 个 key: ${missing.join(", ")}`).toEqual([]);
  });

  it("zh.json / en.json key 集合一致 (OR: 任意一边孤儿都报, 跟项目 dedup 规则一致)", () => {
    const zhKeys = new Set(Object.keys(zhMessages));
    const enKeys = new Set(Object.keys(enMessages));
    const zhOnly = [...zhKeys].filter((key) => !enKeys.has(key));
    const enOnly = [...enKeys].filter((key) => !zhKeys.has(key));
    const orphans = [...zhOnly, ...enOnly].toSorted();
    expect(
      orphans,
      `双边 key 不一致, zh-only=${JSON.stringify(zhOnly)} en-only=${JSON.stringify(enOnly)}`,
    ).toEqual([]);
  });
});
