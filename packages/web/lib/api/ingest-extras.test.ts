// Ingest API 额外单测 (taskDownload 4xx + presign 路径 + parseFilename)
import { afterEach, describe, expect, it, vi } from "vitest";
import { taskDownload, uploadViaPresign } from "./ingest";

const okResponse = (data: unknown): Response =>
  ({ ok: true, status: 200, text: async () => JSON.stringify(data) }) as unknown as Response;

describe("uploadViaPresign", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("完整 presign→PUT→finalize 流程", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          okResponse({
            task_id: "t1",
            total_files: 1,
            state: "queued",
            uploads: [
              {
                name: "f.pdf",
                uri: "minio/uri",
                put_url: "https://minio/put",
                mime: "application/pdf",
              },
            ],
          }),
        )
        .mockResolvedValueOnce({ ok: true } as Response)
        .mockResolvedValueOnce(okResponse({ task_id: "t1", total_files: 1, state: "queued" })),
    );
    const result = await uploadViaPresign([new File(["x"], "f.pdf")]);
    expect(result.task_id).toBe("t1");
  });

  it("presign 不返 PUT URL 抛错", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          task_id: "t1",
          uploads: [{ name: "f.pdf", uri: "minio/uri", put_url: null, mime: "pdf" }],
          total_files: 1,
          state: "queued",
        }),
      ),
    );
    await expect(uploadViaPresign([new File(["x"], "f.pdf")])).rejects.toThrow();
  });

  it("parseFilename 提取文件名", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => new Blob(["x"]),
        headers: { get: () => 'attachment; filename="report.zip"' },
      } as unknown as Response),
    );
    const result = await taskDownload("t1");
    expect(result.filename).toBe("report.zip");
  });
});
