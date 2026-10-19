/**
 * useConfirm — 配 <AppConfirm> 弹框, 返回 trigger + props
 * 替 6+ 处手写 useState(open) + onConfirm + onOpenChange
 */
import { useState } from "react";

/** useConfirm 返回的控制器, 含 trigger + <AppConfirm> 绑定 props.
 * @client-bff */
export interface ConfirmControl {
  confirm: () => void;
  confirmProps: {
    open: boolean;
    onConfirm: () => void;
    onOpenChange: (val: boolean) => void;
  };
}

/** useConfirm — 配 <AppConfirm> 弹框, 返回 trigger + props
 * @param onConfirm 确认回调 (async 或同步)
 * @returns ConfirmControl 包含 confirm 触发函数 + confirmProps 绑定
 * @client-bff */
export const useConfirm = (onConfirm: () => Promise<void> | void): ConfirmControl => {
  const [open, setOpen] = useState(false);
  const confirm = () => setOpen(true);
  const handleConfirm = async () => {
    await onConfirm();
    setOpen(false);
  };
  return { confirm, confirmProps: { open, onConfirm: handleConfirm, onOpenChange: setOpen } };
};
