// Ingest API 额外单测 (URL 工厂)
import { describe, expect, it } from "vitest";
import { taskDownloadUrl, taskFileUrl, taskUrl, tasksUrl } from "./ingest";

describe("URL 工厂", () => {
  it("tasksUrl", () => expect(tasksUrl()).toBe("/api/ingest/tasks"));
  it("taskUrl 转义", () => expect(taskUrl("a/b")).toBe("/api/ingest/tasks/a%2Fb"));
  it("taskFileUrl", () =>
    expect(taskFileUrl("t1", "f.md")).toBe("/api/ingest/tasks/t1/files/f.md"));
  it("taskDownloadUrl", () => expect(taskDownloadUrl("t1")).toBe("/api/ingest/tasks/t1/download"));
});
