"use client";
/**
 * AppCollapsible — antd Collapse 风格折叠面板 (2026-06-25)
 * 封装 Radix Collapsible 3 子组件为 1 行 API
 * 受控/非受控双模式: open + onOpenChange 是受控, defaultOpen 是非受控
 */
import { ChevronDown } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * AppCollapsible 属性接口 — 标题、受控/非受控展开状态、图标及内容
 * @client-bff
 * @property title 折叠面板标题
 * @property defaultOpen 非受控默认展开
 * @property open 受控展开状态
 * @property onOpenChange 受控状态变化回调
 * @property icon 触发按钮左侧图标
 * @property testId 测试 ID
 * @property className 自定义类名
 * @property children 折叠内容
 */
export interface AppCollapsibleProps {
  title: string;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  icon?: ReactNode;
  testId?: string;
  className?: string;
  children: ReactNode;
}

/**
 * 折叠面板 — 受控/非受控双模式 (open 存在则受控, 否则用 defaultOpen)
 * @client-bff
 * @param props.open 受控展开状态, 跟 onOpenChange 一起用
 * @param props.defaultOpen 非受控默认展开
 * @param props.icon 触发按钮左侧 icon, 默认 ChevronDown
 * @returns 折叠面板 JSX
 */
export const AppCollapsible = ({
  title,
  defaultOpen,
  open,
  onOpenChange,
  icon,
  testId,
  className,
  children,
}: AppCollapsibleProps) => (
  <Collapsible
    className={cn(className)}
    open={open !== undefined ? open : undefined}
    defaultOpen={open !== undefined ? undefined : defaultOpen}
    onOpenChange={onOpenChange}
  >
    <CollapsibleTrigger asChild>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1 px-2 text-xs text-muted-foreground"
        data-testid={testId}
      >
        {icon ?? <ChevronDown className="h-4 w-4" />}
        {title}
      </Button>
    </CollapsibleTrigger>
    <CollapsibleContent>{children}</CollapsibleContent>
  </Collapsible>
);
