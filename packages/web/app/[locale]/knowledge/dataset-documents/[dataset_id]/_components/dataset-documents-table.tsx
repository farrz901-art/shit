"use client";
// 数据集文档列表 client 子组件 (2026-06-12, Task 18) — 接 RSC 灌的 initialData, 管本地分页.
// (2026-06-14) 切到 DataTable<T> 统一抽象, 删手写 Table/Pagination (137 → 50 行)
// (2026-06-14) React 19 use(promise): 接 RSC 传的 Promise, Suspense 边界控制 loading
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import type { DatasetRow, QAListResponse } from "@/lib/api/knowledge";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { Badge } from "@/components/ui/badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ZERO } from "@/const";
import { FileText } from "lucide-react";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { DELAY } from "@/lib/motion";
import { use } from "react";

/** statusStyle - 文档索引状态 → 样式映射表 */
const statusStyle: Record<string, string> = {
  completed: "bg-status-success/10 text-status-success",
  error: "bg-status-error/10 text-status-error",
  indexing: "bg-status-running/10 text-status-running animate-pulse",
  queued: "bg-muted text-muted-foreground",
};

/** Props - DatasetDocumentsTable 组件属性 */
interface Props {
  /** 数据集 ID */
  datasetId: string;
  /** 数据集列表 Promise (用于查找数据集名称) */
  datasetsPromise: Promise<DatasetRow[]>;
  /** QA 文档列表 Promise */
  qaPromise: Promise<QAListResponse>;
}

/** DatasetDocumentsTable - 数据集文档列表组件, 含 DataTable 展示文档名、状态和预览
 * @client-bff
 */
export const DatasetDocumentsTable = ({ datasetId, datasetsPromise, qaPromise }: Props) => {
  const datasets = use(datasetsPromise);
  const datasetName = datasets?.find((doc) => doc.id === datasetId)?.name ?? datasetId;
  const initialData = use(qaPromise);
  const items = initialData?.items ?? [];
  const total = items.length;

  const columns: ColumnDef<(typeof items)[number]>[] = [
    {
      accessorKey: "name",
      cell: (ctx) => (
        <span className="font-medium">{ctx.row.original.name || ctx.row.original.id}</span>
      ),
      header: () => "文档名",
      size: 192,
    },
    {
      accessorKey: "indexing_status",
      cell: (ctx) => (
        <Badge className={statusStyle[ctx.row.original.indexing_status] ?? statusStyle.queued}>
          {ctx.row.original.indexing_status}
        </Badge>
      ),
      header: () => "状态",
      size: 112,
    },
    {
      accessorKey: "question",
      cell: (ctx) => (
        <span className="max-w-md truncate text-muted-foreground">
          {ctx.row.original.question || "—"}
        </span>
      ),
      header: () => "预览",
    },
  ];

  let metaText: string | undefined = undefined;
  if (total > ZERO) {
    metaText = `共 ${total} 条`;
  }

  return (
    <div className="flex h-full flex-col gap-8">
      <PageHero
        eyebrow="Documents"
        title={datasetName}
        meta={metaText}
        actions={<BackLink href="/knowledge/datasets" useHistory data-testid="back-link" />}
      />

      <Reveal delay={DELAY.primary}>
        <DataTable<(typeof items)[number]>
          columns={columns}
          dataSource={items}
          rowKey="id"
          emptyText={
            <DataEmpty
              icon={FileText}
              title="暂无文档"
              description="请先在 Documents 页面录入或导入文档"
            />
          }
        />
      </Reveal>
    </div>
  );
};
