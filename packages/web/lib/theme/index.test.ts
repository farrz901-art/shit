import { describe, expect, it, vi } from "vitest";

import { ZERO } from "@/const";

// 自实现 theme-provider 的 useTheme 需要 ThemeProvider context, 单元测试不挂 Provider
// 用 mock 替身, 只验证 barrel 是否把 useTheme 正确 re-export 出去
vi.mock("@/components/theme-provider", () => ({
  useTheme: () => ({ setTheme: () => {}, theme: "light" }),
}));

import * as ThemeModule from "./index";

describe("theme barrel", () => {
  it("导出 themes", () => {
    expect(ThemeModule.themes).toBeDefined();
    expect(ThemeModule.themes.length).toBeGreaterThan(ZERO);
  });

  it("导出 getThemeConfig", () => {
    expect(ThemeModule.getThemeConfig).toBeTypeOf("function");
  });

  it("导出 useTheme", () => {
    expect(ThemeModule.useTheme).toBeTypeOf("function");
  });
});
