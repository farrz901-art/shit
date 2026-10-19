/**
 * Chat 反馈按钮 (2026-06-13 Task 21) — 双状态折叠/展开
 *
 * 折叠态 (FeedbackButtons): 不满意 / 满意 2 按钮
 *   - 不满意 → 切展开态 (setOpen=true)
 *   - 满意 → 调 likeAnswer server action, kind=like approval, 一次性不可 unlike
 * 展开态 (FeedbackForm): Textarea 改进回答 + Input 改进理由 + 提交/取消
 *   - 改进回答必填 (校验: improved.trim() 空 → toast.error 拦截)
 *   - 提交 → optimizeAnswer server action → kind=optimize approval
 *   - 成功 → toast.success + 跳 /submissions 让用户看审核进度
 *
 * 触发审核流: improve:approval kind=optimize/like, 通过后 Executor 异步更新 Dify QA + Neo4j (可选)
 */
"use client";
// Chat 反馈按钮 (2026-06-13 Task 21) — 不满意时弹小输入框,
// 让用户写"改进后回答 + 改进理由", 提交后调 optimizeAnswer server action
// 触发审核, 然后跳 /submissions 让用户看审核进度.
// (2026-06-13) 优化回答触发 improve:approval 审核 (kind=optimize), 通过后 Executor
// 异步更新 Dify QA + 同步 Neo4j (可选).
// (2026-06-16 Task 6) 满意按钮接通 → kind=like approval, 走 likeAnswer server action.
// 一次性 (不可 unlike), 点击后 toast.success + 按钮 disabled.
import { Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import { likeAnswer, optimizeAnswer } from "@/app/[locale]/_actions/knowledge";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useState } from "react";
import { useBoolean } from "react-use";
import { useTranslations } from "next-intl";

/**
 * MessageFeedback 组件属性接口
 * @client-bff
 */
interface Props {
  /** 消息 id (用于 testid / 关联 log, server action 不依赖) */
  messageId: string;
  /** 用户提问原文 (assistant 消息配对) */
  question: string;
  /** 当前 assistant 回答原文 (用于拼 optimize payload) */
  originalAnswer: string;
  /** Dataset id (从 app store 取, 默认 ds-default 兜底) */
  datasetId?: string;
}

/**
 * FeedbackForm 子组件属性接口
 * @client-bff
 */
interface FeedbackFormProps {
  messageId: string;
  question: string;
  originalAnswer: string;
  datasetId?: string;
  onClose: () => void;
}

/**
 * FeedbackButtons 子组件属性接口
 * @client-bff
 */
interface FeedbackButtonsProps {
  messageId: string;
  question: string;
  originalAnswer: string;
  onOpen: () => void;
}

/** 打开态: 弹小输入框 (改进回答 Textarea + 改进理由 Input + 提交/取消按钮) */
const FeedbackForm = ({
  messageId,
  question,
  originalAnswer,
  datasetId,
  onClose,
}: FeedbackFormProps) => {
  const translation = useTranslations();
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const [improved, setImproved] = useState("");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useBoolean(false);

  /**
   * 提交成功回调 — toast 提示 + 重置表单 + 关闭 + 跳转审核页
   * @param approvalId 创建的审核记录 id
   * @client-bff
   */
  const handleSubmitSuccess = (approvalId: number) => {
    toast.success(translation("感谢反馈! 审核 #{id} 已创建", { id: approvalId }));
    setImproved("");
    setReason("");
    onClose();
    router.push(`/${params.locale}/submissions`);
  };

  /**
   * 提交优化回答 — 校验 + 调 server action + 处理结果
   * @client-bff
   */
  const submit = async () => {
    if (!improved.trim()) {
      toast.error(translation("改进回答必填"));
      return;
    }
    setPending(true);
    const result = await optimizeAnswer({
      dataset_id: datasetId ?? "ds-default",
      improved_answer: improved.trim(),
      original_answer: originalAnswer,
      question,
      reason: reason.trim(),
    });
    setPending(false);
    if (result.ok) {
      handleSubmitSuccess(result.data.approval_id);
    } else {
      toast.error(result.error);
    }
  };

  const submitLabel = pending ? translation("正在提交…") : translation("提交反馈");

  return (
    <div
      data-testid={`feedback-form-${messageId}`}
      className="mt-2 space-y-2 rounded border border-status-warning/30 bg-status-warning/5 p-3"
    >
      <Textarea
        value={improved}
        onChange={(ev) => setImproved(ev.target.value)}
        placeholder={`${translation("改进回答占位符")} (${translation("改进回答")})`}
        maxLength={2000}
        data-testid="feedback-improved"
        rows={3}
      />
      <Input
        value={reason}
        onChange={(ev) => setReason(ev.target.value)}
        placeholder={`${translation("改进理由占位符")} (${translation("改进理由")})`}
        maxLength={500}
        data-testid="feedback-reason"
      />
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={submit}
          disabled={pending || !improved.trim()}
          data-testid="btn-submit-feedback"
        >
          {pending && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
          {submitLabel}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onClose}
          disabled={pending}
          data-testid="btn-cancel-feedback"
        >
          {translation("取消")}
        </Button>
      </div>
    </div>
  );
};

/** 折叠态: 不满意 / 满意 两个小按钮 */
const FeedbackButtons = ({ messageId, question, originalAnswer, onOpen }: FeedbackButtonsProps) => {
  const translation = useTranslations();
  const [liked, setLiked] = useBoolean(false);
  const [liking, setLiking] = useBoolean(false);

  // (2026-06-16 Task 6) 满意按钮 handler: 调 likeAnswer → toast + 置 liked
  /**
   * 满意按钮 handler — 调 likeAnswer server action
   * @client-bff
   */
  const handleLike = async () => {
    if (liked || liking) {
      return;
    }
    setLiking(true);
    const result = await likeAnswer({
      answer: originalAnswer,
      messageId,
      question,
    });
    setLiking(false);
    if (result.ok) {
      toast.success(translation("已点赞"));
      setLiked(true);
    } else {
      toast.error(result.error);
    }
  };

  const likeIconElement: React.ReactNode = liking ? (
    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
  ) : (
    <ThumbsUp className="mr-1 h-3 w-3" />
  );
  const likeLabelText: string = liked ? translation("已点赞") : translation("满意");

  return (
    <div className="mt-1 flex gap-1">
      <Button size="sm" variant="ghost" onClick={onOpen} data-testid={`btn-improve-${messageId}`}>
        <ThumbsDown className="mr-1 h-3 w-3" />
        {translation("不满意")}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={handleLike}
        disabled={liked || liking}
        data-testid={`btn-good-${messageId}`}
      >
        {likeIconElement}
        {likeLabelText}
      </Button>
    </div>
  );
};

/**
 * Chat 反馈双态组件 — 折叠态(满意/不满意按钮) + 展开态(改进表单)
 * @param props.messageId 消息 id
 * @param props.question 用户提问原文
 * @param props.originalAnswer 当前 assistant 回答
 * @param props.datasetId Dataset id (可选)
 * @returns JSX 元素
 * @client-bff
 */
export const MessageFeedback = ({ messageId, question, originalAnswer, datasetId }: Props) => {
  const [open, setOpen] = useState(false);

  if (open) {
    return (
      <FeedbackForm
        messageId={messageId}
        question={question}
        originalAnswer={originalAnswer}
        datasetId={datasetId}
        onClose={() => setOpen(false)}
      />
    );
  }

  return (
    <FeedbackButtons
      messageId={messageId}
      question={question}
      originalAnswer={originalAnswer}
      onOpen={() => setOpen(true)}
    />
  );
};
