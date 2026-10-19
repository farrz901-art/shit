"use client";
// 客户端表格 (2026-06-12): 接 RSC 预取的 initialData, 管本地分页.
// 切 dataset/domain 时父级调 router.refresh() 触发 RSC 重跑.
// (2026-06-14) 切到 DataTable<T> 统一抽象, 删手写 Table/Pagination (150 → 60 行)
// (2026-06-14) React 19 use(promise): 接 RSC 传的 Promise, Suspense 边界控制 loading
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { Database } from "lucide-react";
import type { DatasetRow } from "@/lib/api/knowledge";
import Link from "next/link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { DELAY } from "@/lib/motion";
import { use } from "react";

/** 空值常量 */
const EMPTY = 0;

/** Props - DatasetsTable 组件属性 */
interface Props {
  /** 数据集列表 Promise */
  datasetsPromise: Promise<DatasetRow[]>;
}

/** DatasetsTable - 数据集表格组件, 含 DataTable 展示名称/描述/文档数/字数
 * @client-bff
 */
export const DatasetsTable = ({ datasetsPromise }: Props) => {
  const initialData = use(datasetsPromise);
  const total = initialData.length;

  const columns: ColumnDef<DatasetRow>[] = [
    {
      accessorKey: "name",
      cell: (ctx) => (
        <Link
          href={`/knowledge/dataset-documents/${ctx.row.original.id}`}
          className="text-base font-medium text-foreground hover:underline"
        >
          {ctx.row.original.name}
        </Link>
      ),
      header: () => "名称",
      size: 192,
    },
    {
      accessorKey: "description",
      cell: (ctx) => (
        <span className="max-w-xs truncate text-muted-foreground">
          {ctx.row.original.description || "—"}
        </span>
      ),
      header: () => "描述",
    },
    {
      accessorKey: "document_count",
      cell: (ctx) => (
        <span className="num text-muted-foreground">{ctx.row.original.document_count ?? "—"}</span>
      ),
      header: () => "文档数",
      size: 96,
    },
    {
      accessorKey: "word_count",
      cell: (ctx) => (
        <span className="num text-muted-foreground">{ctx.row.original.word_count ?? "—"}</span>
      ),
      header: () => "字数",
      size: 96,
    },
  ];

  // 计算 meta 文本: total > 0 时显示 "共 N 个"
  let metaText: string | undefined = undefined;
  if (total > EMPTY) {
    metaText = `共 ${total} 个`;
  }

  return (
    <div className="flex h-full flex-col gap-8">
      <PageHero eyebrow="Datasets" title="数据集" meta={metaText} />

      <Reveal delay={DELAY.primary}>
        <DataTable<DatasetRow>
          columns={columns}
          dataSource={initialData}
          rowKey="id"
          maxHeight="auto"
          emptyText={
            <DataEmpty
              icon={Database}
              title="暂无数据集"
              description="可通过 Dify 同步或后端管理 API 导入数据集"
            />
          }
        />
      </Reveal>
    </div>
  );
};
