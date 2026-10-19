// Ingest 业务客户端 (2026-06-10)
// 上传走 BFF (multipart), 任务查询走 BFF, 下载走 apiProxy() 拿 blob (2026-06-11 改, 见下)
// (2026-06-11) 原 taskDownloadUrl <a href download> 失败: 浏览器原生导航不带 x-user-token
//   BFF 转发给后端时缺鉴权 → 后端 _check_token 返 401, 用户拿不到 zip
//   改用 fetch+authHeaders 拿 blob, 再 URL.createObjectURL 触发下载
// (2026-06-14) 全部 fetch 改走 apiFetch()/apiProxy(); 不再裸 fetch
// (2026-06-17) Task 9: 加 uploadViaPresign, 优先 presign/finalize 走 MinIO 直传, 失败 fallback upload
import { apiFetch, apiProxy, parseErrorDetail } from "./config";
import { HEADER_CONTENT_TYPE } from "@/const";
// NetworkError / ApiError 在 taskDownload 内 dynamic import (避免循环依赖 + 跟 auth 同模式)

/**
 * Ingest 任务详情 (带输入/输出文件清单)
 * @shared
 */
export interface IngestTask {
  id: string;
  state: "queued" | "running" | "completed" | "failed";
  total_files: number;
  processed: number;
  failed: number;
  started_at: string;
  finished_at?: string;
  error?: string;
  // (2026-06-11) 用户上传的原始文件; /output 列表首列展示这个, 不是 output_files (那是转换后的产物)
  input_files?: { name: string; size: number; mime: string; uri?: string }[];
  output_files?: { name: string; size: number; mime: string; error?: string; uri?: string }[];
}

/** 上传响应 (task_id + state)
 * @shared */
export interface UploadResponse {
  task_id: string;
  state: "queued";
  total_files: number;
}

/** 下载结果 (blob + 文件名)
 * @shared */
export interface DownloadResult {
  blob: Blob;
  filename: string;
}

/** Pre-sign 上传响应 (task_id + 文件上传列表)
 * @shared */
export interface PresignUploadResponse {
  task_id: string;
  uploads: { name: string; uri: string; put_url: string | null; mime: string }[];
}

/**
 * 查单条 ingest 任务详情
 * @param id 任务 id
 * @returns task 详情
 */
export const fetchTask = (id: string): Promise<IngestTask> => apiFetch<IngestTask>(taskUrl(id));
/**
 * 列全部 ingest 任务
 * @returns task 列表
 */
export const fetchTasks = (): Promise<IngestTask[]> => apiFetch<IngestTask[]>(tasksUrl());

/** 取消 ingest 任务 — POST /api/ingest/tasks/{taskId}/cancel */
export const cancelTask = (taskId: string, headers?: Record<string, string>) =>
  apiFetch<{ ok: true }>(`/api/ingest/tasks/${encodeURIComponent(taskId)}/cancel`, {
    headers,
    method: "POST",
  });

/**
 * 下载任务产物 zip: 走 apiProxy() 拿 raw Response, 调方拿到 blob 后用 URL.createObjectURL
 * + <a download> 触发浏览器下载.
 * 不能用 <a href download>: 浏览器原生导航不带自定义头, 后端 _check_token 返 401.
 *
 * 走 apiProxy() 而非 apiFetch(): 返 Blob/stream (非 JSON). apiProxy 不读 body, 不归一错误,
 * 4xx 仍返 Response, 调方自己处理.
 */
// oxlint-disable-next-line max-statements -- 函数较长但逻辑完整
export const taskDownload = async (id: string): Promise<DownloadResult> => {
  const { ApiError, getErrorMessage, NetworkError } = await import("./errors");
  // oxlint-disable-next-line init-declarations -- try 块赋值后使用
  let res: Response;
  try {
    res = await apiProxy(taskDownloadUrl(id));
  } catch (error) {
    throw new NetworkError(getErrorMessage(error));
  }
  if (!res.ok) {
    // (2026-06-28 P3) 用公共 parseErrorDetail 替原 17 行 inline
    const detail = await parseErrorDetail(res);
    throw new ApiError(res.status, detail);
  }
  const blob = await res.blob();
  const filename = parseFilename(res.headers.get("content-disposition"), id);
  return { blob, filename };
};

/**
 * 拼任务下载 URL
 * @param id 任务 id
 * @returns 下载端点路径
 */
