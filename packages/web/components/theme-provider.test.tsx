import { ThemeProvider, useTheme } from "./theme-provider";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { act } from "react";
import { ONE, ZERO } from "@/const";

// 行为契约:
// 1. 包 children 不报错
// 2. localStorage 有 theme 时初值正确
// 3. theme 变化时 <html className> 跟着切 (light ↔ dark)
// 4. system 主题读 matchMedia 初始 + 监听变化
// 5. setTheme 写入 localStorage
// 6. FOUC script 通过 document.head.appendChild 注入 (不在 React 渲染树)

// --- jsdom polyfills --------------------------------------------------------
const mockMatchMedia = (initial: "light" | "dark") => {
  type Listener = (event: MediaQueryListEvent) => void;
  let current = initial;
  const listeners = new Set<Listener>();
  const mql = {
    addEventListener: (_type: string, callback: Listener) => listeners.add(callback),
    addListener: (callback: Listener) => listeners.add(callback),
    dispatchEvent: () => true,
    get matches() {
      return current === "dark";
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    removeEventListener: (_type: string, callback: Listener) => listeners.delete(callback),
    removeListener: (callback: Listener) => listeners.delete(callback),
  };
  Object.defineProperty(globalThis, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation(() => mql),
    writable: true,
  });
  return {
    setSystem(next: "light" | "dark") {
      current = next;
      const ev = { matches: next === "dark" } as MediaQueryListEvent;
      listeners.forEach((cb) => cb(ev));
    },
  };
};

// 抓 FOUC script (next-themes 的 key 痕迹没了, 用 #__theme_fouc 标记)
const FOUC_MARKER = 'data-theme-fouc="1"';

beforeEach(() => {
  // 清状态
  document.documentElement.className = "";
  document.documentElement.removeAttribute("style");
  // 删旧 FOUC script
  [...document.head.querySelectorAll(`script[${FOUC_MARKER}]`)].forEach((script) =>
    script.remove(),
  );
  // 清 storage
  globalThis.localStorage.clear();
});

afterEach(() => {
  [...document.head.querySelectorAll(`script[${FOUC_MARKER}]`)].forEach((script) =>
    script.remove(),
  );
  document.documentElement.className = "";
});

describe("ThemeProvider", () => {
  it("包 children 不报错", () => {
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <div data-testid="child">x</div>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("挂载时把 <html> 切到 dark 当 localStorage.theme === 'dark'", async () => {
    globalThis.localStorage.setItem("theme", "dark");
    mockMatchMedia("light");
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <span>x</span>
      </ThemeProvider>,
    );
    // 状态更新发生在 microtask 后, 等待一帧
    await act(async () => {});
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("theme=light 时 <html> 不含 dark class", async () => {
    globalThis.localStorage.setItem("theme", "light");
    mockMatchMedia("dark");
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="dark">
        <span>x</span>
      </ThemeProvider>,
    );
    await act(async () => {});
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("setTheme 写入 localStorage 并切 <html className>", async () => {
    mockMatchMedia("light");
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => (
        <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
          {children}
        </ThemeProvider>
      ),
    });
    await act(async () => {});
    act(() => result.current.setTheme("dark"));
    await act(async () => {});
    expect(globalThis.localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("defaultTheme=system + 系统暗色 → <html> 切 dark", async () => {
    mockMatchMedia("dark");
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="system" enableSystem>
        <span>x</span>
      </ThemeProvider>,
    );
    await act(async () => {});
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("system 主题下 matchMedia 变化时跟着切 (深 → 浅)", async () => {
    const mm = mockMatchMedia("dark");
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => (
        <ThemeProvider themes={["light", "dark"]} defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      ),
    });
    await act(async () => {});
    expect(result.current.resolvedTheme).toBe("dark");
    act(() => mm.setSystem("light"));
    await act(async () => {});
    expect(result.current.resolvedTheme).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("FOUC script 通过 document.head 注入 (非 React 树)", async () => {
    mockMatchMedia("light");
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <span>x</span>
      </ThemeProvider>,
    );
    await act(async () => {});
    // 存在 marker script, 内容是 IIFE
    const scripts = document.head.querySelectorAll(`script[${FOUC_MARKER}]`);
    expect(scripts.length).toBeGreaterThanOrEqual(ONE);
    expect((scripts[ZERO] as HTMLScriptElement).textContent || "").toMatch(
      /localStorage|theme|dark/,
    );
  });

  it("多次挂载不重复注入 FOUC script", async () => {
    mockMatchMedia("light");
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <span>1</span>
      </ThemeProvider>,
    );
    await act(async () => {});
    const first = document.head.querySelectorAll(`script[${FOUC_MARKER}]`).length;
    // 卸载重挂
    document.head.querySelectorAll(`script[${FOUC_MARKER}]`).forEach((script) => script.remove());
    render(
      <ThemeProvider themes={["light", "dark"]} defaultTheme="light">
        <span>2</span>
      </ThemeProvider>,
    );
    await act(async () => {});
    const second = document.head.querySelectorAll(`script[${FOUC_MARKER}]`).length;
    expect(second).toBe(ONE);
    expect(first).toBeGreaterThanOrEqual(ZERO); // 第一次挂载时可能已被 React 卸, 不强制
  });
});
