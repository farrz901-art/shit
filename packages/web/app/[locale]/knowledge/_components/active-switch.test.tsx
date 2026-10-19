import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

let mockPathname = "/knowledge/documents";
// (2026-06-26 FE-001) ActiveSwitch 改用 @/i18n/navigation 的 usePathname
// (locale-stripped), mock 必须跟 component import 一致.
vi.mock("@/i18n/navigation", () => ({
  usePathname: () => mockPathname,
}));

// Mock 子组件: 不渲染真实 Select, 只标记 testid 区分
// (2026-06-15) ActiveSwitch 挪到本目录 (app/[locale]/knowledge/_components/),
// 子组件 DatasetSwitcher/DomainSwitcher 仍在 components/knowledge/, mock 改绝对路径
vi.mock("@/components/knowledge/DatasetSwitcher", () => ({
  DatasetSwitcher: () => <div data-testid="dataset-switcher" />,
}));
vi.mock("@/components/knowledge/DomainSwitcher", () => ({
  DomainSwitcher: () => <div data-testid="domain-switcher" />,
}));

import { ActiveSwitch } from "./active-switch";

describe("ActiveSwitch", () => {
  beforeEach(() => {
    mockPathname = "/knowledge/documents";
  });

  it("/knowledge/documents → 渲染 DatasetSwitcher", () => {
    mockPathname = "/knowledge/documents";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
    expect(screen.queryByTestId("domain-switcher")).not.toBeInTheDocument();
  });

  it("/knowledge/qa → 渲染 DatasetSwitcher", () => {
    mockPathname = "/knowledge/qa";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("/knowledge/documents/import → 渲染 DatasetSwitcher", () => {
    mockPathname = "/knowledge/documents/import";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("dataset-switcher")).toBeInTheDocument();
  });

  it("/knowledge/graph → 渲染 DomainSwitcher", () => {
    mockPathname = "/knowledge/graph";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
    expect(screen.queryByTestId("dataset-switcher")).not.toBeInTheDocument();
  });

  it("/knowledge/triples → 渲染 DomainSwitcher", () => {
    mockPathname = "/knowledge/triples";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("/knowledge/batch → 渲染 DomainSwitcher", () => {
    mockPathname = "/knowledge/batch";
    render(<ActiveSwitch />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });

  it("(FE-001) /en/knowledge/graph 也必须渲染 DomainSwitcher (旧实现因含 locale 前缀失效)", () => {
    // (2026-06-26 FE-001 critical) 旧实现从 next/navigation 引 usePathname,
    // 返回 /en/knowledge/graph (含 locale 前缀), startsWith("/knowledge/graph") 永 false.
    // 修复后从 @/i18n/navigation 引, 返回 locale-stripped 路径, en locale 下也正确匹配.
    // 这里 mock 模拟 next-intl 行为: usePathname 直接返回 stripped path (strip locale 前缀).
    mockPathname = "/knowledge/graph"; // mock 模拟 stripped 结果
    render(<ActiveSwitch />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
    expect(screen.queryByTestId("dataset-switcher")).not.toBeInTheDocument();
  });

  it("(FE-001) /zh/knowledge/triples 也渲染 DomainSwitcher (locale-stripped 后匹配)", () => {
    // mock 模拟 stripped path, 跟真实 next-intl usePathname 行为一致.
    mockPathname = "/knowledge/triples"; // strip "/zh" 前缀
    render(<ActiveSwitch />);
    expect(screen.getByTestId("domain-switcher")).toBeInTheDocument();
  });
});
