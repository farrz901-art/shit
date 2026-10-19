"use client";
// RSC 灌 + 客户端读: datasets / schemas 列表.
// Zustand 仍管 datasetId/domain (用户选择), 但列表数据本身不进 zustand (跨请求新鲜).
import { type ReactNode, createContext, useContext } from "react";

/** 数据集行, 含文档数/字数.
 * @client-bff */
export interface DatasetRow {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}

/** RSC 注入的 App 数据 (datasets + schemas).
 * @client-bff */
export interface AppData {
  datasets: DatasetRow[];
  schemas: { name: string }[];
}

const Ctx = createContext<AppData | null>(null);

/** RSC 注入 Context Provider, 包裹子树以提供 datasets/schemas 数据.
 * @param props.datasets 数据集列表
 * @param props.schemas schema 名称列表
 * @client-bff */
export const AppDataProvider = ({
  datasets,
  schemas,
  children,
}: AppData & { children: ReactNode }) => (
  // (2026-06-14) React 19 Context 简写: <Ctx.Provider> → <Ctx>
  <Ctx value={{ datasets, schemas }}>{children}</Ctx>
);

/** 从 Context 读取 App 数据, 必须在 <AppDataProvider> 内使用.
 * @returns AppData (datasets + schemas)
 * @client-bff */
export const useAppData = (): AppData => {
  const ctxValue = useContext(Ctx);
  if (!ctxValue) {
    throw new Error("useAppData must be used inside <AppDataProvider>");
  }
  return ctxValue;
};
