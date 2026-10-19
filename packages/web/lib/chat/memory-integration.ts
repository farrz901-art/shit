// 长期记忆 ChatProvider 装饰器 (2026-06-16)
// 任何 ChatProvider 套上自动获得长期记忆能力; 换掉 dify 不影响记忆层.
//
// 三段:
//   1. Pre-LLM: 搜相关记忆, 拼成 inputs.memory_context (失败降级为空串)
//   2. 流中: 累积 user + assistant 完整对话 (流式 delta 拼装)
//   3. Post-LLM: fire-and-forget 写记忆 (失败仅 warning, 不阻断)
//
// (2026-06-16) 改成 server-only: 只在 BFF route (server) 里跑, 直接读 cookie
// 拿 token, 不用走 apiFetch (apiFetch 纯 transport 不注 server auth,
// 装饰器又拿不到 cookie 上下文, 自己 import auth.server 又是循环).
// 因此 memory search/add 也走 fetch + cookie 显式注 x-user-token.
import "server-only";

import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";

import { cookies } from "next/headers";
import { log } from "@/lib/log";
import { API_BASE as BACKEND_URL } from "@/lib/api/config";
import { COOKIE_USER_TOKEN, HEADER_CONTENT_TYPE, HEADER_X_USER_TOKEN, MIME_JSON } from "@/const";

// Dify chatflow 长期记忆字段
const MEMORY_CONTEXT_KEY = "memory_context";
// Dify chatflow 客户画像字段
const BUYER_PROFILE_KEY = "buyer_profile";
const MEMORY_SEARCH_LIMIT = 5;
const LAST_TURN_INDEX = 1;

interface MemoryHitRaw {
  id: string;
  text: string;
}

interface SearchResponseRaw {
  memories?: MemoryHitRaw[];
}

interface MemoryTurn {
  content: string;
  role: "user" | "assistant";
}

/** 读 cookie 拼鉴权头 (admin 优先, 跟 backend auth.py:58-67 一致). */
const readAuthHeaders = async (): Promise<Record<string, string>> => {
  const cookieJar = await cookies();
  const userToken = cookieJar.get(COOKIE_USER_TOKEN)?.value;
  const headers: Record<string, string> = {};
  if (userToken) {
    headers[HEADER_X_USER_TOKEN] = userToken;
  }
  return headers;
};

const buildMemoryContext = (memories: { text: string }[]): string => {
  const MIN_MEMORIES = 0;
  if (memories.length === MIN_MEMORIES) {
    return "";
  }
  return `用户相关记忆:\n${memories.map((memory) => `- ${memory.text}`).join("\n")}`;
};

// memory 搜索 HTTP 调用, 拆函数增加间接调用栈, 保持内聚
// (2026-07-08 lint-ignores.md §4.2 FC-02)
const searchMemory = async (query: string): Promise<string> => {
  try {
    const authHeaders = await readAuthHeaders();
    const res = await fetch(`${BACKEND_URL}/api/memory/search`, {
      body: JSON.stringify({ limit: MEMORY_SEARCH_LIMIT, query }),
      headers: { [HEADER_CONTENT_TYPE]: MIME_JSON, ...authHeaders },
      method: "POST",
    });
    log.info("[memory-integration] search response", { ok: res.ok, status: res.status });
    if (!res.ok) {
      return "";
    }
    const data = (await res.json()) as SearchResponseRaw;
    return buildMemoryContext(data.memories ?? []);
  } catch (error) {
    log.warn("[memory] search failed, fallback", { error: String(error) });
    return "";
  }
};

