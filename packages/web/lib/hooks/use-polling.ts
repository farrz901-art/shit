// 通用轮询 hook — 封装 react-use useInterval, 统一 2 处独立轮询实现
// 用法: usePolling(callback, isActive ? POLL_INTERVAL_MS : null)
import { useInterval } from "react-use";

/**
 * 通用轮询 hook
 * @param callback 轮询回调
 * @param delay 间隔毫秒数, 传 null 暂停轮询
 */
export const usePolling = (callback: () => void, delay: number | null): void => {
  useInterval(callback, delay);
};
