"use client";
/**
 * Clipboard + 1.5s 反馈 (2026-06-14): 替 4 处 navigator.clipboard.writeText
 *   用法: <CopyButton text={inviteUrl} label="复制" successLabel="已复制 ✓" />
 *   失败走 sonner toast.error, 成功 1.5s "已复制 ✓" 反馈
 * 副作用: 调 navigator.clipboard.writeText, 需要 https 或 localhost + 用户激活手势
 */
import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

/** 复制成功后回退到默认文案的延时 (ms) @shared */
const COPIED_RESET_MS = 1500;

/**
 * 复制按钮属性接口
 * @client-bff
 */
export interface CopyButtonProps {
  text: string;
  label?: string;
  successLabel?: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  onCopied?: () => void;
  className?: string;
  dataTestid?: string;
}

/**
 * 复制按钮 — 成功后 1.5s 内显示 successLabel, 失败弹 toast
 * @param props.text 要复制到剪贴板的文本
 * @param props.onCopied 复制成功额外回调 (例如关闭弹窗)
 * @returns JSX 元素
 * @client-bff
 */
export const CopyButton = ({
  text,
  label = "复制",
  successLabel = "已复制 ✓",
  variant = "default",
  size = "default",
  onCopied,
  className,
  dataTestid,
}: CopyButtonProps) => {
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  /**
   * 点击复制到剪贴板, 成功后显示 successLabel 1.5s 后回退
   * @client-bff
   */
  const handleClick = () => {
    startTransition(async () => {
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        onCopied?.();
        setTimeout(() => setCopied(false), COPIED_RESET_MS);
      } catch (error) {
        let message = "复制失败";
        if (error instanceof Error) {
          const { message: errMessage } = error;
          message = errMessage;
        }
        toast.error(message);
      }
    });
  };

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      onClick={handleClick}
      disabled={pending}
      className={className}
      data-testid={dataTestid}
    >
      {copied ? successLabel : label}
    </Button>
  );
};
