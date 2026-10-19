"use client";
// DeletionSection — 注销账号 (T3.3 申请/撤销按钮; T4.1 加 RequestDeletionDialog 真实表单)
// (2026-06-18) pending 状态显示撤销 inline 表单, 非 pending 状态显示申请按钮
// 使用 SettingsCard 统一卡片样式 + Stagger 入场动画
// (2026-06-25) 迁移到 AppForm (撤销 inline 表单部分)
import { type DeletionState, cancelDeletionAction } from "@/app/[locale]/_actions/account-settings";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { RequestDeletionDialog } from "./request-deletion-dialog";
import { SettingsCard } from "@/components/common/display/app-settings-card";
import { AlertTriangle } from "lucide-react";
import { useActionState } from "react";
import { useToggle } from "react-use";
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

/** 账号注销 Section: 待注销时显示撤销表单, 正常状态显示申请注销按钮
 * @param isPending - 是否处于待注销状态
 * @param expiresAt - 注销生效截止时间
 * @returns 卡片区 JSX
 * @client-bff
 */
export const DeletionSection = ({
  isPending,
  expiresAt,
}: {
  isPending: boolean;
  expiresAt: string | null;
}) => {
  const tr = useTranslations();
  const [open, toggleOpen] = useToggle(false);
  const [state, action, isCanceling] = useActionState(cancelDeletionAction, INITIAL);

  if (isPending) {
    return (
      <SettingsCard
        icon={AlertTriangle}
        title={tr("注销账号")}
        iconClassName="text-status-error"
        titleClassName="text-status-error"
        className="border-status-error/30 bg-status-error/5"
        data-testid="deletion-section"
      >
        <div data-testid="deletion-pending">
          <p className="text-sm">
            {tr("账号将在 7 天后删除")}
            {expiresAt ? ` (${expiresAt})` : ""}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{tr("注销账号说明")}</p>
          <AppForm action={action} className="mt-4 space-y-2" defaultValues={INITIAL_VALUES}>
            <AppField name="current_password" type="password">
              <Input
                data-testid="deletion-cancel-password"
                placeholder={tr("当前密码")}
                type="password"
              />
            </AppField>
            {state.error && (
              <ErrorBanner
                variant="destructive"
                description={state.error}
                dataTestid="deletion-cancel-error-banner"
              />
            )}
            <div className="flex items-center gap-2">
              <AppSubmit
                data-testid="deletion-cancel-submit"
                disabled={isCanceling}
                size="sm"
                variant="destructive"
              >
                {tr("撤销注销")}
              </AppSubmit>
              {state.ok && (
                <span className="text-sm text-status-success" data-testid="deletion-cancel-success">
                  {tr("撤销成功")}
                </span>
              )}
            </div>
          </AppForm>
        </div>
      </SettingsCard>
    );
  }

  return (
    <SettingsCard icon={AlertTriangle} title={tr("注销账号")} data-testid="deletion-section">
      <div data-testid="deletion-active">
        <p className="text-xs text-muted-foreground">{tr("注销账号说明")}</p>
        <button
          type="button"
          onClick={() => toggleOpen(true)}
          className="mt-3 rounded-md border border-status-error/40 px-3 py-1.5 text-sm font-medium text-status-error hover:bg-status-error/5 disabled:pointer-events-none disabled:opacity-50"
          data-testid="deletion-request-button"
        >
          {tr("申请注销")}
        </button>
      </div>
      <RequestDeletionDialog open={open} onOpenChange={toggleOpen} />
    </SettingsCard>
  );
};
