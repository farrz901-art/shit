"use client";
// admin/pre-analysis detail 客户端组件 (2026-07-02 PR6)
// 0 自建组件: 复用 <BackLink> + <PageHero> + <DataTable> + <Badge>
// + <ErrorBanner> + <Button> 触发浏览器原生下载
// (2026-07-06) 加 ⟳ 刷新按钮 + 阶段化可见产物 + ZIP disabled 在 running 状态

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { StatCard } from "@/components/common/display/app-stat-card";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { useRouter } from "@/i18n/navigation";
import { formatElapsedMs } from "@/lib/date";
import { ONE_KB, ONE_MB, ZERO } from "@/const";
import {
  downloadPreAnalysisFile,
  downloadPreAnalysisZip,
  getPreAnalysisTask,
  parseTableFilename,
  type PreAnalysisOutputFile,
  type PreAnalysisTaskState,
} from "@/lib/api/pre-analysis";

/**
 * KIND_LABEL 映射产物 kind → 中文标签 (前端展示).
 */
const KIND_LABEL: Record<PreAnalysisOutputFile["kind"], string> = {
  chapter_structure: "章节结构",
  flagged_paragraphs: "规则段落",
  table: "表格",
  index: "Index",
};

/** 任务已完成状态常量 */
const STATE_COMPLETED: PreAnalysisTaskState = "completed";
/** 压缩包文件名后缀 */
const ZIP_FILENAME_SUFFIX = "_pre_analysis";
/** 大小显示小数位数 */
const SIZE_DECIMAL_PLACES = 1;
/** 详情页每页条数 */
const DETAIL_PAGE_SIZE = 5;
/** 分页初始页码 */
const INITIAL_PAGE = 1;
/**
 * (2026-07-08) 任务状态 → 中文标签 (前端展示). 走 lookup 避免 `translate(state)`
 * 抛 MISSING_MESSAGE — 英文 "completed" 等在 zh.json 没注册, 直接用 key 会触发错误边界,
 * 导致整个 StatCard 区无法渲染, 用户看到的就是"表格数显示为 0".
 */
const STATE_LABELS: Record<PreAnalysisTaskState, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

/**
 * (2026-07-09 viewer pages) 可在 web 端预览的产物 kind — chapter_structure 跳 chapters 子路由,
 * flagged_paragraphs 跳 flagged 子路由, table 跳 tables 子路由 (带 ?page=N#table-M).
 * index 没 viewer 页, 仍只走 download 按钮.
 */
const VIEWABLE_KINDS = ["chapter_structure", "flagged_paragraphs", "table"] as const;
type ViewableKind = (typeof VIEWABLE_KINDS)[number];

/**
 * 类型守卫: 检查 kind 是否在 VIEWABLE_KINDS 列表, 是则 narrow 成 ViewableKind.
 * @param kind 产物 kind
 * @returns true 当 kind 可在 web 端查看
 */
const isViewableKind = (kind: PreAnalysisOutputFile["kind"]): kind is ViewableKind =>
  (VIEWABLE_KINDS as readonly PreAnalysisOutputFile["kind"][]).includes(kind);

/**
 * (2026-07-09 tables viewer) 算 viewable href.
 * chapter_structure / flagged_paragraphs 跟 task_id 拼固定子路由.
 * table 需要从 filename 解析 page + table_index, URL 带 ?page=N#table-M.
 *
 * @param kind ViewableKind
 * @param taskId 任务 ID
 * @param filename (table 必填) 文件名, e.g. "tables/page-9-table-1.csv"
 * @returns 子路由 href
 */
const viewHrefForKind = (kind: ViewableKind, taskId: string, filename?: string): string => {
  if (kind === "table") {
    if (!filename) {
      throw new Error("table kind 需要 filename 算 ?page=N#table-M");
    }
    const { pageNumber, tableIndex } = parseTableFilename(filename);
    return `/admin/pre-analysis/${taskId}/tables?page=${pageNumber}#table-${tableIndex}`;
  }
  if (kind === "chapter_structure") {
    return `/admin/pre-analysis/${taskId}/chapters`;
  }
  return `/admin/pre-analysis/${taskId}/flagged`;
};

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 字节数 -> 人类可读字符串 (B / KB / MB).
 * @param bytes - 字节数
 * @returns 格式化后的字符串 (如 "1.5 MB")
 * @shared
 */