const addMemory = async (
  turns: MemoryTurn[],
  conversationId: string | undefined,
  buyerKey?: string,
): Promise<void> => {
  try {
    const authHeaders = await readAuthHeaders();
    const body: Record<string, unknown> = {
      conversation_id: conversationId,
      messages: turns,
    };
    if (buyerKey) {
      body.buyer_key = buyerKey;
    }
    const res = await fetch(`${BACKEND_URL}/api/memory/add`, {
      body: JSON.stringify(body),
      headers: { [HEADER_CONTENT_TYPE]: MIME_JSON, ...authHeaders },
      method: "POST",
    });
    log.info("[memory-integration] add response", { ok: res.ok, status: res.status });
  } catch (error) {
    log.warn("[memory] add failed", { error: String(error) });
  }
};

const EMPTY_ENTRIES = 0;
const JOIN_SEPARATOR = ", ";

const appendAssistantDelta = (turns: MemoryTurn[], delta: string): void => {
  const last = turns[turns.length - LAST_TURN_INDEX];
  if (last?.role === "assistant") {
    turns[turns.length - LAST_TURN_INDEX] = { content: last.content + delta, role: "assistant" };
  } else {
    turns.push({ content: delta, role: "assistant" });
  }
};

// ── 买家画像辅助函数 ──────────────────────────────────────

/** 从后端取当前登录用户的买家画像 profile_data. */
const fetchBuyerProfile = async (): Promise<Record<string, { value: unknown }> | null> => {
  try {
    const authHeaders = await readAuthHeaders();
    const res = await fetch(`${BACKEND_URL}/api/buyer-profiles/my-profile`, {
      headers: { ...authHeaders },
    });
    if (!res.ok) {
      return null;
    }
    const data = (await res.json()) as { profile_data?: Record<string, { value: unknown }> };
    return data?.profile_data ?? null;
  } catch {
    return null; // 降级: 拿不到画像不影响聊天
  }
};

/** 将 profile_data 格式化为纯文本描述. */
const formatProfile = (profile: Record<string, { value: unknown }> | null): string => {
  if (!profile || Object.keys(profile).length === EMPTY_ENTRIES) {
    return "";
  }
  const pairs = Object.entries(profile)
    .filter(([, val]) => val?.value != null && val?.value !== "")
    .map(([key, val]) => `${key}=${val.value}`);
  return pairs.length > EMPTY_ENTRIES ? `买家信息: ${pairs.join(JOIN_SEPARATOR)}` : "";
};

/** Pre-LLM: 并行搜索记忆和获取买家画像, 返回增强后的 inputs. */
const prepareInputs = async (req: SendMessageRequest): Promise<SendMessageRequest["inputs"]> => {
  const [memoryContext, profileData] = await Promise.all([
    searchMemory(req.query),
    fetchBuyerProfile(),
  ]);
  const profileText = formatProfile(profileData);
  return {
    ...req.inputs,
    [MEMORY_CONTEXT_KEY]: memoryContext,
    [BUYER_PROFILE_KEY]: profileText,
  };
};

/**
 * 套上长期记忆能力的 ChatProvider 装饰器
 * @param inner  原始 ChatProvider
 * @returns      带记忆能力的 ChatProvider
 * @server-only
 */
export const withMemoryHooks = (inner: ChatProvider): ChatProvider => ({
  name: `${inner.name}+memory`,

  async *sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    // 1. Pre-LLM: 搜记忆 + 取买家画像 (并行, 任一失败降级)
    const inputs = await prepareInputs(req);
    const enhancedReq: SendMessageRequest = { ...req, inputs };

    // 2. 流中: 累积 user + assistant 完整对话
    const turns: MemoryTurn[] = [{ content: req.query, role: "user" }];
    for await (const ev of inner.sendMessage(enhancedReq, signal)) {
      if (ev.type === "message") {
        appendAssistantDelta(turns, ev.delta);
      }
      yield ev;
    }

    // 3. Post-LLM: fire-and-forget add (失败仅 warning, 不阻断)
    const hasAssistant = turns.some((turn) => turn.role === "assistant");
    if (hasAssistant) {
      void addMemory(turns, req.conversationId, req.inputs.buyer_key as string | undefined);
    }
  },
});
