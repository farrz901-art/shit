// 集中定义所有 queryKey, RSC 预取和 RQ 客户端必须用同一 key.
// 每次调用 factory 函数返回**新数组** (避免误共享引用, RQ 内部 hash 相同不影响).

/**
 * React Query key 工厂 — 所有 queryKey 集中定义
 * RSC 预取和 RQ 客户端必须用同一 key 避免缓存未命中
 *
 * @shared
 */
export const qKeys = {
  all: ["rag"] as const,
  batch: {
    all: ["rag", "batch"] as const,
    status: (id: string) => [...qKeys.batch.all, "status", id] as const,
  },
  health: {
    all: ["rag", "health"] as const,
    system: () => [...qKeys.health.all, "system"] as const,
  },
  output: {
    all: ["rag", "output"] as const,
    detail: (id: string) => [...qKeys.output.all, "detail", id] as const,
    list: () => [...qKeys.output.all, "list"] as const,
  },
} as const;
