"use client";
// ChangePasswordDialog — 改密码 (输当前密码 + 新密码 + 确认)
// (2026-06-18) T4.1 完整实现, 替 T3.3 stub
// (2026-06-25) 迁移到 AppForm + AppField + AppSubmit; useActionState 留在 consumer
// (2026-06-29 P1) footer 内的提交按钮通过 formRef.current?.requestSubmit() 跨容器触发 AppForm submit
import { type PasswordState, changePasswordAction } from "@/app/[locale]/_actions/account-settings";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppField, AppForm } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useActionState, useRef } from "react";
import { useTranslations } from "next-intl";

/** changePasswordAction 的初始状态: 无错误 */
const INITIAL: PasswordState = { error: null, ok: false };

/** AppForm 初始字段值 (action 模式, 满足 useForm 类型要求) */
const INITIAL_VALUES: Record<string, string> = {
  confirm: "",
  current_password: "",
  new_password: "",
};

/** 修改密码弹框: 用户输入当前密码和新密码完成密码修改
 * @param open - 弹框是否打开
 * @param onOpenChange - 弹框开关回调
 * @returns 弹框 JSX
 * @client-bff
 */
export const ChangePasswordDialog = ({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (val: boolean) => void;
}) => {
  const tr = useTranslations();
  const [state, action] = useActionState(changePasswordAction, INITIAL);
  const formRef = useRef<HTMLFormElement>(null);

  return (
    <AppDialog
      dataTestid="change-password-dialog"
      onOpenChange={onOpenChange}
      open={open}
      title={tr("修改密码")}
      error={state.error}
      errorTestid="password-error"
      footer={
        <>
          <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
            {tr("取消")}
          </Button>
          <Button
            data-testid="password-submit"
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
        <AppField name="current_password" label={tr("当前密码")} type="password" required>
          <Input data-testid="password-current" required type="password" />
        </AppField>
        <AppField name="new_password" label={tr("新密码")} type="password" required>
          <Input data-testid="password-new" minLength={8} required type="password" />
        </AppField>
        <AppField name="confirm" label={tr("确认新密码")} type="password" required>
          <Input data-testid="password-confirm" minLength={8} required type="password" />
        </AppField>
        {state.ok && (
          <div className="text-sm text-status-success" data-testid="password-success">
            {tr("已保存")}
          </div>
        )}
      </AppForm>
    </AppDialog>
  );
};
