"use client";
// AppForm — @tanstack/react-form 包装, antd 风格 API (2026-06-25)
// 支持 action 模式 (原生 form 提交) 和 onFinish 模式 (客户端提交)
import { cn } from "@/lib/utils";
import { useForm } from "@tanstack/react-form";
import * as React from "react";
import { createContext, forwardRef, type ReactNode, useContext } from "react";
import type { z } from "zod";

// ── Types ──────────────────────────────────────────

/**
 * AppForm 属性接口 — 初始值、校验 Schema、提交模式及布局
 * @client-bff
 */
interface AppFormProps<TFormData extends Record<string, unknown>> {
  /** 表单初始值, 类型推导到各 Field */
  defaultValues: TFormData;
  /** 可选 Zod 4 schema (Standard Schema 直连 TanStack validators) */
  schema?: z.ZodType<TFormData>;
  /** 简单模式: server action (原生 <form action> 提交) */
  action?: (formData: FormData) => void | Promise<void>;
  /** 复杂模式: 客户端提交回调 */
  onFinish?: (values: TFormData) => void | Promise<void>;
  /** 校验失败回调 */
  onFinishFailed?: (errors: Record<string, string>) => void;
  /** 布局模式 */
  layout?: "vertical" | "horizontal";
  /** MIME 编码 (如 multipart/form-data 用于文件上传) */
  encType?: "application/x-www-form-urlencoded" | "multipart/form-data" | "text/plain";
  className?: string;
  children: ReactNode;
}

/** FormCtx 值类型 — 表单实例及布局模式 */
interface FormCtxValue {
  // form 类型用 any: TanStack Form 泛型有 12 个参数, 完整标注可读性差
  // 跟 react-hook-form 的 useForm<T>() 方式一致, 用户通过 defaultValues 推导类型
  form: any;
  layout: "vertical" | "horizontal";
}

// ── Context ─────────────────────────────────────────
/** 表单上下文 — provide form 实例给子组件 */
const FormCtx = createContext<FormCtxValue | null>(null);

/**
 * 获取 AppForm 上下文 — 必须在 <AppForm> 内部调用
 * @returns { form, layout } 表单实例和布局模式
 */
export const useFormCtx = (): FormCtxValue => {
  const ctx = useContext(FormCtx);
  if (!ctx) {
    throw new Error("useFormCtx must be used within <AppForm>");
  }
  return ctx;
};

// ── AppForm ─────────────────────────────────────────
// 用 forwardRef 暴露 <form> ref, 用于外部 requestSubmit (如 avatar-uploader 文件选择后自动提交)
/**
 * 通用表单 — @tanstack/react-form 包装, antd 风格 API, forwardRef 暴露 <form> ref
 * 支持 action 模式 (服务端提交) 和 onFinish 模式 (客户端提交)
 * @param props.defaultValues 表单初始值
 * @param props.schema Zod schema 校验
 * @param props.action Server Action 提交
 * @param props.onFinish 客户端提交回调
 * @param props.layout 垂直/水平布局 (默认 vertical)
 * @param props.ref 透传给 <form> 的 ref
 * @returns 表单 JSX
 */
export const AppForm = forwardRef(
  <TFormData extends Record<string, unknown>>(
    {
      defaultValues,
      schema,
      action,
      onFinish,
      onFinishFailed: _onFinishFailed,
      layout = "vertical",
      encType,
      className,
      children,
    }: AppFormProps<TFormData>,
    ref: React.Ref<HTMLFormElement>,
  ) => {
    const form = useForm({
      defaultValues: defaultValues as any,
      validators: schema ? { onChange: schema as any, onSubmit: schema as any } : undefined,
      onSubmit: onFinish
        ? async ({ value }: { value: any }) => {
            try {
              await onFinish(value as TFormData);
            } catch (error) {
              // onFinish 内部出错时吞掉, 避免 unhandled rejection
              console.error("[AppForm] onFinish 执行出错:", error);
            }
          }
        : undefined,
    });

    // 表单提交处理: onFinish 模式走 TanStack Form 校验 + 提交
    // action 模式交由浏览器原生提交 (server action 或普通 form 提交)
    const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
      if (onFinish) {
        event.preventDefault();
        form.handleSubmit();
      }
      // action 模式: 让浏览器原生提交
    };

    // 提取 layout className 到变量, 避免 JSX 中三目运算 (项目规约)
    const formClassName = cn(
      layout === "horizontal" ? "grid grid-cols-[140px_1fr] gap-3 items-start" : "space-y-4",
      className,
    );

    return (
      <FormCtx.Provider value={{ form, layout }}>
        <form
          action={action ?? undefined}
          className={formClassName}
          encType={encType}
          noValidate
          onSubmit={handleSubmit}
          ref={ref}
        >
          {children}
        </form>
      </FormCtx.Provider>
    );
  },
) as <TFormData extends Record<string, unknown>>(
  props: AppFormProps<TFormData> & { ref?: React.Ref<HTMLFormElement> },
) => React.ReactElement;
