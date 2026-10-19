"use client";

// 登录后清 IDB + toast 提示 (2026-06-19 chat spec §7)
//
// 设计要点:
// - ChatShell 在 isAccount=true 时挂 useAnonToLoginMigration
//   Hook 自身负责: 拿 t (闭包) → 调 performAnonToLoginMigration (弹 toast + 备份下载 + 清 IDB)
// - 老版本 hook 是空壳 (只 count IDB, 不弹 toast, 实际触发在 ChatShell useEffect),
//   2026-06-23 收紧: hook 直接驱动, 调用方不用再传 t, 减少 "hook 触发 ≠ 实际迁移" 的不一致.
// - downloadLocalBackup() 把 IDB 拼成 JSON 走 a.click() 触发浏览器下载
import { clearLocalChat, db } from "./db";
import { groupBy } from "es-toolkit";
import { nowIso, nowMs } from "@/lib/date";
import { toast } from "sonner";
import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { MIME_JSON, ZERO } from "@/const";

// Re-export 让 ChatShell / 其他模块统一从 migration.ts 取
export { clearLocalChat } from "./db";

const JSON_INDENT = 2; // JSON 格式化缩进空格数
const MIGRATION_TOAST_ID = "anon-migration";
const DEBOUNCE_KEY = "rag.chat.migration.last-fired.v1";
const DEBOUNCE_MS = 5000;

/** Next-intl 翻译函数简化签名 (避免迁移模块强依赖 next-intl 类型). */
type Translator = (key: string, vars?: Record<string, unknown>) => string;

/** 登录后检测 IDB anon 数据, 弹 toast 让用户下载备份或确认清除.
 *  Hook 直接驱动 performAnonToLoginMigration (闭包拿 t), 不再依赖 ChatShell 二次 useEffect.
 *  副作用:
 *    1. 弹 toast 让用户选下载 / 知道
 *    2. 任一操作都 clearLocalChat() (跟 5 标杆一致, anon → login 不合并)
 *    3. 防抖: 5s 内不重复弹 (Strict Mode 双调用 + 副作用触发场景)
 */
export const useAnonToLoginMigration = (isAccount: boolean): void => {
  const translate = useTranslations();
  useEffect(() => {
    if (!isAccount) {
      return;
    }
    if (typeof globalThis === "undefined" || !globalThis.localStorage) {
      return;
    }
    const last = Number(globalThis.localStorage.getItem(DEBOUNCE_KEY) ?? String(ZERO));
    if (nowMs() - last < DEBOUNCE_MS) {
      return;
    }
    globalThis.localStorage.setItem(DEBOUNCE_KEY, String(nowMs()));
    void performAnonToLoginMigration(translate as unknown as Translator);
  }, [isAccount, translate]);
};

/**
 * ChatShell mount 时调用. 弹 toast + 备份下载 + clear.
 * 跟 hook 解耦, 方便 mock test.
 * toast 用固定 id 实现单例: 多次调用只保留最后一次的 toast.
 */
export const performAnonToLoginMigration = async (translate: Translator): Promise<void> => {
  const count = await db.conversations.where("owner").equals("anon").count();
  if (!count) {
    return;
  }

  // 弹 toast 等待用户操作 (固定 id 防止堆叠)
  const result = await new Promise<"download" | "dismiss">((resolve) => {
    toast(translate("本地 {count} 段聊天将清除", { count }), {
      action: {
        label: translate("下载 JSON 备份"),
        onClick: () => resolve("download"),
      },
      cancel: {
        label: translate("知道了"),
        onClick: () => resolve("dismiss"),
      },
      description: translate("登录后历史会从服务器同步, 本地数据不再保留"),
      duration: Number.POSITIVE_INFINITY,
      id: MIGRATION_TOAST_ID,
    });
  });

  if (result === "download") {
    await downloadLocalBackup();
  }

  await clearLocalChat();
  toast.success(translate("本地聊天已清除"), { id: MIGRATION_TOAST_ID });
};

/**
 * 把 IDB 里 anon 数据导出为 JSON 文件, 触发浏览器下载.
 * 用 a.click() 模式 (兼容所有现代浏览器, 零额外依赖).
 */
export const downloadLocalBackup = async (): Promise<void> => {
  const conversations = await db.conversations.where("owner").equals("anon").toArray();
  const messages = await db.messages.where("owner").equals("anon").toArray();
  const payload = {
    conversations,
    exported_at: nowIso(),
    messages_by_conv: groupBy(messages, (msg) => msg.conversationId ?? ""),
  };
  const blob = new Blob([JSON.stringify(payload, null, JSON_INDENT)], {
    type: MIME_JSON,
  });
  const { triggerBrowserDownload } = await import("@/lib/dom");
  triggerBrowserDownload(blob, `rag-chat-backup-${nowMs()}.json`);
};
