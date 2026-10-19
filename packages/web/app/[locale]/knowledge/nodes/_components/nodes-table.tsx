"use client";
// 节点列表 client 子组件 (2026-06-12) — 接 RSC 灌的 initialData, 用 DataTable 渲染.
// 列定义里 t() 必须放在组件内 (翻译 hook).
// (2026-06-14) React 19 use(promise): 接 RSC 传的 Promise, Suspense 边界控制 loading
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { Badge } from "@/components/ui/badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { type NodeRow } from "@/lib/api/knowledge";
import { DELAY } from "@/lib/motion";
import { use } from "react";
import { useTranslations } from "next-intl";

/**
 * 节点列表组件属性
 * @property nodesPromise - 节点数据 Promise (React use() 模式)
 */
interface Props {
  nodesPromise: Promise<NodeRow[]>;
}

/**
 * NodesTable - 节点列表组件
 * @param props.nodesPromise - 节点数据 Promise (React use() 模式)
 * @client-bff
 */
export const NodesTable = ({ nodesPromise }: Props) => {
  const tr = useTranslations();
  const initialData = use(nodesPromise);
  const total = initialData.length;

  // 列定义用 t() 翻译, 必须放在组件内
  const columns: ColumnDef<NodeRow>[] = [
    {
      accessorKey: "business_id",
      cell: (ctx) => (
        <span className="num text-muted-foreground">
          {ctx.row.original.business_id || ctx.row.original.id}
        </span>
      ),
      header: () => tr("编号"),
      size: 80,
    },
    {
      accessorKey: "label",
      cell: (ctx) => (
        <Badge variant="outline" className="font-normal">
          {ctx.row.original.label}
        </Badge>
      ),
      header: () => tr("类型"),
      size: 128,
    },
    {
      accessorKey: "name",
      cell: (ctx) => <span className="num text-base">{ctx.row.original.name || "—"}</span>,
      header: () => tr("名称"),
      size: 192,
    },
    {
      accessorKey: "props",
      cell: (ctx) => (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(ctx.row.original.props)
            .filter(([key]) => key !== "id" && key !== "name")
            .map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1 rounded bg-muted/40 px-1.5 py-0.5 text-sm"
              >
                <span className="text-muted-foreground">{key}:</span>
                <span className="num">{String(value)}</span>
              </span>
            ))}
        </div>
      ),
      header: () => tr("属性"),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-8">
      <PageHero
        eyebrow={tr("知识图谱")}
        title={tr("全部节点")}
        meta={
          <span className="num text-sm text-muted-foreground/60">
            {total} {tr("个节点")}
          </span>
        }
        description={tr("Neo4j 中所有节点的 label 和属性。")}
        backHref="/knowledge"
        backLabel={tr("返回知识图谱")}
      />

      <Reveal delay={DELAY.primary}>
        <DataTable
          dataSource={initialData}
          columns={columns}
          rowKey="id"
          emptyText={<DataEmpty title={tr("暂无节点")} />}
        />
      </Reveal>
    </div>
  );
};
