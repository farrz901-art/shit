/**
 * NavDropdown: 桌面端 hover 弹出子菜单 (2026-07-02 nav spec §4.3)
 * - 父级 trigger 不可点 (button 不是 a, 按用户决策)
 * - 子项渲染为 AppDropdownMenu 的 Link 项
 * - 复用项目已封装的 AppDropdownMenu (Radix DropdownMenu)
 */
"use client";
import { ChevronDown } from "lucide-react";
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import type { NavNode } from "@/lib/nav/nav-types";
import { useTranslations } from "next-intl";

/** 分组根节点 chevron 图标 className */
const GROUPED_ROOT_CHEVRON = "h-3 w-3 transition-transform group-data-[state=open]:rotate-180";
/** 导航 fallback href, 当 NavNode.path 为 undefined 时兜底 */
const FALLBACK_HREF = "#";

/**
 * NavDropdown — 桌面端导航下拉菜单
 * 父级 trigger 不可点 (button 不是 a); 子项渲染为 AppDropdownMenu 的 Link 项
 * @param props.node - 导航节点 (含子项列表)
 * @returns JSX 元素
 * @client-bff
 */
export const NavDropdown = ({ node }: { node: NavNode }) => {
  const translate = useTranslations();

  return (
    <AppDropdownMenu
      trigger={
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded="false"
          data-testid={`nav-dropdown-${node.key}`}
          className="group relative flex items-center gap-1 rounded-md px-3 py-1.5 text-muted-foreground transition-colors duration-300 hover:text-foreground"
        >
          <span className="relative z-10">{translate(node.label_zh)}</span>
          <ChevronDown className={GROUPED_ROOT_CHEVRON} />
          <span className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100" />
        </button>
      }
      contentClassName="w-48"
      items={node.children.map((child) => ({
        key: child.key,
        href: child.path ?? FALLBACK_HREF,
        label: translate(child.label_zh),
        testid: `nav-dropdown-item-${child.key}`,
      }))}
    />
  );
};
