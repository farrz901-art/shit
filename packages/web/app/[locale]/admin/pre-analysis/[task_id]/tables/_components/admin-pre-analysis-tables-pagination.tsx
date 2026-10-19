/**
 * 表格 viewer 分页条 (2026-07-09 refactor)
 *
 * 从 tables client 拆出来的纯展示组件, shadcn Pagination 组件套壳:
 * - Pagination → PaginationContent → [PaginationPrevious, PaginationItem×N, PaginationNext]
 * - ellipsis 走 PaginationEllipsis, 当前页走 PaginationLink isActive
 * - 全部页号按钮 + 省略号逻辑封在 buildVisiblePages (内部纯函数)
 *
 * Props 化: 数据从外面传 (allPages + currentPage), 点击通过 onPageChange 上抛.
 * 上层 (tables client) 负责 router.push URL 跳转.
 */
"use client";

import { useTranslations } from "next-intl";
import type { MouseEvent, ReactElement } from "react";

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { INDEX_NOT_FOUND, ONE, ZERO } from "@/const/index";

/** ellipsis 左侧 (起点) 默认显示的页数: P1, P2, P3 全部可见 */
const ELLIPSIS_LEFT_PAGE_COUNT = 3;
/** ellipsis 右侧 (终点) 默认显示的页数: 倒数 2 页全部可见 */
const ELLIPSIS_RIGHT_PAGE_COUNT = 2;
/** 当前页左右各显示几个 (siblings) */
const ELLIPSIS_SIBLING_COUNT = 1;
/** siblings 总数 (左 + 右) */
const ELLIPSIS_SIBLING_SIDES = 2;
/** for 循环迭代步长 */
const LOOP_STEP = 1;
/** 当前页跟左/右 ellipsis 的最小间隔 */
const ADJACENT_OFFSET = 1;
/** 禁用态样式: 不响应指针 + 半透明 (跟 data-table-pagination 一致) */
const DISABLED_CLASS = "pointer-events-none opacity-50";

/** 单项可见的页号或 ellipsis 渲染槽 */
type VisibleItem = { kind: "page"; page: number } | { kind: "ellipsis"; key: string };

/**
 * 算可见页号按钮 + ellipsis 位置 (shadcn 标准 pagination 风格):
 * 首 3 + 当前 ±1 + 末 2, 中间 ... 收起. 总数较少时全显示.
 *
 * @param allPages 全部有表格的 PDF 页号 (升序数组)
 * @param currentIdx 当前页在 allPages 中的下标 (< 0 表示未选)
 * @returns 渲染列表, 元素要么是页号要么是 ellipsis 槽
 */
const buildVisiblePages = (allPages: number[], currentIdx: number): VisibleItem[] => {
  const totalThreshold =
    ELLIPSIS_LEFT_PAGE_COUNT +
    ELLIPSIS_RIGHT_PAGE_COUNT +
    ELLIPSIS_SIBLING_SIDES * ELLIPSIS_SIBLING_COUNT +
    LOOP_STEP;
  if (allPages.length <= totalThreshold) {
    return allPages.map((p) => ({ kind: "page" as const, page: p }));
  }

  const leftEnd = ELLIPSIS_LEFT_PAGE_COUNT;
  const rightStart = allPages.length - ELLIPSIS_RIGHT_PAGE_COUNT;
  const siblingsStart = Math.max(leftEnd + ADJACENT_OFFSET, currentIdx - ELLIPSIS_SIBLING_COUNT);
  const siblingsEnd = Math.min(rightStart - ADJACENT_OFFSET, currentIdx + ELLIPSIS_SIBLING_COUNT);

  const visible: VisibleItem[] = [];

  for (let idx = 0; idx < leftEnd; idx += LOOP_STEP) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  if (siblingsStart > leftEnd + ADJACENT_OFFSET) {
    visible.push({ kind: "ellipsis", key: "left" });
  }

  for (let idx = siblingsStart; idx <= siblingsEnd; idx += LOOP_STEP) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  if (siblingsEnd < rightStart - ADJACENT_OFFSET) {
    visible.push({ kind: "ellipsis", key: "right" });
  }

  for (let idx = rightStart; idx < allPages.length; idx += LOOP_STEP) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  return visible;
};

