"use client";
// 返回链接 (2026-06-15) — 从 output/new 内联 + 旧 knowledge/BackButton 合并, 统一风格
// 两种模式:
//   - 默认 (LocalizedLink 模式): 纯 <a href={href}>, 可右键/中键/SEO, 跟 output/new 一致
//   - useHistory=true: <a href={href}> 上叠 onClick 走 router.back()/push(href),
//     保留 <a href> 让右键/中键仍可用, onClick 只是 JS 增强. 旧 BackButton 走这条
// 视觉统一: eyebrow 小字 + Lucide ArrowLeft + group hover translate-x 动画
import { ArrowLeft } from "lucide-react";

import { LocalizedLink } from "@/components/i18n/localized-link";
import { cn } from "@/lib/utils";
import { useRouter } from "@/i18n/navigation";

/**
 * BackLink 属性接口 — 目标 URL、history 模式开关及文案
 * @client-bff
 */
export interface BackLinkProps {
  /** 目标 URL. useHistory 模式下作 fallback href (无历史栈时 push 过去) */
  href: string;
  /** True: 点击走 history.back() (有历史) / router.push(href) (无历史). 默认 false 纯 link */
  useHistory?: boolean;
  /** 链接文案, 默认 "返回" */
  label?: string;
  className?: string;
  "data-testid"?: string;
}

/** 鼠标左键 button 编号 (MouseEvent.button 字段) */
const MOUSE_BUTTON_LEFT = 0;
/** History 栈深度的最小有效值, 大于 1 表示有前页可 back */
const MIN_HISTORY_FOR_BACK = 2;

/**
 * 返回链接 — LocalizedLink 包装, 支持纯链接和 history.back() 两种模式
 * 默认纯链接 (右键/中键/SEO 友好); useHistory=true 时左键走 history.back()
 * @param props.href 目标 URL
 * @param props.useHistory 是否启用 history.back() 模式
 * @param props.label 链接文案
 * @returns 返回链接 JSX
 */
export const BackLink = ({
  href,
  useHistory = false,
  label = "返回",
  className,
  "data-testid": dataTestid,
}: BackLinkProps) => {
  const router = useRouter();

  /**
   * UseHistory 模式叠 onClick: 修饰键 (ctrl/cmd/shift/middle-click) 透传给浏览器原生
   * (新标签打开), 只在普通左键时拦截走 history. 保留 <a href> 让 SEO + 右键/中键仍可用.
   * @param event 鼠标事件
   */
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== MOUSE_BUTTON_LEFT) {
      return;
    }
    event.preventDefault();
    if (typeof globalThis !== "undefined" && globalThis.history.length >= MIN_HISTORY_FOR_BACK) {
      router.back();
    } else {
      router.push(href);
    }
  };
  /**
   * 非 useHistory 模式不挂 onClick, 让浏览器走原生 <a href> 行为 (SEO/右键/中键)
   */
  const clickHandler = useHistory ? handleClick : undefined;

  const linkClass = cn(
    "eyebrow group inline-flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground",
    className,
  );

  return (
    <LocalizedLink
      href={href}
      onClick={clickHandler}
      data-testid={dataTestid}
      className={linkClass}
    >
      <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-1" />
      {label}
    </LocalizedLink>
  );
};
