// 生成带代码片段的重复度报告
// 读取 jscpd JSON 报告，从源文件提取代码行，输出可读 Markdown
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { nowIso } from "@/lib/date";

const EXIT_FAILURE = 1;
const FIRST_INDEX = 0;
const DATE_SLICE_END = 10;
const LINE_OFFSET = 1;

interface Loc {
  column: number;
  line: number;
  position: number;
}

interface FileInfo {
  end: number;
  endLoc: Loc;
  name: string;
  start: number;
  startLoc: Loc;
}

interface Duplicate {
  firstFile: FileInfo;
  format: string;
  fragment: string;
  lines: number;
  secondFile: FileInfo;
  tokens: number;
}

interface Report {
  duplicates: Duplicate[];
  statistics: {
    total: { lines: number; tokens: number; sources: number; clones: number };
    formats: Record<string, { lines: number; tokens: number; sources: number; clones: number }>;
  };
}

const REPO_ROOT = resolve(import.meta.dirname, "../../.."); // Scripts/ -> packages/web/ -> packages/ -> repo root
const REPORT_PATH = resolve(import.meta.dirname, "../reports/duplication/jscpd-report.json");
const OUTPUT_PATH = resolve(import.meta.dirname, "../reports/duplication/duplication-report.md");

// 扫描根目录：用于解析 jscpd 报告中的相对路径
// Jscpd 报告路径相对于扫描起点（../../packages/web/app 或 ../../packages/service/src）
const SCAN_BASES = [
  resolve(REPO_ROOT, "packages/web/app"),
  resolve(REPO_ROOT, "packages/service/src"),
];

if (!existsSync(REPORT_PATH)) {
  console.error(`找不到报告文件: ${REPORT_PATH}\n先运行 bun run find-duplicates`);
  process.exit(EXIT_FAILURE);
}

const reportJson = readFileSync(REPORT_PATH, "utf8");
const report: Report = JSON.parse(reportJson);

const lines: string[] = [];
let idx = LINE_OFFSET;

lines.push("# 重复代码检测报告");
lines.push("");
lines.push(`检测时间: ${nowIso().slice(FIRST_INDEX, DATE_SLICE_END)}`);
lines.push("");
lines.push(`共发现 **${report.duplicates.length}** 处重复`);
lines.push("");
lines.push("## 汇总");
lines.push("");
lines.push("| 格式 | 重复数 |");
lines.push("|------|--------|");
for (const [fmt, stat] of Object.entries(report.statistics.formats)) {
  lines.push(`| ${fmt} | ${stat.clones} |`);
}
lines.push("");

const readCode = (filePath: string, startLine: number, endLine: number): string => {
  // 尝试在每个扫描根目录下找文件
  for (const base of SCAN_BASES) {
    const fullPath = resolve(base, filePath);
    if (existsSync(fullPath)) {
      try {
        const content = readFileSync(fullPath, "utf8");
        const allLines = content.split("\n");
        return allLines.slice(startLine - LINE_OFFSET, endLine).join("\n");
      } catch {
        return `// 读取失败: ${fullPath}`;
      }
    }
  }
  return `// 找不到文件: ${filePath}`;
};

for (const dup of report.duplicates) {
  const fmt = dup.format;
  const f1 = dup.firstFile;
  const f2 = dup.secondFile;

  const code1 = readCode(f1.name, f1.startLoc.line, f1.endLoc.line);
  const code2 = readCode(f2.name, f2.startLoc.line, f2.endLoc.line);

  lines.push(`### ${idx}. ${fmt} 重复`);
  lines.push("");
  lines.push(`**${f1.name}:${f1.startLoc.line}-${f1.endLoc.line}**`);
  lines.push("");
  lines.push(`\`\`\`${fmt === "typescript" || fmt === "tsx" ? "tsx" : fmt}`);
  lines.push(code1);
  lines.push("```");
  lines.push("");
  lines.push(`**${f2.name}:${f2.startLoc.line}-${f2.endLoc.line}**`);
  lines.push("");
  lines.push(`\`\`\`${fmt === "typescript" || fmt === "tsx" ? "tsx" : fmt}`);
  lines.push(code2);
  lines.push("```");
  lines.push("");
  lines.push(`重复行数: ${dup.lines} | 重复Token数: ${dup.tokens}`);
  lines.push("");
  lines.push("---");
  lines.push("");

  idx++;
}

writeFileSync(OUTPUT_PATH, lines.join("\n"), "utf8");
console.error(`报告已生成: ${OUTPUT_PATH}`);
console.error(`共 ${report.duplicates.length} 处重复`);
