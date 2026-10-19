"use client";
// ProfileSection — 基础资料 (头像 + 昵称)
// (2026-06-18) T3.3 完整实现 + T4.2 AvatarUploader 接入
// 使用 SettingsCard 统一卡片样式 + Stagger 入场动画
// (2026-06-25) 迁移到 AppForm; displayName 受控保留 (me.display_name 同步)
import { type ProfileState, updateProfileAction } from "@/app/[locale]/_actions/account-settings";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { SettingsCard } from "@/components/common/display/app-settings-card";
import { AvatarUploader } from "./avatar-uploader";
import { User } from "lucide-react";
import { useActionState, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

/** updateProfileAction 的初始状态: 无错误 */
const INITIAL: ProfileState = { error: null, ok: false };

/** 基础资料卡片: 头像上传 + 昵称编辑保存
 * @param me - 当前用户基础信息 (display_name / avatar_url)
 * @returns 卡片 JSX
 * @client-bff
 */
export const ProfileSection = ({
  me,
}: {
  me: { display_name: string | null; avatar_url: string | null };
}) => {
  const tr = useTranslations();
  const [state, action, isPending] = useActionState(updateProfileAction, INITIAL);
  const [displayName, setDisplayName] = useState(me.display_name ?? "");

  useEffect(() => {
    setDisplayName(me.display_name ?? "");
  }, [me.display_name]);

  return (
    <SettingsCard icon={User} title={tr("基础资料")} data-testid="profile-section">
      <AvatarUploader currentUrl={me.avatar_url} />
      <AppForm action={action} className="space-y-4" defaultValues={{ display_name: displayName }}>
        <AppField label={tr("昵称")} name="display_name">
          <Input
            data-testid="profile-display-name"
            id="profile-display-name"
            maxLength={50}
            onChange={(event) => setDisplayName(event.target.value)}
            value={displayName}
          />
        </AppField>
        {state.error && (
          <ErrorBanner variant="destructive" description={state.error} dataTestid="profile-error" />
        )}
        <div className="flex items-center gap-2">
          <AppSubmit data-testid="profile-save" disabled={isPending}>
            {tr("保存")}
          </AppSubmit>
          {state.ok && (
            <span className="text-sm text-status-success" data-testid="profile-saved">
              {tr("已保存")}
            </span>
          )}
        </div>
      </AppForm>
    </SettingsCard>
  );
};
