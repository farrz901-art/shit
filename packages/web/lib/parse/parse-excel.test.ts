import * as XLSX from "xlsx";
import { ONE, TWO, ZERO } from "@/const";
import { describe, expect, it } from "vitest";
import { parseExcelBuffer } from "./parse-excel";

const makeExcel = (rows: (string | number)[][]): ArrayBuffer => {
  const ws = XLSX.utils.aoa_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Sheet1");
  const buf = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  return buf as ArrayBuffer;
};

describe("parseExcelBuffer", () => {
  it("valid rows", () => {
    const buf = makeExcel([
      ["question", "answer", "tags"],
      ["Q1?", "A1", "t1"],
      ["Q2?", "A2", "t2"],
    ]);
    const out = parseExcelBuffer(buf);
    expect(out.total).toBe(TWO);
    expect(out.errorCount).toBe(ZERO);
    expect(out.rows[ZERO].data.question).toBe("Q1?");
  });

  it("flags short question", () => {
    const buf = makeExcel([
      ["question", "answer"],
      ["Q", "A1"],
    ]);
    const out = parseExcelBuffer(buf);
    expect(out.errorCount).toBe(ONE);
    expect(out.rows[ZERO].errors).toContain("question 至少 2 字");
  });

  it("empty sheet only headers", () => {
    const buf = makeExcel([["question", "answer"]]);
    const out = parseExcelBuffer(buf);
    expect(out.total).toBe(ZERO);
  });
});
