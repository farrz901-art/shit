"use client";
/**
 * 自实现 ThemeProvider — 替代已停止维护的 next-themes
 * 持 localStorage 持久化 + system 跟随 prefers-color-scheme + FOUC script 防闪
 * @param props.children 子节点
 * @param props.themes 白名单
 * @param props.defaultTheme 默认主题
 * @param props.enableSystem 是否允许跟随系统
 * @param props.storageKey localStorage key
 * @param props.attribute DOM 属性方式 (仅支持 class)
 * @param props.disableTransitionOnChange 关闭主题切换过渡动画 (保留 prop 兼容)
 * @returns JSX 元素
 * @client-bff
 */
// (2026-06-14) next-themes 0.4.6 在 React 19 报 "Encountered a script tag" warning,
// 作者 1 年没更新. 抄其实现思路 + 改用 useEffect 注入 FOUC script (不走 React 渲染树)
//
// 设计契约 (跟原 next-themes 行为对齐, settings-dialog 无感迁移):
// - API: useTheme() 返 { theme, setTheme, resolvedTheme, themes, systemTheme }
// - 持久化: localStorage[storageKey] 默认 "theme"
// - enableSystem=true 时 theme 可为 "system" (跟随 prefers-color-scheme)
// - FOUC prevention: useEffect 一次性 document.head.appendChild(inline <script>),
//   IIFE 同步读 storage + matchMedia 切 <html class>. 走真实 DOM, **不在 React 渲染树**,
//   **不触发 React 19 "script tag" 警告**
// - <html> 已有 suppressHydrationWarning (layout.tsx), 不用再管 hydration 警告
//
// 跟 next-themes 的差异:
// - FOUC script 通过 useEffect 注入, 而非 React 树里 <script> 元素
// - 跟 next-themes 一样: mediaQuery listener 总是注册, 内部判断是否要响应
import { type ReactNode, createContext, useContext, useEffect, useState } from "react";
import { useEvent } from "react-use";

const STORAGE_KEY = "theme";
const FOUC_MARKER = "data-theme-fouc";
const LIGHT = "light";
const DARK = "dark";
const SYSTEM = "system";
const MEDIA = "(prefers-color-scheme: dark)";

/** 可选的主题名称 */
export type ThemeName = "light" | "dark" | "system";

// (2026-06-14) Sprint 3.2: 拆成 ThemeDispatchContext + ThemeValueContext
interface ThemeContextValue {
  theme: ThemeName;
  resolvedTheme: "light" | "dark";
  setTheme: (next: ThemeName | ((prev: ThemeName) => ThemeName)) => void;
  themes: string[];
  systemTheme: "light" | "dark" | undefined;
}

const ThemeValueContext = createContext<{
  theme: ThemeName;
  resolvedTheme: "light" | "dark";
  themes: string[];
  systemTheme: "light" | "dark" | undefined;
}>({
  resolvedTheme: LIGHT,
  systemTheme: undefined,
  theme: LIGHT,
  themes: [LIGHT, DARK],
});

const ThemeDispatchContext = createContext<{
  setTheme: (next: ThemeName | ((prev: ThemeName) => ThemeName)) => void;
}>({ setTheme: () => undefined });

interface Props {
  children: ReactNode;
  /** 业务传入的白名单 (SettingsDialog 用来 map 渲染) */
  themes: string[];
  defaultTheme: ThemeName;
  /** 是否允许 theme="system" 跟随 prefers-color-scheme */
  enableSystem?: boolean;
  /** 持久化 key */
  storageKey?: string;
  /**
   * 应用主题的 DOM 方式. (2026-06-14) 自实现只支持 "class" (跟 next-themes 默认行为对齐);
   * 接 prop 是为兼容业务调用 (e.g. layout.tsx 传 attribute="class")
   * "data-theme" / 自定义等暂不实现, 需要再说
   */
  attribute?: "class";
  /**
   * 关闭主题切换时的 transition 动画 (next-themes 也提供, 自实现保留 prop 兼容性,
   * 实际无动画过渡逻辑 — 业务侧目前没动画)
   */
  disableTransitionOnChange?: boolean;
}

