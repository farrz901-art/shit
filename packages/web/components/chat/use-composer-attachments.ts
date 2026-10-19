/**
 * useComposerAttachments (2026-06-29)
 * 把 ComposerAttachments 主组件的 items state + upload/remove/toggle/close 4 个 handler 抽出来
 * 主组件只负责 UI 组合, hook 管所有状态变更
 * 上传链: doUpload (presign/finalize → multipart fallback) — 走 @/lib/api/chat
 */
"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { ChatFile } from "@/lib/chat/types";
import { doUpload } from "@/lib/api/chat";
import { nowMs } from "@/lib/date";

// 内部附件状态: 比 ChatFile 多个 status 字段, 跟 UI 状态机对齐
/**
 * 内部附件状态 — 扩展 ChatFile 增加上传 status 字段
 * @client-bff
 */
export interface AttachmentItem extends ChatFile {
  id: string; // 内部 id (uploadFileId 或临时)
  name: string;
  status: "uploading" | "done" | "error";
}

/** 随机 id 基数 @shared */
const RANDOM_ID_RADIX = 36;
/** 随机 id 截取起始位置 @shared */
const RANDOM_ID_START = 2;

/**
 * 根据 MIME 类型推断附件类型
 * @param mime 文件 MIME 类型
 * @returns 附件类型 (image / audio / document)
 * @shared
 */
const inferType = (mime: string): ChatFile["type"] => {
  if (mime.startsWith("image/")) {
    return "image";
  }
  if (mime.startsWith("audio/")) {
    return "audio";
  }
  return "document";
};

/**
 * 附件插槽类型 — 图片/文件/语音
 * @client-bff
 */
export type Slot = "image" | "file" | "voice";

/**
 * Composer 附件状态 hook — 管理 items state + upload/remove/toggle/close handler
 * @param onAttachmentsChange 附件列表变更时上抛回调
 * @returns activeSlot, closeSlot, items, removeItem, toggleSlot, uploadAndAdd
 * @client-bff
 */
export const useComposerAttachments = (onAttachmentsChange: (files: ChatFile[]) => void) => {
  const [items, setItems] = useState<AttachmentItem[]>([]);
  // 3 个入口的 popover/dropzone 显隐 (互斥)
  const [activeSlot, setActiveSlot] = useState<Slot | null>(null);

  // 列表变更 → 提取 status=done 的项, 上抛给 Composer
  useEffect(() => {
    const done = items
      .filter((item) => item.status === "done")
      .map<ChatFile>(({ id: _id, name: _name, status: _s, ...rest }) => rest);
    onAttachmentsChange(done);
  }, [items, onAttachmentsChange]);

  /**
   * 统一处理上传流程: 加 uploading → 调 doUpload → 改 done/error
   * @param file 要上传的文件
   * @client-bff
   */
  const uploadAndAdd = async (file: File): Promise<void> => {
    const tempId = `tmp-${nowMs()}-${Math.random().toString(RANDOM_ID_RADIX).slice(RANDOM_ID_START)}`;
    setItems((prev) => [
      ...prev,
      {
        id: tempId,
        name: file.name,
        status: "uploading",
        transferMethod: "local_file",
        type: inferType(file.type),
      },
    ]);
    try {
      const { uploadFileId, uri } = await doUpload(file);
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === tempId) {
            return {
              ...item,
              id: uploadFileId,
              status: "done",
              uploadFileId,
              url: uri || item.url,
            };
          }
          return item;
        }),
      );
    } catch (error) {
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === tempId) {
            return { ...item, status: "error" };
          }
          return item;
        }),
      );
      toast.error(`上传失败: ${(error as Error).message}`);
    }
  };

  /**
   * 按 id 移除附件
   * @param id 附件 id
   * @client-bff
   */
  const removeItem = (id: string): void => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  };

  /**
   * 切换附件插槽展开/收起
   * @param slot 插槽类型
   * @client-bff
   */
  const toggleSlot = (slot: Slot) => {
    setActiveSlot((prev) => {
      if (prev === slot) {
        return null;
      }
      return slot;
    });
  };

  /**
   * 关闭活动附件插槽
   * @client-bff
   */
  const closeSlot = () => {
    setActiveSlot(null);
  };

  return { activeSlot, closeSlot, items, removeItem, toggleSlot, uploadAndAdd };
};
