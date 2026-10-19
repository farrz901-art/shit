"use client";
// 创 invite 按钮 - 调 CreateInviteDialog

import { useToggle } from "react-use";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { CreateInviteDialog } from "./create-invite-dialog";

/**
 * 创建邀请按钮组件 — 调 CreateInviteDialog
 * @returns 创建邀请按钮与对应弹框
 * @client-bff
 */
export const CreateInviteButton = () => {
  const tr = useTranslations();
  const [open, toggleopen] = useToggle(false);
  return (
    <>
      <Button onClick={toggleopen} data-testid="create-invite-btn">
        {tr("创账号")}
      </Button>
      <CreateInviteDialog open={open} onOpenChange={toggleopen} onCreated={() => {}} />
    </>
  );
};
