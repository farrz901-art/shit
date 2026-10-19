import { describe, expect, it } from "vitest";
import { qKeys } from "./query-keys";

describe("qKeys", () => {
  it("root all 不变", () => {
    expect(qKeys.all).toEqual(["rag"]);
  });

  it("health.system 嵌套一致", () => {
    expect(qKeys.health.system()).toEqual(["rag", "health", "system"]);
  });

  it("output.list 和 output.detail 参数化正确", () => {
    expect(qKeys.output.list()).toEqual(["rag", "output", "list"]);
    expect(qKeys.output.detail("abc-123")).toEqual(["rag", "output", "detail", "abc-123"]);
  });

  it("batch.status 接收 taskId", () => {
    expect(qKeys.batch.status("task-1")).toEqual(["rag", "batch", "status", "task-1"]);
  });

  it("每次调用 list() 返新数组但内容相等 (避免误共享引用)", () => {
    const first = qKeys.output.list();
    const second = qKeys.output.list();
    expect(first).not.toBe(second); // 不同引用
    expect(first).toEqual(second); // 同内容
  });
});
