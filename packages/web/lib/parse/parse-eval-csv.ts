// CSV 解析逻辑 (从 evaluate/new/page.tsx 提取)
import Papa from "papaparse";
import { ZERO } from "@/const";

/**
 * CSV 解析结果
 * @property rows   解析后的问答行列表
 * @property total  有效行数
 */
export interface ParsedCsv {
  rows: { question: string; ground_truth: string | null }[];
  total: number;
}

/** CSV 题数上限 */
const MAX_CSV_ROWS = 200;

/**
 * 解析 CSV 评估文件, 提取 question 和 ground_truth 列
 * @param file   CSV 文件对象
 * @returns      包含 rows 和 total 的解析结果
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
// eslint-disable-next-line arrow-body-style, max-statements -- 需要 block 包裹 Promise 回调 (11 条语句)
export const parseEvalCsv = (file: File): Promise<ParsedCsv> => {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      // eslint-disable-next-line max-statements -- Papa.parse complete 回调 (11 条语句)
      complete: (res) => {
        // 检查是否有 question 列
        if (!res.meta.fields?.includes("question")) {
          reject(new Error("缺 'question' 列, 表头必须包含: question"));
          return;
        }

        // 处理: papaparse 把多余列放到 __parsed_extra, 需要拼回去
        // 例如: ground_truth="西门子", __parsed_extra=[" 常见为增量式"] → 应该是 "西门子, 常见为增量式"
        const rows = res.data
          .map((row) => {
            let groundTruth = (row.ground_truth ?? "").trim();
            // eslint-disable-next-line no-underscore-dangle -- papaparse 的 __parsed_extra 字段名约定
            const extra = (row as Record<string, unknown>).__parsed_extra;
            if (Array.isArray(extra) && extra.length > ZERO) {
              groundTruth += extra.join("");
            }
            return {
              ground_truth: groundTruth || null,
              question: (row.question ?? "").trim(),
            };
          })
          .filter((row) => row.question);

        if (rows.length === ZERO) {
          reject(new Error("至少 1 行有效数据"));
          return;
        }
        if (rows.length > MAX_CSV_ROWS) {
          reject(new Error(`题数 ${rows.length} 超过上限 ${MAX_CSV_ROWS}`));
          return;
        }
        resolve({ rows, total: rows.length });
      },
      error: (err) => reject(new Error(`CSV 解析失败: ${err.message}`)),
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
    });
  });
};
