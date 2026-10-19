/** 登录后清 IDB + 备份下载测试 (2026-06-19 chat spec, vitest + fake-indexeddb) */

import "fake-indexeddb/auto";
import { type LocalConversation, type LocalMessage, clearLocalChat, db } from "./db";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

// Mock sonner toast (spec §7 复用 shadcn/ui sonner)
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    error: vi.fn(),
    success: vi.fn(),
  }),
}));

import { toast } from "sonner";
import { HUNDRED } from "@/const";

const SAMPLE_CONV: LocalConversation = {
  createdAt: 1_700_000_000_000,
  id: "c1",
  messageCount: 0,
  owner: "anon",
  title: "test",
  updatedAt: 1_700_000_000_000,
};

const SAMPLE_MSG: LocalMessage = {
  content: "hello",
  conversationId: "c1",
  createdAt: 1_700_000_000_000,
  id: "m1",
  owner: "anon",
  role: "user",
};

// (2026-06-23) hook 自身在 useTranslations 顶层调用, renderHook 需要 IntlProvider 包装.
const renderHookInI18n = <TResult,>(callback: () => TResult) =>
  renderHook(callback, {
    wrapper: ({ children }) => (
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {children}
      </NextIntlClientProvider>
    ),
  });

beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
  vi.mocked(toast).mockClear();
  vi.mocked(toast.success).mockClear();
  vi.mocked(toast.error).mockClear();
  // (2026-06-23) 防抖: 清掉上次测试留下的时间戳, 避免 hook 直接被 5s 防抖拦掉.
  if (typeof globalThis !== "undefined" && globalThis.localStorage) {
    globalThis.localStorage.removeItem("rag.chat.migration.last-fired.v1");
  }
});

describe("clearLocalChat", () => {
  it("只清 anon 数据, 保留 imported", async () => {
    // 跟 db.test.ts 同款: 直用 bulkPut 保留 owner 字段 (saveConversations 会强转 anon, 不能用)
    await db.conversations.bulkPut([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    await db.messages.bulkPut([SAMPLE_MSG, { ...SAMPLE_MSG, conversationId: "c2", id: "m2" }]);

    await clearLocalChat();

    const remaining = await db.conversations.toArray();
    expect(remaining.map((conv) => conv.id)).toEqual(["c2"]);
    const remainingMsgs = await db.messages.toArray();
    expect(remainingMsgs.map((msg) => msg.conversationId)).toEqual(["c2"]);
  });
});

describe("useAnonToLoginMigration", () => {
  it("isAccount=false 不触发", async () => {
    const { useAnonToLoginMigration } = await import("./migration");
    renderHookInI18n(() => useAnonToLoginMigration(false));
    // 等 100ms 让 useEffect 跑完
    await new Promise((resolve) => setTimeout(resolve, HUNDRED));
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    expect(vi.mocked(toast.success)).not.toHaveBeenCalled();
  });

  it("isAccount=true + IDB 空 不弹 toast", async () => {
    const { useAnonToLoginMigration } = await import("./migration");
    renderHookInI18n(() => useAnonToLoginMigration(true));
    await new Promise((resolve) => setTimeout(resolve, HUNDRED));
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    expect(vi.mocked(toast.success)).not.toHaveBeenCalled();
  });
});

describe("performAnonToLoginMigration", () => {
  beforeEach(async () => {
    await db.conversations.clear();
    await db.messages.clear();
  });

  it("无 anon 数据时直接返回, 不弹 toast", async () => {
    const { performAnonToLoginMigration } = await import("./migration");
    await performAnonToLoginMigration(vi.fn() as any);
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });

  it("有 anon 数据时弹 toast", async () => {
    await db.conversations.bulkPut([{ ...SAMPLE_CONV, owner: "anon" }]);
    const { performAnonToLoginMigration } = await import("./migration");
    (toast as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      (_msg: string, opts?: any) => {
        opts?.cancel?.onClick?.();
        return "";
      },
    );
    await performAnonToLoginMigration((key: string) => key);
    expect(vi.mocked(toast)).toHaveBeenCalled();
  });
});

describe("downloadLocalBackup", () => {
  beforeEach(async () => {
    await db.conversations.clear();
    await db.messages.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("导出 anon 数据为 JSON 文件", async () => {
    await Promise.all([
      db.conversations.bulkPut([{ ...SAMPLE_CONV, owner: "anon" }]),
      db.messages.bulkPut([SAMPLE_MSG]),
    ]);

    const clickFn = vi.fn();
    const createElementFn = vi.fn().mockReturnValue({
      click: clickFn,
      href: "",
      download: "",
      style: {},
    });
    const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:url");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.stubGlobal("document", {
      createElement: createElementFn,
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    });

    const { downloadLocalBackup } = await import("./migration");
    await downloadLocalBackup();
    expect(createObjectURLSpy).toHaveBeenCalled();
    expect(clickFn).toHaveBeenCalled();
  });
});
