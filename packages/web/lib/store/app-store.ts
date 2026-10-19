// 全局状态 store (2026-06-09)
// 当前: dataset 选择 / domain 选择 — 跨组件共享
// 后续: 可加 chat 草稿、用户偏好、配置等
//
// 替代之前 localStorage + CustomEvent 的方式:
// 之前: useEffect 读 localStorage + globalThis.addEventListener("kg:dataset-changed", sync)
// 现在: const datasetId = useAppStore((s) => s.datasetId); setDatasetId(id);
import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * 全局应用状态 — 跨组件共享的用户选择.
 * 用 zustand + persist middleware, 刷新后保留.
 */
interface AppState {
  /** 当前选中的 Dify dataset id. 跟 useDatasets() 返的 DatasetRow.id 同源.
   *  空串 = 未选中. */
  datasetId: string;
  setDatasetId: (id: string) => void;
  /** 当前 schema domain (业务域). 默认 "motor" = 电机行业 (项目主业). */
  domain: string;
  setDomain: (domainVal: string) => void;
}

/**
 * 管理全局应用状态 (数据集选择、业务域)
 * @client-bff
 */
// partialize 只持久化 2 个用户选择字段, 避免 set 函数 / 临时 state 写 localStorage
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      datasetId: "",
      domain: "motor",
      setDatasetId: (idVal) => set({ datasetId: idVal }),
      setDomain: (domainVal) => set({ domain: domainVal }),
    }),
    {
      name: "rag.app-store.v1",
      partialize: (state) => ({ datasetId: state.datasetId, domain: state.domain }),
    },
  ),
);
