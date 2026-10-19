"use client";
// admin/pre-analysis 章节目录客户端组件 (2026-07-09)
// 调 getPreAnalysisChapterStructure 拉扁平 JSON, 客户端嵌套结构扁平化 + indent 列.
// 默认全部折叠 (用户进页只看 L1 节点), 点击 chevron 展开/收起.
// 复用 <DataTable<T>> + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty>.

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { getPreAnalysisChapterStructure, type ChapterTreeNode } from "@/lib/api/pre-analysis";

/** 章节树展平后的扁平行 (UI 内部类型) */
interface FlatChapterRow {
  id: string;
  depth: number;
  title: string;
  pageRange: string;
  childCount: number;
  hasChildren: boolean;
}

/** 每级缩进宽度 (px), 章节标签左移对齐 */
const INDENT_PX_PER_LEVEL = 24;
/** chevron 按钮尺寸 (h-/w- Tailwind class), 跟缩进空格 w-6 对齐 */
const CHEVRON_BUTTON_CLASS = "h-6 w-6";
/** 叶子节点占位宽度, 跟 chevron 按钮对齐, 防止缩进抖动 */
const LEAF_PLACEHOLDER_CLASS = "inline-block w-6";
/** 表格最大高度 (像素), 启用 sticky 表头 */
const TABLE_MAX_HEIGHT_PX = 600;
/** 章节标签文字大小 class */
const TITLE_TEXT_CLASS = "text-sm";
/** 缩进容器 class */
const INDENT_ROW_CLASS = "flex items-center gap-1";
/** 根节点深度 (flattenChapters 起始) */
const ROOT_DEPTH = 0;
/** 节点深度递增量 */
const DEPTH_INCREMENT = 1;
/** Object.keys 返回 0 时表示字典空 */
const EMPTY_KEY_LENGTH = 0;

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 递归扁平化状态 (闭包上下文, 避免 max-params 4 限制).
 */
interface FlattenContext {
  collapsed: Record<string, boolean>;
  acc: FlatChapterRow[];
}

/**
 * 递归扁平化 + 应用 collapsed 状态 (深度优先).
 * 用户点 chevron → setCollapsed(record) → 重 flatten, 客户端无后端 roundtrip.
 * collapsed[id] === true → 折叠; 缺省 (undefined) 或 false → 展开.
 * 默认空字典 = 全部展开. UI 端用 initialCollapsed 预填 L1 之外节点 → 进页只看 L1.
 * @param nodes 当前层节点
 * @param ctx 折叠字典 + 累加器上下文
 * @param depth 当前深度 (root = 0)
 */
const flattenChapters = (nodes: ChapterTreeNode[], ctx: FlattenContext, depth: number): void => {
  for (const node of nodes) {
    ctx.acc.push({
      id: node.id,
      depth,
      title: node.title,
      pageRange: `${node.page_start} – ${node.page_end}`,
      childCount: node.children.length,
      hasChildren: node.children.length > EMPTY_KEY_LENGTH,
    });
    if (node.children.length > EMPTY_KEY_LENGTH && ctx.collapsed[node.id] !== true) {
      flattenChapters(node.children, ctx, depth + DEPTH_INCREMENT);
    }
  }
};

/**
 * 从嵌套树中收集 L1 之外所有节点 ID (作为 collapsed 字典初值).
 * @param nodes L1 节点列表
 * @returns id → true 字典 (L1 之外全部折叠)
 */
const buildInitialCollapsed = (nodes: ChapterTreeNode[]): Record<string, boolean> => {
  const result: Record<string, boolean> = {};
  const visit = (list: ChapterTreeNode[]): void => {
    for (const node of list) {
      if (node.children.length > EMPTY_KEY_LENGTH) {
        result[node.id] = true;
        visit(node.children);
      }
    }
  };
  visit(nodes);
  return result;
};

/**
 * admin/pre-analysis 章节目录客户端组件 (2026-07-09)
 *
 * 调 getPreAnalysisChapterStructure 拉嵌套 chapter 树, 客户端 flattenChapters 展开
 * + 应用 collapsed 状态 → DataTable 4 列 (标题含 chevron + indent / 页范围 / 子章节数).
 * 默认全部折叠, 用户逐级点开. 章节数小 (< 100), 不分页, maxHeight=600px 滚动.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisChaptersClient = ({ params }: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id, "chapter_structure"],
    queryFn: () => getPreAnalysisChapterStructure(params.task_id),
  });

  // 数据到位后, 把 L1 之外所有节点预先标记为折叠 (用户进页只看 L1)
  useEffect(() => {
    if (data && Object.keys(collapsed).length === EMPTY_KEY_LENGTH) {
      setCollapsed(buildInitialCollapsed(data.chapters));
    }
  }, [data, collapsed]);

  // DataTable 未用 React.memo, columns/dataSource 引用稳定性无关. L1 数 < 100,
  // DFS 微秒级, 直接在组件体内算 flattened + columns, 避免 useMemo/useCallback
  // 失效但徒增心智负担.
  const flattened: FlatChapterRow[] = [];
  if (data) {
    flattenChapters(data.chapters, { collapsed, acc: flattened }, ROOT_DEPTH);
  }

  const columns: ColumnDef<FlatChapterRow>[] = [
    {
      accessorKey: "title",
      cell: (ctx) => {
        const row = ctx.row.original;
        const isCollapsed = collapsed[row.id] === true;
        return (
          <div
            className={INDENT_ROW_CLASS}
            style={{ paddingLeft: `${row.depth * INDENT_PX_PER_LEVEL}px` }}
          >
            {row.hasChildren ? (
              <Button
                aria-label={translate("展开章节")}
                className={CHEVRON_BUTTON_CLASS}
                data-testid={`chapter-toggle-${row.id}`}
                onClick={() => {
                  setCollapsed((prev) => ({ ...prev, [row.id]: !prev[row.id] }));
                }}
                size="icon"
                variant="ghost"
              >
                {isCollapsed ? (
                  <ChevronRight className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            ) : (
              <span className={LEAF_PLACEHOLDER_CLASS} />
            )}
            <span className={TITLE_TEXT_CLASS}>{row.title}</span>
          </div>
        );
      },
      header: () => translate("标题"),
    },
    {
      accessorKey: "pageRange",
      header: () => translate("页范围"),
    },
    {
      accessorKey: "childCount",
      header: () => translate("子章节"),
    },
  ];

  return (
    <div className="space-y-6">
      <BackLink href={`/admin/pre-analysis/${params.task_id}`} label={translate("返回")} />
      <PageHero
        description={
          data
            ? `${translate("总章节")}: ${data.total_chapters} · ${translate("toc 来源")}: ${data.toc_source}`
            : undefined
        }
        eyebrow="admin"
        title={translate("章节目录")}
      />
      {error ? <ErrorBanner description={String(error)} variant="destructive" /> : null}
      {data ? (
        <DataTable<FlatChapterRow>
          columns={columns}
          dataSource={flattened}
          emptyText={<DataEmpty title={translate("无章节数据")} />}
          loading={isLoading}
          maxHeight={TABLE_MAX_HEIGHT_PX}
          pagination={undefined}
          rowKey="id"
        />
      ) : null}
    </div>
  );
};
