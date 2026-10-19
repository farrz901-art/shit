"use client";
// kg_extract 任务列表 (2026-07-03): Task ID (复制) + Dataset/Extractor/Splitter + 状态 + 进度 + 创建时间 + 重跑
// 行 click 路由: done/partial → preview; 其他 → 进度页. 重跑弹 AppConfirm 二次确认.
/* oxlint-disable id-length, max-statements -- TanStack cell 参数 row 短, 表格列定义连贯 */
import { useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { FileText, RefreshCw } from "lucide-react";
import { type ColumnDef, DataTable } from "@/components/common/table";
import { Button } from "@/components/ui/button";
import { AppConfirm } from "@/components/common/confirm";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { startExtract, type ExtractTaskRow } from "@/lib/api/knowledge";
import { fmtRelativeTime } from "@/lib/date";
import { ONE, ZERO } from "@/const";

/**
 * ExtractTasksTableProps - 抽取任务表格属性
 * @property rows - 任务行数据
 * @property total - 总任务数
 * @property totalSuccess - 成功数
 * @property totalFailed - 失败数
 * @property page - 当前页
 * @property pageSize - 每页大小
 * @property loading - 是否加载中
 * @property error - 错误信息
 * @property onPageChange - 翻页回调
 * @property onRetry - 重试回调
 */
export interface ExtractTasksTableProps {
  rows: ExtractTaskRow[];
  total: number;
  totalSuccess: number;
  totalFailed: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
  onRetry: () => void;
}

const TASK_ID_PREVIEW_LENGTH = 8;

/**
 * ExtractTasksTable - kg_extract 任务列表表格
 * @param props.rows - 任务行数据
 * @param props.loading - 是否加载中
 * @param props.error - 错误信息
 * @param props.page - 当前页
 * @param props.pageSize - 每页大小
 * @param props.total - 总任务数
 * @param props.totalSuccess - 成功数
 * @param props.totalFailed - 失败数
 * @param props.onPageChange - 翻页回调
 * @param props.onRetry - 重试回调
 * @client-bff
 */
const ExtractTasksTable = ({
  rows,
  loading,
  error,
  page,
  pageSize,
  total,
  totalSuccess,
  totalFailed,
  onPageChange,
  onRetry,
}: ExtractTasksTableProps) => {
  const tr = useTranslations();
  const router = useRouter();
  const [confirmRow, setConfirmRow] = useState<ExtractTaskRow | null>(null);

  const handleRowClick = (row: ExtractTaskRow) => {
    const dataset = row.dataset ?? "motor";
    if (row.state === "done" || row.state === "partial") {
      void router.push(
        `/knowledge/extract/${row.task_id}/preview?dataset=${encodeURIComponent(dataset)}`,
      );
    } else {
      void router.push(`/knowledge/extract/${row.task_id}?dataset=${encodeURIComponent(dataset)}`);
    }
  };

  const handleRerunClick = (row: ExtractTaskRow) => {
    if (!row.uri || !row.dataset || !row.extractor || !row.splitter) {
      toast.error(tr("重跑参数缺失"));
      return;
    }
    setConfirmRow(row);
  };

  const handleRerunConfirm = async () => {
    const row = confirmRow;
    if (!row || !row.uri || !row.dataset || !row.extractor || !row.splitter) {
      return;
    }
    setConfirmRow(null);
    try {
      const { task_id } = await startExtract({
        uri: row.uri,
        dataset: row.dataset,
        extractor: row.extractor as "spacy_rule" | "llm_pydantic",
        splitter: row.splitter as "heading" | "token" | "semantic",
      });
      void router.push(`/knowledge/extract/${task_id}?dataset=${encodeURIComponent(row.dataset)}`);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "";
      toast.error(`${tr("重跑失败")}: ${message}`);
    }
  };

  const columns: ColumnDef<ExtractTaskRow>[] = [
    {
      id: "task_id",
      header: tr("任务 ID"),
      cell: ({ row }) => {
        const taskId = row.original.task_id;
        return (
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{taskId.slice(ZERO, TASK_ID_PREVIEW_LENGTH)}…</span>
            <CopyButton
              text={taskId}
              label={tr("复制")}
              successLabel="✓"
              size="sm"
              variant="ghost"
            />
          </div>
        );
      },
    },
    {
      id: "dataset",
      header: tr("数据集"),
      cell: ({ row }) => <span>{row.original.dataset ?? "-"}</span>,
    },
    {
      id: "extractor",
      header: tr("抽取器"),
      cell: ({ row }) => <span className="text-xs">{row.original.extractor ?? "-"}</span>,
    },
    {
      id: "splitter",
      header: tr("切片器"),
      cell: ({ row }) => <span className="text-xs">{row.original.splitter ?? "-"}</span>,
    },
    {
      id: "state",
      header: tr("状态"),
      cell: ({ row }) => <TaskStatusBadge state={row.original.state} />,
    },
    {
      id: "progress",
      header: tr("进度"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.success}/{row.original.success + row.original.failed}
        </span>
      ),
    },
    {
      id: "created_at",
      header: tr("创建时间"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {fmtRelativeTime(row.original.created_at)}
        </span>
      ),
    },
    {
      id: "actions",
      header: tr("操作"),
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation(); // 不触发行 click 路由
            handleRerunClick(row.original);
          }}
          data-testid={`rerun-${row.original.task_id}`}
        >
          <RefreshCw className="mr-1 h-3 w-3" />
          {tr("重跑")}
        </Button>
      ),
    },
  ];

  return (
    <>
      <DataTable<ExtractTaskRow>
        dataSource={rows}
        columns={columns}
        rowKey="task_id"
        loading={loading}
        onRowClick={handleRowClick}
        rowClassName={() => "cursor-pointer hover:bg-muted/50"}
        emptyText={
          <DataEmpty icon={FileText} title={tr("暂无任务")} description={tr("暂无任务描述")} />
        }
        pagination={
          total > ZERO
            ? {
                current: page + ONE,
                pageSize,
                total,
                onChange: (pageNum) => onPageChange(pageNum - ONE),
              }
            : undefined
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner
            variant="destructive"
            title={tr("加载任务失败")}
            description={error}
            action={
              <Button variant="outline" size="sm" onClick={onRetry}>
                {tr("刷新")}
              </Button>
            }
          />
        </div>
      ) : null}
      {confirmRow ? (
        <AppConfirm
          open
          onOpenChange={(open) => {
            if (!open) {
              setConfirmRow(null);
            }
          }}
          title={tr("重跑确认")}
          description={tr("重跑将基于历史参数启动新任务, 是否继续?")}
          onConfirm={() => {
            void handleRerunConfirm();
          }}
        />
      ) : null}
      <p className="mt-2 text-xs text-muted-foreground">
        {tr("任务列表")} · {tr("总数")}: {total} · {tr("成功")}: {totalSuccess} · {tr("失败")}:{" "}
        {totalFailed}
      </p>
    </>
  );
};

/** @client-bff */
export default ExtractTasksTable;
