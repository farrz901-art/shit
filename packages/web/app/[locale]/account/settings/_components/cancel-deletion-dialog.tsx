"use client";
// CancelDeletionDialog — 撤销注销 (输当前密码)
// (2026-06-18) T4.1 新增, 给 RestoreDeletionBanner (T4.3) 用
// 跟 DeletionSection 的 inline 撤销表单等价, 但走 dialog
// (2026-06-25) 迁移到 AppForm
// (2026-06-29 P1) footer 内的提交按钮通过 formRef.current?.requestSubmit() 跨容器触发 AppForm submit
import { type DeletionState, cancelDeletionAction } from "@/app/[locale]/_actions/account-settings";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppField, AppForm } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActionState, useRef } from "react";
import { useTranslations } from "next-intl";

/** cancelDeletionAction 的初始状态 */
const INITIAL: DeletionState = {
  error: null,
  expiresAt: null,
  ok: false,
  restoreUrl: null,
};

/** AppForm 密码字段初始值 */
const INITIAL_VALUES: Record<string, string> = { current_password: "" };

/** 撤销注销弹框: 用户输入当前密码确认撤销注销申请
 * @param open - 弹框是否打开
 * @param onOpenChange - 弹框开关回调
 * @returns 弹框 JSX
 * @client-bff
 */
export const CancelDeletionDialog = ({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (val: boolean) => void;
}) => {
  const tr = useTranslations();
  const [state, action] = useActionState(cancelDeletionAction, INITIAL);
  const formRef = useRef<HTMLFormElement>(null);

  return (
    <AppDialog
      dataTestid="cancel-deletion-dialog"
      onOpenChange={onOpenChange}
      open={open}
      title={tr("撤销注销")}
      error={state.error}
      errorTestid="cancel-deletion-error"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
            {tr("取消")}
          </Button>
          <Button
            data-testid="cancel-deletion-submit"
            onClick={(event) => {
              event.preventDefault();
              formRef.current?.requestSubmit();
            }}
            type="submit"
          >
            {tr("撤销注销")}
          </Button>
        </>
      }
    >
      <AppForm ref={formRef} defaultValues={INITIAL_VALUES} action={action}>
        <p className="text-sm text-muted-foreground">
          {tr("输入当前密码撤销注销申请, 账号将恢复正常")}
        </p>
        <AppField name="current_password" label={tr("当前密码")} type="password" required>
          <Input data-testid="cancel-deletion-password" required type="password" />
        </AppField>
      </AppForm>
    </AppDialog>
  );
};
