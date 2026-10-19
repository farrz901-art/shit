// 抽取进度页测试 (2026-07-03)
// 守门测试: RSC entry 必须 await params, 把 string task_id 透传给 client 子组件.
// 若 page.tsx 没 await, 会把 Promise<{task_id}> 原样透传 → client 拿 undefined → fetch /tasks/undefined.
// 跟 admin/pre-analysis/[task_id]/page.test.tsx 守门模式对齐.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

vi.mock("server-only", () => ({}));

const FIRST_CALL = 0;
const mockTask = {
  task_id: "kg-tx-abc123",
  state: "running" as const,
  success: 0,
  failed: 0,
  errors: [],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TaskProgressPage (RSC)", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => Response.json(mockTask, { status: 200 })) as never;
  });

  it("把 URL 上的 task_id 透传给 client 子组件, 触发正确的 fetch URL", async () => {
    const mod = await import("./page");
    const page = mod.default;
    const element = await page({
      params: Promise.resolve({ task_id: "kg-tx-abc123" }),
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <QueryClientProvider client={qc}>{element}</QueryClientProvider>
      </NextIntlClientProvider>,
    );
    await waitFor(() => {
      const { calls: fetchedCalls } = (globalThis.fetch as ReturnType<typeof vi.fn>).mock;
      const fetchedUrls = fetchedCalls.map((call) => String(call[FIRST_CALL]));
      // 关键断言: 透传 task_id, 不能 fetch /tasks/undefined
      expect(fetchedUrls.some((url) => url.includes("/api/kg/extract/tasks/kg-tx-abc123"))).toBe(
        true,
      );
      expect(fetchedUrls.some((url) => url.includes("/undefined"))).toBe(false);
    });
  });
});

describe("TaskProgressClient", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => Response.json(mockTask, { status: 200 })) as never;
  });

  it("渲染 task_id 描述行 (从 props 透传, 不读 params)", async () => {
    const { TaskProgressClient } = await import("./_components/task-progress-client");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <IntlWrapper locale="zh">
        <QueryClientProvider client={qc}>
          <TaskProgressClient taskId="kg-tx-abc123" />
        </QueryClientProvider>
      </IntlWrapper>,
    );
    await waitFor(() => {
      // description 行: "task_id: kg-tx-abc123 | dataset: motor"
      expect(document.body.textContent).toContain("kg-tx-abc123");
    });
  });
});
