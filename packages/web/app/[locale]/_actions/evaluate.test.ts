import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock server-only: evaluate.ts 间接 import auth.server.ts 它顶部 import "server-only"
vi.mock("server-only", () => ({}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "test-tok" } : undefined),
  })),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

import { createRun, deleteRun } from "./evaluate";

beforeEach(() => {
  globalThis.fetch = vi.fn(async () =>
    Response.json(
      { id: 1, status: "pending" },
      {
        headers: { "Content-Type": "application/json" },
        status: 200,
      },
    ),
  ) as never;
});

describe("createRun", () => {
  it("成功后 revalidatePath /[locale]/evaluate", async () => {
    const { revalidatePath } = await import("next/cache");
    await createRun({ name: "test" });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/evaluate");
  });

  it("请求带 content-type: application/json", async () => {
    await createRun({ name: "test" });
    const [firstCall] = vi.mocked(globalThis.fetch).mock.calls;
    const [url, init] = firstCall;
    expect(url).toContain("/api/evaluate/runs");
    expect(init?.method).toBe("POST");
    const headers = init?.headers as Record<string, string>;
    expect(headers["content-type"]).toBe("application/json");
  });

  it("透传 name 到后端 body", async () => {
    await createRun({ name: "eval-A" });
    const [firstCall] = vi.mocked(globalThis.fetch).mock.calls;
    const [, init] = firstCall;
    expect(JSON.parse(init?.body as string)).toEqual({ name: "eval-A" });
  });

  it("失败时返 ActionResult { ok: false } 不抛异常", async () => {
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const result = await createRun({ name: "test" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      // (2026-06-28) P4 4.3 refactor: actionError -> getErrorMessage 不再加 "HTTP {status}" 前缀
      expect(typeof result.error).toBe("string");
    }
  });
});

describe("deleteRun", () => {
  it("成功后 revalidatePath /[locale]/evaluate/{id}", async () => {
    const { revalidatePath } = await import("next/cache");
    await deleteRun("run-1");
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/evaluate/run-1");
  });

  it("成功后同时 revalidatePath 列表 /[locale]/evaluate", async () => {
    const { revalidatePath } = await import("next/cache");
    await deleteRun("run-1");
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/evaluate");
  });

  it("发 DELETE 请求到 /api/evaluate/runs/{id}", async () => {
    await deleteRun("run-1");
    const [firstCall] = vi.mocked(globalThis.fetch).mock.calls;
    const [url, init] = firstCall;
    expect(url).toContain("/api/evaluate/runs/run-1");
    expect(init?.method).toBe("DELETE");
  });

  it("失败时返 ActionResult { ok: false } 不抛异常", async () => {
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const result = await deleteRun("run-1");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      // (2026-06-28) P4 4.3 refactor: actionError -> getErrorMessage 不再加 "HTTP {status}" 前缀
      expect(typeof result.error).toBe("string");
    }
  });
});
