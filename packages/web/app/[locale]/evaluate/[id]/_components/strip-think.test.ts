// (2026-06-11) stripThink 单元测试
import { describe, expect, it } from "vitest";
import { stripThink } from "./strip-think";

describe("stripThink", () => {
  it("删 <think>...</think> 块, 保留真正答案", () => {
    expect(stripThink("<think>\n推理中\n</think>1000万")).toBe("1000万");
  });

  it("无 think 块 → 原样返回", () => {
    expect(stripThink("普通答案")).toBe("普通答案");
  });

  it("空串 / null / undefined → 返空串", () => {
    expect(stripThink("")).toBe("");
    expect(stripThink(null)).toBe("");
    expect(stripThink(undefined)).toBe("");
  });

  it("多块 think → 全部删", () => {
    expect(stripThink("<think>推理1</think>答案1<think>推理2</think>答案2")).toBe("答案1答案2");
  });

  it("块后空白清理", () => {
    expect(stripThink("<think>推理</think>   答案   ")).toBe("答案");
  });
});
