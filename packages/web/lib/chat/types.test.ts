import type { ChatEvent, ChatProvider, Citation, SendMessageRequest } from "./types";
import { describe, expect, it } from "vitest";
import { SIX } from "@/const/index";

describe("ChatEvent 类型守卫", () => {
  it("6 种 ChatEvent 都能构造", () => {
    const events: ChatEvent[] = [
      { delta: "x", type: "message" },
      { citations: [], conversationId: "c1", type: "message_end" },
      { node: "n1", status: "started", type: "thinking" },
      { status: "succeeded", type: "workflow_done" },
      { code: "c", message: "m", type: "error" },
      { type: "done" },
    ];
    expect(events).toHaveLength(SIX);
    const [firstEvent] = events;
    expect(firstEvent.type).toBe("message");
    if (firstEvent.type === "message") {
      expect(typeof firstEvent.delta).toBe("string");
    }
  });

  it("Citation summary 接受 null", () => {
    const citation: Citation = {
      content: "x",
      documentName: "d",
      score: 0.8,
      summary: null,
    };
    expect(citation.summary).toBeNull();
  });
});

describe("ChatProvider 接口形状", () => {
  it("name 必为 readonly string", () => {
    const provider: ChatProvider = {
      name: "mock",
      async *sendMessage(_req: SendMessageRequest, _signal: AbortSignal): AsyncIterable<ChatEvent> {
        yield { type: "done" };
      },
    };
    expect(provider.name).toBe("mock");
  });
});
