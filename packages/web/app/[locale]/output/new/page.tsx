"use client";
// 新建转换 (2026-06-10) — 拖拽 + 文件列表 + 提交
// (2026-06-11) motion.button 替换为 shadcn Button
// (2026-06-11) i18n: useTranslations + t() + LocalizedLink
// (2026-06-15) 返回链接统一: 内联 LocalizedLink → BackLink (components/common/)
// (2026-06-15) 拖拽区统一: 内联 input + dragover state → FileDropzone (components/common/)
//   FileDropzone 支持 multiple 模式 + accept 字符串 + i18n props, output/new 多文件场景天然适配
//   文件列表 (大小 + 删除) 留在 page 渲染, 跟 single-file 模式调用方保持一致
// (2026-06-17) v2 RBAC: 套 GuardClient 做 4 层防护第 2 层 (client 变种)
import { ApiError, NetworkError } from "@/lib/api/errors";
import { log } from "@/lib/log";
import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { FileText } from "lucide-react";
import { GuardClient } from "@/components/auth/guard-client";
import { ZERO } from "@/const";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { upload, uploadViaPresign } from "@/lib/api/ingest";
import { fmtSize } from "@/lib/format";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";

/** 接受的文件类型 */
const ACCEPT = ".pdf,.jpg,.jpeg,.png,.tiff,.webp,.docx,.xlsx,.pptx,.html,.htm,.dxf,.dwg,.zip";

/**
 * NewUploadInner - 新建转换内部组件
 */
const NewUploadInner = () => {
  const translation = useTranslations();
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [err, setErr] = useState<string | null>(null);
  // (2026-06-14) React 19 useTransition 替 useState(busy) — 错误路径下 transition 自动结束, isPending 自然变 false
  const [isPending, startTransition] = useTransition();

  const submit = () => {
    if (!files.length || isPending) {
      return;
    }
    // (2026-06-14) useTransition 包 upload: 成功 router.push 自动卸载, 失败 catch 后 isPending 自动 false
    // (2026-06-17) Task 9: 优先 presign/finalize 走 MinIO 直传, 失败 fallback multipart
    setErr(null);
    startTransition(async () => {
      try {
        try {
          await uploadViaPresign(files);
        } catch (error) {
          // Fallback multipart, 跟老 BFF 兼容
          log.warn("presign/finalize 失败, fallback multipart", { error: String(error) });
          await upload(files);
        }
        router.push("/output");
      } catch (error) {
        const message =
          error instanceof ApiError || error instanceof NetworkError
            ? error.message
            : String(error);
        setErr(message);
      }
    });
  };

  const fileList =
    files.length > ZERO ? (
      <div className="mt-6">
        <h3 className="eyebrow mb-2 text-muted-foreground">
          {translation("已选 {count}", { count: files.length })}
        </h3>
        <ul className="space-y-2">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between rounded-lg border border-border/60 bg-card px-4 py-2"
            >
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{file.name}</span>
                <span className="text-sm text-muted-foreground">{fmtSize(file.size)}</span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() =>
                  setFiles((cur) => cur.filter((_unused, innerIdx) => innerIdx !== idx))
                }
                className="text-muted-foreground hover:text-destructive"
              >
                ×
              </Button>
            </li>
          ))}
        </ul>
      </div>
    ) : null;

  const buttonLabel = isPending ? translation("上传中…") : translation("开始转换 →");

  return (
    <div className="h-full overflow-y-auto">
      <PageHero
        className="mb-6"
        eyebrow="Output"
        title={translation("新建转换")}
        backHref="/output"
        backLabel={translation("返回 Output")}
      />

      <FileDropzone
        multiple
        accept={ACCEPT}
        onFiles={(picked: File[]) => setFiles((cur) => [...cur, ...picked])}
        title={translation("拖文件到这里")}
        description={translation("支持: PDF, 图片, Office, HTML, CAD (dxf/dwg), 压缩包 (zip)")}
      />

      {fileList}

      {err && <ErrorBanner variant="destructive" description={err} />}

      <div className="mt-6 flex justify-end">
        <Button
          onClick={submit}
          disabled={!files.length || isPending}
          className="bg-clay px-6 text-primary-foreground hover:bg-clay/90"
        >
          {buttonLabel}
        </Button>
      </div>
    </div>
  );
};

/**
 * NewUpload - 新建转换页面
 * @client-bff
 */
const NewUpload = () => (
  <GuardClient pageKey="output">
    <NewUploadInner />
  </GuardClient>
);

/** @client-bff */
export default NewUpload;
