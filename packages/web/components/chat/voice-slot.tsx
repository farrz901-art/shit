"use client";
/**
 * 语音附件插槽 — 用 VoiceRecorder 录制音频后上传
 * @param props.uploadAndAdd 上传并添加到附件列表
 * @param props.closeSlot 关闭插槽
 * @returns JSX 元素
 * @client-bff
 */
import { VoiceRecorder } from "./voice-recorder";

/**
 * 语音附件插槽 — 用 VoiceRecorder 录制后上传
 * @param props.uploadAndAdd 上传并添加到附件列表
 * @param props.closeSlot 关闭插槽
 * @returns JSX 元素
 * @client-bff
 */
export const VoiceSlot = ({
  uploadAndAdd,
  closeSlot,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
}) => (
  <VoiceRecorder
    onRecorded={async (blob, fileName) => {
      const file = new File([blob], fileName, { type: blob.type });
      await uploadAndAdd(file);
      closeSlot();
    }}
  />
);
