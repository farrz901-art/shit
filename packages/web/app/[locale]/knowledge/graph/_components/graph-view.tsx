"use client";
// 知识图谱入口 client 子组件 (2026-06-12) — 接 RSC 预取的 stats.
// 仿老 Neo4j tab: 节点/关系统计卡 + 录入入口 (录三元组 / 批量导入).
//   切换 domain 时由父级通过 router.refresh() 重新触发 RSC fetch.
// (2026-06-28) Phase3 Task3.5: 用 StatsGrid + EntryCardGrid wrapper 消 14+14 行重复
import { Network, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EntryCardGrid, ENTRY_COLS_TWO } from "@/components/common/display/entry-card-grid";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { SchemaBrowser } from "@/components/knowledge/schema-browser";
import { StatsGrid, STATS_COLS_TWO } from "@/components/common/display/stats-grid";
import { DELAY } from "@/lib/motion";
import { useToggle } from "react-use";
import { useTranslations } from "next-intl";

/**
 * GraphStats - 知识图谱统计
 * @property nodes - 节点数
 * @property relations - 关系数
 */
export interface GraphStats {
  nodes: number;
  relations: number;
}

/**
 * GraphView 组件属性
 * @property stats - 知识图谱统计
 */
interface Props {
  stats: GraphStats;
}

/**
 * GraphView - 知识图谱入口 client 子组件
 * @param props.stats - 图谱统计
 * @client-bff
 */
export const GraphView = ({ stats }: Props) => {
  const tr = useTranslations();
  const [schemaOpen, toggleSchemaOpen] = useToggle(false);

  return (
    <div className="h-full overflow-y-auto space-y-6 pb-8">
      {/* Hero + 右侧 actions (schema 浏览器; DomainSwitcher 由 layout ActiveSwitch 提供) */}
      <PageHero
        eyebrow="Knowledge"
        title={tr("知识图谱")}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSchemaOpen}
            data-testid="schema-browser-trigger"
          >
            ?
          </Button>
        }
      />
      <Reveal delay={DELAY.heroStep2}>
        <StatsGrid
          columns={STATS_COLS_TWO}
          items={[
            {
              accent: "clay",
              hint: tr("点击查看全部 →"),
              href: "/knowledge/nodes",
              label: tr("节点数"),
              value: stats.nodes,
            },
            {
              accent: "moss",
              hint: tr("点击查看全部 →"),
              href: "/knowledge/relations",
              label: tr("关系数"),
              value: stats.relations,
            },
          ]}
        />
      </Reveal>

      {/* 录入入口: 仿老 Neo4j tab 的 2 个 EntryCard */}
      <Reveal delay={DELAY.primary}>
        <EntryCardGrid
          columns={ENTRY_COLS_TWO}
          items={[
            {
              desc: tr("实体-关系写入 Neo4j"),
              href: "/knowledge/triples",
              icon: <Network className="h-6 w-6" />,
              title: tr("录三元组"),
            },
            {
              desc: tr("后台批量任务"),
              href: "/knowledge/batch",
              icon: <Package className="h-6 w-6" />,
              title: tr("批量导入"),
            },
          ]}
        />
      </Reveal>

      <SchemaBrowser open={schemaOpen} onOpenChange={toggleSchemaOpen} />
    </div>
  );
};
