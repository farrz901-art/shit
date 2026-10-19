// 智能体聊天 BFF 客户端 (2026-06-10 从 lib/api.ts 移过来)
// (2026-06-14) 改走 apiProxy(): 返 raw Response (流式), 不读 body
// (2026-06-16) 加 uploadFile: 文件上传 (BFF 透传 Dify Files API)
import { apiFetch, apiProxy } from "./config";
import { log } from "@/lib/log";
import { HEADER_CONTENT_TYPE, HEADER_X_CHAT_TOKEN, MIME_JSON } from "@/const";

const EMPTY_URI = "";

// 内部 token 获取函数, 不再通过 this 引用
const getChatToken = (): string => process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";

/**
 * 聊天发送消息输入
 */
export interface SendMessageInput {
  query: string;
  user: string;
  inputs?: Record<string, unknown>;
  conversationId?: string;
  // (2026-06-16) Composer 拆后支持携带附件 (image/document/audio → Dify Files API uploadFileId)
  files?: {
    type: "image" | "document" | "audio" | "video" | "custom";
    transferMethod: "remote_url" | "local_file";
    url?: string;
    uploadFileId?: string;
  }[];
}

/**
 * 发送聊天消息 (流式)
 * @param body  消息请求体 (query, user, conversationId, files)
 * @returns     可读流 (Uint8Array)
 *
 * @server-only
 */
// 流式响应: apiProxy 不读 body, 返 raw Response 供调用方 getReader
export const sendMessage = async (body: SendMessageInput): Promise<ReadableStream<Uint8Array>> => {
  const res = await apiProxy("/api/chat/messages", {
    body: body as unknown as Record<string, unknown>, // 同源 BFF, server 端会处理; 这里通过类型转换
    headers: {
      [HEADER_CONTENT_TYPE]: MIME_JSON,
      [HEADER_X_CHAT_TOKEN]: getChatToken(),
    },
    method: "POST",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`chat api ${res.status}: ${text}`);
  }
  if (!res.body) {
    throw new Error("chat api 无 body");
  }
  return res.body;
};

/**
 * 通过 multipart 上传文件 (后备路径)
 * @param file  要上传的文件
 * @returns     上传文件 ID + URI
 *
 * @client-bff
 */
// (2026-06-16) 文件上传: BFF 透传 Dify /files/upload, 返 {uploadFileId}
// (2026-06-17) Task 9: 后端 schema UploadFileResponse 加了 uri 字段 (默认空串)
// 用 apiFetch 而不是 apiProxy: 上传完了想直接拿 JSON (uploadFileId), 不需要 raw Response
export const uploadFile = async (file: File): Promise<{ uploadFileId: string; uri: string }> => {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/api/chat/files", { body: formData, method: "POST" });
};

/**
 * 通过 presign URL 上传文件 (MinIO 直传)
 * @param file  要上传的文件
 * @returns     上传文件 ID + URI
 *
 * @client-bff
 */
// (2026-06-29) presign/finalize 流程: 拿 PUT URL → PUT MinIO 直传 → finalize
// 失败 fallback 到 uploadFile (multipart 路径), log.warn 记录
// 返 {uploadFileId, uri} 跟旧 multipart 路径 shape 对齐
export const uploadFileViaPresign = async (
  file: File,
): Promise<{ uploadFileId: string; uri: string }> => {
  const { uri, put_url, mime } = await apiFetch<{
    uri: string;
    put_url: string | null;
    mime: string;
  }>("/api/chat/files/presign", {
    body: { mime: file.type, name: file.name, size: file.size },
    method: "POST",
  });
  if (!put_url) {
    throw new Error("presign 未返 PUT URL, 需要 fallback");
  }
  const putResp = await fetch(put_url, {
    body: file,
    headers: { "Content-Type": mime },
    method: "PUT",
  });
  if (!putResp.ok) {
    throw new Error(`PUT MinIO 失败: ${putResp.status}`);
  }
  const data = await apiFetch<{ uploadFileId: string; uri: string }>("/api/chat/files/finalize", {
    body: { mime, name: file.name, uri },
    method: "POST",
  });
  return { uploadFileId: data.uploadFileId, uri: data.uri };
};

/**
 * 上传文件 (自动选择 presign 或 multipart)
 * @param file  要上传的文件
 * @returns     上传文件 ID + URI
 *
 * @shared
 */
// (2026-06-29) doUpload: 优先 presign/finalize 走 MinIO 直传, 失败 fallback 到 multipart uploadFile
// 静默 fallback, log.warn 记录 (跟 ingest 上传 fallback 模式一致)
export const doUpload = async (file: File): Promise<{ uploadFileId: string; uri: string }> => {
  try {
    return await uploadFileViaPresign(file);
  } catch (error) {
    log.warn("presign/finalize 失败, fallback multipart", { error: String(error) });
    const out = await uploadFile(file);
    return { uploadFileId: out.uploadFileId, uri: out.uri ?? EMPTY_URI };
  }
};
