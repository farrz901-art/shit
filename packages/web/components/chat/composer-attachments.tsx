/**
 * Composer 附件主组件 (2026-06-29 重构)
 * 状态管理: useComposerAttachments hook (拆自本文件)
 * 子组件: ImageSlot / FileSlot / VoiceSlot (拆自原 ActivePanel if-else 链)
 */
"use client";
import { FileText, Image as ImageIcon, Loader2, Mic, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ZERO } from "@/const";
import { FileSlot } from "./file-slot";
import { ImageSlot } from "./image-slot";
import { useComposerAttachments } from "./use-composer-attachments";
import { VoiceSlot } from "./voice-slot";
import type { ChatFile } from "@/lib/chat/types";

/**
 * ComposerAttachments — 附件列表属性
 * @property onAttachmentsChange 附件列表变更时回调
 * @client-bff
 */
export interface ComposerAttachmentsProps {
  /** 附件列表变更时回调, 把"已完成"的 ChatFile[] 传给父组件 */
  onAttachmentsChange: (files: ChatFile[]) => void;
}

const ATTACHMENT_URI_PLACEHOLDER = "";

/**
 * Composer 附件主组件 — 状态管理 + 3 类媒体入口 (图片/文件/语音)
 * @param props.onAttachmentsChange 附件列表变更回调
 * @returns JSX 元素
 * @client-bff
 */
/** composer-attachments @client-bff */
export const ComposerAttachments = ({ onAttachmentsChange }: ComposerAttachmentsProps) => {
  const translation = useTranslations();
  const { activeSlot, closeSlot, items, removeItem, toggleSlot, uploadAndAdd } =
    useComposerAttachments(onAttachmentsChange);

  return (
    <div className="flex flex-col gap-2" data-testid="composer-attachments">
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => toggleSlot("image")}
          aria-label={translation("图片")}
          data-testid="composer-attach-image"
        >
          <ImageIcon className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => toggleSlot("file")}
          aria-label={translation("文件")}
          data-testid="composer-attach-file"
        >
          <FileText className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => toggleSlot("voice")}
          aria-label={translation("语音")}
          data-testid="composer-attach-voice"
        >
          <Mic className="h-4 w-4" />
        </Button>
      </div>
      {items.length > ZERO && (
        <div className="flex flex-wrap gap-2" data-testid="composer-attachments-list">
          {items.map((item) => (
            <div
              key={item.id}
              data-testid={`attachment-${item.id}`}
              data-attachment-uri={item.url ?? ATTACHMENT_URI_PLACEHOLDER}
              className="flex items-center gap-2 rounded-md border bg-muted/50 px-2 py-1 text-xs"
            >
              {item.status === "uploading" && <Loader2 className="h-3 w-3 animate-spin" />}
              <span className="max-w-[160px] truncate">{item.name}</span>
              <button
                type="button"
                onClick={() => removeItem(item.id)}
                data-testid={`attachment-remove-${item.id}`}
                aria-label="remove"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      {activeSlot === "image" && (
        <ImageSlot uploadAndAdd={uploadAndAdd} closeSlot={closeSlot} title={translation("图片")} />
      )}
      {activeSlot === "file" && (
        <FileSlot uploadAndAdd={uploadAndAdd} closeSlot={closeSlot} title={translation("文件")} />
      )}
      {activeSlot === "voice" && <VoiceSlot uploadAndAdd={uploadAndAdd} closeSlot={closeSlot} />}
    </div>
  );
};
