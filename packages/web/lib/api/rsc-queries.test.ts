// Server-only RQ 工具测试: per-request QueryClient 单例 + apiFetch 集成
import { HTTP_INTERNAL_SERVER_ERROR, HTTP_OK } from "@/const";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getRscQueryClient, prefetchQuery, rscGet } from "./rsc-queries";

// Mock server-only: rsc-queries.ts 顶部 import "server-only" (Next.js marker),
// 在 vitest jsdom 环境没有这个 module, mock 成空 module 让 import 解析通过.
vi.mock("server-only", () => ({}));

// Mock next/headers: 模拟 Next 16 的 async cookies() API
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => {
      if (key === "rag_user_token") {
        return { value: "test-token-123" };
      }
      return undefined;
    },
  })),
}));

// Mock react cache: 在 jsdom (client) 下 react 的 cache 是 no-op, 真实 RSC 服务端
// 才提供 per-request memoization. 这里用 globalThis 暴露重置函数, 测试在 beforeEach
// 清掉, 避免上一个 test 留下的 QueryClient 污染后续断言.
type GlobalWithCacheReset = typeof globalThis & {
  // oxlint-disable-next-line no-underscore-dangle -- 测试用重置函数名需要双下划线
  __rscQueriesTestResetCache__?: () => void;
};
vi.mock("react", async () => {
  // oxlint-disable-next-line typescript/consistent-type-imports -- 动态类型引用需保持
  const actual = await vi.importActual<typeof import("react")>("react");
  let cached: { result: unknown } | null = null;
  // oxlint-disable-next-line no-underscore-dangle -- 测试用重置函数名需要双下划线
  (globalThis as GlobalWithCacheReset).__rscQueriesTestResetCache__ = () => {
    cached = null;
  };
  const cacheFn = (fn: (...args: never[]) => unknown) =>
    ((...args: never[]) => {
      if (cached === null) {
        cached = { result: fn(...args) };
      }
      return cached.result;
    }) as unknown as typeof fn;
  return { ...actual, cache: cacheFn };
});

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

describe("rsc-queries", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // oxlint-disable-next-line no-underscore-dangle -- 测试用重置函数名需要双下划线
    (globalThis as GlobalWithCacheReset).__rscQueriesTestResetCache__?.();
    globalThis.fetch = vi.fn(async () => okResponse({ ok: true }));
  });

  it("getRscQueryClient 返新单例 per call", async () => {
    const first = await getRscQueryClient();
    const second = await getRscQueryClient();
    expect(first).toBe(second);
  });

  it("prefetchQuery 成功时写入 qc cache", async () => {
    const qc = await getRscQueryClient();
    globalThis.fetch = vi.fn(async () => okResponse({ val: 1 }));
    await prefetchQuery(qc, ["test", "ok"], "/api/val");
    const got = await qc.fetchQuery({ queryKey: ["test", "ok"] });
    expect(got).toEqual({ val: 1 });
  });

  it("prefetchQuery 失败时不抛 (留给客户端 useQuery 接管重拉 + QueryCache.onError 弹 toast)", async () => {
    globalThis.fetch = vi.fn(async () => errResponse(HTTP_INTERNAL_SERVER_ERROR, "boom"));
    const qc = await getRscQueryClient();
    // (2026-06-14) 失败不抛 → 整页不挂, 客户端 useQuery 看到 cache miss 会重拉,
    // 重拉失败时由 lib/api/query-client.ts 的 QueryCache.onError 弹 sonner toast.
    await expect(prefetchQuery(qc, ["test", "fail"], "/api/y")).resolves.toBeUndefined();
  });

  // (2026-06-14) rscGet 自动解包 { data: T } wrapper. 后端 list endpoint 统一返 Dify 形态
  // (见 [[feedback-dify-api-returns-data-wrapper]]), 调用方继续当裸数组用.
  // (2026-06-15) Dify 真响应除 data 外还带 has_more/limit/total/page, 启发式改成 "data 是数组就拆",
  //   否则多 key 漏拆 → datasets.find is not a function 那种 shim 就会钻出来.
  describe("rscGet wrapper 解包", () => {
    it("返简化 { data: T[] } → 自动拆出 T[]", async () => {
      globalThis.fetch = vi.fn(async () => okResponse({ data: [{ id: 1 }, { id: 2 }] }));
      const out = await rscGet<{ id: number }[]>("/api/kg/datasets");
      expect(out).toEqual([{ id: 1 }, { id: 2 }]);
    });

    it("返 Dify 完整包装 { data, has_more, total, limit, page } → 仍拆出 T[] (回归)", async () => {
      // 后端 /api/kg/datasets 透传 Dify 真响应, 5 个 key 齐. 旧启发式 (Object.keys.length === 1) 漏拆,
      // 引发 [dataset_id]/page.tsx 的 datasets.find is not a function 错.
      globalThis.fetch = vi.fn(async () =>
        okResponse({
          data: [
            { id: "ds1", name: "数据集A" },
            { id: "ds2", name: "数据集B" },
          ],
          has_more: false,
          limit: 20,
          page: 1,
          total: 2,
        }),
      );
      const out = await rscGet<{ id: string; name: string }[]>("/api/kg/datasets");
      expect(out).toEqual([
        { id: "ds1", name: "数据集A" },
        { id: "ds2", name: "数据集B" },
      ]);
      // 防御: 必须拿回数组, 不是包装对象
      expect(Array.isArray(out)).toBe(true);
    });

    it("data 是非数组 (e.g. { data: { foo: 1 } }) → 不拆 (避免误拆嵌套对象)", async () => {
      globalThis.fetch = vi.fn(async () => okResponse({ data: { foo: 1 } }));
      const out = await rscGet<{ foo: number }>("/api/val");
      // 启发式只看 data 是不是数组, 对象形态 (非 list wrapper) 保持原样, 不误拆
      expect(out).toEqual({ data: { foo: 1 } });
    });

    it("返裸 T[] → 原样透传", async () => {
      globalThis.fetch = vi.fn(async () => okResponse([{ id: 1 }]));
      const out = await rscGet<{ id: number }[]>("/api/evaluate/runs");
      expect(out).toEqual([{ id: 1 }]);
    });

    it("返复合对象 { datasets, documents } → 不拆 (多 key 跳过)", async () => {
      globalThis.fetch = vi.fn(async () => okResponse({ datasets: 3, documents: 42 }));
      const out = await rscGet<{ datasets: number; documents: number }>("/api/kg/stats?type=dify");
      expect(out).toEqual({ datasets: 3, documents: 42 });
    });

    it("返裸对象 { val: 1 } → 不拆 (无 data 字段)", async () => {
      globalThis.fetch = vi.fn(async () => okResponse({ val: 1 }));
      const out = await rscGet<{ val: number }>("/api/val");
      expect(out).toEqual({ val: 1 });
    });
  });
});
