/**
 * 公开 share 页只读对话视图 — 复用 MessageBubble, 无 Composer/交互入口
 * @param props.shareId 分享 id
 * @param props.title 对话标题
 * @param props.messages 分享消息列表
 * @param props.model AI 模型标识
 * @param props.createdAt 创建时间
 * @returns JSX 元素
 * @shared
 */
// 复用 MessageBubble (pairedQuestion 故意不传 → 内部不渲染 MessageFeedback)
// 不挂 Composer; 公开只读, 无任何交互入口
import { MessageBubble } from "./message-bubble";
import type { SharedMessage } from "@/lib/api/chat-share";
import { formatDate, nowMs, toInstant } from "@/lib/date";

/**
 * 公开分享页只读视图的属性接口
 * @property shareId 分享 id
 * @property title 对话标题
 * @property messages 分享消息列表
 * @property model AI 模型标识
 * @property createdAt 创建时间
 * @shared
 */
export interface SharedChatViewProps {
  shareId: string;
  title: string;
  messages: SharedMessage[];
  model: string | null;
  createdAt: string;
}

/** 头部信息的左边距 class @shared */
const HEADER_MARGIN_CLASS = "ml-3";

/**
 * 公开分享页只读对话视图 — 复用 MessageBubble, 无交互入口
 * @param props.title 对话标题
 * @param props.messages 分享消息列表
 * @param props.model AI 模型标识
 * @param props.createdAt 创建时间
 * @returns JSX 元素
 * @shared
 */
export const SharedChatView = ({ title, messages, model, createdAt }: SharedChatViewProps) => {
  /**
   * 渲染头部信息 (模型名称 + 创建日期)
   * @returns JSX 元素
   * @client-bff
   */
  const renderHeader = () => {
    const modelLine = model ? <span>{model}</span> : null;
    let dateLine: React.ReactNode = null;
    if (createdAt) {
      dateLine = <span className={HEADER_MARGIN_CLASS}>{formatDate(createdAt, "zh-CN")}</span>;
    }
    return (
      <div className="mt-1 text-sm text-muted-foreground">
        {modelLine}
        {dateLine}
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8" data-testid="shared-chat-view">
      <header className="mb-6 border-b pb-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {renderHeader()}
      </header>
      <div className="space-y-4">
        {messages.map((msg, idx) => (
          // 关键: 不传 pairedQuestion → MessageBubble 内部不会渲染 MessageFeedback
          <MessageBubble
            key={idx}
            message={{
              content: msg.content,
              createdAt: msg.timestamp ? toInstant(msg.timestamp).epochMilliseconds : nowMs(),
              id: `shared-${idx}`,
              role: msg.role,
            }}
          />
        ))}
      </div>
      <footer className="mt-12 border-t pt-4 text-center text-xs text-muted-foreground">
        via RAG Project
      </footer>
    </div>
  );
};
