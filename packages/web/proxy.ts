import { type NextRequest, NextResponse } from "next/server";
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

const LOCALE_PREFIXES = ["/zh", "/en"];
const LOCALE_PREFIX_PATH_OFFSET = 1; // 跳过 /zh /en 前缀后第一个字符

const isProtected = (pathname: string): boolean =>
  // /admin/* 需账号 (后端再 401/403 兜底 is_admin 检查)
  // /submissions/* 需账号 (任何登录用户, 后端兜底 owner/审批人检查)
  // /account/* 需账号 (页面里也有 is_account 检查, proxy 早拦避免 RSC 多跑一次)
  LOCALE_PREFIXES.some(
    (locale) =>
      pathname.startsWith(`${locale}/admin`) ||
      pathname === `${locale}/admin` ||
      pathname.startsWith(`${locale}/submissions`) ||
      pathname === `${locale}/submissions` ||
      pathname.startsWith(`${locale}/account`) ||
      pathname === `${locale}/account`,
  );

const stripLocale = (pathname: string): string => {
  for (const locale of LOCALE_PREFIXES) {
    if (pathname.startsWith(`${locale}/`)) {
      return pathname.slice(locale.length + LOCALE_PREFIX_PATH_OFFSET);
    }
    if (pathname === locale) {
      return "/";
    }
  }
  return pathname;
};

// eslint-disable-next-line max-statements -- authGuard 11 句, 拆函数代价高于守卫
const authGuard = (request: NextRequest): NextResponse | null => {
  const { pathname } = request.nextUrl;
  if (!isProtected(pathname)) {
    return null;
  }

  const token = request.cookies.get("rag_user_token")?.value;
  if (token) {
    return null;
  }

  // 无 token: 重定向到当前 locale 的 /login, 保留 ?next= 便于登录后跳回
  const locale = LOCALE_PREFIXES.find(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )!;
  const url = request.nextUrl.clone();
  url.pathname = `${locale}/login`;
  url.searchParams.set("next", stripLocale(pathname));
  return NextResponse.redirect(url);
};

// 修复 next-intl + Turbopack dev 模式下 HTML 注入 `/zh/_next/...` 但实际资产在 `/_next/...` 的不一致
// 根因: Turbopack 输出的 manifest 路径拼接 base href, 产生双前缀; 把 /zh/_next/* 重写到 /_next/*
const rewritePrefixedAsset = (request: NextRequest): NextResponse | null => {
  const { pathname } = request.nextUrl;
  for (const locale of LOCALE_PREFIXES) {
    if (pathname.startsWith(`${locale}/_next/`)) {
      const url = request.nextUrl.clone();
      url.pathname = pathname.slice(locale.length);
      return NextResponse.rewrite(url);
    }
  }
  return null;
};

const intlMiddleware = createMiddleware(routing);

/**
 * Next.js 中间件: 路由守卫 + next-intl locale 处理 + 资产路径重写
 * @param request - 入站请求
 * @returns 转发 / 重定向 / 重写响应
 * @server-only
 */
export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // -1) /api/* BFF 路由 (app/api/...) 走 NextResponse.next 直通
  //     BFF 路径在 app/api/ 不在 app/[locale]/api/, 不能让 next-intl 强制加 locale 前缀
  //     (会 307 → /zh/api/... → 404). matcher 排除了 api 路径不进入 middleware,
  //     但这里再守一次: matcher 规则匹配复杂, 直通更稳.
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // 0) 修复 /zh/_next/* /en/_next/* 资产路径 (Turbopack manifest 在 HTML 里注入了 locale 前缀)
  const assetRewrite = rewritePrefixedAsset(request);
  if (assetRewrite) {
    return assetRewrite;
  }

  // 1) /admin/* + /submissions/* 路由守卫 (无 token → 提前 redirect 到 /login, 防 flash of unauthorized content)
  const guardResponse = authGuard(request);
  if (guardResponse) {
    return guardResponse;
  }

  // 2) next-intl 处理 /zh /en locale 路由
  return intlMiddleware(request);
}

/**
 * 中间件匹配规则: 排除 /api /_next /_vercel 及带点文件, locale 前缀下排除 _vercel
 * @server-only
 */
export const config = {
  // 两条规则: 根路径排除 _next/api/_vercel/带点文件; 带 locale 前缀的路径**不**排除 _next
  // 因为 Turbopack manifest 会在 HTML 里给资产 URL 注入 locale 前缀 (/zh/_next/...) 但实际文件在 /_next/...
  // Proxy 里 rewritePrefixedAsset 把 /zh/_next/* 重写回 /_next/* 修这个不一致
  // eslint-disable-next-line unicorn/prefer-string-raw -- Next.js 16 extractExportedConstValue 不识别 TaggedTemplateExpression, 改 String.raw 会触发 build 失败 (Invalid segment configuration export detected)
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)", "/(zh|en)/((?!api|_vercel).*)"],
};
