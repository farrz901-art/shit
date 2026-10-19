"use client";
// admin/pre-analysis 段落提取客户端组件 (2026-07-09)
// 调 getPreAnalysisFlaggedParagraphs 拉 CSV 解析后的 rows, 14 列 DataTable 全字段展示.
// text 列用 line-clamp-3 + AppTooltip 看完整, is_dense=true 行用 AlertTriangle + Badge,
// rule_categories 拆 4 个 deontic badge (neg/obl/cond/perm).
// 复用 <DataTable<T>> (2026-07-10 起支持列宽拖动) + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty>.

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import {
  type ColumnDef,
  DataTable,
  type TanstackColumnMeta,
} from "@/components/common/table/data-table";
import { ZERO } from "@/const/index";
import { getPreAnalysisFlaggedParagraphs, type FlaggedParagraphRow } from "@/lib/api/pre-analysis";

/** 段落页每页条数 (跟详情页产物列表一致) */
const FLAG_PAGE_SIZE = 5;
/** 初始化分页页码 */
const INITIAL_PAGE = 1;
/** 密度列小数位 */
const DENSITY_DECIMALS = 1;
/** token 列千分位分隔符 */
const THOUSAND_SEPARATOR = ",";
/** text 列最大宽度 (ch 单位) */
const TEXT_MAX_WIDTH_CH = 60;
/** 表格最大高度 (像素) */
const TABLE_MAX_HEIGHT_PX = 600;
/** total=0 时表示空数据 (DataTable 走空态) */
const EMPTY_TOTAL = ZERO;
/** (2026-07-10) deontic 4 类 badge 颜色映射 (跟 extractor.py:86 4 类一致) */
const DEONTIC_COLOR: Record<DeonticKey, string> = {
  cond: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
  neg: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  obl: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  perm: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
};
/** (2026-07-10) 未命中类别阈值 (counts[key] > NO_MATCH_THRESHOLD 才展示 badge) */
const NO_MATCH_THRESHOLD = ZERO;
/** (2026-07-10) entries 长度阈值 (entries.length === EMPTY_ENTRIES_LENGTH 时空态) */
const EMPTY_ENTRIES_LENGTH = ZERO;
/** 4 类 deontic 类型 key */
type DeonticKey = "neg" | "obl" | "cond" | "perm";
/** 4 类中文 label (i18n key 直查) */
const DEONTIC_LABEL_KEY: Record<DeonticKey, string> = {
  cond: "条件",
  neg: "否定",
  obl: "义务",
  perm: "许可",
};

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 数字保留 DENSITY_DECIMALS 位小数.
 * @param num 原始 number
 * @returns 格式化字符串 (e.g. "0.9")
 */
const formatNumber = (num: number): string => num.toFixed(DENSITY_DECIMALS);

/**
 * 千分位分隔数字 (e.g. 12000 → "12,000").
 * @param num 原始 number
 * @returns 千分位格式化字符串
 */
const formatToken = (num: number): string =>
  num.toString().replace(/\B(?=(?<group>\d{3})+(?!\d))/g, THOUSAND_SEPARATOR);

/**
 * (2026-07-10) 解析 rule_categories 字符串 (e.g. "neg=2,obl=1") → 4 类 deontic count map.
 * 容错: 空字符串 / 解析失败 → 全 0; 未知 key 忽略.
 * @param raw CSV 里的 rule_categories 字段值
 * @returns 4 类 count (无 key 的类别返 0)
 */
const parseRuleCategories = (raw: string): Record<DeonticKey, number> => {
  const empty: Record<DeonticKey, number> = { cond: ZERO, neg: ZERO, obl: ZERO, perm: ZERO };
  if (raw === "") {
    return empty;
  }
  const knownKeys = Object.keys(empty) as DeonticKey[];
  // (2026-07-10) 容错跳过: 缺字段 / 未知 key / 非数字 (filter 走 .every, 无 continue)
  const validParts = raw.split(",").filter((part) => {
    const [key, value] = part.split("=");
    return (
      key !== undefined &&
      value !== undefined &&
      knownKeys.includes(key as DeonticKey) &&
      Number.isFinite(Number(value))
    );
  });
  return validParts.reduce<Record<DeonticKey, number>>((acc, part) => {
    const [key, value] = part.split("=");
    if (key === undefined || value === undefined) {
      return acc;
    }
    acc[key as DeonticKey] = Number(value);
    return acc;
  }, empty);
};

