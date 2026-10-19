/**
 * MobileNavDrawer: < sm 断点汉堡菜单 (2026-07-02 nav spec §4.4)
 * - 父级节点默认折叠, 点击展开
 * - 叶子节点直接 link
 * - 路由切换由父组件 close (Header 在 usePathname 变化时设 open=false)
 *
 * 注意: 用 shadcn Sheet 直实现, 没抽 AppDrawer 包装
 * (项目内现有 app-dialog 无 drawer variant). 后续若需多处复用再抽 AppDrawer.
 */
"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
export { Menu as MobileMenuIcon } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { LocalizedLink } from "@/components/i18n/localized-link";
import type { NavTree } from "@/lib/nav/nav-types";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

/** 子节点数量为 0 的判断常量 */
const EMPTY_CHILDREN = 0;
/** 子菜单缩进像素值 */
const INDENT_PX = 16;

/**
 * MobileNavDrawer — 移动端导航抽屉 (< sm 断点汉堡菜单)
 * 父级节点默认折叠, 点击展开; 叶子节点直接 link; 路由切换由父组件 close
 * @param props.tree - 导航树配置
 * @param props.open - 抽屉展开状态
 * @param props.onOpenChange - 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
export const MobileNavDrawer = ({
  tree,
  open,
  onOpenChange,
}: {
  tree: NavTree;
  open: boolean;
  onOpenChange: (openState: boolean) => void;
}) => {
  const translate = useTranslations();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  /**
   * 切换父级导航项的折叠/展开状态
   * @param key 导航节点 key
   */
  const toggleExpanded = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-80 overflow-y-auto p-0">
        <SheetHeader className="border-b border-border/60 p-4">
          <SheetTitle>{translate("导航")}</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-1 p-4">
          {tree.roots.map((node) => {
            if (node.children.length === EMPTY_CHILDREN) {
              return (
                <LocalizedLink
                  key={node.key}
                  href={node.path ?? "#"}
                  onClick={() => onOpenChange(false)}
                  data-testid={`mobile-nav-link-${node.key}`}
                  className="rounded-md px-4 py-3 text-base font-medium text-foreground hover:bg-muted/40"
                >
                  {translate(node.label_zh)}
                </LocalizedLink>
              );
            }
            const isExpanded = expanded.has(node.key);
            return (
              <div key={node.key} data-testid={`mobile-nav-group-${node.key}`}>
                <button
                  type="button"
                  onClick={() => toggleExpanded(node.key)}
                  aria-expanded={isExpanded}
                  data-testid={`mobile-nav-toggle-${node.key}`}
                  className="flex w-full items-center justify-between rounded-md px-4 py-3 text-left text-base font-semibold text-foreground hover:bg-muted/40"
                >
                  <span>{translate(node.label_zh)}</span>
                  <ChevronDown
                    className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-180")}
                  />
                </button>
                {isExpanded && (
                  <div
                    className="ml-4 mt-1 flex flex-col gap-1 border-l border-border/40 pl-2"
                    style={{ paddingLeft: `${INDENT_PX}px` }}
                  >
                    {node.children.map((child) => (
                      <LocalizedLink
                        key={child.key}
                        href={child.path ?? "#"}
                        onClick={() => onOpenChange(false)}
                        data-testid={`mobile-nav-item-${child.key}`}
                        className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                      >
                        {translate(child.label_zh)}
                      </LocalizedLink>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </SheetContent>
    </Sheet>
  );
};

// re-export for Header: see top of file
