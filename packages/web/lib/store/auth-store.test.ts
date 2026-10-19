// Auth-store zustand 单测
// 覆盖: 默认值 / setAccountId / 覆盖旧值
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./auth-store";

const TEST_ACCOUNT_ID_1 = 42;
const TEST_ACCOUNT_ID_2 = 1;
const TEST_ACCOUNT_ID_3 = 99;

describe("auth-store", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({ accountId: null });
  });
  afterEach(() => localStorage.clear());

  it("默认 accountId 为 null", () => {
    const { accountId } = useAuthStore.getState();
    expect(accountId).toBeNull();
  });

  it("setAccountId 写入后能读取", () => {
    useAuthStore.getState().setAccountId(TEST_ACCOUNT_ID_1);
    expect(useAuthStore.getState().accountId).toBe(TEST_ACCOUNT_ID_1);
  });

  it("setAccountId 覆盖旧值", () => {
    useAuthStore.getState().setAccountId(TEST_ACCOUNT_ID_2);
    useAuthStore.getState().setAccountId(TEST_ACCOUNT_ID_3);
    expect(useAuthStore.getState().accountId).toBe(TEST_ACCOUNT_ID_3);
  });

  it("setAccountId(null) 清空 accountId（清除 persist 残留）", () => {
    useAuthStore.getState().setAccountId(TEST_ACCOUNT_ID_1);
    expect(useAuthStore.getState().accountId).toBe(TEST_ACCOUNT_ID_1);
    useAuthStore.getState().setAccountId(null);
    expect(useAuthStore.getState().accountId).toBeNull();
  });

  it("persist 写入 localStorage", () => {
    useAuthStore.getState().setAccountId(TEST_ACCOUNT_ID_1);
    const stored = JSON.parse(localStorage.getItem("rag.auth-store.v1") ?? "{}");
    expect(stored.state.accountId).toBe(TEST_ACCOUNT_ID_1);
  });
});
