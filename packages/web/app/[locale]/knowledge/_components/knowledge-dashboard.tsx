"use client";
// 知识库根 dashboard client 子组件 (2026-06-12, Task 21) — 接 RSC 预取的 stats.
// 仿老两个 tab (Dify 向量库 + Neo4j 图谱) 合成一个根 dashboard: 4 张 stat 卡 + 4 张录入入口卡.
//   复用 <PageHero> / <StatCard> / <EntryCard> 跟 Task 15 graph / Task 14 documents 同型.
// (2026-06-28) Phase3 Task3.5: 用 StatsGrid + EntryCardGrid wrapper 消 14+14 行重复
import { Download, FileUp, MessageSquare, Network } from "lucide-react";
import { ENTRY_COLS_FOUR, EntryCardGrid } from "@/components/common/display/entry-card-grid";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { STATS_COLS_FOUR, StatsGrid } from "@/components/common/display/stats-grid";
import { DELAY } from "@/lib/motion";
import { useTranslations } from "next-intl";

/** KnowledgeStats - 知识库统计数据类型 */
export interface KnowledgeStats {
  /** Dify 数据集数 */
  datasets: number;
  /** Dify 文档数 (跨所有数据集求和) */
  documents: number;
  /** Neo4j 节点数 */
  nodes: number;
  /** Neo4j 关系数 */
  relations: number;
}

/** Props - KnowledgeDashboard 组件属性 */
interface Props {
  /** 知识库统计数据 */
  stats: KnowledgeStats;
}

/** KnowledgeDashboard - 知识库根 dashboard 客户端组件, 展示 4 张 stat 卡 + 4 张录入入口卡
 * @client-bff
 */
export const KnowledgeDashboard = ({ stats }: Props) => {
  const tr = useTranslations();

  return (
    <div className="h-full overflow-y-auto space-y-8 pb-8">
      {/* Hero */}
      <PageHero eyebrow="Knowledge" title={tr("知识库")} />

      {/* 4 张 stat 卡: datasets / documents (Dify) + nodes / relations (Neo4j) */}
      <Reveal delay={DELAY.heroStep1}>
        <StatsGrid
          columns={STATS_COLS_FOUR}
          items={[
            {
              accent: "ochre",
              hint: tr("点击查看全部 →"),
              href: "/knowledge/datasets",
              label: tr("数据集"),
              value: stats.datasets,
            },
            {
              accent: "indigo",
              hint: tr("点击查看全部 →"),
              href: "/knowledge/documents",
              label: tr("文档数"),
              value: stats.documents,
            },
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

      {/* 4 张录入入口: 录三元组 / 批量导入 (Neo4j) + 录 QA / 批量导入文档 (Dify) */}
      <Reveal delay={DELAY.heroStep3}>
        <EntryCardGrid
          columns={ENTRY_COLS_FOUR}
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
              icon: <FileUp className="h-6 w-6" />,
              title: tr("批量导入"),
            },
            {
              desc: tr("表单写入 Dify 向量库"),
              href: "/knowledge/qa",
              icon: <MessageSquare className="h-6 w-6" />,
              title: tr("录 QA 对"),
            },
            {
              desc: tr("Excel / JSON 模板批量导入"),
              href: "/knowledge/documents/import",
              icon: <Download className="h-6 w-6" />,
              title: tr("批量导入文档"),
            },
          ]}
        />
      </Reveal>
    </div>
  );
};
