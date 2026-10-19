"use client";
// AppSubmit — 提交按钮，自动感知 form.isSubmitting 并禁用（2026-06-25）
import { Button, type ButtonProps } from "@/components/ui/button";
import type { ReactNode } from "react";
import { useFormCtx } from "./app-form";
import { useStore } from "@tanstack/react-form";

/**
 * AppSubmit 属性接口 — 继承 ButtonProps, 透传 children
 * @client-bff
 */
interface AppSubmitProps extends ButtonProps {
  children: ReactNode;
}

/**
 * 提交按钮 — 自动感知 form.isSubmitting 并禁用
 * @param props.children 按钮文字
 * @param props 其余 ButtonProps 透传
 * @returns 禁用态 Button 组件
 */
export const AppSubmit = ({ children, ...props }: AppSubmitProps) => {
  const { form } = useFormCtx();
  const isSubmitting = useStore(form.store, (state: any) => state.isSubmitting);

  return (
    <Button type="submit" disabled={isSubmitting || props.disabled} {...props}>
      {children}
    </Button>
  );
};
