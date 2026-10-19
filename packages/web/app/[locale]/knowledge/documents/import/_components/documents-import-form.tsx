"use client";
// 文档导入子页 client 子组件 (2026-06-12) — 3 步流程 (上传 → 解析 → 提交)
// 提交步改用 commitDocuments server action (Task 12 建的), 走 form action pattern
// (RSC wrapper 在 import/page.tsx, 只做 i18n 透传 + child render)
//
// (2026-06-29) 拆 4 子组件: StepIndicator / UploadStep / ParseResultCard / TemplateDownload
// 主组件只保留 useState + 步骤切换逻辑. 审计依据: C-04 (>300 行)
// 表格列定义 buildParseColumns 移到 parse-result-card.tsx (列跟 rows 渲染 1:1 绑定)
import { type Dispatch, type SetStateAction, useState } from "react";
import { type ParseResult, parseExcelBuffer } from "@/lib/parse/parse-excel";
import { AnimateUp, Reveal } from "@/components/motion/animated";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { DELAY } from "@/lib/motion";
import { ImportCommitCard } from "./import-commit-card";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { ParseResultCard } from "./parse-result-card";
import { StepIndicator, type ImportStep } from "./step-indicator";
import { TemplateDownload, type TemplateLink } from "./template-download";
import { UploadStep } from "./upload-step";
import { parseJsonText } from "@/lib/parse/parse-json";
import { triggerBrowserDownload } from "@/lib/dom";
import { useAppStore } from "@/lib/store/app-store";
import { useTranslations } from "next-intl";

/** 步进常量 (避免 magic number) */
const ZERO = 0;
/** 步进常量 (步骤 1) */
const ONE = 1;
/** 步进常量 (步骤 2) */
const TWO = 2;
/** 步进常量 (步骤 3) */
const THREE = 3;

/** 有效行数据类型 (answer + question + tags) */
interface ValidRow {
  answer: string;
  question: string;
  tags: string;
}

/**
 * 解析上传文件 (JSON / Excel)
 * @param file - 上传的文件
 * @param setResult - 设置解析结果的 state setter
 */
const handleFileParse = async (
  file: File,
  setResult: Dispatch<SetStateAction<ParseResult | null>>,
) => {
  if (file.name.endsWith(".json")) {
    const text = await file.text();
    const out = parseJsonText(text);
    let errorCount = ZERO;
    if (out.errors.length > ZERO) {
      errorCount = out.items.length;
    }
    setResult({
      errorCount,
      rows: out.items.map((item, idx) => ({
        data: item as unknown as Record<string, string>,
        errors: out.errors,
        row: idx + ONE,
      })),
      total: out.items.length,
    });
  } else {
    const buf = await file.arrayBuffer();
    setResult(parseExcelBuffer(buf));
  }
};

/**
 * 下载错误行 CSV 文件
 * @param result - 解析结果
 */
