/**
 * 消息列表 — 自动滚到底, 用户向上滚看历史时停止自动滚
 * @param props.messages 消息列表
 * @param props.streamingMessageId 当前流式消息 id, 非空时追加闪烁光标
 * @returns JSX 元素
 * @shared
 */
import { ONE, ZERO } from "@/const";
import { useEffect, useRef, useState } from "react";
import type { Message } from "@/lib/chat/types";
import { MessageBubble } from "./message-bubble";

/**
 * 消息列表组件属性接口
 * @client-bff
 */
interface Props {
  messages: Message[];
  streamingMessageId?: string;
}

/** 自动滚底阈值 (距底部 px 内视为"粘底") @shared */
const STICKY_THRESHOLD_PX = 80;
/** 空列表提示文案 @shared */
const EMPTY_HINT = "开始一段新对话 ↓";

/**
 * 消息列表组件 — 自动滚底 + 向上滚动暂停自动滚
 * @param props.messages 消息列表
 * @param props.streamingMessageId 当前流式消息 id (追加闪烁光标)
 * @returns JSX 元素
 * @shared
 */
export const MessageList = ({ messages, streamingMessageId }: Props) => {
  const ref = useRef<HTMLDivElement>(null);
  const [sticky, setSticky] = useState(true);

  useEffect(() => {
    if (!sticky) {
      return;
    }
    const el = ref.current;
    if (!el) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [messages, sticky]);

  /**
   * 滚动事件 handler — 判断用户是否在底部附近, 同步 sticky 状态
   * @param event 滚动事件
   * @client-bff
   */
  const onScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setSticky(distFromBottom < STICKY_THRESHOLD_PX);
  };

  /**
   * 渲染空列表提示
   * @client-bff
   */
  const renderEmpty = () => (
    <p className="text-center text-sm text-muted-foreground">{EMPTY_HINT}</p>
  );

  /**
   * 渲染消息列表, 含 assistant 配对查找 + streaming 光标
   * @client-bff
   */
  const renderMessages = () => (
    <div className="space-y-4">
      {messages.map((msg, idx) => {
        // 找最近的 user message (assistant 消息的配对)
        let pairedQuestion: string | undefined = undefined;
        if (msg.role === "assistant") {
          for (let prevIdx = idx - ONE; prevIdx >= ZERO; prevIdx--) {
            if (messages[prevIdx].role === "user") {
              pairedQuestion = messages[prevIdx].content;
              break;
            }
          }
        }
        return <MessageBubble key={msg.id} message={msg} pairedQuestion={pairedQuestion} />;
      })}
      {streamingMessageId && (
        <span className="inline-block h-4 w-1 animate-pulse bg-foreground/60" />
      )}
    </div>
  );

  return (
    <div
      ref={ref}
      onScroll={onScroll}
      className="min-h-0 flex-1 overflow-y-auto px-4 py-4"
      data-testid="message-list"
    >
      {messages.length === ZERO ? renderEmpty() : renderMessages()}
    </div>
  );
};
