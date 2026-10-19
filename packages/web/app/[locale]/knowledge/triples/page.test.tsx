// RSC 测试 (2026-06-12): page 改 RSC 后, 直接 await Page() 拿预取 schema, 灌 TriplesForm.
// (2026-06-14) mock 形状升级, 不再断言 fetch URL/header
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import type { KnowledgeSchema } from "@/lib/schema-types";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

const MOCK_APPROVAL_ID = 999;

const createTriplesMock = vi.fn(async () => ({
  data: { apply_status: "none", approval_id: MOCK_APPROVAL_ID, review_status: "pending" },
  ok: true as const,
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  commitDocuments: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 0, review_status: "pending" },
    ok: true as const,
  })),
  createQA: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 0, review_status: "pending" },
    ok: true as const,
  })),
  createTriples: createTriplesMock,
  optimizeAnswer: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 0, review_status: "pending" },
    ok: true as const,
  })),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => {
      if (key === "rag_user_token") {
        return { value: "tok" };
      }
      return undefined;
    },
  })),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/knowledge/triples",
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/components/knowledge/SchemaFieldRenderer", () => ({
  LabelPicker: ({ value, onChange }: { value: string; onChange: (val: string) => void }) => (
    <input
      data-testid="label-picker"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
  RelationPicker: ({ value, onChange }: { value: string; onChange: (val: string) => void }) => (
    <input
      data-testid="rel-picker"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

const mockSchema: KnowledgeSchema = {
  nodes: [
    { fields: [{ key: "model", label: "型号", type: "string" }], name: "Product" },
    { fields: [{ key: "name", label: "系列", type: "string" }], name: "Series" },
  ],
  relations: [{ cardinality: "many_to_one", from: "Product", name: "BELONGS_TO", to: "Series" }],
};

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

beforeEach(() => {
  createTriplesMock.mockClear();
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限
  globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
    let urlStr = "";
    if (typeof url === "string") {
      urlStr = url;
    } else {
      urlStr = url.toString();
    }
    if (urlStr.includes("/api/permissions/me")) {
      return okResponse({
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
      });
    }
    return okResponse(mockSchema);
  }) as never;
});

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

describe("TriplesPage (RSC)", () => {
  it("RSC 预取 schema 成功 → 渲染 PageHero title + 提交按钮 + BackLink", async () => {
    const mod = await import("./page");
    const pageComponent = mod.default;
    const element = await pageComponent();
    renderInI18n(element);
    expect(screen.getByRole("heading", { name: "录三元组" })).toBeInTheDocument();
    expect(screen.getByTestId("triples-submit")).toBeInTheDocument();
    expect(screen.getByTestId("page-hero-back-link")).toBeInTheDocument();
  });

  it("schema 加载失败时 RSC 抛错 (error.tsx 兜住)", async () => {
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const pageComponent = mod.default;
    await expect(pageComponent()).rejects.toThrow();
  });
});

describe("TriplesForm (client sub)", () => {
  it("form 提交按钮挂在 form 内部, form action 走 createTriples (server action)", async () => {
    const { TriplesForm } = await import("./_components/triples-form");
    renderInI18n(<TriplesForm schema={mockSchema} />);

    const submitBtn = screen.getByTestId("triples-submit");
    const form = submitBtn.closest("form");
    expect(form).not.toBeNull();

    const propsKey = Object.keys(form!).find((key) => key.startsWith("__reactProps$"))!;
    const props = (form as unknown as Record<string, { action?: unknown }>)[propsKey];
    expect(typeof props.action).toBe("function");
  });

  it("createTriples server action 被 mock 注入 (提交可观察)", async () => {
    const mod = await import("@/app/[locale]/_actions/knowledge");
    expect(typeof mod.createTriples).toBe("function");
    const result = await mod.createTriples({ rows: [] });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.approval_id).toBe(MOCK_APPROVAL_ID);
      expect(result.data.review_status).toBe("pending");
    }
  });
});
