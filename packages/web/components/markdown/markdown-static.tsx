"use client";
/**
 * MarkdownStatic — 静态 markdown 渲染 (2026-06-30 streamdown 迁移)
 * 取代 output/[task_id]/[file]/page.tsx 内联 <ReactMarkdown>
 * mode="static" + 无 onPreview + 默认 <img>
 */
import { type ReactNode } from "react";
import { Streamdown, type StreamdownProps } from "streamdown";

/** Streamdown 静态模式组件覆盖 — img 默认 <img> 加 rounded */
const components: StreamdownProps["components"] = {
  // output 页无预览, 走默认 <img> 加 rounded
  img: ({ src, alt }) => <img src={src} alt={alt} className="max-w-full rounded" />,
};

/** MarkdownStatic 组件的属性 */
export interface MarkdownStaticProps {
  /** markdown 源文本 */
  children: string;
  /** 容器 className */
  className?: string;
  /** 透传到 Streamdown, 预留未来 rehype 插件接入 */
  remarkPlugins?: StreamdownProps["remarkPlugins"];
  rehypePlugins?: StreamdownProps["rehypePlugins"];
}

/**
 * MarkdownStatic — 静态渲染 markdown 内容, 基于 Streamdown mode="static"
 * @param props.children markdown 源文本
 * @param props.className 容器 className
 * @param props.remarkPlugins 透传到 Streamdown 的 remark 插件
 * @param props.rehypePlugins 透传到 Streamdown 的 rehype 插件
 * @returns JSX 元素
 * @client-bff
 */
export const MarkdownStatic = ({
  children,
  className,
  remarkPlugins,
  rehypePlugins,
}: MarkdownStaticProps): ReactNode => (
  <div className={className ?? "max-w-none"}>
    <Streamdown
      mode="static"
      components={components}
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
    >
      {children}
    </Streamdown>
  </div>
);
