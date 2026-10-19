"use client";
// Invite 兑换页 — React 19 useActionState 模式
// (2026-06-14) 改手写 useState+useTransition → useActionState + <form action>
// (2026-06-24) 删 router.push("/") + router.refresh(): server action 内已 server-redirect.
//   原 bug: useActionState 的 isPending 跟 React transition 绑死, 客户端 router.push
//   未完成前 isPending 不复位 → 按钮卡"兑换中…"; 且 next/navigation 的 push 不带 locale
//   被 intlMiddleware 307, 用户实际已经兑换成功但 UI 看不出.
// (2026-06-25) 迁移到 AppForm
import { type AcceptInviteState, acceptInviteAction } from "@/app/[locale]/_actions/account";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getInvite } from "@/lib/api/invites";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useActionState, useEffect, useState } from "react";
import { MIN_PASSWORD_LENGTH } from "@/const";

/** InviteRedeemPage - 邀请链接兑换页面, 含 useActionState 表单提交 + 邀请有效性校验
 * @returns 兑换表单 JSX 或错误/加载状态
 * @client-bff
 */
// eslint-disable-next-line max-statements -- 单一兑换页, 6 渲染分支各自独立, 拆函数反而割裂阅读
export default function InviteRedeemPage() {
  const translate = useTranslations();
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [email, setEmail] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }
    getInvite(token)
      .then((body) => setEmail(body.email))
      .catch(() => setInvalid(true));
  }, [token]);

  // 成功路径走 server-side redirect (acceptInviteAction 抛 NEXT_REDIRECT), 这里只处理失败 state.
  const [state, formAction, isPending] = useActionState<AcceptInviteState, FormData>(
    acceptInviteAction,
    { error: null, ok: false },
  );

  if (invalid) {
    return (
      <div className="mx-auto mt-20 max-w-sm space-y-4">
        <h1 className="display text-3xl text-destructive">邀请链接无效</h1>
        <p className="text-sm text-muted-foreground">请联系管理员重新发送邀请。</p>
      </div>
    );
  }

  if (email === null) {
    return <div className="mx-auto mt-20 text-muted-foreground">加载中…</div>;
  }

  const initialValues: Record<string, string> = {
    confirm: "",
    displayName: "",
    email: email ?? "",
    password: "",
    token,
  };

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{translate("接受邀请")}</h1>
      {state.error && <ErrorBanner variant="destructive" description={state.error} />}
      <AppForm action={formAction} defaultValues={initialValues}>
        <input name="token" type="hidden" value={token} />
        <div className="space-y-1.5">
          <Label className="eyebrow block">{translate("邮箱")}</Label>
          <Input
            className="bg-muted/30 text-muted-foreground"
            data-testid="email-input"
            readOnly
            type="email"
            value={email ?? ""}
          />
        </div>
        <AppField label={translate("显示名称")} name="displayName" required>
          <Input data-testid="name-input" required type="text" />
        </AppField>
        <AppField label={translate("密码")} name="password" required type="password">
          <Input
            data-testid="password-input"
            minLength={MIN_PASSWORD_LENGTH}
            required
            type="password"
          />
        </AppField>
        <AppField label={translate("确认密码")} name="confirm" required type="password">
          <Input data-testid="confirm-input" required type="password" />
        </AppField>
        <AppSubmit className="w-full" data-testid="submit" disabled={isPending}>
          {isPending ? translate("兑换中…") : translate("接受邀请")}
        </AppSubmit>
      </AppForm>
    </div>
  );
}
