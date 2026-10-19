/** stream-handler unit tests (2026-07-01 Phase 2 重构)
 *  只覆盖: persistAssistantToServer / persistUserToServer
 *  applyEvent / processStream / handleStreamError 已在 Phase 2 删除, 由 useChat 接管.
 */
import { describe, expect, it, vi } from "vitest";

import { ONE } from "@/const";

const { persistAssistantToServer, persistUserToServer } = await import("./stream-handler");

describe("persistAssistantToServer", () => {
  it("登录态 + finish_reason=stop → 调 mutate, 带 meta 完整字段", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      citations: [{ documentName: "d", content: "cite" }],
      content: "answer",
      convId: "c1",
      finishReason: "stop",
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledTimes(ONE);
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "answer",
      meta: {
        citations: [{ documentName: "d", content: "cite" }],
        error_code: undefined,
        finish_reason: "stop",
      },
    });
  });

  it("abort 路径 finish_reason=interrupted → 写 partial content", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      content: "partial",
      convId: "c1",
      finishReason: "interrupted",
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "partial",
      meta: { citations: undefined, error_code: undefined, finish_reason: "interrupted" },
    });
  });

  it("error 路径带 error_code → meta 含 code", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      content: "err part",
      convId: "c1",
      errorCode: "upstream_error",
      finishReason: "error",
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "err part",
      meta: { citations: undefined, error_code: "upstream_error", finish_reason: "error" },
    });
  });

  it("anon 用户 → 不调 mutate (走 IDB 老路径)", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      content: "x",
      convId: "c1",
      finishReason: "stop",
      isAccount: false,
      mutate,
    });
    expect(mutate).not.toHaveBeenCalled();
  });
});

describe("persistUserToServer", () => {
  it("登录态 → mutate role=user", () => {
    const mutate = vi.fn();
    persistUserToServer({ content: "hi", convId: "c1", isAccount: true, mutate });
    expect(mutate).toHaveBeenCalledWith({ convId: "c1", role: "user", content: "hi" });
  });

  it("anon → 不调 mutate", () => {
    const mutate = vi.fn();
    persistUserToServer({ content: "hi", convId: "c1", isAccount: false, mutate });
    expect(mutate).not.toHaveBeenCalled();
  });
});
