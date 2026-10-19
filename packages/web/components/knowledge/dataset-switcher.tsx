"use client";
/**
 * 数据集选择器 — 选当前 Dify dataset, 写到 zustand store 跨组件共享
 * 用 StandaloneQueryProvider 自包 QueryClient 单例
 * @returns JSX 元素
 * @client-bff
 */
// 模式: useSWR → useQuery (Task 28-prep, 2026-06-12 redesign) — 跟 HealthDot 同型:
//   - 挂在 root Header (不在 B 档 QC provider 下), 自包 QueryClientProvider (useState 工厂单例).
// (2026-06-15) 删 (data as { data?: Dataset[] } | undefined)?.data ?? [] shim — knowledgeApi.fetchDatasets
//   现在内部解 Dify 包装返裸数组 DatasetRow[], 调用方零感知. 跟 DifyDatasets.listDatasets 风格一致.
import { AppSelect } from "@/components/common/input/app-select";
import { StandaloneQueryProvider } from "@/components/common/providers";
import { useDatasets } from "@/lib/hooks/use-datasets";
import { useAppStore } from "@/lib/store/app-store";

/**
 * 数据集选择器内部组件 (StandaloneQueryProvider 子节点)
 * @returns JSX 元素
 */
const Switcher = () => {
  const { data: datasets = [] } = useDatasets();
  const datasetId = useAppStore((state) => state.datasetId);
  const setDatasetId = useAppStore((state) => state.setDatasetId);

  // 首次加载自动选第一个
  // eslint-disable-next-line no-magic-numbers -- 数组索引取首元素
  if (!datasetId && datasets[0]?.id) {
    // eslint-disable-next-line no-magic-numbers -- 数组索引取首元素
    setDatasetId(datasets[0].id);
  }

  return (
    <AppSelect
      options={datasets.map((dataset) => ({ label: dataset.name, value: dataset.id }))}
      value={datasetId}
      onChange={setDatasetId}
      placeholder="选择数据集"
      className="w-64"
      dataTestid="dataset-switcher"
    />
  );
};

/** dataset-switcher @client-bff */
export const DatasetSwitcher = () => (
  <StandaloneQueryProvider>
    <Switcher />
  </StandaloneQueryProvider>
);
