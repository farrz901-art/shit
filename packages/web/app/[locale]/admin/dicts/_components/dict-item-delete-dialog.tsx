"use client";
// 删除字典项二次确认 (2026-06-19 lookup module Task 9)
// 二次确认输入框: 必须字面输入 itemKey 才能点 "确认删除".
// 调 fetchAdminConfirmToken 拿短时 token, 再调父组件 onConfirm (page 接住后调 fetchAdminDeleteItem 带 token).
// 走 AppConfirm + 内嵌 Input, 不直接复用 AppConfirm (需要字面输入确认环节).
import { useEffect, useState } from "react";
import { useBoolean } from "react-use";
import { ApiError } from "@/lib/api/errors";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchAdminConfirmToken } from "@/lib/api/lookups";
import { useTranslations } from "next-intl";

/** 删除字典项二次确认弹框属性 */
export interface DictItemDeleteDialogProps {
  /** 弹框打开状态 */
  open: boolean;
  /** 打开状态变更回调 */
  onOpenChange: (open: boolean) => void;
  /** 当前 dict_code (用于提示用户) */
  dictCode: string;
  /** 即将删除的 item key, null 时 dialog 不渲染 */
  itemKey: string | null;
  /** 显示用 label (用于 prompt: "输入 pending 以确认") */
  itemLabel?: string | null;
  /** 确认回调: 父组件接住后调 fetchAdminDeleteItem (带 token) */
  onConfirm: (confirmToken: string) => void;
}

/**
 * 删除字典项二次确认弹框组件
 *
 * 二次确认输入框: 必须字面输入 itemKey 才能点 "确认删除".
 * 调 fetchAdminConfirmToken 拿短时 token, 再调父组件 onConfirm.
 *
 * @param props - 组件属性
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 打开状态变更回调
 * @param props.dictCode - 当前字典编码
 * @param props.itemKey - 即将删除的 item key
 * @param props.itemLabel - 显示用 label
 * @param props.onConfirm - 确认回调 (带 token)
 * @client-bff
 */
export const DictItemDeleteDialog = ({
  open,
  onOpenChange,
  dictCode,
  itemKey,
  itemLabel,
  onConfirm,
}: DictItemDeleteDialogProps) => {
  const translate = useTranslations();
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useBoolean(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // 每次打开时清空输入 + 错误
  useEffect(() => {
    if (open) {
      setConfirmText("");
      setSubmitError(null);
    }
  }, [open, itemKey]);

  const performDeleteWithToken = async () => {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const { token } = await fetchAdminConfirmToken();
      onConfirm(token);
      handleClose(false);
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : translate("申请确认 token 失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!itemKey || confirmText.trim() !== itemKey) {
      if (itemKey) {
        setSubmitError(translate("输入的 key 不匹配"));
      }
      return;
    }
    await performDeleteWithToken();
  };

  const handleClose = (next: boolean) => {
    if (!next) {
      setConfirmText("");
      setSubmitError(null);
    }
    onOpenChange(next);
  };

  return !itemKey ? null : (
    <AppDialog
      open={open}
      onOpenChange={handleClose}
      title={translate("确认删除字典项")}
      description={translate("该操作软删除字典项, 不可恢复。")}
      maxWidth="md"
      dataTestid="dict-item-delete-dialog"
      error={submitError}
      errorTestid="dict-item-delete-error"
    >
      <form className="space-y-4" noValidate onSubmit={handleSubmit}>
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
          <div className="text-muted-foreground">{translate("即将删除")}</div>
          <div className="mt-1 space-y-1">
            <div>
              <span className="eyebrow text-xs">{translate("字典")}</span>
              <span className="num font-mono ml-2">{dictCode}</span>
            </div>
            <div>
              <span className="eyebrow text-xs">key</span>
              <span className="num font-mono ml-2">{itemKey}</span>
              {itemLabel && <span className="ml-2 text-muted-foreground">({itemLabel})</span>}
            </div>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="eyebrow block" htmlFor="confirm-input">
            {translate("请输入 {key} 以确认", { key: itemKey })}
          </Label>
          <Input
            id="confirm-input"
            value={confirmText}
            onChange={(evt) => setConfirmText(evt.target.value)}
            placeholder={itemKey}
            required
            data-testid="confirm-input"
            autoComplete="off"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <Button
            type="submit"
            variant="destructive"
            disabled={submitting || confirmText.trim() !== itemKey}
            data-testid="dict-item-delete-submit"
            className="flex-1"
          >
            {submitting ? translate("确认中…") : translate("确认删除")}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={submitting}
            data-testid="dict-item-delete-cancel"
          >
            {translate("取消")}
          </Button>
        </div>
      </form>
    </AppDialog>
  );
};
