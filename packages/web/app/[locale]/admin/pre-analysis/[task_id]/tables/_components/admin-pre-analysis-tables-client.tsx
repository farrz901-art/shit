"use client";
// admin/pre-analysis 表格 viewer 客户端组件 (2026-07-09)
// 调 getPreAnalysisTablePages 拉页号数组, 调 getPreAnalysisTablePage 拉当前页所有表格数据.
// pagination 显示真实 PDF 页号 (P3, P9, P12...). 当前页多个表格纵向堆叠, 动态列 DataTable 渲染.
// 复用 <DataTable<T>> + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty> + <TablesPaginationBar>.
// 跟 chapters/flagged viewer 模式一致, 差异在 URL searchParams + lazy per-page fetch + 动态列.
// (2026-07-09 refactor) pagination 拆到 _components/admin-pre-analysis-tables-pagination.tsx.

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { ZERO } from "@/const/index";
import { useRouter } from "@/i18n/navigation";
import {
  getPreAnalysisTablePage,
  getPreAnalysisTablePages,
  type TablePageItem,
  type TablePageResponse,
  type TablePagesResponse,
} from "@/lib/api/pre-analysis";
import { TablesPaginationBar } from "./admin-pre-analysis-tables-pagination";

/** tables 区域滚动到 anchor 时的 behavior 选项 */
const SCROLL_BEHAVIOR: ScrollBehavior = "smooth";
/** rowKey 拼接前缀 (table_index-行索引) */
const ROW_KEY_SEP = "-";
/** 合成行 ID 字段名 (DataTable rowKey 用) */
const ROW_ID_FIELD = "__rag_row_id__";
/** 表格 DataTable 默认行高 (跟其他 viewer 一致) */
const TABLE_MAX_HEIGHT_PX = 400;
/** DataTable 行 key 兜底字符串 (行索引序列化成字符串) */
const STRING_INDEX_BASE = 10;
/** window.location.hash 前缀字符 "#" */
const HASH_PREFIX_LENGTH = 1;
/** 没有 anchor 时的 hash 长度 ("#" = 1, "" = 0) */
const HASH_MIN_LENGTH_WITH_ANCHOR = 2;

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 从 CSV 列名构造 DataTable ColumnDef (动态列场景).
 */
const buildDynamicColumns = (columns: string[]): ColumnDef<Record<string, string>>[] =>
  columns.map((col) => ({
    accessorKey: col,
    header: col,
  }));

