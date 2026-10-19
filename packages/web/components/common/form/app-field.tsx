"use client";
// AppField — @tanstack/react-form Field 组件包装, antd 风格 API (2026-06-25)
// 自动加载默认 Input 或无 children 时渲染 Input, 有 children 时 cloneElement 注入
import { useFormCtx } from "./app-form";
import { ZERO } from "@/const";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { getErrorMessage as normalizeErrorMessage } from "@/lib/api/errors";
import type { AnyFieldApi } from "@tanstack/react-form";
import { cloneElement, type ReactElement, type ReactNode, isValidElement, useId } from "react";

/**
 * AppField 属性接口 — 字段名、标签、必填、帮助文本及类型
 * @client-bff
 */
interface AppFieldProps {
  /** 字段名, 对应 form state 的 key */
  name: string;
  label?: string;
  required?: boolean;
  help?: string;
  type?: "text" | "number" | "email" | "password";
  placeholder?: string;
  children?: ReactNode;
}

// 从 DOM 事件或自定义事件中提取值
/**
 * 从 DOM 事件或自定义事件中提取值
 * @param event 事件对象
 * @param isNumberType 是否为数字类型
 * @returns 提取后的值
 */
const extractEventValue = (event: unknown, isNumberType: boolean): unknown => {
  if (event && typeof event === "object" && "target" in event) {
    const { value } = (event as React.ChangeEvent<HTMLInputElement>).target;
    return isNumberType ? Number(value) : value;
  }
  return event;
};

// 提取输入组件或默认 Input
/**
 * 提取输入组件或默认 Input — 有 children 时 cloneElement 注入, 否则渲染默认 Input
 * @param options.field 字段实例
 * @param options.customChildren 自定义子组件
 * @param options.inputId 输入框 id
 * @param options.name 字段名
 * @param options.type 输入类型
 * @param options.required 必填标记
 * @param options.placeholder 占位符
 * @param options.value 当前值
 * @returns 输入组件 ReactNode
 */
const buildInputElement = (options: {
  field: AnyFieldApi;
  customChildren: ReactNode | undefined;
  inputId: string;
  name: string;
  type: string;
  required: boolean | undefined;
  placeholder: string | undefined;
  value: unknown;
}): ReactNode => {
  const { field, customChildren, inputId, name, type, required, placeholder, value } = options;
  const isNumberType = type === "number";
  const handleChange = (event: unknown) => {
    field.handleChange(extractEventValue(event, isNumberType));
  };
  const handleBlur = () => {
    field.handleBlur();
  };

  if (customChildren && isValidElement(customChildren)) {
    return cloneElement(customChildren as ReactElement<Record<string, unknown>>, {
      id: inputId,
      // 必须注入 name, 否则 <form action={serverAction}> 提交时 FormData 拿不到字段
      name,
      value,
      onChange: handleChange,
      onBlur: handleBlur,
      required,
      placeholder,
    });
  }
  return (
    <Input
      id={inputId}
      name={name}
      type={type}
      value={value as string}
      onChange={handleChange}
      onBlur={handleBlur}
      placeholder={placeholder}
      required={required}
    />
  );
};

// 从 field 提取错误消息文本. tanstack-form field state 需要 string | undefined 签名 (无错误返 undefined)
// 字段校验器常返 { message: "..." } 对象 (非 Error 实例), 需单独提取 .message
/**
 * 从 field 提取错误消息文本 — 支持 string / Error / { message } 三种格式
 * @param rawError 原始错误
 * @returns 错误消息文本或 undefined
 */
const getErrorMessage = (rawError: unknown): string | undefined => {
  if (!rawError) {
    return undefined;
  }
  if (typeof rawError === "string") {
    return rawError;
  }
  if (rawError instanceof Error) {
    return normalizeErrorMessage(rawError);
  }
  return (rawError as Record<string, unknown>).message as string | undefined;
};

/**
 * 表单字段 — @tanstack/react-form Field 包装, antd 风格 API
 * 自动渲染 Input, 有 children 时 cloneElement 注入 onChange/onBlur
 * @param props.name 字段名
 * @param props.label 标签文案
 * @param props.required 必填标记
 * @param props.help 帮助文本
 * @param props.type 输入类型 (默认 text)
 * @param props.placeholder 占位符
 * @param props.children 自定义输入组件 (可选)
 * @returns 字段包装 JSX
 */
export const AppField = ({
  name,
  label,
  required,
  help,
  type = "text",
  placeholder,
  children: customChildren,
}: AppFieldProps) => {
  const { form, layout } = useFormCtx();
  const autoId = useId();
  const inputId = `app-field-${name}-${autoId}`;

  // 提取布局类名到变量, 避免 JSX 中三目运算
  const fieldClassName = cn(layout === "horizontal" ? "contents" : "space-y-2");

  return (
    <form.Field name={name}>
      {(field: AnyFieldApi) => {
        // 当前值和错误信息
        const value = field.state.value ?? "";
        const rawError = field.state.meta.errors?.[ZERO];
        const errorMessage = getErrorMessage(rawError);

        const inputElement = buildInputElement({
          field,
          customChildren,
          inputId,
          name,
          type,
          required,
          placeholder,
          value,
        });

        // 提取 help / 错误提示元素, 避免 JSX 中嵌套三目运算
        let helpOrErrorElement: ReactNode = null;
        if (errorMessage) {
          helpOrErrorElement = <p className="text-sm text-destructive">{errorMessage}</p>;
        } else if (help) {
          helpOrErrorElement = <p className="text-sm text-muted-foreground">{help}</p>;
        }

        return (
          <div className={fieldClassName}>
            {label && (
              <Label
                htmlFor={inputId}
                className={cn(
                  required && "after:content-['*'] after:ml-0.5 after:text-destructive",
                  layout === "horizontal" && "pt-2",
                )}
              >
                {label}
              </Label>
            )}
            <div className="flex flex-col gap-1.5">
              {inputElement}
              {helpOrErrorElement}
            </div>
          </div>
        );
      }}
    </form.Field>
  );
};
