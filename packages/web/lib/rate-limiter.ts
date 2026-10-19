// 内存 IP 限流 (2026-06-24)
// 跟 SEC-007 模式同: 按 IP 统计请求, 超阈值返 429
// 注意: 多实例部署不协同, 仅轻量防护, 生产环境建议换 Redis 方案

import { nowMs } from "@/lib/date";

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const store = new Map<string, RateLimitEntry>();

/**
 * 限流检查结果
 * @property allowed    是否允许请求通过
 * @property remaining  该窗口剩余可用请求数
 */
export interface CheckResult {
  allowed: boolean;
  remaining: number;
}

// 最大条目数, 超时触发惰性清理
const MAX_STORE_SIZE = 10_000;
// 新窗口首条计数的余量 (maxRequests - 1)
const INITIAL_REMAINING_OFFSET = 1;
// 被限流时的余量
const ZERO_REMAINING = 0;
// X-Forwarded-For 取第一个 IP
const FIRST_IP_INDEX = 0;

// 惰性清理过期条目
const pruneExpired = (): void => {
  if (store.size <= MAX_STORE_SIZE) {
    return;
  }
  const now = nowMs();
  for (const [entryKey, entryval] of store) {
    if (entryval.resetAt <= now) {
      store.delete(entryKey);
    }
  }
};

/**
 * 检查并递增 IP 请求计数, 实现内存限流
 * @param key         限流 key (通常为 IP)
 * @param maxRequests 窗口内最大请求数
 * @param windowMs    窗口大小 (毫秒)
 * @returns           是否允许通过及剩余配额
 *
 * 调用边界:
 *   @server-only  RSC / Server Action / route.ts 专用
 */
export const checkAndIncrement = (
  key: string,
  maxRequests: number,
  windowMs: number,
): CheckResult => {
  const now = nowMs();

  pruneExpired();

  const entry = store.get(key);

  if (!entry || entry.resetAt <= now) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: maxRequests - INITIAL_REMAINING_OFFSET };
  }

  if (entry.count >= maxRequests) {
    return { allowed: false, remaining: ZERO_REMAINING };
  }

  entry.count += 1;
  return { allowed: true, remaining: maxRequests - entry.count };
};

// 提取客户端 IP (支持 X-Forwarded-For 和直接连接)
/**
 * 从请求头中提取客户端 IP
 * @param headers  Headers 对象
 * @returns        IP 字符串 (支持 X-Forwarded-For)
 *
 * 调用边界:
 *   @server-only  RSC / Server Action / route.ts 专用
 */
export const extractClientIp = (headers: Headers): string => {
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[FIRST_IP_INDEX].trim();
  }
  return "unknown";
};

// 测试用: 清空限流状态
/**
 * 清空限流状态 (测试用)
 *
 * 调用边界:
 *   @server-only  RSC / Server Action / route.ts 专用
 */
export const resetRateLimiter = (): void => {
  store.clear();
};
