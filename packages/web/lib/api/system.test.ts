// SystemApi 业务客户端单测
// 覆盖: 5 个 API 方法 (decode / health / listOutputFiles / listSeries / readOutputFile)
import { afterEach, describe, expect, it, vi } from "vitest";
import { ONE, ZERO } from "@/const";
import { decode, health, listOutputFiles, listSeries, readOutputFile } from "./system";

const okResponse = <Data>(responseData: Data): Response =>
  ({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(responseData),
  }) as unknown as Response;

describe("system", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("decode POST /decode", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ decoded: "ABC123" })));
    const result = await decode("ABC");
    expect(result).toEqual({ decoded: "ABC123" });
  });

  it("health GET /health", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ status: "ok", series_count: 5 })),
    );
    const result = await health();
    expect(result).toEqual({ status: "ok", series_count: 5 });
  });

  it("listOutputFiles GET /api/output/files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ files: [{ name: "log.txt", size: 100, mtime: 1 }] })),
    );
    const result = await listOutputFiles();
    expect(result.files).toHaveLength(ONE);
    expect(result.files[ZERO].name).toBe("log.txt");
  });

  it("listSeries GET /series", async () => {
    const seriesData = [{ series: "1LE", manufacturer: "Siemens", name: "1LE1001", prefix: "1LE" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(seriesData)));
    const result = await listSeries();
    expect(result).toHaveLength(ONE);
    expect(result[ZERO].series).toBe("1LE");
  });

  it("readOutputFile GET /api/output/files/{name}", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ name: "report.pdf", content: "abc", mime: "pdf" })),
    );
    const result = await readOutputFile("report.pdf");
    expect(result.name).toBe("report.pdf");
    expect(result.content).toBe("abc");
  });

  it("readOutputFile 转义特殊字符", async () => {
    let capturedUrl = "";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        capturedUrl = url;
        return okResponse({ name: "my file.txt", content: "", mime: "text" });
      }),
    );
    await readOutputFile("my file.txt");
    expect(capturedUrl).toContain(encodeURIComponent("my file.txt"));
  });
});
