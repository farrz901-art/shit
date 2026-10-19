// Excel 解析: 第 1 行表头, 之后每行一个对象; 错误行收集返回
import * as XLSX from "xlsx";
import { ONE, TWO, ZERO } from "@/const";

/**
 * 解析后的 Excel 行
 * @property row     行号 (1-based, 含表头)
 * @property data    列名到值的映射
 * @property errors  该行的校验错误列表
 */
export interface ParsedRow {
  row: number; // 1-based (含表头)
  data: Record<string, string>;
  errors: string[];
}

/**
 * Excel 解析结果
 * @property rows       解析后的行列表
 * @property total      总行数
 * @property errorCount 有校验错误的行数
 */
export interface ParseResult {
  rows: ParsedRow[];
  total: number;
  errorCount: number;
}

/**
 * 解析 Excel 文件 Buffer, 提取表头和行数据
 * @param buf  ArrayBuffer 格式的 Excel 文件
 * @returns    ParseResult 包含解析后的行和错误统计
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const parseExcelBuffer = (buf: ArrayBuffer): ParseResult => {
  // eslint-disable-next-line max-statements -- Excel 解析连续操作
  const wb = XLSX.read(buf, { type: "array" });
  const ws = wb.Sheets[wb.SheetNames[ZERO]];
  const raw: string[][] = XLSX.utils.sheet_to_json(ws, { defval: "", header: ONE });
  if (raw.length === ZERO) {
    return { errorCount: ZERO, rows: [], total: ZERO };
  }
  const [headerRow, ...dataRows] = raw;
  const headers = headerRow.map((header) => String(header).trim());
  const rows: ParsedRow[] = [];
  dataRows.forEach((dataRow, rowIdx) => {
    const data: Record<string, string> = {};
    const errors: string[] = [];
    headers.forEach((header, colIdx) => {
      const val = String(dataRow[colIdx] ?? "").trim();
      data[header] = val;
      if (header === "question" && val.length < TWO) {
        errors.push("question 至少 2 字");
      }
      if (header === "answer" && val.length < TWO) {
        errors.push("answer 至少 2 字");
      }
    });
    rows.push({ data, errors, row: rowIdx + TWO });
  });
  return {
    errorCount: rows.filter((row) => row.errors.length > ZERO).length,
    rows,
    total: rows.length,
  };
};
