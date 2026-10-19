"use client";
// AppDropdownMenu — antd 风格 Dropdown 包装 (2026-06-25)
//   items 数组定义菜单项, 省去手写 DropdownMenu 4-6 个子组件模板.
//   用法:
//     <AppDropdownMenu
//       trigger={<Button variant="ghost" size="sm"><MoreHorizontal /></Button>}
//       items={[
//         { key: "edit", label: "编辑", icon: <Pencil />, onClick: onEdit },
//         { key: "delete", label: "删除", icon: <Trash2 />, variant: "destructive", onClick: onDelete },
//       ]}
//     />
//   支持分隔线 (separator), 链接 (href), 条件隐藏 (hidden).
//   复杂场景 (inline form / 特殊 onSelect) 仍用 shadcn 原生组件.
import {
  DropdownMenuSeparator,
  DropdownMenuItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenu,
} from "@/components/ui/dropdown-menu";
import { ZERO } from "@/const";
import { cn } from "@/lib/utils";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * AppDropdownMenu 菜单项 — key、文案、图标、回调、链接、变体及分隔线
 * @client-bff
 */
export interface AppDropdownMenuItem {
  /** 菜单项唯一 key */
  key: string;
  label: string;
  /** lucide-react 图标, 直接传 <Edit /> 或 <Trash2 /> 等 */
  icon?: ReactNode;
  /** 点击回调 */
  onClick?: () => void;
  /** 设为 Link 模式 (走 Next.js <Link>) */
  href?: string;
  disabled?: boolean;
  variant?: "default" | "destructive";
  testid?: string;
  /** true 时跳过此项 (不渲染) */
  hidden?: boolean;
  /** 在此项前渲染分隔线 */
  separator?: boolean;
}

/**
 * AppDropdownMenu 属性接口 — 触发器元素、菜单项列表及对齐方向
 * @client-bff
 */
export interface AppDropdownMenuProps {
  /** 触发菜单的按钮 / 元素 */
  trigger: ReactNode;
  /** 菜单项列表 */
  items: AppDropdownMenuItem[];
  /** 菜单对齐方向 (默认 end) */
  align?: "start" | "end" | "center";
  /** 菜单内容的额外 className (e.g. "w-48") */
  contentClassName?: string;
}

/** destructive 变体 className — 文字 + focus + icon 全红 */
const DESTRUCTIVE_CLASS = "text-destructive focus:text-destructive [&>svg]:text-destructive";

/**
 * 下拉菜单 — antd 风格 Dropdown 包装, 省去手写 4-6 个子组件模板
 * 支持分隔线 / 链接 / 条件隐藏 / destructive 变体
 * @param props.trigger 触发元素
 * @param props.items 菜单项列表 (含 separator/href/variant/destructive 等)
 * @param props.align 对齐方向 (默认 end)
 * @returns DropdownMenu JSX
 */
export const AppDropdownMenu = ({
  trigger,
  items,
  align = "end",
  contentClassName,
}: AppDropdownMenuProps) => {
  const visibleItems = items.filter((item) => !item.hidden);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      {visibleItems.length > ZERO && (
        <DropdownMenuContent align={align} className={contentClassName}>
          {visibleItems.map((item) => {
            // separator-only 项 (无 label): 只渲染分隔线
            if (item.separator && !item.label) {
              return <DropdownMenuSeparator key={item.key} />;
            }
            return (
              <span key={item.key}>
                {item.separator && <DropdownMenuSeparator />}
                {item.href ? (
                  <DropdownMenuItem
                    asChild
                    className={cn(
                      "cursor-pointer",
                      item.variant === "destructive" && DESTRUCTIVE_CLASS,
                    )}
                    disabled={item.disabled}
                    data-testid={item.testid}
                  >
                    <Link href={item.href}>
                      {item.icon}
                      {item.label}
                    </Link>
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem
                    className={cn(
                      "cursor-pointer",
                      item.variant === "destructive" && DESTRUCTIVE_CLASS,
                    )}
                    disabled={item.disabled}
                    onClick={item.onClick}
                    data-testid={item.testid}
                  >
                    {item.icon}
                    {item.label}
                  </DropdownMenuItem>
                )}
              </span>
            );
          })}
        </DropdownMenuContent>
      )}
    </DropdownMenu>
  );
};
