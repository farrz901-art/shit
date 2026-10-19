/**
 * ChatProvider 工厂 (2026-06-16) — 根据 env CHAT_PROVIDER 选 dify/openai 实例
 * dify 自动套 withMemoryHooks 装饰器 (长期记忆); openai v1 暂不套
 * 调用方: 业务单点 (server side) `import { getChatProvider } from "@/lib/chat/factory"`
 */
import "server-only";

import type { ChatProvider } from "./types";

import { DifyChatProvider } from "./dify";
import { OpenAIChatProvider } from "./openai";
import { withMemoryHooks } from "./memory-integration";

// (2026-06-16) 把 require() 动态加载改成静态 import, 让 vitest ESM 能测 name 后缀.
//              顺便在 dify case 上套 withMemoryHooks 装饰器, 任何 ChatProvider 套了它
//              就自动获得长期记忆能力; 换 provider 不用动记忆层.

/** 根据 env CHAT_PROVIDER 选 dify/openai 实例, dify 带 withMemoryHooks 装饰器.
 * @returns ChatProvider 实例
 * @server-only */
export const getChatProvider = (): ChatProvider => {
  const name = process.env.CHAT_PROVIDER;
  if (!name) {
    throw new Error(
      "CHAT_PROVIDER 未设置; 在 .env 里加 CHAT_PROVIDER=dify 或 CHAT_PROVIDER=openai",
    );
  }
  switch (name) {
    case "dify": {
      // Dify 套记忆装饰器 (核心对话场景, 长期记忆价值高)
      return withMemoryHooks(new DifyChatProvider());
    }
    case "openai": {
      // Openai 暂不套 (2026-06-16 v1 范围只覆盖 dify)
      return new OpenAIChatProvider();
    }
    case "llamaindex": {
      throw new Error("llamaindex provider 未实现");
    }
    default: {
      throw new Error(`unknown provider: ${name}`);
    }
  }
};
