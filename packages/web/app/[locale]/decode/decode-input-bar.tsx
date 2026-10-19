"use client";
// 型号解码输入栏: chunks preview + 大 input + 示例/系列/提交按钮
// 从 DecodePage 抽出来降低主组件复杂度 (oxlint complexity 22→<20)
// E2E 选择器兼容: input[data-testid=decode-input] + button[data-testid=decode-submit]
// (2026-06-28) ChunksPreview 抽到 components/decode/chunks-preview.tsx
// (2026-06-28) LoadingSpinner 改 <Spinner /> (components/common/display)
import { CSS_EASE_STR } from "@/components/motion/animated";
import { Button } from "@/components/ui/button";
import { ChunksPreview } from "@/components/decode/chunks-preview";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/common/display/app-spinner";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";
import type { RefObject } from "react";

/** 空数组长度判定常量 @shared */
const EMPTY_LENGTH = 0;

/** 根据错误状态返回输入框边框样式类
 * @param hasError - 是否有错误
 * @returns Tailwind 边框类名
 * @shared
 */
const getBorderClass = (hasError: boolean): string => {
  if (hasError) {
    return "border-destructive/50 shadow-[0_0_0_4px_hsl(0_70%_45%/0.08)]";
  }
  return "border-border/80 hover:border-ink/30 focus-within:border-ink/50 focus-within:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)]";
};

/** 获取提交按钮标签
 * @param translate - i18n 翻译函数
 * @param loading - 是否正在加载
 * @returns 按钮文本
 * @shared
 */
const getSubmitLabel = (translate: (key: string) => string, loading: boolean): string => {
  if (loading) {
    return translate("解码中…");
  }
  return translate("解码");
};

/** 解码视图类型 @shared */
type View = "cards" | "llm";

/** DecodeInputBar - 型号解码输入栏: chunks preview + 大 input + 示例/系列/提交按钮 */
export const DecodeInputBar = (props: {
  model: string;
  loading: boolean;
  hasError: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onModelChange: (val: string) => void;
  onFillExample: () => void;
  onPickSeries: () => void;
  onSubmit: () => void;
}) => {
  const translate = useTranslations();
  const {
    model,
    loading,
    hasError,
    inputRef,
    onModelChange,
    onFillExample,
    onPickSeries,
    onSubmit,
  } = props;
  const chunks = chunkInput(model);
  const borderClass = getBorderClass(hasError);
  const submitLabel = getSubmitLabel(translate, loading);

  return (
    <div className="relative">
      <div
        className={cn(
          "group relative overflow-hidden rounded-2xl border bg-card transition-all duration-500",
          borderClass,
        )}
      >
        {chunks.length > EMPTY_LENGTH && <ChunksPreview chunks={chunks} model={model} />}
        <div className="flex items-center gap-3 px-6 py-5">
          <span className="eyebrow shrink-0">{translate("型号")}</span>
          <Input
            ref={inputRef}
            value={model}
            onChange={(ev) => onModelChange(ev.target.value)}
            placeholder="1LE0001-1AA42-1AA4"
            disabled={loading}
            className="num border-0 bg-transparent text-xl tracking-tight shadow-none focus-visible:ring-0 md:text-2xl"
            data-testid="decode-input"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onFillExample}
            disabled={loading}
            className="shrink-0"
            style={{ transitionTimingFunction: CSS_EASE_STR.outQuint }}
          >
            {translate("示例")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onPickSeries}
            className="shrink-0"
          >
            {translate("已导入系列")}
          </Button>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Button
          onClick={onSubmit}
          disabled={!model || loading}
          className={cn(
            "group relative h-12 gap-3 overflow-hidden rounded-full bg-ink px-6 text-base text-paper hover:bg-ink/90",
            "hover:shadow-[0_4px_12px_hsl(0_0%_0%/0.10),0_2px_4px_hsl(0_0%_0%/0.06)]",
          )}
          style={{ transitionTimingFunction: CSS_EASE_STR.outExpo }}
          data-testid="decode-submit"
        >
          <span>{submitLabel}</span>
          {!loading && (
            <span className="num text-sm opacity-50 transition-transform duration-300 group-hover:translate-x-1">
              →
            </span>
          )}
          {loading && <Spinner />}
        </Button>
        <span className="num text-sm text-muted-foreground/50">{model.length} chars</span>
      </div>
    </div>
  );
};

/** 按连字符分割输入文本为块
 * @param input - 输入字符串
 * @returns 分割后的块数组
 * @shared
 */
const chunkInput = (input: string): string[] => input.split(/-+/).filter(Boolean);

// 静默 View 类型, 避免 page.tsx 与本文件都定义 (将来扩展 mode 可共用)
/** View - 解码视图类型 (cards | llm) */
export type { View };
