"use client";
// 文件拖拽区 (2026-06-15) — 从 components/knowledge/ 升 common/, 跟 BackLink 同位
// 替项目里手写 <input type="file"> + dragover state 模板. 跟 [CLAUDE.md] 表格 + 反模式章节对齐.
//
// 升级点 (相对旧 knowledge/FileDropzone):
//   - 位置: components/knowledge → components/common (跨域, 不专属 knowledge)
//   - 命名: PascalCase FileDropzone.tsx → kebab-case file-dropzone.tsx
//   - multiple 模式: 支持多文件 (output/new 多文件上传场景), onFiles 回调
//   - accept 字符串: ".pdf,.jpg,.png" 直接传, 内部解析成 MIME 字典, 旧 MIME 字典也支持
//   - title/hint/description 走 props, 方便 i18n (旧版硬编码中文)
//   - 视觉: Lucide UploadCloud 图标 + rounded-2xl + hover 渐变 + active 缩放
//
// 跟现有 2 个调用点 (DocumentsImportForm / EvaluateNewForm) 完全后向兼容, 默认 props 等同旧行为.
import { type Accept, useDropzone } from "react-dropzone";
import { UploadCloud } from "lucide-react";
import { cn } from "@/lib/utils";
import { ONE_KB, ZERO } from "@/const";

/**
 * FileDropzone 属性接口 — 多文件模式、类型过滤、大小限制及回调
 * @client-bff
 */
export interface FileDropzoneProps {
  /** 多文件模式 (默认 false) */
  multiple?: boolean;
  /** 接受的文件类型: 扩展字符串 ".pdf,.jpg" 或 MIME 字典 { "application/pdf": [".pdf"] } */
  accept?: string | Record<string, string[]>;
  /** 大小上限 MB (默认 50) */
  maxSizeMB?: number;
  /** 单文件回调 (multiple=false 时用) */
  onFile?: (file: File) => void;
  /** 多文件回调 (multiple=true 时用) */
  onFiles?: (files: File[]) => void;
  /** 主标题 (i18n 友好, 默认 "拖文件到这 或 点击选择") */
  title?: string;
  /** 副标题/限制说明 (默认 "上限 {maxSizeMB}MB") */
  hint?: string;
  /** 附加说明 (如 "支持: PDF, 图片, Office, ..."), 可空 */
  description?: string;
  className?: string;
  "data-testid"?: string;
}

// 扩展 → MIME 映射 (覆盖项目常见: PDF/图片/Office/HTML/CAD/压缩包/csv/json)
/** 扩展名 → MIME 类型映射 (覆盖项目常见: PDF/图片/Office/HTML/CAD/压缩包/csv/json) */
const EXT_TO_MIME: Record<string, string> = {
  ".csv": "text/csv",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".dwg": "application/acad",
  ".dxf": "application/dxf",
  ".htm": "text/html",
  ".html": "text/html",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".json": "application/json",
  ".md": "text/markdown",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".tiff": "image/tiff",
  ".webp": "image/webp",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".zip": "application/zip",
};

/** 默认大小上限 MB */
const DEFAULT_MAX_SIZE_MB = 50;
/** 每 MB 的字节数 */
const BYTES_PER_MB = ONE_KB * ONE_KB;

/**
 * 解析文件扩展名字符串为 react-dropzone Accept 字典
 * @param input 逗号分隔的扩展名列表, 例 ".pdf,.jpg,.png"
 * @returns Accept 字典或 undefined
 */
const parseAcceptString = (input: string): Accept | undefined => {
  // 字符串 ".pdf, .jpg , .png" → MIME 字典
  const exts = input
    .split(",")
    .map((val) => val.trim().toLowerCase())
    .filter(Boolean);
  if (!exts.length) {
    return undefined;
  }
  const out: Record<string, string[]> = {};
  for (const ext of exts) {
    const mime = EXT_TO_MIME[ext] ?? "application/octet-stream";
    (out[mime] ??= []).push(ext);
  }
  return out;
};

/**
 * 统一的 accept 解析入口 — 支持字符串和 MIME 字典两种格式
 * @param input 扩展名字符串或 MIME 字典
 * @returns Accept 字典或 undefined
 */
const parseAccept = (input: string | Record<string, string[]> | undefined): Accept | undefined => {
  if (!input) {
    return undefined;
  }
  if (typeof input === "object") {
    return input;
  }
  return parseAcceptString(input);
};

/**
 * 文件拖拽上传区 — react-dropzone 包装, 替手写 <input type="file"> + dragover 模板
 * 支持多文件 / 扩展名或 MIME 过滤 / 大小限制 / 拖拽反馈
 * @param props.multiple 多文件模式
 * @param props.accept 文件类型过滤
 * @param props.maxSizeMB 大小上限 MB
 * @param props.onFile 单文件回调
 * @param props.onFiles 多文件回调
 * @returns 拖拽区 JSX
 */
export const FileDropzone = ({
  multiple = false,
  accept,
  maxSizeMB = DEFAULT_MAX_SIZE_MB,
  onFile,
  onFiles,
  title = "拖文件到这 或 点击选择",
  hint,
  description,
  className,
  "data-testid": dataTestid = "file-dropzone",
}: FileDropzoneProps) => {
  const resolvedAccept = parseAccept(accept);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    accept: resolvedAccept,
    maxSize: maxSizeMB * BYTES_PER_MB,
    multiple,
    onDrop: (droppedFiles) => {
      if (multiple) {
        onFiles?.(droppedFiles);
      } else {
        const firstFile = droppedFiles.at(ZERO);
        if (firstFile) {
          onFile?.(firstFile);
        }
      }
    },
  });

  const hintText = hint ?? `上限 ${maxSizeMB}MB`;

  const rejectionError = fileRejections.at(ZERO)?.errors.at(ZERO)?.message;

  return (
    <div
      {...getRootProps()}
      data-testid={dataTestid}
      className={cn(
        "group rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-300",
        isDragActive && "border-clay bg-clay/5 scale-[1.01]",
        !isDragActive &&
          "border-border bg-card/40 hover:border-muted-foreground/40 hover:bg-card/60",
        className,
      )}
    >
      <input {...getInputProps()} />
      <UploadCloud
        className={cn(
          "mx-auto mb-4 h-10 w-10 transition-transform duration-300",
          isDragActive && "text-clay scale-110",
          !isDragActive && "text-muted-foreground/60 group-hover:text-muted-foreground",
        )}
      />
      <div className="display mb-1 text-xl text-foreground/80">{title}</div>
      <p className="text-sm text-muted-foreground">{hintText}</p>
      {description && <p className="mt-2 text-xs text-muted-foreground/80">{description}</p>}
      {rejectionError && (
        <p className="mt-3 text-sm text-status-error" data-testid="dropzone-error">
          {rejectionError}
        </p>
      )}
    </div>
  );
};
