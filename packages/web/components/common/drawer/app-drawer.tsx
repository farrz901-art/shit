"use client";
/**
 * AppDrawer — 侧拉抽屉封装 (2026-06-10)
 * 走 shadcn Sheet, 默认从右侧拉出. 跟 AppDialog 一样内建 header (border-b) + footer (border-t)
 */
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * AppDrawer 属性接口 — 侧拉抽屉可见性、方向、标题、底部操作及内容
 * @client-bff
 */
export interface AppDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  side?: "left" | "right";
  maxWidth?: string;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * 侧拉抽屉 — shadcn Sheet 包装, 默认右侧拉出
 * @param props.side 拉出方向: left / right (默认 right)
 * @param props.maxWidth 抽屉最大宽度 (CSS 单位, 例 "400px" / "30vw")
 * @param props.footer 抽屉底部操作区, 自动 border-t 分隔
 */
export const AppDrawer = ({
  open,
  onOpenChange,
  title,
  description,
  side = "right",
  maxWidth,
  footer,
  children,
  className,
}: AppDrawerProps) => (
  <Sheet open={open} onOpenChange={onOpenChange}>
    <SheetContent
      side={side}
      className={cn("flex flex-col gap-0 p-0", className)}
      style={maxWidth ? { maxWidth } : undefined}
    >
      {(title || description) && (
        <SheetHeader className="border-b border-border/40 px-6 py-4">
          {title && <SheetTitle>{title}</SheetTitle>}
          {description && <SheetDescription>{description}</SheetDescription>}
        </SheetHeader>
      )}
      <div className="flex-1 overflow-auto px-6 py-4">{children}</div>
      {footer && (
        <SheetFooter className="border-t border-border/40 px-6 py-4">{footer}</SheetFooter>
      )}
    </SheetContent>
  </Sheet>
);
