"use client";
// 关系列表 client 子组件 (2026-06-12) — 接 RSC 灌的 initialData, 用 DataTable 渲染.
// 列定义里 t() 必须放在组件内 (翻译 hook).
//   关系天然需要 src+type+dst 复合 rowKey, 预生成 _key.
// (2026-06-14) React 19 use(promise): 接 RSC 传的 Promise, Suspense 边界控制 loading
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { Badge } from "@/components/ui/badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { type RelationRow } from "@/lib/api/knowledge";
import { DELAY } from "@/lib/motion";
import { use } from "react";
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";

/** 关系行类型 (含复合 _key) */
type Row = RelationRow & { _key: string };

/**
 * 关系列表组件属性
 * @property relationsPromise - 关系数据 Promise (React use() 模式)
 */
interface Props {
  relationsPromise: Promise<RelationRow[]>;
}

/**
 * RelationsTable - 关系列表组件
 * @param props.relationsPromise - 关系数据 Promise (React use() 模式)
 * @client-bff
 */
export const RelationsTable = ({ relationsPromise }: Props) => {
  const tr = useTranslations();
  const initialData = use(relationsPromise);
  const total = initialData.length;
  // DataTable 的 rowKey 只接受单字段; 关系天然需要 src+type+dst 复合, 这里预生成唯一 key
  const rows: Row[] = initialData.map((row, idx) => ({
    ...row,
    _key: `${row.src}-${row.type}-${row.dst}-${idx}`,
  }));

  // 列定义用 t() 翻译, 必须放在组件内
  const columns: ColumnDef<Row>[] = [
    {
      accessorKey: "type",
      cell: (ctx) => (
        <Badge variant="outline" className="font-normal">
          {ctx.row.original.type}
        </Badge>
      ),
      header: () => tr("类型"),
      size: 128,
    },
    {
      accessorKey: "src",
      cell: (ctx) => (
        <div className="flex flex-col gap-0.5">
          <Badge variant="secondary" className="font-normal text-xs w-fit">
            {ctx.row.original.src_label}
          </Badge>
          <span className="num text-base">
            {ctx.row.original.src_name || ctx.row.original.src_business_id || "—"}
          </span>
        </div>
      ),
      header: () => tr("起点"),
      size: 192,
    },
    {
      meta: { align: "center" },
      accessorKey: "arrow",
      cell: () => <span className="text-muted-foreground">→</span>,
      header: () => "→",
      size: 40,
    },
    {
      accessorKey: "dst",
      cell: (ctx) => (
        <div className="flex flex-col gap-0.5">
          <Badge variant="secondary" className="font-normal text-xs w-fit">
            {ctx.row.original.dst_label}
          </Badge>
          <span className="num text-base">
            {ctx.row.original.dst_name || ctx.row.original.dst_business_id || "—"}
          </span>
        </div>
      ),
      header: () => tr("终点"),
      size: 192,
    },
    {
      accessorKey: "props",
      cell: (ctx) => {
        const hasProps =
          Object.keys(ctx.row.original.props).filter((key) => key !== "onMatch").length > ZERO;
        if (!hasProps) {
          return <span className="text-muted-foreground">—</span>;
        }
        return (
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(ctx.row.original.props)
              .filter(([key]) => key !== "onMatch")
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
        );
      },
      header: () => tr("属性"),
    },
  ];

  return (
    <div className="flex h-full flex-col gap-8">
      <PageHero
        eyebrow={tr("知识图谱")}
        title={tr("全部关系")}
        meta={
          <span className="num text-sm text-muted-foreground/60">
            {total} {tr("条关系")}
          </span>
        }
        description={tr("Neo4j 中所有关系的类型、起点、终点和属性。")}
        backHref="/knowledge"
        backLabel={tr("返回知识图谱")}
      />

      <Reveal delay={DELAY.primary}>
        <DataTable
          dataSource={rows}
          columns={columns}
          rowKey="_key"
          emptyText={<DataEmpty title={tr("暂无关系")} />}
        />
      </Reveal>
    </div>
  );
};
