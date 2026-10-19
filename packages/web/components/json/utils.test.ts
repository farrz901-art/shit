import { ONE, THREE, TWO, ZERO } from "@/const";
import { describe, expect, it } from "vitest";
import { resolveCssDimension, safeStringify } from "./utils";

const DIMENSION_HUNDRED = 100;
const DIMENSION_TEN_NEG = -10;

describe("safeStringify", () => {
  it("正常 object 应返回缩进 JSON", () => {
    const obj = { alpha: 1, beta: "hello" };
    const result = safeStringify(obj);
    expect(result).toBe('{\n  "alpha": 1,\n  "beta": "hello"\n}');
  });

  it("null 应返回字符串 null", () => {
    expect(safeStringify(null)).toBe("null");
  });

  it("undefined 应返回 null", () => {
    expect(safeStringify(undefined)).toBeNull();
  });

  it("循环引用应返回 null", () => {
    const obj: Record<string, unknown> = {};
    obj.self = obj;
    expect(safeStringify(obj)).toBeNull();
  });

  it("空对象应返回 {} 缩进", () => {
    expect(safeStringify({})).toBe("{}");
  });

  it("数组应正确序列化", () => {
    const data = [ONE, TWO, THREE];
    expect(safeStringify(data)).toBe(`[\n  ${ONE},\n  ${TWO},\n  ${THREE}\n]`);
  });
});

describe("resolveCssDimension", () => {
  it("数字 100 应转为 100px", () => {
    expect(resolveCssDimension(DIMENSION_HUNDRED)).toBe("100px");
  });

  it("字符串 500px 原样返回", () => {
    expect(resolveCssDimension("500px")).toBe("500px");
  });

  it("数字 0 应转为 0px", () => {
    expect(resolveCssDimension(ZERO)).toBe("0px");
  });

  it("负数应转为负 px", () => {
    expect(resolveCssDimension(DIMENSION_TEN_NEG)).toBe("-10px");
  });

  it("字符串 100% 原样返回", () => {
    expect(resolveCssDimension("100%")).toBe("100%");
  });
});
