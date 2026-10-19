import { describe, expect, it } from "vitest";
import { routing } from "./routing";

describe("routing config", () => {
  it("locales 包含 zh 和 en", () => {
    expect(routing.locales).toEqual(["zh", "en"]);
  });

  it("defaultLocale 是 zh", () => {
    expect(routing.defaultLocale).toBe("zh");
  });

  it("localePrefix 用 always (URL 强制前缀)", () => {
    expect(routing.localePrefix).toBe("always");
  });
});
