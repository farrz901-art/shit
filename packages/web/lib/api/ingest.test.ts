// IngestApi 业务客户端单测
// 覆盖: 4 个 URL 工厂 (路径构造 + encodeURIComponent) + upload happy/4xx + taskDownload happy/4xx
// (2026-06-14) 删网络断/networkError 路径 (apiFetch 已统一归一 NetworkError, 测一次在 config.ts 即可)
import { HTTP_BAD_REQUEST, HTTP_OK, HTTP_UNAUTHORIZED } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import {
  fetchFileMeta,
  taskDownload,
  taskDownloadUrl,
  taskFileUrl,
  taskUrl,
  tasksUrl,
  upload,
  uploadViaPresign,
} from "./ingest";

const okResponse = (data: unknown, status = HTTP_OK): Response =>
  ({
    ok: true,
    status,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number, detail?: string): Response => {
  const body = detail ? JSON.stringify({ detail }) : "";
  return {
    ok: false,
    status,
    statusText: "Err",
    text: async () => body,
  } as unknown as Response;
};

describe("URL 工厂", () => {
  it("tasksUrl", () => expect(tasksUrl()).toBe("/api/ingest/tasks"));
  it("taskUrl 转义", () => {
    expect(taskUrl("a/b c")).toBe("/api/ingest/tasks/a%2Fb%20c");
  });
  it("taskFileUrl 拼路径并转义", () => {
    expect(taskFileUrl("t1", "a/b.md")).toBe("/api/ingest/tasks/t1/files/a%2Fb.md");
  });
  it("taskDownloadUrl 拼路径", () =>
    expect(taskDownloadUrl("t1")).toBe("/api/ingest/tasks/t1/download"));
});

describe("upload", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("happy: 返 UploadResponse", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ state: "queued", task_id: "t1", total_files: 1 })),
    );
    const result = await upload([new File(["x"], "a.pdf", { type: "application/pdf" })]);
    expect(result).toEqual({ state: "queued", task_id: "t1", total_files: 1 });
  });

  it("4xx 抛 ApiError, detail 用后端返的", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errResponse(HTTP_BAD_REQUEST, "不支持的格式: .exe")),
    );
    await expect(upload([new File(["x"], "a.exe")])).rejects.toBeInstanceOf(ApiError);
  });
});

describe("taskDownload", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("happy: 200 → blob + 从 Content-Disposition 抽 filename", async () => {
    const fakeBlob = new Blob(["zip-bytes"], { type: "application/zip" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        blob: async () => fakeBlob,
        headers: {
          get: (headerKey: string) => {
            if (headerKey.toLowerCase() === "content-disposition") {
              return 'attachment; filename="2026-06-11-abc.zip"';
            }
            if (headerKey.toLowerCase() === "content-type") {
              return "application/zip";
            }
            return null;
          },
        },
        ok: true,
        status: HTTP_OK,
      } as unknown as Response),
    );
    const result = await taskDownload("2026-06-11-abc");
    expect(result.blob).toBe(fakeBlob);
    expect(result.filename).toBe("2026-06-11-abc.zip");
  });

  it("无 Content-Disposition → fallback 用 taskId.zip", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        blob: async () => new Blob(["x"]),
        headers: { get: () => null },
        ok: true,
        status: HTTP_OK,
      } as unknown as Response),
    );
    const result = await taskDownload("t1");
    expect(result.filename).toBe("t1.zip");
  });

  it("4xx 抛 ApiError, detail 用后端返的", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errResponse(HTTP_UNAUTHORIZED, "缺少 x-user-token")),
    );
    await expect(taskDownload("t1")).rejects.toMatchObject({
      message: "缺少 x-user-token",
      status: HTTP_UNAUTHORIZED,
    });
  });
});

describe("uploadViaPresign", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("完整 presign→PUT→finalize 流程", async () => {
    const presignResp = okResponse({
      task_id: "t1",
      total_files: 1,
      state: "queued",
      uploads: [
        { name: "f.pdf", uri: "minio/uri", put_url: "https://minio/put", mime: "application/pdf" },
      ],
    });
    const putResp = { ok: true } as Response;
    const finalizeResp = okResponse({ task_id: "t1", total_files: 1, state: "queued" });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(presignResp)
        .mockResolvedValueOnce(putResp)
        .mockResolvedValueOnce(finalizeResp),
    );
    const result = await uploadViaPresign([new File(["x"], "f.pdf", { type: "application/pdf" })]);
    expect(result.task_id).toBe("t1");
  });

  it("presign 不返 PUT URL 抛错", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          task_id: "t1",
          uploads: [{ name: "f.pdf", uri: "minio/uri", put_url: null, mime: "application/pdf" }],
          total_files: 1,
          state: "queued",
        }),
      ),
    );
    await expect(uploadViaPresign([new File(["x"], "f.pdf")])).rejects.toThrow("PUT URL");
  });

  it("PUT MinIO 失败抛错", async () => {
    const presignResp = okResponse({
      task_id: "t1",
      uploads: [
        { name: "f.pdf", uri: "minio/uri", put_url: "https://minio/put", mime: "application/pdf" },
      ],
      total_files: 1,
      state: "queued",
    });
    const putResp = { ok: false, status: 403 } as Response;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(presignResp).mockResolvedValueOnce(putResp),
    );
    await expect(uploadViaPresign([new File(["x"], "f.pdf")])).rejects.toThrow("PUT MinIO 失败");
  });
});

describe("fetchFileMeta", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("happy: 返 FileMeta (name/url/size/mime)", async () => {
    const meta = { name: "a.md", url: "minio://files/a.md", size: 1024, mime: "text/markdown" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(meta)));
    const result = await fetchFileMeta("t1", "a.md");
    expect(result).toEqual(meta);
  });

  it("文件名 / taskId 转义, 拼 /api/ingest/tasks/.../files/...", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(okResponse({ mime: "text/plain", name: "a/b.md", size: 0, url: "" }));
    vi.stubGlobal("fetch", fetchMock);
    await fetchFileMeta("t 1", "a/b.md");
    // oxlint-disable-next-line no-magic-numbers -- mock.calls 数组索引
    const url = fetchMock.mock.calls[0]?.[0] as string;
    expect(url).toContain("/api/ingest/tasks/t%201/files/a%2Fb.md");
  });

  it("4xx 抛 ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(errResponse(HTTP_UNAUTHORIZED)));
    await expect(fetchFileMeta("t1", "a.md")).rejects.toBeInstanceOf(ApiError);
  });
});
