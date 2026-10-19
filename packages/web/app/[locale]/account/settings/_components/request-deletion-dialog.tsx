"use client";
// RequestDeletionDialog — 申请注销 (输当前密码 + 字面 '我要注销' 确认)
// (2026-06-18) T4.1 完整实现, 替 T3.3 stub
// 双重确认: 输入密码 + 字面输入 "我要注销" (防误操作)
// (2026-06-25) 迁移到 AppForm; 字面校验由后端 server action 处理
// (2026-06-29 P1) footer 内的提交按钮通过 formRef.current?.requestSubmit() 跨容器触发 AppForm submit
import {
  type DeletionState,
  requestDeletionAction,
} from "@/app/[locale]/_actions/account-settings";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppField, AppForm } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActionState, useRef } from "react";
import { useTranslations } from "next-intl";

/** requestDeletionAction 的初始状态 */
const INITIAL: DeletionState = {
  error: null,
  expiresAt: null,
  ok: false,
  restoreUrl: null,
};

/** AppForm 初始字段值 */
const INITIAL_VALUES: Record<string, string> = {
  confirm_text: "",
  current_password: "",
};

/** 申请注销弹框: 用户输入当前密码和字面确认文本后提交注销申请
 * @param open - 弹框是否打开
 * @param onOpenChange - 弹框开关回调
 * @returns 弹框 JSX
 * @client-bff
 */
export const RequestDeletionDialog = ({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (val: boolean) => void;
}) => {
  const tr = useTranslations();
  const [state, action] = useActionState(requestDeletionAction, INITIAL);
  const formRef = useRef<HTMLFormElement>(null);

  return (
    <AppDialog
      dataTestid="request-deletion-dialog"
      onOpenChange={onOpenChange}
      open={open}
      title={tr("注销账号")}
      error={state.error}
      errorTestid="deletion-error"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
            {tr("取消")}
          </Button>
          <Button
            data-testid="deletion-submit"
            onClick={(event) => {
              event.preventDefault();
              formRef.current?.requestSubmit();
            }}
            type="submit"
            variant="destructive"
          >
            {tr("申请注销")}
          </Button>
        </>
      }
    >
      <AppForm ref={formRef} defaultValues={INITIAL_VALUES} action={action}>
        <div className="rounded border border-status-error/30 bg-status-error/5 p-3 text-sm">
          {tr("注销账号说明")}
        </div>
        <AppField name="current_password" label={tr("当前密码")} type="password" required>
          <Input data-testid="deletion-current-password" required type="password" />
        </AppField>
        <AppField
          name="confirm_text"
          label={tr("我要注销")}
          help={tr("请字面输入 '我要注销' 确认")}
          required
        >
          <Input
            data-testid="deletion-confirm-text"
            placeholder={tr("我要注销")}
            required
            type="text"
          />
        </AppField>
      </AppForm>
    </AppDialog>
  );
};
