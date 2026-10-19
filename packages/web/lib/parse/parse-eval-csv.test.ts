// CSV 解析单元测试
import { ONE, TWO, ZERO } from "@/const";
import { describe, expect, it } from "vitest";
import { parseEvalCsv } from "./parse-eval-csv";

const createFile = (content: string, name = "test.csv"): File =>
  new File([content], name, { type: "text/csv" });

/** CSV 测试数据行数 */
// eslint-disable-next-line no-magic-numbers -- 测试数据常量
const CSV_TEST_ROW_LIMIT = 200;

// eslint-disable-next-line max-statements -- 12 个测试用例的 describe 块
describe("parseEvalCsv", () => {
  it("解析标准 CSV (question + ground_truth)", async () => {
    const csv =
      "question,ground_truth\n什么是电机?,电机是将电能转换为机械能的装置\n如何选型?,根据功率和转速选择";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
    expect(result.rows[ZERO].ground_truth).toBe("电机是将电能转换为机械能的装置");
    expect(result.rows[ONE].question).toBe("如何选型?");
    expect(result.rows[ONE].ground_truth).toBe("根据功率和转速选择");
  });

  it("解析只有 question 列的 CSV (ground_truth 可选)", async () => {
    const csv = "question\n什么是电机?\n如何选型?";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].ground_truth).toBeNull();
    expect(result.rows[ONE].ground_truth).toBeNull();
  });

  it("跳过空行", async () => {
    const csv = "question,ground_truth\n什么是电机?,电机是\n\n如何选型?,选型";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
  });

  it("跳过 question 为空的行", async () => {
    const csv = "question,ground_truth\n什么是电机?,电机是\n,选型\n如何选型?,选型";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
    expect(result.rows[ONE].question).toBe("如何选型?");
  });

  it("trim 空白字符", async () => {
    const csv = "question,ground_truth\n  什么是电机?  ,  电机是  ";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
    expect(result.rows[ZERO].ground_truth).toBe("电机是");
  });

  it("缺少 question 列时报错", async () => {
    const csv = "q,answer\n什么是电机?,电机是";
    const file = createFile(csv);
    await expect(parseEvalCsv(file)).rejects.toThrow("缺 'question' 列");
  });

  it("全部行 question 为空时报错", async () => {
    const csv = "question,ground_truth\n,\n,";
    const file = createFile(csv);
    await expect(parseEvalCsv(file)).rejects.toThrow("至少 1 行有效数据");
  });

  it("超过 200 行时报错", async () => {
    const rows = Array.from({ length: 201 }, (_unused, idx) => `问题${idx}?,答案${idx}`);
    const csv = `question,ground_truth\n${rows.join("\n")}`;
    const file = createFile(csv);
    await expect(parseEvalCsv(file)).rejects.toThrow("超过上限 200");
  });

  it("恰好 200 行不报错", async () => {
    const rows = Array.from({ length: 200 }, (_unused, idx) => `问题${idx}?,答案${idx}`);
    const csv = `question,ground_truth\n${rows.join("\n")}`;
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(CSV_TEST_ROW_LIMIT);
  });

  it("CSV 含 BOM 头时仍能解析", async () => {
    const csv = "﻿question,ground_truth\n什么是电机?,电机是";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(ONE);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
  });

  it("处理带引号的字段", async () => {
    const csv = 'question,ground_truth\n"什么是电机, 电动机?",电机是';
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.rows[ZERO].question).toBe("什么是电机, 电动机?");
  });

  it("处理 3 列 CSV (只取前 2 列, 忽略多余列)", async () => {
    // 用户实际上传的格式: question, ground_truth, 备注(—)
    const csv = "question\tground_truth\t备注\n什么是电机?\t电机是\t—\n如何选型?\t根据功率\t—";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
    expect(result.rows[ZERO].ground_truth).toBe("电机是");
  });

  it("处理制表符分隔的 CSV", async () => {
    const csv = "question\tground_truth\n什么是电机?\t电机是\n如何选型?\t根据功率";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
  });

  it("处理带引号和多余列的制表符 CSV", async () => {
    // 用户实际格式: 制表符分隔, ground_truth 带引号, 末尾有 —
    const csv = 'question\tground_truth\t备注\n什么是电机?\t"电机是"\t—\n如何选型?\t"根据功率"\t—';
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(TWO);
    expect(result.rows[ZERO].question).toBe("什么是电机?");
    expect(result.rows[ZERO].ground_truth).toBe("电机是");
  });

  it("处理 ground_truth 包含逗号的情况 (被错误拆分后拼回)", async () => {
    // 用户实际格式: 逗号分隔, ground_truth 包含逗号但没有引号包裹
    // Papaparse 会把 "1FK7 编码器类型取决于订货号后缀, 常见为增量式 TTL/HTL" 拆成两部分
    const csv =
      "question,ground_truth\n请解释编码器类型,1FK7 编码器类型取决于订货号后缀, 常见为增量式 TTL/HTL";
    const file = createFile(csv);
    const result = await parseEvalCsv(file);
    expect(result.total).toBe(ONE);
    // Ground_truth 应该包含完整内容 (包括逗号后面的部分)
    expect(result.rows[ZERO].ground_truth).toContain("1FK7 编码器类型取决于订货号后缀");
    expect(result.rows[ZERO].ground_truth).toContain("常见为增量式 TTL/HTL");
  });
});