const downloadErrorRows = (result: ParseResult) => {
  const bad = result.rows.filter((row) => row.errors.length > ZERO);
  const csv = `row,question,answer,errors\n${bad
    .map(
      (row) =>
        `${row.row},"${(row.data.question ?? "").replace(/"/g, '""')}","${(row.data.answer ?? "").replace(/"/g, '""')}","${row.errors.join("; ")}"`,
    )
    .join("\n")}`;
  const blob = new Blob([csv], { type: "text/csv" });
  triggerBrowserDownload(blob, "errors.csv");
};

/**
 * 检查指定步骤是否已完成
 * @param stepNum - 步骤编号
 * @param parseResult - 当前解析结果 (可为 null)
 * @returns 该步骤是否已完成
 */
const isStepDone = (stepNum: number, parseResult: ParseResult | null): boolean => {
  if (stepNum === ONE) {
    return true;
  }
  if (stepNum === TWO) {
    return parseResult != null;
  }
  if (stepNum === THREE) {
    return parseResult != null && parseResult.errorCount < parseResult.total;
  }
  return false;
};

/**
 * 获取解析结果中的有效行 (无错误)
 * @param result - 解析结果 (可为 null)
 * @returns 有效行数组
 */
const getValidRows = (result: ParseResult | null): ValidRow[] => {
  if (result) {
    return result.rows
      .filter((row) => row.errors.length === ZERO)
      .map((row) => ({
        answer: row.data.answer ?? "",
        question: row.data.question ?? "",
        tags: row.data.tags ?? "",
      }));
  }
  return [];
};

/**
 * 步骤 + 模板链接 i18n 聚合 (主组件 1 行调用)
 * @param tr - useTranslations 返回值
 * @returns 步骤配置与模板链接
 */
const useImportConfig = (tr: ReturnType<typeof useTranslations>) => {
  const importSteps: ImportStep[] = [
    { description: tr("选择 Excel 或 JSON"), label: tr("上传"), stepNum: ONE },
    { description: tr("看每行 + 下载错误"), label: tr("校验"), stepNum: TWO },
    { description: tr("批量写入 Dify"), label: tr("提交"), stepNum: THREE },
  ];
  const templateLinks: TemplateLink[] = [
    {
      downloadName: "qa-template.xlsx",
      href: "/templates/qa-template.xlsx",
      label: tr("Excel 模板"),
      testId: "dl-excel",
    },
    {
      downloadName: "knowledge-import.json",
      href: "/templates/knowledge-import.json",
      label: tr("JSON 模板"),
      testId: "dl-json",
    },
  ];
  return { importSteps, templateLinks };
};

/**
 * DocumentsImportForm - 文档导入表单, 3 步流程 (上传 -> 解析 -> 提交)
 * @client-bff
 */
export const DocumentsImportForm = () => {
  const tr = useTranslations();
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  // DatasetId 透传给 ImportCommitCard (zustand store 里有)
  void useAppStore((state) => state.datasetId);

  const { importSteps, templateLinks } = useImportConfig(tr);

  const onDownloadErrors = () => {
    if (parseResult) {
      downloadErrorRows(parseResult);
    }
  };

  // 待提交的有效行 (透传给 ImportCommitCard 进 hidden input)
  const validRows = getValidRows(parseResult);
  const validCount = validRows.length;
  const onFile = async (file: File) => {
    await handleFileParse(file, setParseResult);
  };

  return (
    <div className="h-full overflow-y-auto space-y-8">
      {/* Hero + 右侧返回按钮 (DatasetSwitcher 由 layout ActiveSwitch 提供) */}
      <PageHero
        eyebrow={tr("向量库 · 批量导入")}
        title={tr("批量导入")}
        actions={
          <BackLink
            href="/knowledge/documents"
            useHistory
            label={tr("返回向量库")}
            data-testid="back-link"
          />
        }
      />

      {/* 步骤指示器 */}
      <Reveal delay={DELAY.heroStep1}>
        <StepIndicator
          steps={importSteps}
          isStepDone={(stepNum) => isStepDone(stepNum, parseResult)}
        />
      </Reveal>

      {/* 模板下载 */}
      <Reveal delay={DELAY.heroStep2}>
        <TemplateDownload title={tr("模板下载")} templates={templateLinks} />
      </Reveal>

      {/* 1、上传 */}
      <Reveal delay={DELAY.primary}>
        <UploadStep title={tr("1、上传")} fileTypeLabel=".xlsx / .json" onFile={onFile} />
      </Reveal>

      {/* 2、解析 + 校验 */}
      {parseResult && (
        <AnimateUp show>
          <ParseResultCard
            title={tr("2、解析 + 校验")}
            result={parseResult}
            summaryText={tr("{n1} 行 · {n2} 错误", {
              n1: parseResult.total,
              n2: parseResult.errorCount,
            })}
            emptyText={tr("暂无数据")}
            downloadLabel={tr("下载错误行 CSV")}
            onDownloadErrors={onDownloadErrors}
          />
        </AnimateUp>
      )}

      {/* 3、提交 — 拆到 ImportCommitCard (form action + commitDocuments server action) */}
      {parseResult && parseResult.errorCount < parseResult.total && (
        <AnimateUp show delay={DELAY.secondary}>
          <ImportCommitCard validRows={validRows} validCount={validCount} />
        </AnimateUp>
      )}
    </div>
  );
};
