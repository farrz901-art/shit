import { describe, expect, it } from "vitest";

import { getThemeConfig, themes } from "./themes";

describe("themes config", () => {
  it("包含 light 和 dark", () => {
    expect(themes.map((themeEntry) => themeEntry.name)).toEqual(["light", "dark"]);
  });

  it("每个主题有 name / label / icon / colors", () => {
    for (const themeEntry of themes) {
      expect(themeEntry.name).toBeTruthy();
      expect(themeEntry.label).toBeTruthy();
      expect(themeEntry.icon).toMatch(/^(?<iconType>sun|moon|eye)$/u);
      expect(typeof themeEntry.colors).toBe("object");
    }
  });

  it("light 主题覆盖了关键 token", () => {
    const light = getThemeConfig("light");
    expect(light.colors.background).toBeDefined();
    expect(light.colors.foreground).toBeDefined();
    expect(light.colors.primary).toBeDefined();
  });

  it("getThemeConfig 找不到主题时抛错", () => {
    expect(() => getThemeConfig("nope")).toThrow(/主题.*不存在/);
  });

  it("dark 主题的 background 跟 light 不同 (防复制粘贴)", () => {
    const light = getThemeConfig("light");
    const dark = getThemeConfig("dark");
    expect(dark.colors.background).not.toBe(light.colors.background);
  });

  it("light → sun, dark → moon", () => {
    expect(getThemeConfig("light").icon).toBe("sun");
    expect(getThemeConfig("dark").icon).toBe("moon");
  });
});
