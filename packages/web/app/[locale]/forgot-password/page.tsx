"use client";
// 申请重置密码 — React 19 useActionState 模式
// (2026-06-14) 改手写 useState(email)+useTransition → useActionState + <form action>
// (2026-06-25) 迁移到 AppForm
import { type ForgotPasswordState, forgotPasswordAction } from "@/app/[locale]/_actions/account";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { Input } from "@/components/ui/input";
import { useActionState } from "react";
import { useTranslations } from "next-intl";

/** INITIAL_VALUES - 忘记密码表单初始值 */
const INITIAL_VALUES: Record<string, string> = { email: "" };

/** ForgotPasswordPage - 申请重置密码页面, 含 useActionState 表单提交与成功链接展示
 * @client-bff
 */
export default function ForgotPasswordPage() {
  const translate = useTranslations();
  const [state, formAction, isPending] = useActionState<ForgotPasswordState, FormData>(
    forgotPasswordAction,
    { error: null, ok: false, resetUrl: null },
  );

  if (state.resetUrl !== null) {
    return (
      <div className="mx-auto mt-20 max-w-sm space-y-6">
        <h1 className="display text-3xl">{translate("忘记密码?")}</h1>
        <div className="space-y-3 rounded-md border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            {translate("如果邮箱存在, 重置链接已生成")} (admin 复制发给你):
          </p>
          <code className="block break-all rounded bg-muted/30 p-2 text-xs" data-testid="reset-url">
            {state.resetUrl}
          </code>
          <CopyButton dataTestid="copy-url" text={state.resetUrl} />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{translate("忘记密码?")}</h1>
      <AppForm action={formAction} defaultValues={INITIAL_VALUES}>
        <AppField label={translate("邮箱")} name="email" required type="email">
          <Input data-testid="email-input" required type="email" />
        </AppField>
        <AppSubmit className="w-full" data-testid="submit" disabled={isPending}>
          提交
        </AppSubmit>
      </AppForm>
    </div>
  );
}
