/**
 * 消息气泡 (2026-06-19 chat spec) — user / assistant 双形态渲染
 * 关键解析: AssistantBody 拆 thinking / answer, assistant 渲染 markdown + img 点击放大
 *   - user: 纯文本, 无 markdown 渲染
 * 增强: interrupted Badge + CitationPanel + MessageFeedback (满意/不满意)
 * 注意: pair (上一条 user) 没传时不显示反馈按钮 (避免 user 自评)
 *
 * 拆分记录 (2026-06-29 Task 7):
 *   - buildBubbleClass: IIFE bubbleClass 提取
 *   - AssistantBody: IIFE bodyContent (assistant) + parseThinkTag/renderThinking 拆出
 *   - MarkdownImg: 内联 markdownComponents.img 拆出
 */
"use client";

import { AssistantBody } from "./assistant-body";
import { Badge } from "@/components/ui/badge";
import { buildBubbleClass } from "./build-bubble-class";
import { CitationPanel } from "./citation-panel";
import { ImagePreview } from "@/components/common/input/app-image-preview";
import type { Message } from "@/lib/chat/types";
import { MessageFeedback } from "./message-feedback";
import { useState } from "react";
import { ZERO } from "@/const";
import { AppCollapsible } from "@/components/common/display/app-collapsible";

/** 中断标签文案 @shared */
const INTERRUPTED_LABEL = "已中断";

/**
 * 消息气泡属性接口
 * @client-bff
 */
interface MessageBubbleProps {
  message: Message;
  /** 对应的上一条 user message (用于优化答案时拼 Q&A) */
  pairedQuestion?: string;
}

/**
 * 渲染引用折叠面板
 * @param message 消息数据
 * @returns JSX 元素
 * @client-bff
 */
const renderCitations = (message: Message) => (
  <AppCollapsible
    title={`引用 ${message.citations?.length ?? ZERO} 条`}
    testId="citation-panel"
    className="mt-3"
  >
    <CitationPanel citations={message.citations ?? []} />
  </AppCollapsible>
);

/**
 * 消息气泡组件 — user/assistant 双形态渲染, 含 markdown/引用/反馈/中断标识
 * @param props.message 消息数据
 * @param props.pairedQuestion 关联的用户提问 (用于反馈配对)
 * @returns JSX 元素
 * @client-bff
 */
export const MessageBubble = ({ message, pairedQuestion }: MessageBubbleProps) => {
  const isUser = message.role === "user";
  // (2026-06-16 Task 4) 点击 markdown 中的 <img> → 弹 ImagePreview 放大原图
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);

  const bubbleClass = buildBubbleClass(isUser);

  const bodyContent = isUser ? (
    <p className="whitespace-pre-wrap text-base">{message.content}</p>
  ) : (
    <AssistantBody content={message.content} onPreview={setPreviewSrc} />
  );

  /**
   * 渲染中断标识 Badge
   * @client-bff
   */
  const renderInterrupted = () => (
    <Badge
      data-testid="interrupted-badge"
      variant="outline"
      className="mt-2 gap-1 rounded-full border-status-warning/40 bg-status-warning/10 px-2 py-0.5 text-xs text-status-warning"
    >
      {INTERRUPTED_LABEL}
    </Badge>
  );

  /**
   * 图片预览弹框开关回调
   * @param open 弹框是否展开
   * @client-bff
   */
  const handlePreviewClose = (open: boolean) => {
    if (!open) {
      setPreviewSrc(null);
    }
  };

  return (
    <div
      data-testid={`message-${message.id}`}
      data-role={message.role}
      className={isUser ? "flex justify-end" : "flex justify-start"}
    >
      <div className={bubbleClass}>
        {bodyContent}

        {message.interrupted && renderInterrupted()}

        {/* (2026-06-13 Task 21) chat 反馈: 不满意触发审核流, 满意留扩展位 */}
        {!isUser && pairedQuestion !== undefined && message.content && (
          <MessageFeedback
            messageId={message.id}
            question={pairedQuestion ?? ""}
            originalAnswer={message.content}
          />
        )}

        {!isUser &&
          message.citations &&
          message.citations.length > ZERO &&
          renderCitations(message)}

        {/* 思考过程已由 AssistantBody / parseThinkTag 从 content 中提取并渲染 */}
      </div>

      {/* (2026-06-16 Task 4) 点击 markdown 内 <img> → 弹 ImagePreview 放大 */}
      <ImagePreview
        open={previewSrc !== null}
        onOpenChange={handlePreviewClose}
        src={previewSrc ?? ""}
      />
    </div>
  );
};
