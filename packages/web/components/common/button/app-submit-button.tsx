"use client";
/**
 * 通用提交按钮 — 内部用 useFormStatus 感知 pending, 父组件不用传 pending prop
 * (2026-06-14) Sprint 2.1 新建: React 19 useFormStatus 模式
 * 必须放在 <form> 内部才生效 (useFormStatus 读父 form 的 pending 状态)
 */
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useFormStatus } from "react-dom";

/**
 * 通用提交按钮的属性接口
 * @client-bff
 */
export interface SubmitButtonProps {
  /** 按钮默认文案 */
  children: React.ReactNode;
  /** 提交中显示的文案, 默认 "提交中…" */
  pendingLabel?: string;
  className?: string;
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  disabled?: boolean;
  "data-testid"?: string;
}

/**
 * 提交按钮: 自动禁用 + 切换文案 当父 <form> 处于 pending 状态
 * @param props.children 按钮默认文案
 * @param props.pendingLabel 提交中文案 (默认 "提交中…")
 * @param props.disabled 外部禁用, 跟 pending 取或
 * @returns JSX 元素
 * @client-bff
 */
export const SubmitButton = ({
  children,
  pendingLabel = "提交中…",
  className,
  variant = "default",
  size = "default",
  disabled,
  "data-testid": dataTestid,
}: SubmitButtonProps) => {
  const { pending } = useFormStatus();

  return (
    <Button
      type="submit"
      disabled={pending || disabled}
      variant={variant}
      size={size}
      className={cn(className)}
      data-testid={dataTestid}
    >
      {pending ? pendingLabel : children}
    </Button>
  );
};