const formatSize = (bytes: number): string => {
  if (bytes < ONE_KB) {
    return `${bytes} B`;
  }
  if (bytes < ONE_MB) {
    return `${(bytes / ONE_KB).toFixed(SIZE_DECIMAL_PLACES)} KB`;
  }
  return `${(bytes / ONE_MB).toFixed(SIZE_DECIMAL_PLACES)} MB`;
};

/**
 * 拼接下载文件名: `{pdf_stem}_pre_analysis_{task_id}.zip`.
 * @param pdfFilename - PDF 文件名 (用于提取 stem)
 * @param taskId - 任务 ID
 * @returns 完整的下载文件名
 * @shared
 */
const buildZipFilename = (pdfFilename: string | undefined, taskId: string): string => {
  const stem = pdfFilename?.replace(/\.pdf$/i, "") ?? "pre_analysis";
  return `${stem}${ZIP_FILENAME_SUFFIX}_${taskId}.zip`;
};

/**
 * (2026-07-09) 构造 StatCard 点击跳转 handler: 当对应产物数 > 0 时跳到子路由 viewer 页,
 * 0 时返回 undefined (StatCard 内部据此判断是否渲染 cursor + button role).
 * @param ctx - 跳转上下文 (count + kind + router + taskId, 用对象聚合避免 max-params 4 lint)
 * @param ctx.count 对应产物数 (total_chapters / total_flagged_paragraphs)
 * @param ctx.kind 跳转目标 kind (chapter_structure / flagged_paragraphs)
 * @param ctx.router next-intl createNavigation 解构出的 useRouter 实例
 * @param ctx.taskId 任务 ID (URL 参数)
 * @returns 点击 handler 或 undefined
 */
const buildStatCardClickHandler = (ctx: {
  count: number;
  kind: ViewableKind;
  router: ReturnType<typeof useRouter>;
  taskId: string;
}): (() => void) | undefined => {
  const { count, kind, router, taskId } = ctx;
  if (count <= ZERO) {
    return undefined;
  }
  return () => {
    router.push(viewHrefForKind(kind, taskId));
  };
};