/**
 * admin/pre-analysis 段落提取客户端组件 (2026-07-09, 2026-07-10 升级到 14 列全展示)
 *
 * 14 列全展示: 页码 / 章节 / 段落 / 命中规则 (拆 4 badge) / 密度 / 原始密度 / 加权密度 /
 * 安全命中 / 推荐命中 / 高密度 Badge / Token / 词形 / 匹配关键词 / 语言.
 * 用户校对主要看 page + section + text + density, 但 6 隐藏字段全部上表避免「看不全」痛点.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisFlaggedClient = ({ params }: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const [currentPage, setCurrentPage] = useState(INITIAL_PAGE);

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id, "flagged_paragraphs"],
    queryFn: () => getPreAnalysisFlaggedParagraphs(params.task_id),
  });

  // (2026-07-10) 列宽初始值: text 列宽, density 列窄, 数字列窄
  const initialColumnSizing: Record<string, number> = {
    matched_keywords: 140,
    page: 64,
    section: 96,
    text: 360,
    rule_categories: 220,
    density: 72,
    raw_density: 88,
    weighted_density: 100,
    safe_hits: 80,
    rec_hits: 80,
    is_dense: 88,
    token_count: 96,
    lemmas: 200,
    language: 80,
  };

  const columns = useMemo<ColumnDef<FlaggedParagraphRow>[]>(
    () => [
      {
        accessorKey: "page",
        header: () => translate("页码"),
        meta: { width: 64, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "section",
        header: () => translate("章节"),
        meta: { width: 96 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "text",
        cell: (ctx) => (
          <AppTooltip content={ctx.row.original.text}>
            <span
              className="line-clamp-3 cursor-help"
              style={{ maxWidth: `${TEXT_MAX_WIDTH_CH}ch` }}
            >
              {ctx.row.original.text}
            </span>
          </AppTooltip>
        ),
        header: () => translate("段落"),
        meta: { width: 360 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "rule_categories",
        cell: (ctx) => {
          const counts = parseRuleCategories(ctx.row.original.rule_categories);
          const entries = (Object.keys(counts) as DeonticKey[]).filter(
            (key) => counts[key] > NO_MATCH_THRESHOLD,
          );
          if (entries.length === EMPTY_ENTRIES_LENGTH) {
            return <span className="text-muted-foreground">—</span>;
          }
          return (
            <div className="flex flex-wrap gap-1">
              {entries.map((key) => (
                <Badge
                  className={DEONTIC_COLOR[key]}
                  data-testid={`rule-badge-${key}`}
                  key={key}
                  variant="secondary"
                >
                  {translate(DEONTIC_LABEL_KEY[key])} {counts[key]}
                </Badge>
              ))}
            </div>
          );
        },
        header: () => translate("命中规则"),
        meta: { width: 220 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "density",
        cell: (ctx) => formatNumber(ctx.row.original.density),
        header: () => translate("密度"),
        meta: { width: 72, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "raw_density",
        cell: (ctx) => formatNumber(ctx.row.original.raw_density),
        header: () => translate("原始密度"),
        meta: { width: 88, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "weighted_density",
        cell: (ctx) => formatNumber(ctx.row.original.weighted_density),
        header: () => translate("加权密度"),
        meta: { width: 100, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "safe_hits",
        cell: (ctx) => ctx.row.original.safe_hits,
        header: () => translate("安全命中"),
        meta: { width: 80, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "rec_hits",
        cell: (ctx) => ctx.row.original.rec_hits,
        header: () => translate("推荐命中"),
        meta: { width: 80, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "is_dense",
        cell: (ctx) =>
          ctx.row.original.is_dense ? (
            <Badge variant="destructive">
              <AlertTriangle className="mr-1 h-3 w-3" />
              {translate("高密度")}
            </Badge>
          ) : null,
        header: () => translate("高密度"),
        meta: { width: 88 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "token_count",
        cell: (ctx) => formatToken(ctx.row.original.token_count),
        header: () => translate("Token"),
        meta: { width: 96, align: "right" } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "lemmas",
        cell: (ctx) => (
          <AppTooltip content={ctx.row.original.lemmas}>
            <span className="line-clamp-2 cursor-help">{ctx.row.original.lemmas}</span>
          </AppTooltip>
        ),
        header: () => translate("词形还原"),
        meta: { width: 200 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "matched_keywords",
        cell: (ctx) => (
          <AppTooltip content={ctx.row.original.matched_keywords}>
            <span className="line-clamp-2 cursor-help">{ctx.row.original.matched_keywords}</span>
          </AppTooltip>
        ),
        header: () => translate("匹配关键词"),
        meta: { width: 140 } satisfies TanstackColumnMeta,
      },
      {
        accessorKey: "language",
        header: () => translate("语言"),
        meta: { width: 80 } satisfies TanstackColumnMeta,
      },
    ],
    [translate],
  );

  return (
    <div className="space-y-6">
      <BackLink href={`/admin/pre-analysis/${params.task_id}`} label={translate("返回")} />
      <PageHero
        description={data ? `${data.length} ${translate("条标记段落")}` : undefined}
        eyebrow="admin"
        title={translate("段落提取")}
      />
      {error ? <ErrorBanner description={String(error)} variant="destructive" /> : null}
      <DataTable<FlaggedParagraphRow>
        columns={columns}
        dataSource={data ?? []}
        emptyText={<DataEmpty title={translate("无标记段落")} />}
        initialColumnSizing={initialColumnSizing}
        loading={isLoading}
        maxHeight={TABLE_MAX_HEIGHT_PX}
        pagination={{
          current: currentPage,
          onChange: setCurrentPage,
          pageSize: FLAG_PAGE_SIZE,
          total: data?.length ?? EMPTY_TOTAL,
        }}
        rowKey="row_index"
      />
    </div>
  );
};
