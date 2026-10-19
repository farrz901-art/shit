"use client";
/**
 * AppConfirm — 危险操作二次确认 (2026-06-10)
 * 替手写 window.confirm(): 走 shadcn AlertDialog 跟项目风格统一
 * variant="destructive" 触发红按钮 (例 删除/注销)
 */
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

/**
 * AppConfirm 属性接口 — 可见性、文案、变体及确认/取消回调
 * @client-bff
 * @property open 弹框是否可见
 * @property onOpenChange 可见性变化回调
 * @property title 确认弹框标题
 * @property description 确认弹框描述 (可选)
 * @property confirmText 确认按钮文案 (默认 "确认")
 * @property cancelText 取消按钮文案 (默认 "取消")
 * @property variant "destructive" 触发红按钮, 危险操作用
 * @property onConfirm 确认按钮回调
 * @property onCancel 取消按钮回调 (可选)
 */
export interface AppConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  /** "destructive" 触发红按钮, 危险操作用 */
  variant?: "default" | "destructive";
  onConfirm: () => void;
  onCancel?: () => void;
}

/**
 * 二次确认弹框 — 走 shadcn AlertDialog, 替手写 window.confirm
 * @client-bff
 * @param props.variant "destructive" 触发红按钮, 用于删除/注销等不可逆操作
 * @param props.onConfirm 确认按钮回调 (按 Enter 或点确认按钮触发)
 * @param props.onCancel 取消按钮回调 (按 Esc 或点取消按钮触发, 可选)
 * @returns 二次确认弹框 JSX
 */
export const AppConfirm = ({
  open,
  onOpenChange,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  variant = "default",
  onConfirm,
  onCancel,
}: AppConfirmProps) => (
  <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel onClick={onCancel}>{cancelText}</AlertDialogCancel>
        <AlertDialogAction
          onClick={onConfirm}
          className={cn(variant === "destructive" && "bg-destructive text-destructive-foreground")}
        >
          {confirmText}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);
