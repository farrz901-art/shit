// 内外网路径分流 middleware (2026-06-09)
// CHAT_PUBLIC_MODE=true 时: 非 /chat* 全部 404, 防攻击者扫描后台
// 内网模式: 放行所有
import { type NextRequest, NextResponse } from "next/server";

/** CHAT_PUBLIC_MODE=true 时仅放行的公开路径前缀
 * @server-only */
const PUBLIC_PATHS = ["/chat", "/api/chat"];

/** 内外网路径分流 middleware: CHAT_PUBLIC_MODE=true 时仅放行 /chat* 和 /api/chat*
 * @param req - 请求对象
 * @returns NextResponse (404) 或 undefined (放行)
 * @server-only */
export const middleware = (req: NextRequest): NextResponse | undefined => {
  if (process.env.CHAT_PUBLIC_MODE !== "true") {
    return undefined;
  }
  const { pathname } = req.nextUrl;
  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
  if (isPublic) {
    return undefined;
  }
  return new NextResponse("Not Found", { status: 404 });
};

/** Next.js middleware 匹配规则: 排除 _next/static, _next/image, favicon.ico
 * @server-only */
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
