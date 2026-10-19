"use client";
// RestoreDeletionBanner — 全局横幅, pending_deletion 状态时显示
// (2026-06-18) T4.3 实现: layout 顶层挂, is_pending_deletion=true 时渲染
// 倒计时 + 撤销按钮 (inline 表单) + 撤销成功 / 失败反馈
// 跟 CancelDeletionDialog 二选一: 横幅用 inline, dialog 用于更明确的"撤销"入口 (T4.1 stub)
// (2026-06-25) 迁移到 AppForm
import { type DeletionState, cancelDeletionAction } from "@/app/[locale]/_actions/account-settings";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HOURS_PER_DAY, ZERO } from "@/const";
import { differenceInDays, differenceInHours } from "@/lib/date";
import { useActionState, useState } from "react";
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

/** 待注销全局横幅: 显示注销倒计时和撤销按钮/表单
 * @param expiresAt - 注销生效截止时间
 * @returns 横幅 JSX (expiresAt 为 null 时返回 null)
 * @client-bff
 */
export const RestoreDeletionBanner = ({ expiresAt }: { expiresAt: string | null }) => {
  const tr = useTranslations();
  const [state, action] = useActionState(cancelDeletionAction, INITIAL);
  const [showForm, setShowForm] = useState(false);

  if (!expiresAt) {
    return null;
  }

  const exp = new Date(expiresAt);
  const days = Math.max(ZERO, differenceInDays(exp, new Date()));
  const hours = Math.max(ZERO, differenceInHours(exp, new Date()) % HOURS_PER_DAY);

  return (
    <div
      className="w-full border-b border-status-error/30 bg-status-error/10 px-4 py-3"
      data-testid="restore-deletion-banner"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2">
        <div className="flex-1">
          <strong className="font-semibold text-status-error">{tr("账号将在 7 天后删除")}</strong>
          <span className="ml-2 text-sm text-muted-foreground">
            ({days} {tr("天")} {hours} {tr("小时")})
          </span>
          {state.ok && (
            <span className="ml-3 text-sm text-status-success" data-testid="banner-cancel-success">
              {tr("撤销成功")}
            </span>
          )}
          {state.error && (
            <span className="ml-3 text-sm text-status-error" data-testid="banner-cancel-error">
              {state.error}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {!showForm ? (
            <Button
              data-testid="banner-cancel-button"
              onClick={() => setShowForm(true)}
              size="sm"
              variant="destructive"
            >
              {tr("撤销注销")}
            </Button>
          ) : (
            <AppForm action={action} className="flex gap-2" defaultValues={INITIAL_VALUES}>
              <AppField name="current_password" type="password">
                <Input
                  className="h-8 w-40"
                  data-testid="banner-cancel-password"
                  placeholder={tr("当前密码")}
                  type="password"
                />
              </AppField>
              <AppSubmit data-testid="banner-cancel-submit" size="sm" variant="destructive">
                {tr("确认")}
              </AppSubmit>
            </AppForm>
          )}
        </div>
      </div>
    </div>
  );
};
