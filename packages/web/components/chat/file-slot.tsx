"use client";
/**
 * 文件附件插槽 — 用 FileDropzone 接受 .pdf/.docx/.xlsx/.txt/.md
 * @param props.uploadAndAdd 上传并添加到附件列表
 * @param props.closeSlot 关闭插槽
 * @param props.title 弹框标题
 * @returns JSX 元素
 * @client-bff
 */
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

/** 允许上传的文件扩展名 @shared */
const FILE_ACCEPT = ".pdf,.docx,.xlsx,.txt,.md";

/** file-slot @client-bff */
export const FileSlot = ({
  uploadAndAdd,
  closeSlot,
  title,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
  title: string;
}) => (
  <FileDropzone
    accept={FILE_ACCEPT}
    onFile={(file: File) => {
      void uploadAndAdd(file);
      closeSlot();
    }}
    title={title}
  />
);
