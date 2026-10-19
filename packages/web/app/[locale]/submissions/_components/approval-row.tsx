"use client";
// ApprovalRow — 共用行组件, 2 个独立 badge (review + apply) + Collapsible 展开 + 行内按钮
// Mine / all 都用, 按 isAdmin 决定显隐批准/拒绝/重试按钮
// (2026-06-13) Task 17
import {
  approve,
  getDetail,
  reject,
  retry,
  type Approval,
  type RejectReasonKey,
} from "@/lib/api/approvals";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RejectDialog } from "./reject-dialog";
import { TWO } from "@/const";
import { useState } from "react";
import { useTranslations } from "next-intl";

/**
 * useApprovalMutations — 审批操作 mutations hook
 * @param approvalId 审批 ID
 * @returns mutations 和状态
 * @client-bff
 */
const useApprovalMutations = (approvalId: number) => {
  const qc = useQueryClient();
  const [rejectOpen, setRejectOpen] = useState(false);

  const approveMut = useMutation({
    mutationFn: () => approve(approvalId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
  const retryMut = useMutation({
    mutationFn: () => retry(approvalId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["approvals"] }),
  });
  const rejectMut = useMutation({
    mutationFn: ({ reason, note }: { reason: RejectReasonKey; note?: string }) =>
      reject(approvalId, reason, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals"] });
      setRejectOpen(false);
    },
  });

  return { approveMut, rejectMut, rejectOpen, retryMut, setRejectOpen };
};

/** REVIEW_BADGE - 审核状态 badge 色映射 */
const REVIEW_BADGE: Record<string, string> = {
  approved: "bg-status-success/20 text-status-success",
  pending: "bg-status-warning/20 text-status-warning",
  rejected: "bg-status-error/20 text-status-error",
};

const APPLY_BADGE: Record<string, string> = {
  applied: "bg-status-success/20 text-status-success",
  failed: "bg-status-error/20 text-status-error",
  none: "bg-muted/20 text-muted-foreground",
};

// 状态 label 映射 (测试期望: pending→待审, approved→已批, none→未写入, failed→写库失败)
const REVIEW_LABEL: Record<string, string> = {
  approved: "已批",
  pending: "待审",
  rejected: "被拒",
};

const APPLY_LABEL: Record<string, string> = {
  applied: "已写入",
  failed: "写库失败",
  none: "未写入",
};

/**
 * ApprovalRow - 审批行组件, 展示单个审批项的审核状态和操作按钮, 支持展开查看详情
 * @param props.approval - 审批数据
 * @param props.isAdmin - 是否为管理员
 * @client-bff
 */
export const ApprovalRow = ({ approval, isAdmin }: { approval: Approval; isAdmin: boolean }) => {
  const tr = useTranslations("submissions");
  const [open, setOpen] = useState(false);
  const { approveMut, rejectMut, rejectOpen, retryMut, setRejectOpen } = useApprovalMutations(
    approval.id,
  );

  // 展开时拉详情
  const detail = useQuery({
    enabled: open,
    queryFn: () => getDetail(approval.id),
    queryKey: ["approval-detail", approval.id],
  });

  // 行内按钮显隐: admin + 状态机
  const isReviewPending = isAdmin && approval.review_status === "pending";
  const canRetry =
    isAdmin && approval.review_status === "approved" && approval.apply_status === "failed";

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded border p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" data-testid="expand-trigger">
              {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
          </CollapsibleTrigger>
          <span className="font-mono text-sm">#{approval.id}</span>
          <Badge className={REVIEW_BADGE[approval.review_status]} data-testid="badge-review">
            {REVIEW_LABEL[approval.review_status]}
          </Badge>
          <Badge className={APPLY_BADGE[approval.apply_status]} data-testid="badge-apply">
            {APPLY_LABEL[approval.apply_status]}
          </Badge>
          <span className="text-xs text-muted-foreground">{approval.created_at}</span>
        </div>
        <div className="flex gap-1">
          {isReviewPending && (
            <Button size="sm" onClick={() => approveMut.mutate()} data-testid="btn-approve">
              {tr("actions.approve")}
            </Button>
          )}
          {isReviewPending && (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => setRejectOpen(true)}
              data-testid="btn-reject"
            >
              {tr("actions.reject")}
            </Button>
          )}
          {canRetry && (
            <Button size="sm" onClick={() => retryMut.mutate()} data-testid="btn-retry">
              {tr("actions.retry")}
            </Button>
          )}
        </div>
      </div>

      {/* 拒绝原因 / 写库错误 — 始终显示, 不需要展开 */}
      {approval.review_status === "rejected" && approval.rejection_reason && (
        <div className="mt-3 rounded bg-status-error/10 p-3 text-sm" data-testid="rejection-block">
          <strong>{tr("rejectionReason")}:</strong> {approval.rejection_reason}
          {approval.rejection_note && (
            <div className="mt-1 text-muted-foreground">{approval.rejection_note}</div>
          )}
        </div>
      )}
      {approval.apply_status === "failed" && approval.error_msg && (
        <div
          className="mt-3 rounded bg-status-error/10 p-3 text-sm"
          data-testid="apply-error-block"
        >
          <strong>Error:</strong> {approval.error_msg}
        </div>
      )}

      <CollapsibleContent className="mt-3 space-y-2">
        {detail.isLoading && <p className="text-sm text-muted-foreground">加载中...</p>}
        {detail.data?.payload && (
          <div className="rounded bg-muted/30 p-3 text-sm">
            <pre className="whitespace-pre-wrap">
              {JSON.stringify(detail.data.payload, null, TWO)}
            </pre>
          </div>
        )}
      </CollapsibleContent>

      <RejectDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        onSubmit={(reason, note) => rejectMut.mutate({ note, reason })}
        isPending={rejectMut.isPending}
      />
    </Collapsible>
  );
};
