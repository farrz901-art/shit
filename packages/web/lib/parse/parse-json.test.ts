import { ONE, ZERO } from "@/const";
import { describe, expect, it } from "vitest";
import { parseJsonText } from "./parse-json";

describe("parseJsonText", () => {
  it("valid", () => {
    const text = JSON.stringify({
      items: [{ payload: { question: "Q" }, target: "dify", type: "qa" }],
    });
    const out = parseJsonText(text);
    expect(out.errors).toEqual([]);
    expect(out.items).toHaveLength(ONE);
  });

  it("invalid json", () => {
    const out = parseJsonText("not json");
    expect(out.errors.length).toBeGreaterThan(ZERO);
  });

  it("missing items", () => {
    const out = parseJsonText(JSON.stringify({}));
    expect(out.errors.length).toBeGreaterThan(ZERO);
  });

  it("bad target", () => {
    const out = parseJsonText(
      JSON.stringify({
        items: [{ payload: {}, target: "wrong", type: "qa" }],
      }),
    );
    expect(out.errors.length).toBeGreaterThan(ZERO);
  });
});
