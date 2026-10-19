// 知识库模块 layout (2026-06-10 redesign) — Tabs + ActiveSwitch 提到上层
//   所有 /knowledge/* 页面共用同一处 tab + switch, 父子页自动继承
//   EnvBadge / HealthDot 已在根 header, SchemaBrowser 在 /graph 页 hero actions
// (2026-06-15) ErrorBoundary 升 common/; ActiveSwitch 挪到本目录 _components/ (跟消费方同域, 不进 common)
import { ActiveSwitch } from "./_components/active-switch";
import { ErrorBoundary } from "@/components/common/feedback/app-error-boundary";
import { KnowledgeTabs } from "@/components/knowledge/knowledge-tabs";
import type { ReactNode } from "react";

/**
 * KnowledgeLayout - 知识库模块 layout
 * @param props.children - 子页面内容
 * @server-only
 */
export default function KnowledgeLayout({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <div className="flex h-full flex-col gap-6">
        {/* Tabs + ActiveSwitch: 顶部一行, 父子页共用 */}
        <div className="flex items-center justify-between gap-4">
          <KnowledgeTabs />
          <ActiveSwitch />
        </div>
        {children}
      </div>
    </ErrorBoundary>
  );
}
