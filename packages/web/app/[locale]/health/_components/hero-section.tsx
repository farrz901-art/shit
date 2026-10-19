"use client";
// HealthStatusBoard: 7/7 大数字 + pulse dot + checkedAt + uptime (2026-06-15)
// 从 health-client.tsx 拆出. 标题 + polling 按钮已迁到 PageHero (本页由 health-client.tsx 装配)
// 视觉: 大数字 ok/total + 状态字 + pulse dot + Python版本 + uptime + CHECKED 计时器
import { useState } from "react";
import { useInterval } from "react-use";
import { MS_PER_SECOND, SECONDS_PER_MINUTE, TWO, ZERO } from "@/const";
import { nowMs, toInstant } from "@/lib/date";

// === 常量 ===
/** 轮询间隔 (1s) */
const POLL_INTERVAL_MS = MS_PER_SECOND;
/** 每小时秒数 */
const SECONDS_PER_HOUR = 3600;
/** 时钟补零位数 */
const CLOCK_PAD_LENGTH = TWO;
/** 进度条默认值 */
const PROGRESS_DEFAULT = ZERO;

// === 格式化工具 ===

/** padClock - 时钟数值补零格式化
 * @param value 原始数值
 * @returns 补零后的字符串 (2 位)
 * @shared
 */
const padClock = (value: number): string => String(value).padStart(CLOCK_PAD_LENGTH, "0");

/** formatUptime - 格式化运行时长 (秒 → "Xh Ym" / "Xm" / "Xs")
 * @param seconds 秒数
 * @returns 格式化后的时长字符串
 * @shared
 */
const formatUptime = (seconds: number): string => {
  const hours = Math.floor(seconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  if (hours > ZERO) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > ZERO) {
    return `${minutes}m`;
  }
  return `${seconds}s`;
};

/** formatClock - ISO 时间戳 → HH:mm:ss 格式
 * @param iso ISO 时间字符串
 * @returns 格式化时钟字符串
 * @shared
 */
const formatClock = (iso: string): string => {
  const date = new Date(iso);
  return `${padClock(date.getHours())}:${padClock(date.getMinutes())}:${padClock(date.getSeconds())}`;
};

// === 状态色 ===

/** statusTextColor - 根据状态返回文字颜色类名
 * @param ok 是否正常
 * @returns Tailwind 颜色类名
 * @shared
 */
const statusTextColor = (ok: boolean): string => (ok ? "text-moss" : "text-destructive");
/** statusDotClass - 根据状态返回状态点样式类名
 * @param ok 是否正常
 * @returns Tailwind 状态点类名
 * @shared
 */
const statusDotClass = (ok: boolean): string =>
  ok
    ? "bg-moss shadow-moss/15 animate-pulse"
    : "bg-destructive shadow-destructive/15 animate-pulse";

// === 实时秒表 ===

/** UptimeCounter - 实时秒表组件, 每秒更新距指定时间的经过秒数
 * @shared
 */
const UptimeCounter = ({ iso }: { iso: string }) => {
  // 初始值用 PROGRESS_DEFAULT (=0) 而非 Date.now(): SSR 时 Date.now() 与客户端 hydration 时
  // 不同, 会触发 React hydration mismatch (服务器渲染 12s, 客户端 1s). mount 后 useInterval
  // 第一次 setNow(Date.now()) 把真实秒数推上去, 用户感知"先 0 → 1s 后开始跳".
  const [now, setNow] = useState<number>(PROGRESS_DEFAULT);
  useInterval(() => setNow(nowMs()), POLL_INTERVAL_MS);
  const elapsed = Math.max(
    PROGRESS_DEFAULT,
    Math.floor((now - toInstant(iso).epochMilliseconds) / MS_PER_SECOND),
  );
  // suppressHydrationWarning: 即便 initial=0 跟 SSR 也 0, 防御 React 19 警告冗余
  return (
    <span className="num tabular-nums" suppressHydrationWarning>
      {elapsed}s 前刷新
    </span>
  );
};

// === HealthStatusBoard ===

/** HealthStatusBoardProps - 健康状态面板属性 */
export interface HealthStatusBoardProps {
  okCount: number;
  totalCount: number;
  allOk: boolean;
  pyVersion: string | undefined;
  uptimeS: number | undefined;
  checkedAt: string;
}

/** HealthStatusBoard
 * @param props
 * @client-bff
 */
export const HealthStatusBoard = ({
  okCount,
  totalCount,
  allOk,
  pyVersion,
  uptimeS,
  checkedAt,
}: HealthStatusBoardProps) => (
  <div className="flex flex-col gap-6 border-b border-border/60 pb-8">
    <div className="flex items-end gap-6">
      <div className="flex items-baseline gap-2">
        <span
          className={`num text-7xl font-light tabular-nums leading-none tracking-tight ${statusTextColor(allOk)}`}
          data-testid="health-ok-count"
        >
          {okCount}
        </span>
        <span className="num text-3xl font-light text-muted-foreground/40">/ {totalCount}</span>
      </div>

      <div className="flex flex-1 items-center gap-3 pb-2">
        <div className={`h-2 w-2 rounded-full shadow-[0_0_0_4px] ${statusDotClass(allOk)}`} />
        <span className={`display text-2xl tracking-tight ${statusTextColor(allOk)}`}>
          {allOk ? "系统正常" : "系统异常"}
        </span>
      </div>

      <div className="hidden text-right lg:block">
        <div className="num text-xs text-muted-foreground tabular-nums">
          <span className="opacity-50">检测</span>{" "}
          <span className="text-foreground">{formatClock(checkedAt)}</span>
          <span className="mx-1.5 opacity-30">·</span>
          <UptimeCounter iso={checkedAt} />
        </div>
        {uptimeS !== undefined && (
          <div className="num text-xs text-muted-foreground tabular-nums">
            正常运行时间 <span className="text-foreground">{formatUptime(uptimeS)}</span>
            {pyVersion !== undefined && (
              <span className="ml-2 opacity-50">Python v{pyVersion}</span>
            )}
          </div>
        )}
      </div>
    </div>
  </div>
);
