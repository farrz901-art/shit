"use client";
/**
 * ThinkBlock — 折叠展示 AI 思考过程 (2026-06-30 streamdown 迁移)
 * 包装 AppCollapsible, 接受纯文本 children, 不做 markdown 解析
 * 取代 assistant-body.tsx 内联 renderThinking IIFE
 */
import { AppCollapsible } from "@/components/common/display/app-collapsible";
import { type ReactNode } from "react";

/** 思考过程标题文本 */
const THINK_TITLE = "思考过程";

/** ThinkBlock 组件的属性 */
export interface ThinkBlockProps {
  /** 思考内容, 纯文本无 markdown */
  children: string;
  /** 非受控默认展开, 默认 false */
  defaultOpen?: boolean;
  /** 受控展开状态 */
  open?: boolean;
  /** 受控展开回调 */
  onOpenChange?: (open: boolean) => void;
  /** 透传到 trigger 按钮的 testId, 默认 'think-toggle' */
  testId?: string;
  /** 外层 className */
  className?: string;
  /** 触发按钮左侧 icon, 默认 ChevronDown */
  icon?: ReactNode;
}

/**
 * ThinkBlock — 折叠展示 AI 思考过程, 基于 AppCollapsible
 * @param props.children 思考内容纯文本
 * @param props.defaultOpen 非受控默认展开
 * @param props.open 受控展开状态
 * @param props.onOpenChange 受控展开回调
 * @param props.testId 触发按钮 testId
 * @param props.className 外层 className
 * @param props.icon 触发按钮左侧图标
 * @returns JSX 元素
 * @client-bff
 */
export const ThinkBlock = ({
  children,
  defaultOpen,
  open,
  onOpenChange,
  testId = "think-toggle",
  className,
  icon,
}: ThinkBlockProps) => (
  <AppCollapsible
    title={THINK_TITLE}
    defaultOpen={defaultOpen}
    open={open}
    onOpenChange={onOpenChange}
    icon={icon}
    testId={testId}
    className={className ?? "mb-2"}
  >
    <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
      {children}
    </div>
  </AppCollapsible>
);
