"use client";
// 用 token 改密码 — React 19 useActionState 模式
// (2026-06-14) 改手写 useState+useTransition → useActionState + <form action>
// (2026-06-25) 迁移到 AppForm
import { type ResetPasswordState, resetPasswordAction } from "@/app/[locale]/_actions/account";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { useActionState } from "react";
import { MIN_PASSWORD_LENGTH } from "@/const";

/** 初始表单值 */
const INITIAL_VALUES: Record<string, string> = { confirm: "", password: "" };

/**
 * ResetPasswordPage - 重置密码页
 * @client-bff
 */
export default function ResetPasswordPage() {
  const router = useRouter();
  const search = useSearchParams();
  const token = search.get("token") ?? "";

  const [state, formAction, isPending] = useActionState<ResetPasswordState, FormData>(
    async (prev, fd) => {
      const res = await resetPasswordAction(prev, fd);
      if (res.ok) {
        router.push("/login");
      }
      return res;
    },
    { error: null, ok: false },
  );

  if (!token) {
    return <div className="mx-auto mt-20 max-w-sm text-center text-destructive">链接无效</div>;
  }

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">重置密码</h1>
      {state.error && <ErrorBanner variant="destructive" description={state.error} />}
      <AppForm action={formAction} defaultValues={INITIAL_VALUES}>
        <input name="token" type="hidden" value={token} />
        <AppField name="password" type="password">
          <Input
            data-testid="password-input"
            minLength={MIN_PASSWORD_LENGTH}
            placeholder="新密码 (至少 8 位)"
            required
            type="password"
          />
        </AppField>
        <AppField name="confirm" type="password">
          <Input data-testid="confirm-input" placeholder="确认新密码" required type="password" />
        </AppField>
        <AppSubmit className="w-full" data-testid="submit" disabled={isPending}>
          重置
        </AppSubmit>
      </AppForm>
    </div>
  );
}
