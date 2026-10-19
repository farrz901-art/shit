/**
 * UploadStep (2026-06-29)
 * 抽自 documents-import-form.tsx 的上传卡 (1、上传 FileDropzone)
 * 用项目 FileDropzone 封装, 替手写 <input type="file"> 模板
 */
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";

/**
 * UploadStepProps - 上传步骤属性
 * @property title - 卡片标题
 * @property fileTypeLabel - 文件类型标签
 * @property onFile - 文件选择回调
 */
export interface UploadStepProps {
  title: string;
  fileTypeLabel: string;
  onFile: (file: File) => void;
}

/** UploadStep - 上传步骤卡片组件 */
export const UploadStep = ({ title, fileTypeLabel, onFile }: UploadStepProps) => (
  <Card className="border-border/60">
    <CardHeader>
      <div className="flex items-baseline justify-between">
        <CardTitle className="text-lg">{title}</CardTitle>
        <span className="eyebrow text-muted-foreground/60">{fileTypeLabel}</span>
      </div>
    </CardHeader>
    <CardContent>
      <FileDropzone
        onFile={onFile}
        accept={{
          "application/json": [".json"],
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        }}
      />
    </CardContent>
  </Card>
);
