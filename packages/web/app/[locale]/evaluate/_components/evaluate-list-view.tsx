"use client";
// 评估历史列表 client 视图 (2026-06-12, Task 19).
// 父 page 改 RSC 后, 数据从 server fetch 灌进来, 客户端管 i18n / 路由跳转 / DataTable.
// (2026-06-14) Sprint 1.6 改: 接 Promise + use(promise) (跟 nodes/datasets/relations/AdminUsers 同步)
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { useLocale, useTranslations } from "next-intl";
import { ClipboardList } from "lucide-react";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import type { EvaluationRunSummary } from "@/lib/evaluate/types";
import { LocalizedLink } from "@/components/i18n/localized-link";
import { StatusBadge } from "@/components/evaluate/status-badge";
import { templateUrl } from "@/lib/api/evaluate";
import { DELAY } from "@/lib/motion";
import { formatDateTime } from "@/lib/date";
import { use } from "react";
import { useRouter } from "@/i18n/navigation";

/** Locale-aware 短日期格式: zh 6/11 14:30, en 6/11, 2:30 PM */
const fmtDate = (iso: string, locale: string): string => formatDateTime(iso, locale);

/** 最小填充长度 @shared */
const MIN_PAD_LENGTH = 2;
/** 填充字符 @shared */
const PAD_CHAR = "0";
/** 行索引基数 @shared */
const FIRST_INDEX = 1;
/** 空数组判定值 @shared */
const EMPTY_LENGTH = 0;

/** EvaluateListView props
 * @property runsPromise - 评估运行列表 Promise (供 use() 消费)
 * @shared
 */
interface Props {
  runsPromise: Promise<EvaluationRunSummary[]>;
}

/** EvaluateListView - 评估历史列表 client 视图
 * @param runsPromise - 评估运行列表 Promise
 * @returns 评估历史列表 JSX
 * @client-bff
 */
export const EvaluateListView = ({ runsPromise }: Props) => {
  const trans = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const runs = use(runsPromise);

  const columns: ColumnDef<EvaluationRunSummary>[] = [
    {
      accessorKey: "index",
      cell: (ctx) => (
        <span className="num text-sm text-muted-foreground">
          {String(ctx.row.index + FIRST_INDEX).padStart(MIN_PAD_LENGTH, PAD_CHAR)}
        </span>
      ),
      header: () => "#",
      size: 56,
    },
    {
      accessorKey: "dataset_name",
      cell: (ctx) => (
        <span className="truncate text-sm font-medium">{ctx.row.original.dataset_name}</span>
      ),
      header: () => trans("名称"),
    },
    {
      accessorKey: "status",
      cell: (ctx) => <StatusBadge status={ctx.row.original.status} />,
      header: () => trans("状态"),
      size: 120,
    },
    {
      accessorKey: "total_samples",
      cell: (ctx) => {
        if (ctx.row.original.status === "running") {
          return (
            <span className="num text-sm text-muted-foreground">
              {ctx.row.original.successful + ctx.row.original.failed}/
              {ctx.row.original.total_samples}
            </span>
          );
        }
        return (
          <span className="num text-sm text-muted-foreground">
            {trans("{total} 题", { total: ctx.row.original.total_samples })}
          </span>
        );
      },
      header: () => trans("题数"),
      size: 96,
    },
    {
      accessorKey: "created_at",
      cell: (ctx) => (
        <span className="num text-sm text-muted-foreground">
          {fmtDate(ctx.row.original.created_at, locale)}
        </span>
      ),
      header: () => trans("时间"),
      size: 96,
    },
    {
      meta: { align: "right" },
      accessorKey: "arrow",
      cell: () => <span className="text-muted-foreground">→</span>,
      header: () => "",
      size: 32,
    },
  ];

  const hasRuns = runs.length > EMPTY_LENGTH;

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <PageHero
        eyebrow={trans("评估")}
        title={trans("评估历史")}
        description={trans("上传 CSV, 让大模型作答, 自动评分")}
      />

      <Reveal delay={DELAY.primary}>
        <div className="flex items-center gap-3">
          <LocalizedLink
            href="/evaluate/new"
            className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90"
          >
            {trans("+ 新建评估")}
          </LocalizedLink>
          <a
            href={templateUrl()}
            download="eval_template.csv"
            className="rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition-colors hover:bg-muted/30"
          >
            {trans("↓ 下载模板")}
          </a>
        </div>
      </Reveal>

      {hasRuns && (
        <Reveal delay={DELAY.data}>
          <DataTable<EvaluationRunSummary>
            dataSource={runs}
            columns={columns}
            rowKey="id"
            onRowClick={(run) => router.push(`/evaluate/${run.id}`)}
          />
        </Reveal>
      )}
      {!hasRuns && (
        <Reveal delay={DELAY.empty}>
          <DataEmpty
            icon={ClipboardList}
            title={trans("还没有评估")}
            description={trans("上传一个问答 CSV, 让大模型自动跑评估")}
            variant="page"
          />
        </Reveal>
      )}
    </div>
  );
};
