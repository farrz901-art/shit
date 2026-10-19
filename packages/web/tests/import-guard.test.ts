/**
 * 禁止 .tsx 文件从 next/navigation 引 useRouter.
 * 必须用 @/i18n/navigation 的 wrapper (createNavigation(routing) 封装).
 *
 * 背景 (2026-06-17, packages/web/CLAUDE.md):
 *   next/navigation 的 useRouter.push("/xxx") 不带 locale, 被 intlMiddleware 307 重定向
 *   到 /zh/xxx, 多一跳 + 用户感"没反应". 真实 bug 案例: 登录成功以为失败.
 *
 *   i18n/navigation.ts 用 createNavigation(routing) 解构出 locale-aware 的 useRouter,
 *   router.push("/xxx") 自动变 /zh/xxx, 1 跳直达.
 *
 *   next-intl 4.x 删了直接 useRouter 导出, 必须先 createNavigation(routing), 所以业务代码
 *   统一 import "@/i18n/navigation", 不许直引 next-intl/navigation 也不许直引 next/navigation.
 *
 * 测试模式 1 (mock): vitest + fs walk, 不连真依赖. 跑这个测试就能把守则推到 CI.
 *
 * 已知 pre-existing 违规 (master plan FE-003 ~ FE-011, 后续单独修).
 * 当前 task (FE-001) 只修 evaluate-new-form; 守则严格 enforce 留 FE-003~FE-011 各自 task.
 * 这里把 assert 用 it.skip 暂不强制, console.warn 持续输出违规, 后续 task 改完取消 skip.
 */
// eslint-disable-next-line -- 测试文件 .ts 不用 JSX, 跳过 sort-imports 复杂排序
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP_ROOT = join(process.cwd(), "app");

// Walk: 递归扫 .tsx 文件. 跳过 node_modules / .next / dist
const walkTsxFiles = (dir: string): string[] => {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      results.push(...walkTsxFiles(path));
    } else if (entry.endsWith(".tsx")) {
      results.push(path);
    }
  }
  return results;
};

// 检测: import { ..., useRouter, ... } from "next/navigation"
// 不包括 useSearchParams / useParams (这两个 next-intl 不重新导出, 仍走 next/navigation —
//   见 packages/web/CLAUDE.md "路由跳转必须用 next-intl 的 useRouter" 段 Note)
const USE_ROUTER_FROM_NEXT_NAVIGATION =
  /import\s*\{[^}]*\buseRouter\b[^}]*\}\s*from\s*["']next\/navigation["']/;

describe("import guard: useRouter from next/navigation", () => {
  // (2026-06-24 FE-001, 2026-06-26 取消 skip — 2026-07-09 验证 0 违规, 移除 skip)
  it("所有 .tsx 文件不允许从 next/navigation 引 useRouter (FE-003~FE-011 修完后取消 skip)", () => {
    const files = walkTsxFiles(APP_ROOT);
    const violations: string[] = [];

    for (const file of files) {
      const content = readFileSync(file, "utf8");
      if (USE_ROUTER_FROM_NEXT_NAVIGATION.test(content)) {
        violations.push(file);
      }
    }

    expect(violations).toEqual([]);
  });

  // 实际跑扫描 + 输出当前违规 (不强制 fail, 只信息)
  it("扫描 + 打印当前 useRouter from next/navigation 违规 (info-only)", () => {
    const ZERO_VIOLATIONS = 0;
    const files = walkTsxFiles(APP_ROOT);
    const violations: string[] = [];

    for (const file of files) {
      const content = readFileSync(file, "utf8");
      if (USE_ROUTER_FROM_NEXT_NAVIGATION.test(content)) {
        violations.push(file);
      }
    }

    // info-only: 期望 violations 数量随 FE-003~FE-011 修复逐渐减少到 0
    if (violations.length > ZERO_VIOLATIONS) {
      // eslint-disable-next-line no-console -- 测试诊断输出
      console.warn(
        `[import-guard] ${violations.length} 处 useRouter from next/navigation 违规 (FE-003~FE-011 后续修):`,
        violations,
      );
    }
    expect(typeof violations).toBe(typeof []);
  });
});
