import { HTTP_NOT_FOUND, HTTP_OK } from "@/const/index";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "./middleware";

const req = (path: string): NextRequest => new NextRequest(new Request(`http://localhost${path}`));

describe("middleware", () => {
  const ORIGINAL = process.env.CHAT_PUBLIC_MODE;

  beforeEach(() => {
    process.env.CHAT_PUBLIC_MODE = "true";
  });
  afterEach(() => {
    if (ORIGINAL === undefined) {
      delete process.env.CHAT_PUBLIC_MODE;
    } else {
      process.env.CHAT_PUBLIC_MODE = ORIGINAL;
    }
  });

  it("公网模式 + /chat 放行", async () => {
    const res = await middleware(req("/chat"));
    expect(res?.status).not.toBe(HTTP_NOT_FOUND);
  });

  it("公网模式 + /api/chat 放行", async () => {
    const res = await middleware(req("/api/chat/messages"));
    expect(res?.status).not.toBe(HTTP_NOT_FOUND);
  });

  it("公网模式 + / 返回 HTTP_NOT_FOUND", async () => {
    const res = await middleware(req("/"));
    expect(res?.status).toBe(HTTP_NOT_FOUND);
  });

  it("公网模式 + /knowledge 返 HTTP_NOT_FOUND", async () => {
    const res = await middleware(req("/knowledge"));
    expect(res?.status).toBe(HTTP_NOT_FOUND);
  });

  it("公网模式 + /api/knowledge 返 HTTP_NOT_FOUND", async () => {
    const res = await middleware(req("/api/knowledge/stats"));
    expect(res?.status).toBe(HTTP_NOT_FOUND);
  });
});

describe("middleware (内网模式)", () => {
  beforeEach(() => {
    process.env.CHAT_PUBLIC_MODE = "false";
  });

  it("内网模式 + 任何路径都放行", async () => {
    const res = await middleware(req("/anything"));
    expect(res === undefined || res.status === HTTP_OK).toBe(true);
  });
});
