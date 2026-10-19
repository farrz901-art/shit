/**
 * JSON 只读展示 (RSC) — shiki 着色 + 安全序列化 + 高度滚动
 *
 * 用法: <JsonView data={obj} /> — 单纯展示, 不接受交互
 * 场景: 后端 raw response / dataset 元数据 / RAG 引用预览 等"只看"页面
 *
 * 跟 <JsonDiff> 区别:
 *   - JsonView: 单个对象展示, 只读 (无 diff / 无 add/remove)
 *   - JsonDiff: 两个对象对比, 高亮 add/remove 行
 *   - 同样: RSC + shiki + safeStringify, 都是只读不交互
 *
 * 兜底:
 *   - data == null → "—" 占位
 *   - safeStringify 失败 (循环引用 / BigInt) → "JSON 序列化失败" 错误态
 *   - 序列化成功 → codeToHtml → dangerouslySetInnerHTML 渲染着色 HTML
 *
 * 安全: shiki 在 server 端执行, 输出 HTML 已 escape, 不会有 XSS
 */
import { codeToHtml } from "shiki";
import { cn } from "@/lib/utils";
import type { ShikiTheme } from "./types";
import { resolveCssDimension, safeStringify } from "./utils";

/**
 * JsonView 组件属性
 * @param props.data 要展示的 JSON 数据
 * @param props.theme shiki 主题
 * @param props.className 外层容器 className
 * @param props.maxHeight 容器最大高度
 * @shared
 */
export interface JsonViewProps {
  /** 要展示的 JSON 数据 */
  data: unknown;
  /** shiki 主题, 默认 "github-dark" */
  theme?: ShikiTheme;
  /** 外层容器 className */
  className?: string;
  /** 容器最大高度, 超出滚动, 如 "500px" 或 400 */
  maxHeight?: string | number;
}

/** 空数据占位符 */
const EMPTY_PLACEHOLDER = "—";
/** 序列化错误文本 */
const SERIALIZE_ERROR_TEXT = "JSON 序列化失败";

/**
 * JsonView — JSON 只读展示 (RSC) 组件
 * shiki 着色 + 安全序列化 + 高度滚动
 * @param props.data - 要展示的 JSON 数据
 * @param props.theme - shiki 主题, 默认 "github-dark"
 * @param props.className - 外层容器 className
 * @param props.maxHeight - 容器最大高度
 * @returns JSX 元素
 * @shared
 */
export const JsonView = async ({
  data,
  theme = "github-dark" as ShikiTheme,
  className,
  maxHeight,
}: JsonViewProps) => {
  // 空数据兜底
  if (data === null || data === undefined) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-muted-foreground",
          className,
        )}
      >
        {EMPTY_PLACEHOLDER}
      </div>
    );
  }

  // 序列化
  const jsonStr = safeStringify(data);
  if (jsonStr === null) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-destructive",
          className,
        )}
      >
        {SERIALIZE_ERROR_TEXT}
      </div>
    );
  }

  // shiki 着色
  const html = await codeToHtml(jsonStr, {
    lang: "json",
    theme,
  });

  // 渲染
  return (
    <div
      className={cn(
        "overflow-auto rounded-lg border font-mono text-sm leading-relaxed",
        "[&_pre]:m-0 [&_pre]:p-4",
        className,
      )}
      style={maxHeight != null ? { maxHeight: resolveCssDimension(maxHeight) } : undefined}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
