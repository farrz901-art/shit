/**
 * 区域化链接 (LocalizedLink) — 替代 next/link, 自动加 /<locale> 前缀
 * 强规约 (2026-06-17 教训): next/navigation 的 useRouter 跟 next/link 一样不加 locale
 *   → middleware intlMiddleware 307 重定向 → 用户感觉"刷新一下"
 *   → 改用本组件直接拼 locale, 1 跳直达
 *
 * prependLocale 规则:
 *   - 空 / "/" → `/{locale}`
 *   - 已带 `/{locale}/...` → 不重复加
 *   - 其他 → `/{locale}{path}`
 *
 * 用法: <LocalizedLink href="/admin/users">用户管理</LocalizedLink>
 */
"use client";
import type { ComponentProps } from "react";
import Link from "next/link";
import { useLocale } from "next-intl";

/** LocalizedLink 组件属性 — 透传 next/link 属性 */
type Props = ComponentProps<typeof Link>;

/** 内部用 useLocale 拿 locale, 自动给 href 加 /<locale> 前缀 */
export const LocalizedLink = ({ href, children, ...rest }: Props) => {
  const locale = useLocale();
  const localizedHref = prependLocale(locale, href as string);
  return (
    <Link href={localizedHref} {...rest}>
      {children}
    </Link>
  );
};

/**
 * 为路径自动添加 locale 前缀
 * @param locale 区域标识
 * @param path 原始路径
 * @returns 带 locale 前缀的路径
 */
const prependLocale = (locale: string, path: string): string => {
  if (!path || path === "/") {
    return `/${locale}`;
  }
  if (path.startsWith(`/${locale}/`) || path === `/${locale}`) {
    return path;
  }
  return `/${locale}${path}`;
};
