// (2026-06-11) eval/[id] running 状态动画 — 验证页面渲染 Loader2 旋转图标
// 需求: 用户在评估中要感知"正在跑", 加 Loader2 (lucide) + animate-spin class
// (2026-06-12, Task 19) RSC 测试: page 改 RSC 后, mock next/headers + global.fetch,
//   Await Page() 拿 RSC 元素后, 再用 IntlWrapper render 含 RunDetailView client 子组件的 JSX.
import type { EvaluationSample, ReportMetrics } from "@/lib/evaluate/types";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// RunDetailView 是 client 子组件, 内部用 useRouter + useTranslations,
// 测试 vitest jsdom 没有 App Router, 需 mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const baseRun = (
  overrides: Partial<{
    id: number;
    status: string;
    total_samples: number;
    successful: number;
    failed: number;
    duration_seconds: number | null;
    avg_metrics: ReportMetrics | null;
    samples: EvaluationSample[];
  }> = {},
) => ({
  avg_metrics: null,
  created_at: "2026-06-11T10:00:00.000Z",
  dataset_name: "测试集",
  duration_seconds: null,
  error_message: null,
  failed: 1,
  id: 7,
  name: "test-eval",
  samples: [],
  status: "running",
  successful: 2,
  total_samples: 5,
  ...overrides,
});

const renderRscPage = async (run: ReturnType<typeof baseRun>) => {
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (测试用)
  globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    if (urlStr.includes("/api/permissions/me")) {
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
    return Response.json(run, {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  }) as never;
  const mod = await import("./page");
  const pageComponent = mod.default;
  const element = await pageComponent({ params: Promise.resolve({ id: "7" }) });
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {element}
    </NextIntlClientProvider>,
  );
};

describe("EvaluationDetailPage running 状态动画 (2026-06-11) / RSC (2026-06-12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("running 状态 → 渲染 Loader2 旋转图标 (animate-spin class)", async () => {
    const { container } = await renderRscPage(
      baseRun({ failed: 1, status: "running", successful: 2 }),
    );
    await waitFor(() => {
      // Lucide-react 的 Loader2 会渲染成 <svg> 带 class "lucide lucide-loader-circle animate-spin"
      const spinner = container.querySelector("svg.animate-spin");
      expect(spinner).toBeTruthy();
    });
  });

  it("running 状态 → 评估中文 + 进度文字仍在", async () => {
    await renderRscPage(baseRun({ failed: 1, status: "running", successful: 2 }));
    await waitFor(() => {
      expect(screen.getByText(/评估进行中/)).toBeInTheDocument();
      // 3 (2+1) / 5 已完成
      expect(screen.getByText(/3.*5.*已完成/)).toBeInTheDocument();
    });
  });

  it("completed 状态 → 不渲染 Loader2 旋转图标", async () => {
    const { container } = await renderRscPage(
      baseRun({
        avg_metrics: {
          answer_relevancy: 0.85,
          context_precision: 0.8,
          context_recall: 0.75,
          faithfulness: 0.9,
        },
        duration_seconds: 12.3,
        failed: 0,
        samples: [],
        status: "completed",
        successful: 5,
      }),
    );
    await waitFor(() => {
      const spinner = container.querySelector("svg.animate-spin");
      expect(spinner).toBeFalsy();
    });
  });
});
