"use client";
// ChangeEmailDialog — 修改邮箱 (双重验证: 当前密码 + 验证新邮箱)
// (2026-06-18) T4.1 完整实现, 替 T3.3 stub
// (2026-06-25) 迁移到 AppForm + AppField + AppSubmit; useActionState 留在 consumer
// (2026-06-29 P1) footer 内的提交按钮通过 formRef.current?.requestSubmit() 跨容器触发 AppForm submit
import {
  type EmailState,
  requestEmailChangeAction,
} from "@/app/[locale]/_actions/account-settings";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppField, AppForm } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActionState, useRef } from "react";
import { useTranslations } from "next-intl";

/** requestEmailChangeAction 的初始状态 */
const INITIAL: EmailState = { error: null, ok: false, verificationUrl: null };

/** AppForm 初始字段值 (action 模式, 满足 useForm 类型要求) */
const INITIAL_VALUES: Record<string, string> = {
  current_password: "",
  new_email: "",
};

/** 修改邮箱弹框: 用户输入新邮箱和当前密码提交修改申请
 * @param open - 弹框是否打开
 * @param onOpenChange - 弹框开关回调
 * @returns 弹框 JSX
 * @client-bff
 */
export const ChangeEmailDialog = ({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (val: boolean) => void;
}) => {
  const tr = useTranslations();
  const [state, action] = useActionState(requestEmailChangeAction, INITIAL);
  const formRef = useRef<HTMLFormElement>(null);

  return (
    <AppDialog
      dataTestid="change-email-dialog"
      onOpenChange={onOpenChange}
      open={open}
      title={tr("修改邮箱")}
      error={state.error}
      errorTestid="email-error"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
            {tr("取消")}
          </Button>
          <Button
            data-testid="email-submit"
            onClick={(event) => {
              event.preventDefault();
              formRef.current?.requestSubmit();
            }}
            type="submit"
          >
            {tr("提交")}
          </Button>
        </>
      }
    >
      <AppForm ref={formRef} defaultValues={INITIAL_VALUES} action={action}>
        <AppField name="new_email" label={tr("新邮箱")} type="email" required>
          <Input data-testid="email-new" name="new_email" required type="email" />
        </AppField>
        <AppField name="current_password" label={tr("当前密码")} type="password" required>
          <Input
            data-testid="email-current-password"
            name="current_password"
            required
            type="password"
          />
        </AppField>
        {state.verificationUrl && (
          <div
            className="rounded border border-status-warning bg-status-warning/10 p-3 text-sm"
            data-testid="email-verification-url"
          >
            {tr("请在 7 天内点击验证链接完成修改")}:{" "}
            <code className="text-xs">{state.verificationUrl}</code>
          </div>
        )}
      </AppForm>
    </AppDialog>
  );
};
