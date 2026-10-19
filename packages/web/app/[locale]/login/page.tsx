"use client";
// 登录页 (email + password) — React 19 useActionState 模式
// (2026-06-14) 改手写 useState+useTransition → useActionState + <form action>
// (2026-06-17) 成功跳转下沉到 loginAction 内部 server-side redirect() — 失败/成功状态展示留在 wrapper
// (2026-06-25) 迁移到 AppForm
import { type LoginState, loginAction } from "@/app/[locale]/_actions/account";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { useActionState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

/** 初始表单值 */
const INITIAL_VALUES: Record<string, string> = { email: "", password: "" };

/**
 * LoginPage - 登录页
 * @client-bff
 */
export default function LoginPage() {
  const translate = useTranslations();
  const search = useSearchParams();
  const next = search.get("next") ?? "/";
  const [state, formAction, isPending] = useActionState<LoginState, FormData>(
    async (prev, fd) => {
      // 把 next 注入到 FormData, 走 server action redirect 用
      fd.set("next", next);
      return loginAction(prev, fd);
    },
    { error: null, ok: false },
  );

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{translate("登录")}</h1>
      {state.error && <ErrorBanner variant="destructive" description={state.error} />}
      <AppForm action={formAction} defaultValues={INITIAL_VALUES}>
        <input name="next" type="hidden" value={next} />
        <AppField label={translate("邮箱")} name="email" required type="email">
          <Input data-testid="email-input" required type="email" />
        </AppField>
        <AppField label={translate("密码")} name="password" required type="password">
          <Input data-testid="password-input" required type="password" />
        </AppField>
        <AppSubmit className="w-full" data-testid="login-submit" disabled={isPending}>
          {isPending ? translate("登录中…") : translate("登录")}
        </AppSubmit>
      </AppForm>
      <a href="/forgot-password" className="text-sm text-muted-foreground hover:underline">
        {translate("忘记密码?")}
      </a>
    </div>
  );
}
