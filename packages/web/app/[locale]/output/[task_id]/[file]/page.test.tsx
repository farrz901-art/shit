// (2026-06-14) 更新 mock 形状: apiFetch 调 res.text(), 旧 mock 只有 res.json() 跑不通
// 测行为: md → 渲染 ReactMarkdown, svg → <pre>, 404 → 错误
// (2026-06-17) Task 9: 响应 shape 改 {name, url, size, mime} (无 content).
//   测试 mock 两次 fetch: 第一次 meta (新 shape), 第二次 content (拉 url)
// (2026-06-23) GuardClient 读 zustand store, 不再 mock /api/permissions/me
import { HTTP_NOT_FOUND, ZERO } from "@/const";
import { act, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FilePreview from "./page";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;
const okTextResponse = (text: string): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => text,
  }) as unknown as Response;
const errResponse = (status: number, detail?: string): Response =>
  ({
    ok: false,
    status,
    statusText: "Err",
    text: async () => (detail ? JSON.stringify({ detail }) : ""),
  }) as unknown as Response;

// 业务 fetch mock 用 queue 模拟顺序调用; 权限改走 zustand store, 不再拦截 /api/permissions/me
const makeFetch = (businessQueue: Response[]): typeof fetch =>
  vi.fn(async () => {
    if (businessQueue.length > ZERO) {
      return businessQueue.shift()!;
    }
    return new Response("not mocked", { status: 404 });
  }) as never;

beforeEach(() => {
  vi.restoreAllMocks();
  usePermissionsStore.setState({
    accountId: null,
    allowed: ["output"],
    loaded: true,
    pages: [],
    role: "admin",
  });
});

describe("FilePreview", () => {
  it("md 文件 → 渲染 ReactMarkdown", async () => {
    globalThis.fetch = makeFetch([
      okResponse({
        mime: "text/markdown",
        name: "a.md",
        size: 8,
        url: "https://minio/presigned/a.md",
      }),
      okTextResponse("# Hello"),
    ]);
    await act(async () => {
      render(
        <IntlWrapper locale="zh">
          <FilePreview params={Promise.resolve({ file: "a.md", task_id: "t1" })} />
        </IntlWrapper>,
      );
    });
    await waitFor(() => {
      expect(screen.getByText("Hello")).toBeInTheDocument();
    });
  });

  it("svg 文件 → 用 <pre> 渲染", async () => {
    globalThis.fetch = makeFetch([
      okResponse({
        mime: "image/svg+xml",
        name: "x.svg",
        size: 6,
        url: "https://minio/presigned/x.svg",
      }),
      okTextResponse("<svg/>"),
    ]);
    await act(async () => {
      render(
        <IntlWrapper locale="zh">
          <FilePreview params={Promise.resolve({ file: "x.svg", task_id: "t1" })} />
        </IntlWrapper>,
      );
    });
    await waitFor(() => expect(screen.getByText("<svg/>")).toBeInTheDocument());
  });

  it("fetch 404 → 渲染错误信息", async () => {
    // Meta 走 404, 业务 fetch mock 顺序处理
    globalThis.fetch = makeFetch([errResponse(HTTP_NOT_FOUND, "文件不存在")]);
    await act(async () => {
      render(
        <IntlWrapper locale="zh">
          <FilePreview params={Promise.resolve({ file: "missing.md", task_id: "t1" })} />
        </IntlWrapper>,
      );
    });
    await waitFor(() => expect(screen.getByText(/文件不存在/)).toBeInTheDocument());
  });
});
