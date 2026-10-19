/**
 * 消息输入框组合 — 文本输入 + 附件管理 + 发送/停止切换
 * @param props.value 文本输入值
 * @param props.onChange 文本变更回调
 * @param props.onSend 发送回调 (text + files)
 * @param props.onStop 停止流式回调
 * @param props.disabled 禁用状态
 * @param props.streaming 是否正在流式输出
 * @returns JSX 元素
 * @shared
 */
// 消息输入框 + 发送/停止切换 (2026-06-09)
// (2026-06-14) 受控: value + onChange 由 ChatShell 持有
// (2026-06-16) 拆: Textarea + 调 <ComposerAttachments>, 3 类媒体入口 (图片/文件/语音)
//   Attachments state 提升到 Composer, 跟 text 一起构成发送载荷 (ChatShell.handleSend 接 ChatFile[])
import { Button } from "@/components/ui/button";
import type { ChatFile } from "@/lib/chat/types";
import { ComposerAttachments } from "./composer-attachments";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";

interface Props {
  value: string;
  onChange: (text: string) => void;
  onSend: (text: string, files: ChatFile[]) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
}

const COMPOSER_MIN_HEIGHT = "min-h-[40px]";
const TEXTAREA_ROWS = 1;
const STREAMING_PLACEHOLDER = "AI 正在回复…";
const IDLE_PLACEHOLDER = "输入消息, Enter 发送, Shift+Enter 换行";
const SEND_LABEL = "发送";
const STOP_LABEL = "停止";

// (2026-06-20) 提取到外层避免 max-statements 超限
const createHandleSend =
  ({
    value,
    attachments,
    onSend,
    setAttachments,
  }: {
    value: string;
    attachments: ChatFile[];
    onSend: Props["onSend"];
    setAttachments: React.Dispatch<React.SetStateAction<ChatFile[]>>;
  }) =>
  () => {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    onSend(trimmed, attachments);
    setAttachments([]);
  };

const createOnKeyDown =
  (handleSend: () => void) => (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

/**
 * 消息输入框组合组件 — 文本输入 + 附件管理 + 发送/停止切换
 * @param props.value 文本输入值
 * @param props.onChange 文本变更回调
 * @param props.onSend 发送回调 (text + files)
 * @param props.onStop 停止流式回调
 * @param props.disabled 禁用状态
 * @param props.streaming 是否正在流式输出
 * @returns JSX 元素
 * @shared
 */
export const Composer = ({ value, onChange, onSend, onStop, disabled, streaming }: Props) => {
  // (2026-06-16) 附件状态提升到 Composer, 跟 text 一起作为发送载荷
  const [attachments, setAttachments] = useState<ChatFile[]>([]);

  const handleSend = createHandleSend({ attachments, onSend, setAttachments, value });
  const onKeyDown = createOnKeyDown(handleSend);

  return (
    <div className="flex flex-col gap-2 border-t border-border/60 bg-card/50 px-4 py-3">
      <div className="flex items-end gap-2">
        <Textarea
          data-testid="composer-textarea"
          value={value}
          onChange={(evt) => onChange(evt.target.value)}
          onKeyDown={onKeyDown}
          placeholder={streaming ? STREAMING_PLACEHOLDER : IDLE_PLACEHOLDER}
          disabled={disabled}
          rows={TEXTAREA_ROWS}
          className={`resize-none ${COMPOSER_MIN_HEIGHT}`}
        />
        {streaming ? (
          <Button
            data-testid="composer-stop"
            onClick={onStop}
            variant="outline"
            className="shrink-0"
          >
            {STOP_LABEL}
          </Button>
        ) : (
          <Button
            data-testid="composer-send"
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="shrink-0"
          >
            {SEND_LABEL}
          </Button>
        )}
      </div>
      <ComposerAttachments onAttachmentsChange={setAttachments} />
    </div>
  );
};
