// /output server actions 测试 (Task 25, 2026-06-12)
// (2026-06-14) 不再断言 URL/header, 只测: 成功 → ok:true + revalidate, 失败 → ok:false + 不 revalidate
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "test-tok" } : undefined),
  })),
}));
vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

import { cancelTask } from "./output";
import { HTTP_INTERNAL_SERVER_ERROR } from "@/const";

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number): Response =>
  ({ ok: false, status, statusText: "Err", text: async () => "" }) as unknown as Response;

beforeEach(() => {
  globalThis.fetch = vi.fn(async () => okResponse({ ok: true })) as never;
});

describe("cancelTask", () => {
  it("成功后 ok:true + revalidatePath", async () => {
    const { revalidatePath } = await import("next/cache");
    const result = await cancelTask("task-1");
    expect(result.ok).toBe(true);
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/output/task-1");
  });

  it("失败时 ok:false + 不 revalidate", async () => {
    globalThis.fetch = vi.fn(async () => errResponse(HTTP_INTERNAL_SERVER_ERROR)) as never;
    const { revalidatePath } = await import("next/cache");
    vi.mocked(revalidatePath).mockClear();
    const result = await cancelTask("task-2");
    expect(result.ok).toBe(false);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
