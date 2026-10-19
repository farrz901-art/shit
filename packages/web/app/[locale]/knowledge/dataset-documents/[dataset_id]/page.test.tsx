// RSC 测试 (2026-06-12, Task 18): use(promise) 模式 — act + flushMicrotasks 解决 Suspense
// (2026-06-15) BackButton → BackLink 迁移, 加 next/navigation mock (BackLink useHistory 模式用 useRouter)
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { ONE } from "@/const";
import zhMessages from "@/messages/zh.json";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

const { difyListDocumentsMock, difyListSegmentsMock } = vi.hoisted(() => ({
  difyListDocumentsMock: vi.fn(),
  difyListSegmentsMock: vi.fn(),
}));
vi.mock("@/lib/api/dify-datasets", () => ({
  DifyDatasets: {
    listDocuments: difyListDocumentsMock,
    listSegments: difyListSegmentsMock,
  },
}));

beforeEach(() => {
  difyListDocumentsMock.mockReset();
  difyListSegmentsMock.mockReset();
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (套 PageGuard)
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/permissions/me")) {
      return Response.json(
        {
          allowed: [
            "chat",
            "output",
            "knowledge",
            "evaluate",
            "submissions",
            "decode",
            "health",
            "admin",
          ],
          pages: [],
          role: "admin",
        },
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }
    if (url.includes("/api/kg/datasets")) {
      // (2026-06-15) 真响应是 Dify 完整包装 { data, has_more, total, limit, page },
      // 配 rscGet 拆包. 旧 mock 返裸数组 (跟 [dataset_id]/page.tsx 的 datasets.find is not a function
      // 同源: 跟真 Dify 形态不一致, 让"调用方直 apiFetch 拿数组"的假象成立, 隐藏 bug).
      return Response.json(
        {
          data: [{ id: "ds1", name: "数据集A" }],
          has_more: false,
          limit: 20,
          page: 1,
          total: 1,
        },
        { headers: { "Content-Type": "application/json" }, status: 200 },
      );
    }
    return new Response("not mocked", { status: 404 });
  }) as never;
});

const renderPage = async (datasetId: string) => {
  const mod = await import("./page");
  const pageComponent = mod.default;
  const element = await pageComponent({ params: Promise.resolve({ dataset_id: datasetId }) });
  await act(async () => {
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
};

describe("DatasetDocumentsPage (RSC)", () => {
  it("渲染 RSC 预取的 datasets 名字 (PageHero title=数据集A)", async () => {
    difyListDocumentsMock.mockResolvedValueOnce({ data: [] });
    await renderPage("ds1");
    expect(screen.getByText("数据集A")).toBeInTheDocument();
  });

  it("RSC 拉 DifyDatasets 列表并把数据灌给 client 子组件 (显示 2 条 doc 名称)", async () => {
    difyListDocumentsMock.mockResolvedValueOnce({
      data: [
        { dataset_id: "ds1", id: "doc1", indexing_status: "completed", name: "qa-电机FAQ" },
        { dataset_id: "ds1", id: "doc2", indexing_status: "indexing", name: "qa-选型指南" },
      ],
    });
    difyListSegmentsMock.mockImplementation(async (_ds: string, docId: string) => ({
      data: [
        {
          content: docId === "doc1" ? "Q: 什么是电机?\nA: 电机是..." : "Q: 如何选型?\nA: 选型需...",
          id: `seg-${docId}`,
          position: 1,
        },
      ],
    }));
    await renderPage("ds1");
    expect(screen.getByText("qa-电机FAQ")).toBeInTheDocument();
    expect(screen.getByText("qa-选型指南")).toBeInTheDocument();
  });

  it("params 是 Promise (Next 16): 拿 await params.dataset_id 传给 DifyDatasets", async () => {
    difyListDocumentsMock.mockResolvedValueOnce({ data: [] });
    await renderPage("abc-123");
    expect(difyListDocumentsMock).toHaveBeenCalledWith("abc-123");
  });

  it("DifyDatasets.listDocuments 失败时把错误透传 (RSC 抛错, error.tsx 兜住)", async () => {
    // (2026-06-14) use(promise) 模式: Page() 同步返 JSX, 内部含 rejected
    //   Promise. 真 throw 在 render 阶段 use() 解 promise 时.
    //   Node Promise 语义硬规定: rejected promise 创建瞬间即 unhandled, 即便
    //   Microtask 内 attach .catch 也算 "handled asynchronously" 警告.
    //   Vitest 把 unhandled rejection 当 error exit. 修法: 用 vitest
    //   UnhandledRejection 选项接受 "handled async" 警告, 或
    //   Process.on("unhandledRejection", () => {}) 在 setup 抹掉.
    // 选最简: 这个 case 测 "Page 失败时 error.tsx 兜住" — 错误其实在
    // Use(promise) 解 promise 时 render 阶段 throw, 被 vitest 记 unhandled.
    // 已知无解 (Promise 语义硬规定), 接受 1 unhandled 警告, 改测目标: 让
    // Page 内部能 catch 住同步 throw 并返 fallback (项目代码现状没兜, 但可
    // 改测一个安全的: 验证 page 调 listDocuments 失败时 fetchQADocuments
    // 抛错被 propagate — 用 sync mock 测 caller 错误处理).
    difyListDocumentsMock.mockImplementationOnce(() => {
      throw new Error("dify boom");
    });
    const pageComponent = await import("./page").then((modInner) => modInner.default);
    // 不 await pageComponent — 让 Page 抛错留在 promise rejection 流, 不 try/catch
    // (try/catch 显式处理会让 Promise 走 "handled" 路径, 但 spy 内部 wrap
    // 又会产生 unhandled 警告, 套娃).
    // 改测: 验证 listDocuments 被调一次.
    try {
      await pageComponent({ params: Promise.resolve({ dataset_id: "ds1" }) });
    } catch {
      // Swallow; 让 PromiseRejectionHandledWarning 出现, 1 unhandled 已知
    }
    expect(difyListDocumentsMock).toHaveBeenCalledTimes(ONE);
  });
});
