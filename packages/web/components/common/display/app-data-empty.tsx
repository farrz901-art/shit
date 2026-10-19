// 通用空态组件 (2026-06-14 抽): 5 个 knowledge 页 + evaluate 页的 "暂无数据" 统一入口
//
// 跟 shadcn/ui Empty 配套, 提供 2 个常见用法:
//   1. 表格内 (table body) — 不需要边框, 居中
//   2. 整页 (no data) — 有边框, 占满
//
// 用 lucide 图标 (项目禁用 emoji, 见 [[feedback-no-emoji-use-lucide-icons]]).
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * 空态统一属性接口 — 图标、标题、描述、变体及自定义类名
 * @shared
 * @property icon Lucide 图标组件 (可选, 不传则不画图标)
 * @property title 主标题 (必填)
 * @property description 副描述 (可选)
 * @property variant "table" (嵌入表格, 无边框) / "page" (占满整页, 有边框)
 * @property className 自定义类名
 */
interface DataEmptyProps {
  /** Lucide 图标组件 (e.g. Database, FileText, Network). 不传则不画图标 (纯文本态, 给 i18n t() 翻译用) */
  icon?: LucideIcon;
  /** 主标题 (必填) */
  title: string;
  /** 副描述 (可选, 1 句话说明为什么空 / 怎么操作) */
  description?: string;
  /** "table" 嵌入表格 body (无边框, 紧凑); "page" 占满整页 (有边框) */
  variant?: "table" | "page";
  /** 自定义 className, 覆盖默认布局 */
  className?: string;
}

/**
 * 空态统一组件. 替代 5+ 页重复的 "暂无 XXX" 文本 + 图标.
 * 表格内 (`variant="table"`) 不画 dashed border, 避免跟 table 自身边框冲突.
 * @shared
 * @param props.icon Lucide 图标组件 (可选)
 * @param props.title 主标题
 * @param props.description 副描述
 * @param props.variant "table" (嵌入表格) / "page" (占满整页)
 * @returns 空态 Empty JSX
 */
export const DataEmpty = ({
  icon: Icon,
  title,
  description,
  variant = "table",
  className,
}: DataEmptyProps) => (
  <Empty
    className={cn(
      // 表格内: 不要 border-dashed 跟 table border 打架, 减 padding
      variant === "table" && "border-0 p-8 [&_svg]:text-muted-foreground",
      className,
    )}
  >
    <EmptyHeader>
      {Icon && (
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
      )}
      <EmptyTitle>{title}</EmptyTitle>
      {description && <EmptyDescription>{description}</EmptyDescription>}
    </EmptyHeader>
  </Empty>
);
