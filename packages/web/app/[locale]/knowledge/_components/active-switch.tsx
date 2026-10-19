"use client";
// 知识库上下文 Switch (2026-06-15) — 从 components/knowledge/ActiveSwitch 挪到本目录
// 跟消费方 (layout.tsx) 同域, 简化依赖路径. 知识内 routing, 仍绑 6 个 /knowledge/* path
import { DatasetSwitcher } from "@/components/knowledge/dataset-switcher";
import { DomainSwitcher } from "@/components/knowledge/domain-switcher";
// (2026-06-26 FE-001 critical) 改用 @/i18n/navigation 的 usePathname,
// 返回 locale-stripped path (如 /knowledge/graph 而非 /zh/knowledge/graph).
// 之前从 next/navigation 引, en locale 下 startsWith("/knowledge/graph") 永远 false,
// DomainSwitcher 永不渲染, 知识图谱功能受损.
import { usePathname } from "@/i18n/navigation";

/** ActiveSwitch - 知识库上下文 Switch 组件, 根据路径切换 DatasetSwitcher / DomainSwitcher
 * @client-bff
 */
export const ActiveSwitch = () => {
  const pathname = usePathname();
  // 向量库侧用 DatasetSwitcher, 知识图谱侧用 DomainSwitcher
  if (
    pathname?.startsWith("/knowledge/graph") ||
    pathname?.startsWith("/knowledge/triples") ||
    pathname?.startsWith("/knowledge/batch") ||
    pathname?.startsWith("/knowledge/nodes") ||
    pathname?.startsWith("/knowledge/relations")
  ) {
    return <DomainSwitcher />;
  }
  return <DatasetSwitcher />;
};
