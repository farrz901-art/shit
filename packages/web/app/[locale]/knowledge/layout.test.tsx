import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

let mockPathname = "/knowledge/documents";
// (2026-06-26 FE-001 critical) ActiveSwitch 从 @/i18n/navigation 引 usePathname
// (locale-stripped), layout 测试 mock 必须跟 component import 一致. 旧实现 mock
// "next/navigation" 永远不命中 (ActiveSwitch 不引 next/navigation), pathname undefined,
// /knowledge/graph 分支永远走 DatasetSwitcher, DomainSwitcher 永不渲染.
vi.mock("@/i18n/navigation", () => ({
  usePathname: () => mockPathname,
}));

// Mock switcher 子组件避免 zustand/useEffect 链
vi.mock("@/components/knowledge/DatasetSwitcher", () => ({
  DatasetSwitcher: () => <div data-testid="dataset-switcher" />,
}));
vi.mock("@/components/knowledge/DomainSwitcher", () => ({
  DomainSwitcher: () => <div data-testid="domain-switcher" />,
}));

import KnowledgeLayout from "./layout";

describe("KnowledgeLayout", () => {
  it("渲染 KnowledgeTabs", () => {
    render(
      <KnowledgeLayout>
        <div data-testid="child" />
      </KnowledgeLayout>,
    );
    expect(screen.getByTestId("knowledge-tabs")).toBeInTheDocument();
  });

  it("/knowledge/documents → 渲染 DatasetSwitcher", () => {
    mockPathname = "/knowledge/documents";
    render(
      <KnowledgeLayout>
        <div data-testid="child" />
      </KnowledgeLayout>,
    );
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("/knowledge/graph → 渲染 DomainSwitcher", () => {
    mockPathname = "/knowledge/graph";
    render(
      <KnowledgeLayout>
        <div data-testid="child" />
      </KnowledgeLayout>,
    );
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("children 透传渲染", () => {
    render(
      <KnowledgeLayout>
        <div data-testid="child" />
      </KnowledgeLayout>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});
