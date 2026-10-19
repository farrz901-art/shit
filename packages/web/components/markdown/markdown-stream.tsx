"use client";
/**
 * MarkdownStream — 流式 markdown 渲染 (2026-06-30 streamdown 迁移)
 * 取代 assistant-body.tsx 内联 <ReactMarkdown>
 * mode="streaming" + parseIncompleteMarkdown + 接 onPreview 透传图片点击
 */
import { type ReactNode } from "react";
import { Streamdown } from "streamdown";
import { MarkdownImg } from "@/components/markdown/markdown-img";

/** MarkdownStream 组件的 props 类型 */
export interface MarkdownStreamProps {
  /** markdown 源文本 (已剥离 thinking 部分) */
  children: string;
  /** 图片点击回调, 透传到 components.img */
  onPreview?: (src: string) => void;
  /** 容器 className */
  className?: string;
}

/**
 * MarkdownStream — 流式 markdown 渲染组件
 * 使用 Streamdown mode="streaming" 渲染流式 markdown 内容, 支持图片预览
 * @param props.children - markdown 源文本 (已剥离 thinking 部分)
 * @param props.onPreview - 图片点击回调
 * @param props.className - 容器 className
 * @returns JSX 元素
 * @client-bff
 */
export const MarkdownStream = ({
  children,
  onPreview,
  className,
}: MarkdownStreamProps): ReactNode => (
  <div className={className ?? "max-w-none"}>
    <Streamdown
      mode="streaming"
      parseIncompleteMarkdown
      components={{
        img: ({ src, alt }) => (
          <MarkdownImg src={src} alt={alt} onPreview={onPreview ?? (() => {})} />
        ),
        // think 留口: parseThinkTag 已在 AssistantBody 预处理, 此处不会触发
        // 但若未来上游直接发 <think> 标签, 走这里兜底
        think: ({ children: thinkChildren }) => <>{thinkChildren}</>,
      }}
    >
      {children}
    </Streamdown>
  </div>
);
