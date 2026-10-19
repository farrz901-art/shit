/**
 * ParseResultCard (2026-06-29)
 * 抽自 documents-import-form.tsx 的解析结果卡 (2、解析 + 校验)
 * 含 DataTable + 下载错误行 CSV 按钮 + 状态图标
 * 表格列定义 buildParseColumns 也搬过来, 因为列跟 rows 渲染 1:1 绑定
 */
"use client";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { ButtonLift } from "@/components/motion/animated";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { type ParseResult, type ParsedRow } from "@/lib/parse/parse-excel";
import { Button } from "@/components/ui/button";
import { AlertCircle, CheckCircle, Download } from "lucide-react";
import { useTranslations } from "next-intl";

/** ParseResultCardProps - 解析结果卡属性 */
export interface ParseResultCardProps {
  title: string;
  result: ParseResult;
  /** 状态摘要 i18n 文本, e.g. "{n1} 行 · {n2} 错误" 翻译结果 (含占位符替换) */
  summaryText: string;
  emptyText: string;
  downloadLabel: string;
  onDownloadErrors: () => void;
}

const ZERO = 0;

/**
 * 构建表格列定义
 * @param tr - useTranslations 返回值
 * @returns 表格列定义数组
 * @shared
 */
const buildParseColumns = (tr: ReturnType<typeof useTranslations>): ColumnDef<ParsedRow>[] => [
  {
    id: "row",
    accessorKey: "row",
    cell: (ctx) => <span className="num text-muted-foreground">{ctx.row.original.row}</span>,
    header: () => "#",
    size: 64,
  },
  {
    id: "question",
    accessorKey: "question",
    cell: (ctx) => <span>{ctx.row.original.data.question}</span>,
    header: () => tr("问题"),
  },
  {
    id: "answer",
    accessorKey: "answer",
    cell: (ctx) => <span>{ctx.row.original.data.answer}</span>,
    header: () => tr("答案"),
  },
  {
    id: "errors",
    accessorKey: "errors",
    cell: (ctx) => (
      <div className="text-sm text-destructive">
        {ctx.row.original.errors.map((err, idx) => (
          <div key={idx}>{err}</div>
        ))}
      </div>
    ),
    header: () => tr("错误"),
  },
];

/**
 * 渲染状态图标 (错误/成功)
 * @param errorCount - 错误数
 * @returns JSX 图标元素
 */
const renderStatusIcon = (errorCount: number) =>
  errorCount > ZERO ? (
    <AlertCircle className="inline h-4 w-4 text-destructive" />
  ) : (
    <CheckCircle className="inline h-4 w-4 text-moss" />
  );

/**
 * 获取行样式 (错误行染色)
 * @param row - 解析行数据
 * @returns CSS 类名
 */
const getRowClass = (row: ParsedRow): string =>
  row.errors.length > ZERO ? "bg-destructive/4" : "";

/**
 * ParseResultCard - 解析结果卡 (2、解析 + 校验)
 * @param props.title - 卡片标题
 * @param props.result - 解析结果
 * @param props.summaryText - 状态摘要
 * @param props.emptyText - 空态文本
 * @param props.downloadLabel - 下载按钮文本
 * @param props.onDownloadErrors - 下载错误行回调
 * @client-bff
 */
export const ParseResultCard = ({
  title,
  result,
  summaryText,
  emptyText,
  downloadLabel,
  onDownloadErrors,
}: ParseResultCardProps) => {
  const tr = useTranslations();
  const columns = buildParseColumns(tr);
  return (
    <Card className="border-border/60">
      <CardHeader>
        <div className="flex items-baseline justify-between">
          <CardTitle className="text-lg">{title}</CardTitle>
          <p className="num text-base" data-testid="parse-summary">
            {renderStatusIcon(result.errorCount)} {summaryText}
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <DataTable
          dataSource={result.rows}
          columns={columns}
          rowKey="row"
          maxHeight="24rem"
          rowClassName={getRowClass}
          emptyText={<DataEmpty title={emptyText} />}
        />
        {result.errorCount > ZERO && (
          <ButtonLift className="mt-3 inline-block">
            <Button variant="outline" onClick={onDownloadErrors} data-testid="dl-errors">
              <Download className="mr-2 h-4 w-4" />
              {downloadLabel}
            </Button>
          </ButtonLift>
        )}
      </CardContent>
    </Card>
  );
};
