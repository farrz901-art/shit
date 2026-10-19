"use client";
// EmailSection — 邮箱 (T3.3 显示 + 修改按钮; T4.1 加 ChangeEmailDialog 真实表单)
import { Button } from "@/components/ui/button";
import { ChangeEmailDialog } from "./change-email-dialog";
import { Mail } from "lucide-react";
import { SettingsCard } from "@/components/common/display/app-settings-card";
import { useToggle } from "react-use";
import { useTranslations } from "next-intl";

/** 邮箱信息展示卡片: 显示当前邮箱并提供修改弹框入口
 * @param email - 当前邮箱地址
 * @returns 卡片 JSX
 * @client-bff
 */
export const EmailSection = ({ email }: { email: string }) => {
  const tr = useTranslations();
  const [open, toggleopen] = useToggle(false);

  return (
    <SettingsCard icon={Mail} title={tr("邮箱")} data-testid="email-section">
      <p className="text-sm" data-testid="email-value">
        {email}
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => toggleopen(true)}
        data-testid="email-change-button"
      >
        {tr("修改邮箱")}
      </Button>
      <ChangeEmailDialog open={open} onOpenChange={toggleopen} />
    </SettingsCard>
  );
};
