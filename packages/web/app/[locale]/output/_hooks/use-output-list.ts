"use client";
// /output 任务列表 useOutputList hook (Task 24, 2026-06-12 redesign)
// 职责: 列表数据获取 + 5s 轮询 + 下载状态管理 + 错误提取

import {
  ApiError,
  type IngestTask,
  NetworkError,
  fetchTasks,
  qKeys,
  taskDownload,
} from "@/lib/api";
import { triggerBrowserDownload } from "@/lib/dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

/** 轮询间隔 (ms) */
const POLL_INTERVAL_MS = 5000;

/** 翻译函数类型 */
export type TranslateFn = ReturnType<typeof useTranslations>;

/** 从 useQuery 的 error 中提取可读信息, 无错误时返回 null */
export const extractQueryError = (error: unknown): string | null => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  return null;
};

/** 格式化下载失败的错误信息 */
export const formatDownloadError = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  return String(error);
};

/** 下载状态上下文 */
interface DownloadCtx {
  downloading: Set<string>;
  setDownloading: (prev: Set<string> | ((prev: Set<string>) => Set<string>)) => void;
  setDownloadError: (msg: string | null) => void;
}

/**
 * handleDownload - 下载按钮处理: blob → 浏览器保存
 * @param taskId - 任务 ID
 * @param downloadCtx - 下载上下文
 * @param translate - 翻译函数
 */
const handleDownload = async (taskId: string, downloadCtx: DownloadCtx, translate: TranslateFn) => {
  if (downloadCtx.downloading.has(taskId)) {
    return;
  }
  downloadCtx.setDownloading((prev) => new Set(prev).add(taskId));
  try {
    const { blob, filename } = await taskDownload(taskId);
    triggerBrowserDownload(blob, filename);
    downloadCtx.setDownloadError(null);
  } catch (error) {
    downloadCtx.setDownloadError(translate("下载失败: {msg}", { msg: formatDownloadError(error) }));
  } finally {
    downloadCtx.setDownloading((prev) => {
      const next = new Set(prev);
      next.delete(taskId);
      return next;
    });
  }
};

/**
 * UseOutputListReturn - useOutputList hook 返回值
 * @property downloadError - 下载错误信息
 * @property downloading - 下载中的任务 ID 集合
 * @property isLoading - 是否加载中
 * @property list - 任务列表
 * @property onDownload - 下载回调
 * @property queryError - 查询错误信息
 * @property setDownloadError - 设置下载错误
 * @property translate - 翻译函数
 */
export interface UseOutputListReturn {
  downloadError: string | null;
  downloading: Set<string>;
  isLoading: boolean;
  list: IngestTask[];
  onDownload: (taskId: string) => void;
  queryError: string | null;
  setDownloadError: (msg: string | null) => void;
  translate: TranslateFn;
}

/**
 * useOutputList - /output 任务列表数据 hook
 * @returns UseOutputListReturn
 * @client-bff
 */
export const useOutputList = (): UseOutputListReturn => {
  const translate = useTranslations();
  // 5s 轮询: B 档 (Task 23 改造, layout 包 QueryClientProvider) 下,
  // 跟 RSC 端用同一 qKeys.output.list() key, RSC 预取后客户端首屏不重拉.
  const {
    data,
    isLoading,
    error: rawError,
  } = useQuery<IngestTask[]>({
    queryFn: () => fetchTasks(),
    queryKey: qKeys.output.list(),
    refetchInterval: POLL_INTERVAL_MS,
  });
  const [downloading, setDownloading] = useState<Set<string>>(new Set());

  const list = data ?? [];
  const queryError = extractQueryError(rawError);

  // 下载按钮 onClick: 走 taskDownload (带 x-user-token) → blob → 浏览器保存
  // (2026-06-14) shadcn: globalThis.alert → ErrorBanner (页内反馈, 持续可见, 跟 spec 一致)
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const downloadCtx = { downloading, setDownloadError, setDownloading };
  const onDownload = (taskId: string) => handleDownload(taskId, downloadCtx, translate);

  return {
    downloadError,
    downloading,
    isLoading,
    list,
    onDownload,
    queryError,
    setDownloadError,
    translate,
  };
};
