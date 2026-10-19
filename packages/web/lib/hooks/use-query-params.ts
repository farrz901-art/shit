/**
 * URL query 参数双向同步 hook (P1-9, 2026-06-29 补 JSDoc + setParam replaceState 语义)
 *
 * 仅客户端安全 (useSearchParams + globalThis.history).
 * SSR 阶段 useSearchParams 返 null → 用 defaults 兜底.
 *
 * @param defaults 默认值 (URL 里没传时用, URL 有则覆盖)
 * @returns { params, setParam }
 *   - params: 合并 URL + defaults 的最终值 (URL 优先)
 *   - setParam(key, value): 更新 URL, 用 replaceState 不增加 history entry
 *     (避免每个 filter / tab 切换都污染浏览器 back 按钮栈)
 * @example
 *   const { params, setParam } = useQueryParams({ tab: "info" });
 *   setParam("tab", "settings"); // URL 变 ?tab=settings, back 按钮不增加项
 */
import { useSearchParams } from "next/navigation";

/** URL query 参数双向同步, 参考上方模块注释.
 * @client-bff */
export const useQueryParams = (defaults?: Record<string, string>) => {
  const searchParams = useSearchParams();
  // URL 参数覆盖 defaults: 先展开 defaults, 再用 URL entries 覆盖同名 key
  const params: Record<string, string> = { ...defaults };
  for (const [key, value] of searchParams.entries()) {
    params[key] = value;
  }

  const setParam = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams.toString());
    newParams.set(key, value);
    // replaceState 而非 pushState: 不增加 history entry, 用户按 back 不会陷在 filter 状态里
    globalThis.history.replaceState(null, "", `?${newParams.toString()}`);
  };

  return { params, setParam };
};
