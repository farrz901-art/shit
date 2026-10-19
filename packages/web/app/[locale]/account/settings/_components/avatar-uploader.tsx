"use client";
// AvatarUploader — 头像上传 (FileInput + 上传 + 预览 + 移除)
// (2026-06-18) T4.2 实现: 用 <form encType="multipart/form-data"> 提交, server action 接管
// 跟 T3.1 uploadAvatarAction + deleteAvatarAction 配合
// 渲染: Avatar (20x20) + 上传/移除按钮 + 错误条 + 提示
// 走 useActionState (上传) + useTransition (移除) 双路, 移除直接调 deleteAvatarAction
// (2026-06-25) 迁移到 AppForm (encType + ref 透传到 <form>)
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  type AvatarState,
  deleteAvatarAction,
  uploadAvatarAction,
} from "@/app/[locale]/_actions/account-settings";
import { useActionState, useRef, useState, useTransition } from "react";
import { AppField, AppForm } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Camera } from "lucide-react";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Input } from "@/components/ui/input";
import { ZERO } from "@/const";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";

/** uploadAvatarAction 的初始状态: 无头像 URL, 无错误 */
const INITIAL: AvatarState = { avatarUrl: null, error: null, ok: false };

/** 头像上传组件: 支持选择文件上传预览及移除头像
 * @param currentUrl - 当前头像 URL (若已有)
 * @returns 头像上传区域 JSX
 * @client-bff
 */
export const AvatarUploader = ({ currentUrl }: { currentUrl: string | null }) => {
  const tr = useTranslations();
  const [state, action] = useActionState(uploadAvatarAction, INITIAL);
  const [previewUrl, setPreviewUrl] = useState<string | null>(currentUrl);
  const [isPendingRemove, startRemoveTransition] = useTransition();
  const formRef = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // (2026-06-18) 同步 server 回的 avatarUrl 到本地预览, 避免 useEffect 额外一次渲染
  if (state.ok && state.avatarUrl && state.avatarUrl !== previewUrl) {
    setPreviewUrl(state.avatarUrl);
  }

  /** 文件选择变更: 生成本地预览 URL 后自动提交表单
   * @param event - 文件输入 change 事件
   */
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[ZERO];
    if (file) {
      // 本地预览
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      // 自动提交
      formRef.current?.requestSubmit();
    }
  };

  return (
    <div className="flex items-center gap-4" data-testid="avatar-uploader">
      <Avatar className="h-20 w-20" data-testid="profile-avatar">
        {previewUrl ? <AvatarImage alt={tr("avatar")} src={previewUrl} /> : null}
        <AvatarFallback>?</AvatarFallback>
      </Avatar>

      <AppForm
        ref={formRef}
        action={action}
        className="space-y-2"
        defaultValues={{}}
        encType="multipart/form-data"
      >
        <AppField name="file">
          <Input
            ref={inputRef}
            accept="image/png,image/jpeg,image/webp"
            className="hidden"
            data-testid="avatar-file-input"
            name="file"
            onChange={handleFileChange}
            type="file"
          />
        </AppField>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            data-testid="avatar-upload-button"
            onClick={() => inputRef.current?.click()}
            size="sm"
            type="button"
            variant="outline"
          >
            <Camera className="mr-1 h-4 w-4" />
            {tr("更换头像")}
          </Button>
          {currentUrl && (
            <Button
              data-testid="avatar-remove-button"
              disabled={isPendingRemove}
              onClick={() => {
                startRemoveTransition(async () => {
                  await deleteAvatarAction();
                  setPreviewUrl(null);
                  useRouter().refresh();
                });
              }}
              size="sm"
              type="button"
              variant="ghost"
            >
              {tr("移除头像")}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{tr("支持 PNG / JPG / WebP, ≤ 2MB")}</p>
        {state.error && (
          <ErrorBanner variant="destructive" description={state.error} dataTestid="avatar-error" />
        )}
      </AppForm>
    </div>
  );
};
