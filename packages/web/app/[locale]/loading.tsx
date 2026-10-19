// Locale layout loading 状态 — Suspense fallback, RSC 无需 "use client"
// (2026-06-14) React 19 loading.tsx: 自动包在 <Suspense> 里, 子页面异步数据加载时显示
import { Skeleton } from "@/components/ui/skeleton";

/**
 * LocaleLoading - Suspense fallback 骨架屏
 * @server-only
 */
export default function LocaleLoading() {
  return (
    <div className="space-y-6 px-6 py-10">
      {/* 模拟 page hero 区域 */}
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-12 w-96" />
      <Skeleton className="h-4 w-72" />
      {/* 模拟内容区 */}
      <div className="mt-8 space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-3/4" />
      </div>
    </div>
  );
}
