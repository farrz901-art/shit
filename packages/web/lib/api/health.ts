// Health 业务客户端 (Task 26/27, 2026-06-12 redesign)
// - fetchSystem: 走 BFF /api/health/system (admin-only, 后端返回 5 类检查: Python/Dify/Neo4j/pgvector/system)
// - fetchDifyHealth: 直连 FastAPI /api/kg/health (Dify 简单 ok 指示, HealthDot 用)
// (2026-06-14) 改走 apiFetch(); 401/403 抛 ApiError (status 401/403), 调用方按 status 判 need_admin
import { apiFetch } from "./config";

/**
 * 单项检查结果 (status / latency_ms / error / extra)
 * @shared
 */
export interface CheckResult {
  status: "ok" | "error";
  latency_ms: number | null;
  error: string | null;
  extra: Record<string, unknown>;
}

/**
 * 系统健康检查完整载荷 (含 6 个子检查 + 元信息)
 * @shared
 */
export interface HealthPayload {
  checked_at: string | null;
  status?: string;
  python: CheckResult;
  dify: CheckResult;
  neo4j: CheckResult;
  pgvector: CheckResult;
  minio: CheckResult;
  redis: CheckResult;
  system: CheckResult;
}

/**
 * 直连 FastAPI /api/kg/health 拿 Dify 简单 ok 指示.
 * HealthDot 用, 跟 system 端点无关 (Dify 直连, 不需要 admin token).
 */
export const fetchDifyHealth = (): Promise<{ ok: boolean }> =>
  apiFetch<{ ok: boolean }>("/api/kg/health");

/**
 * 调 BFF /api/health/system 拿 5 类检查 (admin-only, BFF 内部从 cookie 拿 admin token).
 * 401/403 抛 ApiError(status 401/403), 调用方按 status === 401 || 403 判 need_admin
 */
export const fetchSystem = (): Promise<HealthPayload> =>
  apiFetch<HealthPayload>("/api/health/system");