export const taskDownloadUrl = (id: string): string =>
  `/api/ingest/tasks/${encodeURIComponent(id)}/download`;
/**
 * 拼任务产物文件 URL
 * @param taskId 任务 id
 * @param name 文件名
 * @returns 文件端点路径
 */
export const taskFileUrl = (taskId: string, name: string): string =>
  `/api/ingest/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(name)}`;
/**
 * 拼单条任务 URL
 * @param id 任务 id
 * @returns 任务端点路径
 */
export const taskUrl = (id: string): string => `/api/ingest/tasks/${encodeURIComponent(id)}`;
/** 拼任务列表 URL */
export const tasksUrl = (): string => "/api/ingest/tasks";

/**
 * 拉取任务产物的元信息 (name/url/size/mime) — GET /api/ingest/tasks/{id}/files/{name}.
 * 文件预览页 (output/[task_id]/[file]/page.tsx) 拿 url 后二次 fetch 拉文本;
 * size>2MB 或 binary mime → 提示用 <a href> 下载. 鉴权由调用方注入 headers (RSC/server action).
 */
export interface FileMeta {
  name: string;
  url: string;
  size: number;
  mime: string;
}
/**
 * 拉取任务产物的元信息 (name/url/size/mime) — GET /api/ingest/tasks/{id}/files/{name}
 * @param taskId 任务 id
 * @param fileName 文件名
 * @param headers 可选鉴权头
 * @returns 文件元信息
 */
export const fetchFileMeta = (taskId: string, fileName: string, headers?: Record<string, string>) =>
  apiFetch<FileMeta>(taskFileUrl(taskId, fileName), { headers });

/** 上传多个文件, multipart 走 BFF (fallback 路径, presign 失败时用) */
export const upload = (files: File[]): Promise<UploadResponse> => {
  const fd = new FormData();
  for (const file of files) {
    fd.append("files", file);
  }
  return apiFetch<UploadResponse>("/api/ingest/upload", { body: fd, method: "POST" });
};

/** (2026-06-17) Task 9: presign + 客户端 PUT MinIO + finalize. 失败抛错让 caller fallback. */
export const uploadViaPresign = async (files: File[]): Promise<UploadResponse> => {
  // 1. presign: 拿 task_id + 每个文件的 PUT URL
  const presign = await apiFetch<PresignUploadResponse>("/api/ingest/upload/presign", {
    body: {
      files: files.map((file) => ({ mime: file.type, name: file.name, size: file.size })),
    },
    method: "POST",
  });
  // 2. 顺序 PUT 到 MinIO (并发会触发 S3 限流, 串行安全)
  for (let idx = 0; idx < files.length; idx++) {
    const file = files[idx];
    const up = presign.uploads[idx];
    if (!up.put_url) {
      throw new Error(`presign 未返 PUT URL for ${up.name}`);
    }
    const putResp = await fetch(up.put_url, {
      body: file,
      headers: { [HEADER_CONTENT_TYPE]: up.mime },
      method: "PUT",
    });
    if (!putResp.ok) {
      throw new Error(`PUT MinIO 失败: ${putResp.status}`);
    }
  }
  // 3. finalize: 启动后台任务
  return apiFetch<UploadResponse>("/api/ingest/upload/finalize", {
    body: { task_id: presign.task_id },
    method: "POST",
  });
};

/**
 * 从 Content-Disposition 抽 filename; 解析失败 fallback `<id>.zip`.
 * 支持格式: `attachment; filename="xxx.zip"` / `filename=xxx.zip` / `filename*=UTF-8''xxx.zip`
 */
const parseFilename = (contentDisposition: string | null, fallbackId: string): string => {
  const fallback = `${fallbackId}.zip`;
  if (!contentDisposition) {
    return fallback;
  }
  // RFC 5987: filename*=UTF-8''<percent-encoded>
  const rfcMatch = contentDisposition.match(/filename\*\s*=\s*[^']*''(?<filename>[^;]+)/i);
  if (rfcMatch?.groups?.filename) {
    try {
      return decodeURIComponent(rfcMatch.groups.filename.trim().replace(/^"|"$/g, ""));
    } catch {
      return fallback;
    }
  }
  // 普通 filename="xxx" 或 filename=xxx
  const plainMatch = contentDisposition.match(
    /filename\s*=\s*(?<quote>"?)(?<filename>[^";]+)\k<quote>/i,
  );
  return plainMatch?.groups?.filename?.trim() || fallback;
};
