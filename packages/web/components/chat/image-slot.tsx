"use client";
/**
 * 图片附件插槽 — 用 FileDropzone 接受 image/*
 * @param props.uploadAndAdd 上传并添加到附件列表
 * @param props.closeSlot 关闭插槽
 * @param props.title 弹框标题
 * @returns JSX 元素
 * @client-bff
 */
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

/** 允许上传的图片 MIME 类型 @shared */
const IMAGE_ACCEPT = "image/*";

/** image-slot @client-bff */
export const ImageSlot = ({
  uploadAndAdd,
  closeSlot,
  title,
}: {
  uploadAndAdd: (file: File) => Promise<void>;
  closeSlot: () => void;
  title: string;
}) => (
  <FileDropzone
    accept={IMAGE_ACCEPT}
    onFile={(file: File) => {
      void uploadAndAdd(file);
      closeSlot();
    }}
    title={title}
  />
);
