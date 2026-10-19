"use client";
// RejectDialog — shadcn Select 6 预设原因, 选 other 时显示 Textarea 补充
// 跟 ApprovalRow 复用 (子组件, 由 ApprovalRow 调)
// (2026-06-13) Task 18: 实装, 替 Task 17 stub
// 6 个 reason 跟后端 Pydantic Literal 1:1 (duplicate / low_quality / incomplete /
// Wrong_category / format_issue / other); 选 other 强制填 note, 其它可选
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import type { RejectReasonKey } from "@/lib/api/approvals";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";

/**
 * REASONS — 6 个预设拒绝原因, 跟后端 Pydantic Literal 1:1
 * @shared
 */
const REASONS: RejectReasonKey[] = [
  "duplicate",
  "low_quality",
  "incomplete",
  "wrong_category",
  "format_issue",
  "other",
];

/**
 * RejectDialog - 拒绝审批弹框
 * @param props.open - 弹框是否打开
 * @param props.onOpenChange - 打开状态回调
 * @param props.onSubmit - 提交拒绝回调
 * @param props.isPending - 提交中状态
 * @client-bff
 */
export const RejectDialog = ({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (reason: RejectReasonKey, note?: string) => void;
  isPending: boolean;
}) => {
  const tr = useTranslations("submissions.rejectDialog");
  const [reason, setReason] = useState<RejectReasonKey | "">("");
  const [note, setNote] = useState("");

  // 选 other → 强制填 note, 其它原因 note 可选
  const isOther = reason === "other";
  const canSubmit = Boolean(reason) && (!isOther || note.length > ZERO);

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title={tr("拒绝这条提交?")}
      description={tr("选择拒绝原因, 提交者会看到")}
      dataTestid="reject-dialog"
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            data-testid="btn-cancel-reject"
          >
            {tr("取消")}
          </Button>
          <Button
            variant="destructive"
            disabled={!canSubmit || isPending}
            onClick={() => onSubmit(reason as RejectReasonKey, isOther ? note : undefined)}
            data-testid="btn-submit-reject"
          >
            {tr("确认拒绝")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <AppSelect
          options={REASONS.map((re) => ({
            label: tr(`reasons.${re}` as never),
            value: re,
          }))}
          value={reason}
          onChange={(val) => setReason(val as RejectReasonKey)}
          placeholder={tr("请选择原因")}
          dataTestid="select-trigger"
        />
        {isOther && (
          <Textarea
            value={note}
            onChange={(ev) => setNote(ev.target.value)}
            placeholder={tr("请说明具体原因")}
            maxLength={500}
            data-testid="note-textarea"
          />
        )}
      </div>
    </AppDialog>
  );
};