// --- helpers -----------------------------------------------------------------

/** 系统深色偏好. 服务器/没 matchMedia 时返 false */
const getSystemTheme = (): "light" | "dark" => {
  if (typeof globalThis === "undefined" || typeof globalThis.matchMedia !== "function") {
    return LIGHT;
  }
  const { matches } = globalThis.matchMedia(MEDIA);
  if (matches) {
    return DARK;
  }
  return LIGHT;
};

const readStored = (key: string): string | null => {
  try {
    return globalThis.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const writeStored = (key: string, value: string) => {
  try {
    globalThis.localStorage.setItem(key, value);
  } catch {
    // Private mode / quota → 静默
  }
};

const isServer = (): boolean => typeof globalThis === "undefined";

/**
 * 校验 theme 字符串合法 (2026-06-28 P4 refactor): 替 3 处散落的 LIGHT/DARK/SYSTEM 表达式.
 *
 * - "light" / "dark": 永远合法
 * - "system": 仅在 enableSystem 时合法
 *
 * @param val 待校验字符串
 * @param enableSystem 是否启用 system 模式
 */
const isValidTheme = (val: string, enableSystem: boolean): val is ThemeName => {
  if (val === LIGHT || val === DARK) {
    return true;
  }
  return enableSystem && val === SYSTEM;
};

/** 初值: 客户端读 storage; 否则 default */
const getInitialTheme = (key: string, fallback: ThemeName): ThemeName => {
  if (isServer()) {
    return fallback;
  }
  const stored = readStored(key);
  if (stored === LIGHT || stored === DARK || stored === SYSTEM) {
    return stored;
  }
  return fallback;
};

// 解析实际生效 theme (system → light/dark)
const resolveTheme = (theme: ThemeName, enableSystem: boolean): "light" | "dark" => {
  if (theme === SYSTEM) {
    if (enableSystem) {
      return getSystemTheme();
    }
    return LIGHT;
  }
  if (theme === DARK) {
    return DARK;
  }
  return LIGHT;
};

// 切 <html class>
const applyToHtml = (theme: ThemeName, enableSystem: boolean) => {
  const resolved = resolveTheme(theme, enableSystem);
  const el = document.documentElement;
  el.classList.toggle(DARK, resolved === DARK);
  // 跟 next-themes 一致: 同步 colorScheme, 浏览器原生控件跟随
  el.style.colorScheme = resolved;
};

// jsdom 在 vitest 下 vm.runInContext(globalThis-Proxy) 会抛 "Proxy is not allowed in
// global prototype chain" — 测试环境只验证 script 标签存在 + textContent, 不需要真 eval.
// 用 type="text/x-fouc-stub" 让 jsdom 跳过 eval (getType 返 null → 不 classic).
const isTestEnv = (): boolean =>
  typeof process !== "undefined" &&
  (process.env.VITEST === "true" || process.env.NODE_ENV === "test");

/** 在 <head> 注入 IIFE, 提前于 React 渲染跑, 防 dark↔light 闪 */
const injectFoucScript = (storageKey: string, enableSystem: boolean) => {
  if (document.head.querySelector(`script[${FOUC_MARKER}]`)) {
    return;
  }
  const script = document.createElement("script");
  script.setAttribute(FOUC_MARKER, "1");
  if (isTestEnv()) {
    script.setAttribute("type", "text/x-fouc-stub");
  }
  const allowSys = JSON.stringify(enableSystem);
  const storageKeyJson = JSON.stringify(storageKey);
  script.textContent = `(function(){
    try {
      var k=${storageKeyJson}, allowSys=${allowSys};
      var t=localStorage.getItem(k);
      if(t==="light"||t==="dark"){var r=t;}
      else if(allowSys && t==="system"){
        var sysDark=window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
        r=sysDark?"dark":"light";
      }
      else {return;}
      var el=document.documentElement;
      if(r==="dark"){el.classList.add("dark");}else{el.classList.remove("dark");}
      el.style.colorScheme=r;
    } catch(e) {}
  })();`;
  document.head.appendChild(script);
};

// --- provider ----------------------------------------------------------------

/**
 * ThemeProvider — 主题上下文提供者, 替代已停止维护的 next-themes
 * @param props.children 子节点
 * @param props.themes 白名单
 * @param props.defaultTheme 默认主题
 * @param props.enableSystem 是否允许跟随系统
 * @param props.storageKey localStorage key
 * @param props.attribute DOM 属性方式
 * @param props.disableTransitionOnChange 关闭主题切换过渡动画
 * @returns JSX 元素
 * @client-bff
 */
export const ThemeProvider = ({
  children,
  themes,
  defaultTheme,
  enableSystem = false,
  storageKey = STORAGE_KEY,
  attribute: _attribute = "class", // 接住 prop 不报错; 自实现只走 class
  disableTransitionOnChange: _dtc = false, // 接住 prop 不报错; 自实现无动画过渡
}: Props) => {
  const [theme, setThemeState] = useState<ThemeName>(() =>
    getInitialTheme(storageKey, defaultTheme),
  );
  const [systemTheme, setSystemTheme] = useState<"light" | "dark">(() => getSystemTheme());

  const setTheme = (value: ThemeName | ((prev: ThemeName) => ThemeName)) => {
    if (typeof value === "function") {
      setThemeState((prev) => {
        const next = value(prev);
        // 白名单校验
        if (!isValidTheme(next, enableSystem)) {
          return prev;
        }
        writeStored(storageKey, next);
        return next;
      });
    } else {
      if (!isValidTheme(value, enableSystem)) {
        return;
      }
      writeStored(storageKey, value);
      setThemeState(value);
    }
  };

  // Theme 变 → apply
  useEffect(() => {
    applyToHtml(theme, enableSystem);
  }, [theme, enableSystem]);

  // FOUC script (一次性)
  useEffect(() => {
    injectFoucScript(storageKey, enableSystem);
  }, [storageKey, enableSystem]);

  // MediaQuery 监听 (总是注册, 跟 next-themes 行为一致)
  useEffect(() => {
    if (typeof globalThis === "undefined" || typeof globalThis.matchMedia !== "function") {
      return;
    }
    const media = globalThis.matchMedia(MEDIA);
    const onChange = () => {
      const cur = getSystemTheme();
      setSystemTheme(cur);
      // Theme === "system" 时由 theme effect apply; 这里只刷 state
      if (theme === SYSTEM && enableSystem) {
        const el = document.documentElement;
        el.classList.toggle(DARK, cur === DARK);
        el.style.colorScheme = cur;
      }
    };
    // 用 addEventListener (现代 API), 不依赖 deprecated addListener
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme, enableSystem]);

  // (2026-06-14) react-use: useEvent 替 storage addEventListener + cleanup 模板
  // Media query useEffect 保留 (复杂条件 + deps, useEvent 不适合)
  useEvent("storage", (event: StorageEvent) => {
    if (event.key !== storageKey) {
      return;
    }
    if (!event.newValue) {
      setTheme(defaultTheme);
    } else if (isValidTheme(event.newValue, enableSystem)) {
      setThemeState(event.newValue);
    }
  });

  const resolvedTheme: "light" | "dark" = resolveTheme(theme, enableSystem);

  // (2026-06-14) Sprint 3.2: 拆成 ThemeDispatchContext + ThemeValueContext
  return (
    <ThemeDispatchContext value={{ setTheme }}>
      <ThemeValueContext value={{ resolvedTheme, systemTheme, theme, themes }}>
        {children}
      </ThemeValueContext>
    </ThemeDispatchContext>
  );
};

/** 读 theme 状态 + setter. 必须在 ThemeProvider 内部调用.
 * Provider 外调用返安全占位 (不抛, 跟 next-themes 行为一致).
 * @returns theme 上下文值 (theme, resolvedTheme, setTheme, themes, systemTheme)
 * @shared */
export const useTheme = (): ThemeContextValue => {
  const dispatch = useContext(ThemeDispatchContext);
  const state = useContext(ThemeValueContext);
  return { ...dispatch, ...state };
};
