// AppStore Zustand store 单测
// 覆盖: 默认值 / setDatasetId / setDomain / persist 持久化
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useAppStore } from "./app-store";

describe("useAppStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAppStore.setState({ datasetId: "", domain: "motor" });
  });
  afterEach(() => localStorage.clear());

  it("默认值: datasetId 空串, domain=motor", () => {
    const state = useAppStore.getState();
    expect(state.datasetId).toBe("");
    expect(state.domain).toBe("motor");
  });

  it("setDatasetId 更新 datasetId", () => {
    useAppStore.getState().setDatasetId("ds-42");
    expect(useAppStore.getState().datasetId).toBe("ds-42");
  });

  it("setDomain 更新 domain", () => {
    useAppStore.getState().setDomain("pump");
    expect(useAppStore.getState().domain).toBe("pump");
  });

  it("persist 写入 localStorage", () => {
    useAppStore.getState().setDatasetId("ds-1");
    useAppStore.getState().setDomain("fan");
    const stored = JSON.parse(localStorage.getItem("rag.app-store.v1") ?? "{}");
    expect(stored.state.datasetId).toBe("ds-1");
    expect(stored.state.domain).toBe("fan");
  });
});