/**
 * admin/pre-analysis 详情客户端组件
 *
 * 显示 task 详情 (PDF 文件名, state, 耗时) + 产物清单 + 下载 zip 按钮.
 * 复用 BackLink + PageHero + DataTable + Badge + ErrorBanner.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisDetailClient = ({ params }: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(INITIAL_PAGE);
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id],
    queryFn: () => getPreAnalysisTask(params.task_id),
  });

  /** (2026-07-06) 手动刷新: invalidate query 重 fetch DB, 看到该 stage 已落地产物. */
  const handleRefresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["pre-analysis-task", params.task_id] });
  };

  /**
   * 下载产物 zip — fetch Blob -> createObjectURL -> 触发 <a download>.
   * @returns Promise<void>
   */
  const handleDownloadZip = async (): Promise<void> => {
    const blob = await downloadPreAnalysisZip(params.task_id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = buildZipFilename(data?.pdf_filename, params.task_id);
    anchor.click();
    URL.revokeObjectURL(url);
  };

  /**
   * (2026-07-06) 下载单个产物文件 — fetch Blob -> createObjectURL -> 触发 <a download>.
   * @param filename 产物文件名
   * @returns Promise<void>
   */
  const handleDownloadFile = async (filename: string): Promise<void> => {
    const blob = await downloadPreAnalysisFile(params.task_id, filename);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const columns: ColumnDef<PreAnalysisOutputFile>[] = [
    {
      accessorKey: "kind",
      cell: (ctx) => KIND_LABEL[ctx.row.original.kind],
      header: () => translate("类型"),
    },
    {
      accessorKey: "filename",
      header: "filename",
    },
    {
      accessorKey: "size_bytes",
      cell: (ctx) => formatSize(ctx.row.original.size_bytes),
      header: () => translate("大小"),
    },
    {
      accessorKey: "actions",
      cell: (ctx) => {
        const file = ctx.row.original;
        const viewable = isViewableKind(file.kind)
          ? viewHrefForKind(file.kind, params.task_id, file.filename)
          : null;
        return (
          <div className="flex gap-2">
            {viewable ? (
              <Button
                data-testid={`view-file-${file.filename}`}
                onClick={() => {
                  router.push(viewable);
                }}
                size="sm"
                variant="outline"
              >
                <Eye className="mr-1 h-4 w-4" />
                {translate("查看")}
              </Button>
            ) : null}
            <Button
              data-testid={`download-file-${file.filename}`}
              onClick={() => {
                void handleDownloadFile(file.filename);
              }}
              size="sm"
              variant="outline"
            >
              <Download className="mr-1 h-4 w-4" />
              {translate("下载")}
            </Button>
          </div>
        );
      },
      header: () => translate("操作"),
    },
  ];

  return (
    <div className="space-y-6">
      <BackLink href="/admin/pre-analysis" label={translate("返回")} />
      <PageHero
        description={
          data
            ? `${STATE_LABELS[data.state]} · ${translate("耗时")}: ${formatElapsedMs(data.summary.elapsed_ms)}`
            : undefined
        }
        eyebrow="admin"
        title={data?.pdf_filename ?? "-"}
      />
      {data ? (
        <div
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
          data-testid="pre-analysis-summary-stats"
        >
          <StatCard
            accent="clay"
            hint={translate("跨页候选: {N}", {
              N: data.summary.cross_page_candidates,
            })}
            index={0}
            label={translate("表格数")}
            onClick={
              data.summary.total_tables > ZERO
                ? () => {
                    router.push(`/admin/pre-analysis/${params.task_id}/tables`);
                  }
                : undefined
            }
            testId="stat-card-tables"
            value={data.summary.total_tables}
          />
          <StatCard
            accent="moss"
            hint={translate("PDF 自动识别的章节结构")}
            index={1}
            label={translate("章节数")}
            onClick={buildStatCardClickHandler({
              count: data.summary.total_chapters,
              kind: "chapter_structure",
              router,
              taskId: params.task_id,
            })}
            testId="stat-card-chapters"
            value={data.summary.total_chapters}
          />
          <StatCard
            accent="ochre"
            hint={translate("规则命中的待复核段落")}
            index={2}
            label={translate("标记段落数")}
            onClick={buildStatCardClickHandler({
              count: data.summary.total_flagged_paragraphs,
              kind: "flagged_paragraphs",
              router,
              taskId: params.task_id,
            })}
            testId="stat-card-flagged"
            value={data.summary.total_flagged_paragraphs}
          />
        </div>
      ) : null}
      {data?.summary.cross_page_candidates ? (
        <ErrorBanner
          description={translate("本任务含 N 个跨页候选表").replace(
            "{N}",
            String(data.summary.cross_page_candidates),
          )}
          variant="warning"
        />
      ) : null}
      {error ? <ErrorBanner description={String(error)} variant="destructive" /> : null}
      {data ? (
        <>
          {data.state !== STATE_COMPLETED ? (
            <ErrorBanner
              description={translate(
                "任务进行中, 已落地产物可直接下载, 全部打包 ZIP 将在完成后可用",
              )}
              variant="info"
            />
          ) : null}
          <div className="flex justify-end space-x-2">
            <Button
              data-testid="refresh-button"
              onClick={handleRefresh}
              size="sm"
              variant="outline"
            >
              <RefreshCw className="mr-1 h-4 w-4" />
              {translate("刷新")}
            </Button>
            <Button
              disabled={data.state !== STATE_COMPLETED}
              onClick={() => {
                void handleDownloadZip();
              }}
              title={
                data.state !== STATE_COMPLETED
                  ? "任务未完成, 请等待完成后下载 ZIP, 或直接下载上方单个产物"
                  : undefined
              }
            >
              {translate("下载全部 (zip)")}
            </Button>
          </div>
          <DataTable
            columns={columns}
            dataSource={data.output_files}
            emptyText={<DataEmpty title={translate("无产物")} />}
            loading={isLoading}
            pagination={{
              current: currentPage,
              pageSize: DETAIL_PAGE_SIZE,
              total: data.output_files.length,
              onChange: setCurrentPage,
            }}
            rowKey="filename"
            maxHeight="300px"
          />
        </>
      ) : null}
    </div>
  );
};