/**
 * 表格 viewer 客户端组件 (2026-07-09).
 *
 * 1. 拉 pages 数组 → TablesPaginationBar 渲染分页条
 * 2. 当前页用 useQuery 拉单页所有 CSV 解析数据
 * 3. 每张表渲染独立 DataTable (动态列)
 * 4. URL ?page=N 不在 pages 中 → fallback pages[0]
 * 5. URL #table-M → 数据到位后 scrollIntoView
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisTablesClient = ({ params }: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [hashHandled, setHashHandled] = useState(false);

  // ① 拉所有有表格的页号列表
  const pagesQuery = useQuery<TablePagesResponse>({
    queryKey: ["pre-analysis-tables-pages", params.task_id],
    queryFn: () => getPreAnalysisTablePages(params.task_id),
  });

  const allPages = pagesQuery.data?.pages ?? [];

  // 当前页 (URL ?page=N, 无效或缺失 → fallback pages[0])
  const pageParam = searchParams.get("page");
  const requestedPage = pageParam !== null ? Number(pageParam) : null;
  const currentPage = useMemo<number | null>(() => {
    if (allPages.length === ZERO) {
      return null;
    }
    if (requestedPage !== null && allPages.includes(requestedPage)) {
      return requestedPage;
    }
    const firstPage = allPages[ZERO];
    return firstPage ?? null;
  }, [allPages, requestedPage]);

  // ② 当前页数据 (懒加载, 只 fetch 当前页)
  const pageQuery = useQuery<TablePageResponse>({
    queryKey: ["pre-analysis-tables-page", params.task_id, currentPage],
    queryFn: () => {
      if (currentPage === null) {
        throw new Error("currentPage not ready");
      }
      return getPreAnalysisTablePage(params.task_id, currentPage);
    },
    enabled: currentPage !== null,
  });

  // ③ hash anchor 滚动: 数据加载后滚到 #table-M
  useEffect(() => {
    if (hashHandled || !pageQuery.data) {
      return;
    }
    const { hash } = globalThis.window.location;
    if (hash.length >= HASH_MIN_LENGTH_WITH_ANCHOR) {
      const el = document.getElementById(hash.slice(HASH_PREFIX_LENGTH));
      el?.scrollIntoView({ behavior: SCROLL_BEHAVIOR, block: "start" });
    }
    setHashHandled(true);
  }, [pageQuery.data, hashHandled]);

  /** 切到指定 PDF 页 (URL ?page=N). */
  const handlePageClick = useCallback(
    (page: number) => {
      router.push(`/admin/pre-analysis/${params.task_id}/tables?page=${page}`);
    },
    [router, params.task_id],
  );

  const tablesForPage = pageQuery.data?.tables ?? [];
  const tableDataPairs = useMemo(
    () =>
      tablesForPage.map((table: TablePageItem) => {
        const rowsWithId: Record<string, string>[] = table.rows.map((row, idx) => ({
          ...row,
          [ROW_ID_FIELD]: `${table.table_index}${ROW_KEY_SEP}${idx.toString(STRING_INDEX_BASE)}`,
        }));
        return {
          table,
          columns: buildDynamicColumns([...table.columns, ROW_ID_FIELD]),
          rowsWithId,
        };
      }),
    [tablesForPage],
  );

  return (
    <div className="space-y-6">
      <BackLink href={`/admin/pre-analysis/${params.task_id}`} label={translate("返回")} />
      <PageHero
        description={
          pagesQuery.data
            ? `${translate("共 {N} 页含表格").replace("{N}", String(pagesQuery.data.total))}`
            : undefined
        }
        eyebrow="admin"
        title={translate("表格查看")}
      />

      {/* pagination bar */}
      {pagesQuery.error ? (
        <ErrorBanner description={String(pagesQuery.error)} variant="destructive" />
      ) : null}
      <TablesPaginationBar
        allPages={allPages}
        currentPage={currentPage}
        onPageChange={handlePageClick}
      />

      {/* 空态: 无任何表格 */}
      {pagesQuery.data && allPages.length === ZERO ? (
        <DataEmpty
          description={translate("该任务没有提取到表格")}
          title={translate("无表格数据")}
        />
      ) : null}

      {/* page 数据 error */}
      {pageQuery.error ? (
        <ErrorBanner description={String(pageQuery.error)} variant="destructive" />
      ) : null}

      {/* 当前页所有表格 */}
      {tableDataPairs.length > ZERO ? (
        <div className="space-y-8">
          {tableDataPairs.map(({ table, columns, rowsWithId }) => (
            <div
              className="space-y-2"
              data-testid={`table-block-${table.table_index}`}
              key={table.table_index}
            >
              <h3
                className="text-sm font-medium text-muted-foreground"
                id={`table-${table.table_index}`}
              >
                {translate("表格 {index}").replace("{index}", String(table.table_index))}
                <span className="ml-2 text-xs">
                  ({table.filename} · {table.rows.length} {translate("行")})
                </span>
              </h3>
              <DataTable<Record<string, string>>
                columns={columns}
                dataSource={rowsWithId}
                emptyText={<DataEmpty title={translate("无表格数据")} />}
                loading={pageQuery.isLoading}
                maxHeight={TABLE_MAX_HEIGHT_PX}
                pagination={undefined}
                rowKey={ROW_ID_FIELD}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};
