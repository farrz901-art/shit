import { FOUR } from "@/const";
import { describe, expect, it } from "vitest";
import { DUR, EASE, RADIUS, SHADOW, SPRING, stagger } from "./motion";

describe("motion 常量", () => {
  it("DUR 常量引用不报错", () => {
    expect(DUR.fast).toBeDefined();
    expect(DUR.slow).toBeDefined();
  });

  it("EASE 有值", () => {
    expect(EASE.outExpo.length).toBeGreaterThanOrEqual(FOUR);
  });

  it("SPRING 有值", () => {
    expect(SPRING.snappy.type).toBe("spring");
  });

  it("stagger 返对象", () => {
    const result = stagger();
    expect(result.show).toBeDefined();
  });

  it("stagger 自定义 delay", () => {
    const delay = 0.1;
    const staggerResult = stagger(delay);
    expect(staggerResult.show.transition.staggerChildren).toBe(delay);
  });

  it("RADIUS 有值", () => {
    expect(RADIUS.sm).toBe("rounded-md");
  });

  it("SHADOW 有值", () => {
    expect(SHADOW.card).toContain("shadow");
  });
});
