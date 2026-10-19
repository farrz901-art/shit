"use client";
// PasswordSection — 密码 (T3.3 改密码按钮; T4.1 加 ChangePasswordDialog 真实表单)
import { Button } from "@/components/ui/button";
import { ChangePasswordDialog } from "./change-password-dialog";
import { Lock } from "lucide-react";
import { SettingsCard } from "@/components/common/display/app-settings-card";
import { useToggle } from "react-use";
import { useTranslations } from "next-intl";

/** 密码展示卡片: 显示密码掩码并提供修改密码弹框入口
 * @returns 卡片 JSX
 * @client-bff
 */
export const PasswordSection = () => {
  const tr = useTranslations();
  const [open, toggleopen] = useToggle(false);

  return (
    <SettingsCard icon={Lock} title={tr("密码")} data-testid="password-section">
      <p className="text-sm text-muted-foreground" data-testid="password-mask">
        ••••••••
      </p>
      <Button variant="outline" size="sm" onClick={toggleopen} data-testid="password-change-button">
        {tr("修改密码")}
      </Button>
      <ChangePasswordDialog open={open} onOpenChange={toggleopen} />
    </SettingsCard>
  );
};
