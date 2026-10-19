"use client";
/**
 * 知识库 Tab 导航 — 2 个主 tab (向量库/知识图谱) + 子路径联动高亮
 * @returns JSX 元素
 * @client-bff
 */
//   向量库 (documents/qa/import) / 知识图谱 (graph/triples/batch/nodes/relations)
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

/**
 * Tab 定义
 * @property href 跳转链接
 * @property label Tab 标签
 * @property children 归属子路径列表
 */
interface TabDef {
  /** 主 tab href (Link 跳转目标) */
  href: string;
  /** Tab label */
  label: string;
  /** 哪些子路径归到本 tab (pathname.startsWith) */
  children: readonly string[];
}

/** Tab 配置列表 */
const TABS: readonly TabDef[] = [
  {
    children: [
      "/knowledge/documents",
      "/knowledge/qa",
      "/knowledge/datasets",
      "/knowledge/dataset-documents",
    ],
    href: "/knowledge/documents",
    label: "向量库",
  },
  {
    children: [
      "/knowledge/graph",
      "/knowledge/triples",
      "/knowledge/batch",
      "/knowledge/nodes",
      "/knowledge/relations",
      "/knowledge/extract", // 2026-07-01 markdown extract KG PR4 v3
    ],
    href: "/knowledge/graph",
    label: "知识图谱",
  },
] as const;

/** knowledge-tabs @client-bff */
export const KnowledgeTabs = () => {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 border-b border-border/60" data-testid="knowledge-tabs">
      {TABS.map((tab) => {
        const active = tab.children.some((path) => pathname?.startsWith(path)) ?? false;
        let linkClass = "text-muted-foreground hover:text-foreground";
        if (active) {
          linkClass = "border-b-2 border-clay text-foreground";
        }
        return (
          <Link
            key={tab.href}
            href={tab.href}
            data-testid={`tab-${tab.href.split("/").pop()}`}
            className={cn("px-4 py-2 text-sm transition-colors", linkClass)}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
};
