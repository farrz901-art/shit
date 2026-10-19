/**
 * 系统层业务 HTTP client (P1-5, 2026-06-29 补 JSDoc + DEFAULT_TIMEOUT_MS 注释)
 *
 * 监控检查 + 型号解码 + 输出文件
 * (2026-06-14) 改走 apiFetch(), 10s AbortController 超时透传 init.signal
 *
 * ============================================================
 * 调用边界 (calling-boundary, 2026-06-19 audit)
 * ============================================================
 *   - decode: @server-only (Dify 同步等待, server action 用)
 *   - health / listSeries: @shared (浏览器 / server 都查健康, 短超时)
 *   - listOutputFiles / readOutputFile: @server-only (admin 操作)
 */
import { apiFetch } from "./config";

// 健康检查 / 列表端点用 10s 超时, 足够查 Dify / Neo4j 状态; 短超时避免浏览器 long-poll 卡死
const DEFAULT_TIMEOUT_MS = 10_000;

/** Dify 型号解码 — sync 调用, 返完整型号信息
 * @param model 型号名称
 * @returns 完整型号信息
 * @server-only */
export const decode = (model: string) =>
  apiFetch<Record<string, unknown>>("/decode", {
    body: { model },
    method: "POST",
  });

/** 系统健康检查 — 10s 超时, 浏览器 / server 都可调
 * @returns 健康检查结果
 * @shared */
export const health = () =>
  apiFetch<{ status: string; series_count: number }>("/health", {
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  });

/** 列出输出文件 (admin)
 * @returns 文件列表
 * @server-only */
export const listOutputFiles = () =>
  apiFetch<{ files: { name: string; size: number; mtime: number }[] }>("/api/output/files");

/** 列出已解码型号系列 (10s 超时)
 * @returns 型号系列列表
 * @shared */
export const listSeries = () =>
  apiFetch<{ series: string; manufacturer: string; name: string; prefix: string }[]>("/series", {
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  });

/** 读取输出文件内容 (admin)
 * @param name 文件名
 * @returns 文件内容
 * @server-only */
export const readOutputFile = (name: string) =>
  apiFetch<{ name: string; content: string; mime: string }>(
    `/api/output/files/${encodeURIComponent(name)}`,
  );
