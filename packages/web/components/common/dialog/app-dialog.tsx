"use client";
// AppDialog — antd 风格弹框封装 (2026-06-10)
//   标题固定 + 内容滚动 + 底部固定
// (2026-06-16) 加 icon?: ReactNode prop, 跟 antd Modal 风格一致 (icon 渲染在 title 左侧)
// (2026-06-29 P1) footer slot 跨容器触发外部 form submit:
//   调用方在 footer 闭包内 useRef<HTMLFormElement>(null) + formRef.current?.requestSubmit(),
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * AppDialog 属性接口 — 弹框可见性、标题、内容、底部操作及错误提示
 * @client-bff
 * @property open 弹框是否可见
 * @property onOpenChange 可见性变化回调
 * @property title 弹框标题 (可选)
 * @property description 弹框描述 (可选)
 * @property maxWidth 最大宽度: sm/md/lg/xl/2xl/3xl
 * @property footer 底部操作区
 * @property children 内容区
 * @property className 自定义类名
 * @property dataTestid 测试 ID
 * @property icon 标题左侧图标 (建议 lucide-react 图标)
 * @property error 内建错误提示文案
 * @property errorTestid 错误提示测试 ID
 * @property closeOnOverlayClick 点遮罩是否关闭弹框, 默认 true; false 时需主动按钮/ESC 关闭
 * @property closeOnEscape 按 ESC 是否关闭弹框, 默认 true; false 时需主动按钮/点遮罩关闭
 */
export interface AppDialogProps {
  /** 弹框是否可见 */
  open: boolean;
  /** 弹框可见性变化回调 */
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  dataTestid?: string;
  // (2026-06-16) title 左侧 icon, 跟 antd Modal 一致. 建议传 lucide-react 图标 (h-5 w-5).
  icon?: ReactNode;
  // (2026-06-25) 内建错误提示, 替代手写 {error && <ErrorBanner variant="destructive">}
  //   传入后自动在内容区顶部渲染 destructive ErrorBanner, 省去每个调用方重复模板.
  error?: string | null;
  errorTestid?: string;
  // (2026-07-06) 点遮罩是否关闭弹框; 业务场景: 上传中防误关, 默认 true 保持原有行为
  closeOnOverlayClick?: boolean;
  // (2026-07-06) 按 ESC 是否关闭弹框; 默认 true
  closeOnEscape?: boolean;
}

/** maxWidth 到 Tailwind 类的映射: sm/md/lg/xl/2xl/3xl, 默认 lg @shared */
const maxWidthClass: Record<string, string> = {
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
  lg: "max-w-lg",
  md: "max-w-md",
  sm: "max-w-sm",
  xl: "max-w-xl",
};

/**
 * 通用弹框 — antd 风格 Dialog 包装, 内建 header + 内容滚动 + footer + 错误提示
 * @client-bff
 * @param props.open 弹框可见性
 * @param props.onOpenChange 可见性回调
 * @param props.maxWidth 最大宽度 (sm/md/lg/xl/2xl/3xl, 默认 lg)
 * @param props.footer 底部操作区, 自动 border-t 分隔
 * @param props.error 内建错误提示文案, destructive 变体
 * @param props.closeOnOverlayClick 点遮罩是否关闭 (默认 true)
 * @param props.closeOnEscape 按 ESC 是否关闭 (默认 true)
 * @returns AppDialog 弹框 JSX
 */
export const AppDialog = ({
  open,
  onOpenChange,
  title,
  description,
  maxWidth = "lg",
  footer,
  children,
  className,
  dataTestid,
  icon,
  error,
  errorTestid,
  closeOnOverlayClick = false,
  closeOnEscape = true,
}: AppDialogProps) => {
  // (2026-07-06) 阻止点遮罩 / 按 ESC 关闭; Radix 在回调内 preventDefault 即保留弹框打开
  const handlePointerDownOutside = (event: Event): void => {
    if (!closeOnOverlayClick) {
      event.preventDefault();
    }
  };
  const handleEscapeKeyDown = (event: Event): void => {
    if (!closeOnEscape) {
      event.preventDefault();
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid={dataTestid}
        className={cn("flex flex-col gap-0 p-0", maxWidthClass[maxWidth], className)}
        onEscapeKeyDown={handleEscapeKeyDown}
        onPointerDownOutside={handlePointerDownOutside}
      >
        {(title || description) && (
          <DialogHeader className="border-b border-border/40 px-6 py-4">
            {title && (
              <DialogTitle className="flex items-center gap-2">
                {icon}
                {title}
              </DialogTitle>
            )}
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
        )}
        <div className="flex-1 overflow-auto px-6 py-4 [scrollbar-gutter:stable]">
          {error && (
            <ErrorBanner
              variant="destructive"
              description={error}
              dataTestid={errorTestid}
              className="mb-4"
            />
          )}
          {children}
        </div>
        {footer && (
          // shadcn DialogFooter 默认带 justify-end + space-x-2 + 响应式反转, 只需加 border-t 分隔
          <DialogFooter className="border-t border-border/40 px-6 py-4">{footer}</DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};