/**
 * PaginationBar 组件 Props.
 * @property allPages 全部有表格的 PDF 页号 (升序)
 * @property currentPage 当前页号 (可能 null = 初始未确定)
 * @property onPageChange 点击页号回调 (含 prev/next/页号按钮)
 */
interface TablesPaginationBarProps {
  /** 全部有表格的 PDF 页号 (升序数组) */
  allPages: number[];
  /** 当前页号 (可能 null = 初始未确定) */
  currentPage: number | null;
  /** 点击页号回调 (含 prev/next/页号按钮) */
  onPageChange: (page: number) => void;
}

/**
 * 表格 viewer 分页条 (2026-07-09).
 *
 * 纯展示组件: 数据从外面传 (allPages + currentPage), 点击通过 onPageChange 上抛.
 * shadcn Pagination 套壳, 含 ellipsis 自动折叠. 上层负责 router.push URL 跳转.
 *
 * @param props - 组件属性
 * @param props.allPages - 全部有表格的 PDF 页号
 * @param props.currentPage - 当前页号
 * @param props.onPageChange - 点击页号回调
 * @returns 分页条 React 元素 (无页时返 null)
 * @client-bff
 */
export const TablesPaginationBar = ({
  allPages,
  currentPage,
  onPageChange,
}: TablesPaginationBarProps): ReactElement | null => {
  const translate = useTranslations();

  if (allPages.length === ZERO) {
    return null;
  }

  const currentIdx = currentPage === null ? INDEX_NOT_FOUND : allPages.indexOf(currentPage);
  const visibleItems = buildVisiblePages(allPages, currentIdx);
  const prevPage =
    currentIdx > ZERO && currentPage !== null ? (allPages[currentIdx - ONE] ?? null) : null;
  const nextPage =
    currentIdx >= ZERO && currentIdx < allPages.length - ONE && currentPage !== null
      ? (allPages[currentIdx + ONE] ?? null)
      : null;

  const dispatchPage = (e: MouseEvent, target: number | null) => {
    e.preventDefault();
    if (target !== null) {
      onPageChange(target);
    }
  };

  const renderPageLink = (page: number): ReactElement => {
    const isCurrent = page === currentPage;
    return (
      <PaginationItem key={page}>
        <PaginationLink
          aria-current={isCurrent ? "page" : undefined}
          aria-label={`P${page}`}
          data-testid={`page-button-${page}`}
          href={`?page=${page}`}
          isActive={isCurrent}
          onClick={(e) => {
            dispatchPage(e, page);
          }}
          size="default"
        >
          P{page}
        </PaginationLink>
      </PaginationItem>
    );
  };

  return (
    <Pagination aria-label={translate("分页")} data-testid="tables-pagination">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            aria-label={translate("上一页")}
            className={prevPage === null ? DISABLED_CLASS : undefined}
            data-testid="page-prev"
            href={prevPage !== null ? `?page=${prevPage}` : undefined}
            onClick={(e) => {
              dispatchPage(e, prevPage);
            }}
            text={translate("上一页")}
          />
        </PaginationItem>

        {visibleItems.map((item) => {
          if (item.kind === "ellipsis") {
            return (
              <PaginationItem data-testid={`ellipsis-${item.key}`} key={item.key}>
                <PaginationEllipsis />
              </PaginationItem>
            );
          }
          return renderPageLink(item.page);
        })}

        <PaginationItem>
          <PaginationNext
            aria-label={translate("下一页")}
            className={nextPage === null ? DISABLED_CLASS : undefined}
            data-testid="page-next"
            href={nextPage !== null ? `?page=${nextPage}` : undefined}
            onClick={(e) => {
              dispatchPage(e, nextPage);
            }}
            text={translate("下一页")}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
};
