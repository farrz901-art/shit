"use client";
// RestoreForm — 撤销表单 (Client Component, in /account/restore page)
// (2026-06-18) T4.3: 撤销成功 useEffect + router.push("/") 跳首页,
//            不在 render 里 setTimeout (会触发 set-state-during-render 警告)
// (2026-06-25) 迁移到 AppForm
import { type DeletionState, cancelDeletionAction } from "@/app/[locale]/_actions/account-settings";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { useActionState } from "react";
import { useTimeoutFn } from "react-use";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";

/** cancelDeletionAction 的初始状态 */
const INITIAL: DeletionState = {
  error: null,
  expiresAt: null,
  ok: false,
  restoreUrl: null,
};

/** 撤销成功后跳转首页的延迟 (毫秒) */
const REDIRECT_DELAY_MS = 1500;
/** AppForm 的初始字段值 */
const INITIAL_VALUES: Record<string, string> = { current_password: "" };

/** 撤销注销表单组件: 输入当前密码提交撤销, 成功后 1.5s 跳转首页
 * @returns 撤销表单 JSX
 * @client-bff
 */
export const RestoreForm = () => {
  const tr = useTranslations();
  const router = useRouter();
  const [state, action] = useActionState(cancelDeletionAction, INITIAL);

  // 撤销成功, 1.5s 后跳首页; 用 state.ok 守卫避免初始渲染 0 延迟触发跳转
  useTimeoutFn(() => {
    if (state.ok) {
      router.push("/");
    }
  }, REDIRECT_DELAY_MS);

  if (state.ok) {
    return (
      <div className="text-status-success" data-testid="restore-success">
        {tr("撤销成功")}
      </div>
    );
  }

  return (
    <AppForm action={action} className="space-y-4" defaultValues={INITIAL_VALUES}>
      <AppField label={tr("当前密码")} name="current_password" required type="password">
        <Input data-testid="restore-password" required type="password" />
      </AppField>
      {state.error && (
        <ErrorBanner dataTestid="restore-error" description={state.error} variant="destructive" />
      )}
      <AppSubmit data-testid="restore-submit">{tr("撤销注销")}</AppSubmit>
    </AppForm>
  );
};
