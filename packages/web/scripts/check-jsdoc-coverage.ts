import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative, dirname } from "node:path";

// ---------- constants ----------

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SCAN_DIRS = ["app", "components", "lib"] as const;
const EXEMPT_PATTERNS = [/\.test\.[jt]sx?$/, /\.stories\.[jt]sx?$/, /[\\/]components[\\/]ui[\\/]/];
const EXPORT_RE =
  /^export\s+(?:async\s+)?(?:function|const|default\s+function|interface|type|class)\s+(?<name>[A-Za-z_$][\w$]*)/;
const MAX_MISSING_DISPLAY = 50;
const PCT_MULTIPLIER = 100;
const IDX_OFFSET = 1;
const VAL_ZERO = 0;
const VAL_ZERO_PCT = "100.0";
const EXIT_FAILURE = 1;

// ---------- types ----------

interface MissingEntry {
  fileName: string;
  line: number;
  exportName: string;
}

interface ScanResult {
  missing: MissingEntry[];
  totalExports: number;
  exemptCount: number;
}

// ---------- helpers ----------

const isExempt = (relPath: string): boolean =>
  EXEMPT_PATTERNS.some((pattern) => pattern.test(relPath));

const walk = (dir: string, files: string[] = []): string[] => {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const entryStat = statSync(full);
    if (entryStat.isDirectory()) {
      walk(full, files);
    } else if (/\.[jt]sx?$/.test(entry) && !entry.endsWith(".d.ts")) {
      files.push(full);
    }
  }
  return files;
};

const findJsdocStart = (lines: string[], fromIndex: number): boolean => {
  for (let back = fromIndex; back >= VAL_ZERO; back--) {
    const trimmed = lines[back].trim();
    if (trimmed.startsWith("/**")) {
      return true;
    }
    if (trimmed && !trimmed.startsWith("*")) {
      return false;
    }
  }
  return false;
};

const hasJsdocAbove = (lines: string[], lineIndex: number): boolean => {
  const start = lineIndex - IDX_OFFSET;
  for (let idx = start; idx >= VAL_ZERO; idx--) {
    const trimmed = lines[idx].trim();
    // 单行 JSDoc: /** 描述 */ (在同一行以 /** 开头)
    if (trimmed.startsWith("/**")) {
      return true;
    }
    if (trimmed.startsWith("*/")) {
      return findJsdocStart(lines, idx);
    }
    const isComment =
      trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*");
    if (trimmed && !isComment) {
      return false;
    }
  }
  return false;
};

const isReExportOnly = (content: string): boolean => {
  const exportLines = content.match(/^export\s+.+$/gm) ?? [];
  if (exportLines.length === VAL_ZERO) {
    return false;
  }
  return exportLines.every((line) => /from\s+["']/.test(line));
};

// ---------- scanner ----------

const tryMatchExport = (line: string): string | null => {
  const matchResult = line.match(EXPORT_RE);
  if (!matchResult) {
    return null;
  }
  return matchResult.groups?.name ?? "?";
};

const processFileLines = (lines: string[], rel: string, results: ScanResult): void => {
  for (let idx = VAL_ZERO; idx < lines.length; idx++) {
    const exportName = tryMatchExport(lines[idx]);
    if (exportName !== null) {
      results.totalExports++;
      if (!hasJsdocAbove(lines, idx)) {
        results.missing.push({
          fileName: rel,
          line: idx + IDX_OFFSET,
          exportName,
        });
      }
    }
  }
};

const scanFile = (file: string, results: ScanResult): void => {
  const rel = relative(ROOT, file);
  if (isExempt(rel)) {
    results.exemptCount++;
    return;
  }
  const content = readFileSync(file, "utf8");
  if (isReExportOnly(content)) {
    results.exemptCount++;
    return;
  }
  processFileLines(content.split("\n"), rel, results);
};

// ---------- report ----------

const printReport = (results: ScanResult): void => {
  const { missing, totalExports } = results;
  const covered = totalExports - missing.length;
  const pct = totalExports
    ? ((covered / totalExports) * PCT_MULTIPLIER).toFixed(IDX_OFFSET)
    : VAL_ZERO_PCT;

  const listAll = process.argv.includes("--list-all");
  const displayLimit = listAll ? missing.length : MAX_MISSING_DISPLAY;

  console.log(`\n=== JSDoc Coverage Report ===`);
  console.log(`Total exports:   ${totalExports}`);
  console.log(`Covered:         ${covered} (${pct}%)`);
  console.log(`Missing:         ${missing.length}`);
  console.log(`Exempt files:    ${results.exemptCount}\n`);

  const remains = printMissingEntries(missing, displayLimit);
  logMoreWarning(remains, displayLimit, missing.length);
};

const printMissingEntries = (missing: MissingEntry[], displayLimit: number): number => {
  if (missing.length <= VAL_ZERO) {
    return VAL_ZERO;
  }
  console.log(`Missing entries:`);
  const display = missing.slice(VAL_ZERO, displayLimit);
  for (const entry of display) {
    console.log(`  [MISSING] ${entry.fileName}:${entry.line} (export ${entry.exportName})`);
  }
  const remains = missing.length - displayLimit;
  return remains;
};

const logMoreWarning = (remains: number, displayLimit: number, totalMissing: number): void => {
  if (remains > VAL_ZERO && displayLimit < totalMissing) {
    console.log(`  ... and ${remains} more`);
  }
};

// ---------- entry ----------

const main = (): void => {
  const reportOnly = process.argv.includes("--report-only");
  const allFiles = SCAN_DIRS.flatMap((dir) => walk(join(ROOT, dir)));
  const results: ScanResult = {
    missing: [],
    totalExports: VAL_ZERO,
    exemptCount: VAL_ZERO,
  };

  for (const file of allFiles) {
    scanFile(file, results);
  }

  printReport(results);

  if (!reportOnly && results.missing.length > VAL_ZERO) {
    process.exit(EXIT_FAILURE);
  }
};

main();
