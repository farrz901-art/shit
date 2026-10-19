import "@testing-library/jest-dom/vitest";
import type reactDom from "react-dom";
import { vi } from "vitest";

// (2026-06-14) server-only 包在 import 时抛 "cannot be imported from Client
//   Component". 走 barrel (lib/api/index.ts) 时即便只 export client 模块, 编译
//   期间可能拉进 server-only (auth.server / rsc-queries), 触发 throw. 抹掉 throw
//   让 barrel 走通, 行为 mock 为空对象.
vi.mock("server-only", () => ({}));

// (2026-06-18) next-intl/navigation 的 createNavigation 在 jsdom 下解析 next/navigation
//   失败 (Cannot find module 'next/navigation'). 全局 mock 掉避免每个用到 useRouter
//   的测试都得重复 mock. 业务代码仍走真的 next-intl/navigation, 单元测试只测 UI 行为.
vi.mock("@/i18n/navigation", () => ({
  // Link 用简单字符串 tag, 避免 setup 文件触发 JSX 解析 (vitest.setup 是 .ts 不是 .tsx)
  Link: "a",
  redirect: vi.fn(),
  usePathname: () => "/",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({}),
  usePathname: () => "/",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// (2026-06-14) Node Promise 语义硬规定: rejected promise 创建瞬间即 unhandled,
//   即便 microtask 内 attach .catch 也算 "handled asynchronously" 警告.
//   Vitest 把 unhandled rejection 当 error exit. 抹 listener 静默 (测试用,
//   真实运行时 vitest 仍会捕获别的真 unhandled).
process.on("unhandledRejection", () => {});

// DOM environment 没实现 useFormStatus (react-dom), mock 返回 { pending: false }
// (2026-06-21) 用 vi.fn() 以便 submit-button 测试覆写为 pending: true
vi.mock("react-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof reactDom>();
  return {
    ...actual,
    useFormStatus: vi.fn(() => ({ pending: false })),
  };
});

// DOM environment 没实现 IntersectionObserver, motion 12 的 whileInView / useInView 需要
class MockIntersectionObserver {
  observe = () => {};
  unobserve = () => {};
  disconnect = () => {};
  takeRecords = () => [];
  root = null;
  rootMargin = "";
  thresholds = [];
}
(
  globalThis as unknown as { IntersectionObserver: typeof MockIntersectionObserver }
).IntersectionObserver = MockIntersectionObserver;

// DOM environment 没实现 ResizeObserver, shadcn Dialog (Radix) 的 use-size 需要
class MockResizeObserver {
  observe = () => {};
  unobserve = () => {};
  disconnect = () => {};
}
(globalThis as unknown as { ResizeObserver: typeof MockResizeObserver }).ResizeObserver =
  MockResizeObserver;

// Shadcn Select / Dialog 等 Radix 组件读 globalThis.matchMedia, jsdom 默认是 undefined
if (typeof globalThis.window !== "undefined" && !globalThis.matchMedia) {
  Object.defineProperty(globalThis.window, "matchMedia", {
    value: (query: string) => ({
      addEventListener: () => {},
      addListener: () => {}, // 旧 API 兼容
      dispatchEvent: () => false,
      matches: false,
      media: query,
      onchange: null,
      removeEventListener: () => {},
      removeListener: () => {},
    }),
    writable: true,
  });
}
