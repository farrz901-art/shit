"use client";
// 3、提交卡片 (2026-06-12) — form action + commitDocuments server action.
// 拆出来让 ImportPage 主文件 ≤300 行; 含 useActionState + result 展示.
// (2026-06-13) Task 21: 成功后弹 toast + 跳 /submissions 让用户看审核进度.
import { type ActionResult, commitDocuments } from "@/app/[locale]/_actions/knowledge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/common/feedback";
import { useActionState, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { AnimateUp } from "@/components/motion/animated";
import { toast } from "sonner";
import { useAppStore } from "@/lib/store/app-store";
import { useTranslations } from "next-intl";

/**
 * (2026-06-13) Task 11-13: commitDocuments 改调审核, 响应为 approval 形状.
 * @property approval_id - 审批 ID
 * @property review_status - 审核状态 (pending / approved / rejected)
 * @property apply_status - 应用状态 (none / applied / failed)
 */
interface CommitResponse {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

/**
 * 待提交行类型
 * @property question - 问题文本
 * @property answer - 答案文本
 * @property tags - 标签
 */
interface CommitRow {
  question: string;
  answer: string;
  tags: string;
}

interface Props {
  /** 客户端解析的待提交有效行, 序列化为 JSON 塞进 hidden input */
  validRows: CommitRow[];
  /** 提交按钮显示的数量 (total - errorCount) */
  validCount: number;
}

const APPROVAL_ID_NONE = 0;

/**
 * 初始表单状态
 * @shared
 */
const initialState: ActionResult<CommitResponse> = {
  data: { apply_status: "none", approval_id: APPROVAL_ID_NONE, review_status: "pending" },
  ok: true,
};

/**
 * ImportCommitCard - 提交卡片, form action + commitDocuments server action
 * @param props.validRows - 客户端解析的待提交有效行
 * @param props.validCount - 提交按钮显示的数量
 * @client-bff
 */
export const ImportCommitCard = ({ validRows, validCount }: Props) => {
  const tr = useTranslations();
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const datasetId = useAppStore((state) => state.datasetId);
  // (2026-06-13) Task 21: 跟踪上一次 toast 提示的 approval_id, 避免重复弹.
  const [toastedId, setToastedId] = useState<number | null>(null);

  // Form action 包 commitDocuments server action. 客户端待提交行从 FormData 回读.
  const [state, formAction, isPending] = useActionState(
    async (
      _prev: ActionResult<CommitResponse>,
      formData: FormData,
    ): Promise<ActionResult<CommitResponse>> => {
      const rowsJson = formData.get("rows") as string | null;
      if (!rowsJson) {
        return { error: tr("未提供待提交"), ok: false };
      }
      let rows: CommitRow[] = [] as CommitRow[];
      try {
        rows = JSON.parse(rowsJson) as CommitRow[];
      } catch {
        return { error: tr("提交数据格式错误"), ok: false };
      }
      return commitDocuments({ dataset_id: datasetId, rows });
    },
    initialState,
  );

  // (2026-06-13) Task 21: 提交成功后弹 toast + 跳 /submissions.
  // 用 approval_id 去重, 避免 useActionState 在错误回退时重复弹.
  useEffect(() => {
    if (
      state.ok &&
      state.data.approval_id > APPROVAL_ID_NONE &&
      state.data.approval_id !== toastedId
    ) {
      setToastedId(state.data.approval_id);
      toast.success(tr("已提交审核 #{id}", { id: state.data.approval_id }));
      router.push(`/${params.locale}/submissions`);
    } else if (!state.ok && state.error) {
      toast.error(state.error);
    }
  }, [state, tr, router, params.locale, toastedId]);

  const showResult = state.ok && state.data.approval_id > APPROVAL_ID_NONE;
  const showError = !state.ok;

  return (
    <Card className="border-border/60">
      <CardHeader>
        <CardTitle className="text-lg">{tr("3、提交")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form action={formAction}>
          {/* 隐藏字段: 客户端解析的待提交行 (server action 里回读) */}
          <input type="hidden" name="rows" value={JSON.stringify(validRows)} />
          <Button
            type="submit"
            disabled={isPending}
            className="h-10 gap-2 rounded-full bg-ink px-5 text-base text-paper hover:bg-ink/90 hover:shadow-[0_4px_12px_hsl(0_0%_0%/0.10),0_2px_4px_hsl(0_0%_0%/0.06)]"
            data-testid="docs-commit"
          >
            {isPending ? tr("提交中…") : tr("提交 {count} 行到 Dify", { count: validCount })}
          </Button>
        </form>
        {showResult && state.ok && (
          <AnimateUp
            show
            enterFromTop
            data-testid="commit-result"
            className="mt-4 rounded-lg border border-moss/30 bg-moss/5 p-3 text-base text-moss"
          >
            {tr("已提交审核 #{id} (状态: {status})", {
              id: state.data.approval_id,
              status: state.data.review_status,
            })}
          </AnimateUp>
        )}
        {showError && !state.ok && (
          <ErrorBanner
            variant="destructive"
            description={state.error}
            className="mt-4"
            dataTestid="commit-error"
          />
        )}
      </CardContent>
    </Card>
  );
};
