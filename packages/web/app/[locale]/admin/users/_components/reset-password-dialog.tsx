"use client";
// 重设密码弹框 — React 19 useActionState 模式
// (2026-06-14) 改手写 useState+useTransition → useActionState + <form action>
import {
  type ResetPasswordAdminState,
  resetPasswordAdminAction,
} from "@/app/[locale]/_actions/account";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { useActionState } from "react";

/**
 * 重设密码弹框组件 — React 19 useActionState 模式
 * @param props.userId - 目标用户 ID
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 弹框打开状态变更回调
 * @returns 重设密码弹框
 * @client-bff
 */
export const ResetPasswordDialog = ({
  userId,
  open,
  onOpenChange,
}: {
  userId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) => {
  const [state, formAction, isPending] = useActionState<ResetPasswordAdminState, FormData>(
    resetPasswordAdminAction,
    { error: null, ok: false, tempPassword: null },
  );

  const temp = state.tempPassword;
  const err = state.error;

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title="重设密码"
      maxWidth="md"
      dataTestid="reset-password-dialog"
      error={err}
    >
      {temp ? (
        <div className="space-y-3">
          <p className="text-sm">临时密码 (复制发给用户, 用户登录后应尽快改):</p>
          <code
            data-testid="temp-password"
            className="block break-all rounded bg-muted/30 p-2 text-xs"
          >
            {temp}
          </code>
          <div className="flex gap-2">
            <CopyButton text={temp} dataTestid="copy-temp" />
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              关闭
            </Button>
          </div>
        </div>
      ) : (
        <form action={formAction} className="flex gap-2">
          <input type="hidden" name="userId" value={userId} />
          <Button type="submit" disabled={isPending} data-testid="submit" className="flex-1">
            {isPending ? "重设中…" : "确认重设"}
          </Button>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </form>
      )}
    </AppDialog>
  );
};
