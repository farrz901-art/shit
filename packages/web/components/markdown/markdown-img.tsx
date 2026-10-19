/**
 * Markdown img 渲染器 (2026-06-29 message-bubble 拆分)
 * 原 message-bubble.tsx 内联 markdownComponents.img 提取
 * 关键: cursor-zoom-in + 点击触发 onPreview (上抛 src 给父组件弹 ImagePreview)
 */
import type React from "react";

/**
 * MarkdownImg 组件的属性
 * @property src 图片 src
 * @property alt 图片 alt
 * @property onPreview 预览回调, 点击后上抛 src
 * @shared
 */
interface MarkdownImgProps {
  src?: React.ImgHTMLAttributes<HTMLImageElement>["src"];
  alt?: React.ImgHTMLAttributes<HTMLImageElement>["alt"];
  onPreview: (src: string) => void;
}

/**
 * Markdown img 渲染器 — cursor-zoom-in + 点击触发 onPreview
 * @param props.src 图片 src
 * @param props.alt 图片 alt
 * @param props.onPreview 预览回调
 * @returns JSX 元素 (img)
 * @shared
 */
export const MarkdownImg = ({ src, alt, onPreview }: MarkdownImgProps) => {
  // Markdown src 理论上是 string; 类型里允许 Blob 是为兼容 HTMLImageElement
  // 安全起见只对 string 触发预览
  const safeSrc = typeof src === "string" ? src : undefined;
  const handleClick = () => {
    if (safeSrc) {
      onPreview(safeSrc);
    }
  };
  return (
    <img
      src={safeSrc}
      alt={alt}
      className="max-w-full cursor-zoom-in rounded"
      onClick={handleClick}
    />
  );
};
