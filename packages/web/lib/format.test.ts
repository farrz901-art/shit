import { describe, expect, it } from "vitest";
import { ONE_KB, ONE_MB } from "@/const";
import { fmtSize } from "./format";

const KB_15 = 15;
const MB_12_3 = 12.3;
const MB_100_MULTIPLIER = 100;

const BYTES_ZERO = 0;
const BYTES_512 = 512;
const BYTES_15_KB = KB_15 * ONE_KB;
const MB_1 = ONE_MB;
const MB_12_3_VAL = MB_12_3 * ONE_MB;
const MB_100 = MB_100_MULTIPLIER * ONE_MB;

describe("fmtSize", () => {
  it("< 1KB 显示 B", () => {
    expect(fmtSize(BYTES_ZERO)).toBe("0 B");
    expect(fmtSize(BYTES_512)).toBe("512 B");
  });

  it("< 1MB 显示 KB (1 位小数)", () => {
    expect(fmtSize(ONE_KB)).toBe("1.0 KB");
    expect(fmtSize(BYTES_15_KB)).toBe("15.0 KB");
  });

  it(">= 1MB 显示 MB (1 位小数)", () => {
    expect(fmtSize(MB_1)).toBe("1.0 MB");
    expect(fmtSize(MB_12_3_VAL)).toBe("12.3 MB");
    expect(fmtSize(MB_100)).toBe("100.0 MB");
  });
});
