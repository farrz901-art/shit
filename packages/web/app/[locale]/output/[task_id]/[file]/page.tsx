"use client";
// 文件预览 (2026-06-10) — md 用 markdown 渲染, 其他用 <pre>
// (2026-06-30) streamdown 迁移: ReactMarkdown → MarkdownStatic
// (2026-06-11) i18n: useTranslations + t() + LocalizedLink
// (2026-06-14) 改走 apiFetch()
// (2026-06-17) Task 9: 响应 shape 改 {name, url, size, mime} (无 content),
//   拿 url 后二次 fetch 拉文本; size>2MB 或 binary mime → 提示用 <a href> 下载
// (2026-06-17) v2 RBAC: 套 GuardClient 做 4 层防护第 2 层
import { AnimateUp, FadePresence, Reveal } from "@/components/motion/animated";
import { ApiError, NetworkError } from "@/lib/api/errors";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { Card, CardContent } from "@/components/ui/card";
import { use, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { GuardClient } from "@/components/auth/guard-client";
import { MarkdownStatic } from "@/components/markdown/markdown-static";
import { fetchFileMeta } from "@/lib/api/ingest";
import { useTranslations } from "next-intl";

/** 预览大小上限 (MB) */
const PREVIEW_SIZE_MB = 2;
const BYTES_PER_KB = 1024;
const MAX_PREVIEW_BYTES = PREVIEW_SIZE_MB * BYTES_PER_KB * BYTES_PER_KB;
const STATUS_NOT_FOUND = 404;
const MIME_MARKDOWN = "text/markdown";

/**
 * FilePreview - 文件预览页
 * @param props.params - 路由参数 (含 task_id 和 file)
 * @client-bff
 */
export default function FilePreview({
  params,
}: {
  params: Promise<{ task_id: string; file: string }>;
}) {
  return (
    <GuardClient pageKey="output">
      <FilePreviewInner params={params} />
    </GuardClient>
  );
}

/**
 * fetchFileContent - 拉取文件内容
 * @param url - 文件下载 URL
 * @returns 文件文本内容
 */
const fetchFileContent = async (url: string) => {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`拉取文件失败: ${resp.status}`);
  }
  return resp.text();
};

/**
 * getFileErrorMessage - 从 fetch 错误中提取用户可读信息
 * @param fetchError - 捕获的错误
 * @param translate - i18n 翻译函数
 * @returns 用户可读的错误信息
 */
const getFileErrorMessage = (fetchError: unknown, translate: (key: string) => string): string => {
  if (fetchError instanceof ApiError && fetchError.status === STATUS_NOT_FOUND) {
    return translate("文件不存在或已过期");
  }
  if (fetchError instanceof ApiError || fetchError instanceof NetworkError) {
    return fetchError.message;
  }
  return String(fetchError);
};

/**
 * loadFileData - 组件外异步加载逻辑 (减少 useEffect 语句数)
 * @param args - 加载参数 (含文件名、setters、taskId、翻译函数)
 */
const loadFileData = async ({
  fileName,
  setters: { setContent, setErr, setFileUrl, setMime, setTooLarge },
  taskId,
  translateFn,
}: {
  fileName: string;
  setters: {
    setContent: (val: string) => void;
    setErr: (val: string | null) => void;
    setFileUrl: (val: string) => void;
    setMime: (val: string) => void;
    setTooLarge: (val: boolean) => void;
  };
  taskId: string;
  translateFn: (key: string) => string;
}) => {
  try {
    const meta = await fetchFileMeta(taskId, fileName);
    setFileUrl(meta.url);
    setMime(meta.mime);
    if (meta.size > MAX_PREVIEW_BYTES) {
      setTooLarge(true);
      return;
    }
    const text = await fetchFileContent(meta.url);
    setContent(text);
  } catch (fetchError) {
    setErr(getFileErrorMessage(fetchError, translateFn));
  }
};

/**
 * renderFileBody - 渲染文件主体内容
 * @param state - 状态对象
 * @param translate - i18n 翻译函数
 * @returns 渲染的 JSX
 */
const renderFileBody = (
  state: {
    content: string;
    err: string | null;
    fileUrl: string;
    fileName: string;
    mime: string;
    tooLarge: boolean;
  },
  translate: (key: string) => string,
) => {
  if (state.err) {
    return <ErrorBanner variant="destructive" description={state.err} />;
  }
  if (state.tooLarge) {
    return (
      <Card className="border-border/60 p-6">
        <p className="text-base text-muted-foreground">{translate("文件过大, 请下载查看。")}</p>
        <a
          href={state.fileUrl}
          download={state.fileName}
          className="mt-3 inline-block text-clay hover:underline"
        >
          ↓ {state.fileName}
        </a>
      </Card>
    );
  }
  if (!state.content) {
    return <div className="text-base text-muted-foreground">{translate("加载中…")}</div>;
  }
  return (
    <AnimateUp show>
      <Card className="overflow-hidden border-border/60">
        <div className="flex items-center justify-between gap-3 border-b border-border/60 bg-muted/30 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="num inline-flex h-2 w-2 rounded-full bg-clay" />
            <span className="num truncate font-medium text-foreground" title={state.fileName}>
              {state.fileName}
            </span>
            <span className="eyebrow text-muted-foreground/60">{state.mime || "text"}</span>
          </div>
        </div>
        <CardContent className="p-0">
          {state.mime === MIME_MARKDOWN ? (
            <div className="p-6">
              <MarkdownStatic>{state.content}</MarkdownStatic>
            </div>
          ) : (
            <pre className="num overflow-x-auto bg-muted/30 p-6 text-sm leading-relaxed">
              {state.content}
            </pre>
          )}
        </CardContent>
      </Card>
    </AnimateUp>
  );
};

/**
 * FilePreviewInner - 文件预览内部组件
 * @param props.params - 路由参数 Promise
 */
const FilePreviewInner = ({ params }: { params: Promise<{ task_id: string; file: string }> }) => {
  const translate = useTranslations();
  const { task_id, file: fileName } = use(params);
  const [content, setContent] = useState<string>("");
  const [mime, setMime] = useState<string>("");
  const [fileUrl, setFileUrl] = useState<string>("");
  const [tooLarge, setTooLarge] = useState<boolean>(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    loadFileData({
      fileName,
      setters: { setContent, setErr, setFileUrl, setMime, setTooLarge },
      taskId: task_id,
      translateFn: translate,
    });
  }, [task_id, fileName, translate]);

  return (
    <div className="h-full overflow-y-auto">
      <Reveal className="mb-6">
        <BackLink href={`/output/${encodeURIComponent(task_id)}`} label={translate("返回任务")} />
      </Reveal>

      <FadePresence mode="wait">
        {renderFileBody({ content, err, fileName, fileUrl, mime, tooLarge }, translate)}
      </FadePresence>
    </div>
  );
};
