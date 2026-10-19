"use client";
// 任务产物文件列表组件 — 使用 DataTable 展示文件, 支持查看 markdown 文件 (2026-06-23 从 task-detail-client 提取)
import { type ColumnDef, DataTable, DataEmpty } from "@/components/common";
import { FileText, Image as ImageIcon } from "lucide-react";
import { LocalizedLink } from "@/components/i18n";
import { useTranslations } from "next-intl";
import type { IngestTask } from "@/lib/api";

/** 基础常量 */
const KB_DIVISOR = 1024;
const KB_FIXED = 1;
const ZERO_VALUE = 0;

/**
 * OutputFile - 产物文件信息
 * @property name - 文件名
 * @property size - 文件大小
 * @property mime - MIME 类型
 * @property error - 错误信息 (可选)
 * @property taskId - 任务 ID
 */
export interface OutputFile {
  name: string;
  size: number;
  mime: string;
  error?: string;
  taskId: string;
}

/**
 * renderFileIcon - 渲染文件图标
 * @param file - 文件信息
 * @returns JSX 图标
 */
const renderFileIcon = (file: OutputFile): React.ReactNode => {
  if (file.mime === "image/svg+xml") {
    return <ImageIcon className="h-4 w-4 text-muted-foreground" />;
  }
  return <FileText className="h-4 w-4 text-muted-foreground" />;
};

/**
 * renderFileSize - 渲染文件大小
 * @param file - 文件信息
 * @returns JSX 大小文本
 */
const renderFileSize = (file: OutputFile): React.ReactNode => {
  const sizeKB = (file.size / KB_DIVISOR).toFixed(KB_FIXED);
  return <span className="text-xs text-muted-foreground">{sizeKB} KB</span>;
};

/**
 * renderViewLink - 渲染查看链接 (只 md 文件)
 * @param file - 文件信息
 * @param translate - i18n 翻译函数
 * @returns JSX 链接或 null
 */
const renderViewLink = (
  file: OutputFile,
  translate: ReturnType<typeof useTranslations>,
): React.ReactNode => {
  if (file.mime === "text/markdown") {
    return (
      <LocalizedLink
        href={`/output/${encodeURIComponent(file.taskId)}/${encodeURIComponent(file.name)}`}
        className="text-sm text-clay hover:underline"
      >
        {translate("查看")}
      </LocalizedLink>
    );
  }
  return null;
};

/**
 * useOutputColumns - 产物表列定义
 * @param translate - i18n 翻译函数
 * @returns 列定义数组
 */
const useOutputColumns = (
  translate: ReturnType<typeof useTranslations>,
): ColumnDef<OutputFile>[] => [
  {
    id: "name",
    accessorKey: "name",
    cell: (ctx) => (
      <div className="flex items-center gap-2">
        {renderFileIcon(ctx.row.original)}
        <span className="font-mono text-sm">{ctx.row.original.name}</span>
      </div>
    ),
    header: () => translate("文件名"),
  },
  {
    id: "size",
    accessorKey: "size",
    cell: (ctx) => renderFileSize(ctx.row.original),
    header: () => translate("大小"),
    size: 120,
  },
  {
    meta: { align: "right" },
    id: "actions",
    accessorKey: "actions",
    cell: (ctx) => renderViewLink(ctx.row.original, translate),
    header: () => translate("操作"),
    size: 96,
  },
];

/**
 * TaskFiles 组件属性
 * @property task - 任务数据
 */
interface Props {
  task: IngestTask;
}

/**
 * TaskFiles - 任务产物文件列表组件
 * @param props.task - 任务数据
 * @client-bff
 */
export const TaskFiles = ({ task }: Props) => {
  const translate = useTranslations();
  const columns = useOutputColumns(translate);

  const hasFiles = task.output_files && task.output_files.length > ZERO_VALUE;
  if (hasFiles) {
    return (
      <DataTable<OutputFile>
        dataSource={task.output_files!.map((file) => ({ ...file, taskId: task.id }))}
        columns={columns}
        rowKey="name"
      />
    );
  }

  let emptyText = "";
  if (task.state === "completed") {
    emptyText = translate("没有产物");
  } else {
    emptyText = translate("暂无产物, 等待任务完成…");
  }
  return <DataEmpty title={emptyText} variant="page" />;
};
