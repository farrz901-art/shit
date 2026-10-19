"use client";
// Locale layout 错误边界 — 捕获 RSC / 子组件 throw, 局部 reset 不丢整页
// (2026-06-14) React 19 error boundary: app/[locale]/error.tsx
import { Button } from "@/components/ui/button";
import { log } from "@/lib/log";
import { useEffect } from "react";

/** LocaleError - 语言布局错误边界组件
 * @param error - 错误对象
 * @param reset - 重置函数
 * @returns 错误提示 JSX
 * @client-bff
 */
export default function LocaleError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    // 上报到控制台 (生产可接 Sentry)
    log.error("[LocaleError]", { message: error.message, stack: error.stack });
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="display text-3xl tracking-tight">出错了</h1>
      <p className="max-w-md text-base text-muted-foreground">
        {error.message || "页面加载或渲染时遇到错误"}
      </p>
      <Button
        onClick={reset}
        className="mt-2 rounded-lg bg-ink px-5 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-ink/90"
      >
        重试
      </Button>
    </div>
  );
}
