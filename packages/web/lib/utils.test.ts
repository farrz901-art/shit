// Cn 工具函数单测
import { describe, expect, it } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("合并 className", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("过滤 falsy", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });

  it("twMerge 覆盖冲突", () => {
    expect(cn("px-4", "px-2")).toBe("px-2");
  });

  it("空参数", () => {
    expect(cn()).toBe("");
  });
});
