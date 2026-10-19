/**
 * useDialog — open + openDialog/closeDialog/toggleDialog 4 件套
 * 替 8+ 处手写 useState(open) + setter 调用
 */
import { useState } from "react";

/** useDialog 返回的控制器, 含 open/openDialog/closeDialog/toggleDialog.
 * @client-bff */
export interface DialogControl {
  open: boolean;
  openDialog: () => void;
  closeDialog: () => void;
  toggleDialog: () => void;
}

/** useDialog — open + openDialog/closeDialog/toggleDialog 4 件套
 * @param initial 初始状态, 默认 false
 * @returns DialogControl 包含 open/openDialog/closeDialog/toggleDialog
 * @client-bff */
export const useDialog = (initial = false): DialogControl => {
  const [open, setOpen] = useState(initial);
  const openDialog = () => setOpen(true);
  const closeDialog = () => setOpen(false);
  const toggleDialog = () => setOpen((prev) => !prev);
  return { open, openDialog, closeDialog, toggleDialog };
};
