"use client";
// 创账号 invite 弹框 — React 19 useActionState 模式
// (2026-06-14) 改自定义 Form 组件 → 原生 <form> + useActionState
// (2026-06-25) 迁移到 AppForm; isAdmin Checkbox 用 form.Field 处理
import { type CreateInviteState, createInviteAction } from "@/app/[locale]/_actions/account";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppField, AppForm, AppSubmit, useFormCtx } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { useActionState } from "react";
import { useTranslations } from "next-intl";

/** 初始 useActionState 状态 */
const INITIAL: CreateInviteState = { error: null, inviteUrl: null, ok: false };

/** 表单初始值 */
const INITIAL_VALUES: Record<string, unknown> = {
  email: "",
  isAdmin: false,
};

/** isAdmin Checkbox 用 form.Field 原生 (非标准控件: 用 checked 不是 value) */
const AdminCheckbox = () => {
  const tr = useTranslations();
  const { form } = useFormCtx();
  const { Field } = form;
  return (
    <Label className="flex items-center gap-2 text-sm">
      <Field name="isAdmin" mode="value">
        {(field: { handleChange: (value: boolean) => void; state: { value: unknown } }) => (
          <Checkbox
            checked={Boolean(field.state.value)}
            data-testid="admin-checkbox"
            name="isAdmin"
            onCheckedChange={(checked) => field.handleChange(checked === true)}
          />
        )}
      </Field>
      {tr("admin")}
    </Label>
  );
};

/**
 * 创建邀请弹框组件 — React 19 useActionState 模式
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 弹框打开状态变更回调
 * @param props.onCreated - 创建成功后回调
 * @returns 创建邀请弹框
 * @client-bff
 */
export const CreateInviteDialog = ({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
}) => {
  const tr = useTranslations();
  const [state, formAction, isPending] = useActionState<CreateInviteState, FormData>(
    async (_prev, fd) => {
      const res = await createInviteAction(_prev, fd);
      if (res.ok) {
        onCreated?.();
      }
      return res;
    },
    INITIAL,
  );

  const { inviteUrl } = state;
  const err = state.error;

  return (
    <AppDialog
      dataTestid="create-invite-dialog"
      error={err}
      maxWidth="md"
      onOpenChange={(val) => onOpenChange(val)}
      open={open}
      title={tr("创账号")}
    >
      {inviteUrl ? (
        <div className="space-y-3">
          <p className="text-sm">{tr("邀请链接已生成")}:</p>
          <code
            className="block break-all rounded bg-muted/30 p-2 text-xs"
            data-testid="invite-url"
          >
            {/* (2026-06-17) 显示完整 URL, 不只路由 (用户反馈). SSR 时 origin 拿不到, 后备走相对路径 */}
            {typeof globalThis.window !== "undefined"
              ? globalThis.location.origin + inviteUrl
              : inviteUrl}
          </code>
          <div className="flex gap-2">
            <CopyButton
              dataTestid="copy-url"
              text={
                typeof globalThis.window !== "undefined"
                  ? globalThis.location.origin + inviteUrl
                  : inviteUrl
              }
            />
            <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
              关闭
            </Button>
          </div>
        </div>
      ) : (
        <AppForm action={formAction} defaultValues={INITIAL_VALUES}>
          <AppField label={tr("邮箱")} name="email" required type="email">
            <Input data-testid="email-input" required type="email" />
          </AppField>
          <div className="space-y-1.5">
            <Label className="eyebrow block">{tr("权限")}</Label>
            <AdminCheckbox />
          </div>
          <div className="flex gap-2">
            <AppSubmit className="flex-1" data-testid="submit" disabled={isPending}>
              {isPending ? tr("创建中…") : tr("创账号")}
            </AppSubmit>
            <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
              {tr("取消")}
            </Button>
          </div>
        </AppForm>
      )}
    </AppDialog>
  );
};
