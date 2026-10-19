// 智能体聊天 类型契约 (2026-06-09)
// 字段名跟 Dify Chatflow API 1:1 对齐: https://docs.dify.ai/api-reference/对话流/发送对话消息
// 流用 AsyncIterable<ChatEvent> 而非 ReadableStream: 跟 Deno/Node SDK 兼容, 未来切 LlamaIndex 零改上层

/** 发送消息请求体, 跟 Dify Chatflow API 对齐.
 * @shared */
export interface SendMessageRequest {
  query: string;
  inputs: Record<string, unknown>;
  user: string;
  conversationId?: string;
  files?: ChatFile[];
  autoGenerateName?: boolean;
  workflowId?: string;
}

/** 聊天附件 (图片/文档/音频/视频/自定义), 跟 Dify file 结构对齐.
 * @shared */
export interface ChatFile {
  type: "image" | "document" | "audio" | "video" | "custom";
  transferMethod: "remote_url" | "local_file";
  url?: string;
  uploadFileId?: string;
}

/** 流式事件联合类型, 5 段: message / message_end / thinking / workflow_done / error / done.
 * @shared */
export type ChatEvent =
  | { type: "message"; delta: string }
  | { type: "message_end"; conversationId: string; citations?: Citation[] }
  | { type: "thinking"; node: string; status: "started" | "finished"; detail?: string }
  | { type: "workflow_done"; status: "succeeded" | "failed" | "partial-succeeded" | "stopped" }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

/** 引用来源, 含文档名/内容/评分.
 * @shared */
export interface Citation {
  documentName: string;
  datasetName?: string;
  position?: number;
  score?: number;
  content: string;
  summary?: string | null;
}

/** ChatProvider 接口: 发送消息并返回事件流.
 * @shared */
export interface ChatProvider {
  readonly name: string;
  sendMessage: (req: SendMessageRequest, signal: AbortSignal) => AsyncIterable<ChatEvent>;
}

/** 单条消息 (IDB 存储用 flat 结构).
 * @shared */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  conversationId?: string; // (2026-06-19) Dexie IndexedDB 关联字段, 可选
  citations?: Citation[];
  thinking?: { node: string; status: "started" | "finished"; detail?: string }[];
  interrupted?: boolean;
}

/** 对话会话, 含标题/时间/消息数.
 * @shared */
export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  difyConversationId?: string;
}
