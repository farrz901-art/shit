"use client";
// ImagePreview — 通用图片放大预览弹框 (2026-06-16 Task 4).
// 消息内点击放大 + 发送前缩略图共用. shadcn Dialog 包原图, 不引三方 lightbox.
// - open / onOpenChange: 受控, ESC 与 overlay 点击均会触发 onOpenChange(false)
// - src / alt: 透传到 <img>
import { Dialog, DialogContent } from "@/components/ui/dialog";

/**
 * ImagePreview 属性接口 — 弹框可见性、图片 URL 及 alt 文本
 * @client-bff
 */
export interface ImagePreviewProps {
  /** 弹框是否可见 */
  open: boolean;
  /** 可见性变化回调 */
  onOpenChange: (open: boolean) => void;
  /** 图片 URL */
  src: string;
  alt?: string;
}

/**
 * 图片放大预览弹框 — shadcn Dialog 包原图, 不引三方 lightbox
 * @param props.open 弹框可见性
 * @param props.onOpenChange 可见性回调
 * @param props.src 图片 URL
 * @returns Dialog 包裹的图片 JSX
 */
export const ImagePreview = ({ open, onOpenChange, src, alt = "" }: ImagePreviewProps) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-5xl p-0 bg-transparent border-none shadow-none">
      <img
        src={src}
        alt={alt}
        className="w-full h-auto max-h-[90vh] object-contain"
        data-testid="image-preview-img"
      />
    </DialogContent>
  </Dialog>
);
