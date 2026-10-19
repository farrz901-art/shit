"use client";
// 文档入口页 client 子组件 (2026-06-12) — 接 RSC 灌的 stats, 管 datasetId (zustand persist 拿不到).
// 仿老 Dify tab: 文档数 + 数据集 统计 (RSC 预取) + 录入入口卡 (2 张)
// (2026-06-28) Phase3 Task3.5: 用 StatsGrid + EntryCardGrid wrapper 消 14+14 行重复
import { Download, MessageSquare } from "lucide-react";
import { EntryCardGrid, ENTRY_COLS_TWO } from "@/components/common/display/entry-card-grid";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { StatsGrid, STATS_COLS_TWO } from "@/components/common/display/stats-grid";
import { DELAY } from "@/lib/motion";
import { useAppStore } from "@/lib/store/app-store";
import { useTranslations } from "next-intl";

/** DocumentsStats - 文档入口页统计数据 */
export interface DocumentsStats {
  datasets: number;
  documents: number;
}

/** Props - DocumentsEntry 组件属性 */
interface Props {
  /** 文档入口页统计数据 */
  stats: DocumentsStats;
}

/** DocumentsEntry - 文档入口页客户端组件, 展示文档数/数据集统计 + 录入入口卡
 * @client-bff
 */
export const DocumentsEntry = ({ stats }: Props) => {
  const tr = useTranslations();
  const datasetId = useAppStore((store) => store.datasetId);

  // 文档数卡: 有 datasetId 时可跳详情; 无时不可点 + 显示提示
  const documentHref = datasetId ? `/knowledge/dataset-documents/${datasetId}` : undefined;
  const documentHint = datasetId ? undefined : tr("请先选 dataset →");

  return (
    <div className="h-full overflow-y-auto space-y-8">
      {/* Hero */}
      <PageHero eyebrow="Vector" title={tr("向量库")} />

      {/* 仿老 Dify tab: 文档数 + 数据集 统计 */}
      <Reveal delay={DELAY.heroStep1}>
        <StatsGrid
          columns={STATS_COLS_TWO}
          items={[
            {
              accent: "indigo",
              hint: documentHint,
              href: documentHref,
              label: tr("文档数"),
              value: stats.documents,
            },
            {
              accent: "ochre",
              href: "/knowledge/datasets",
              label: tr("数据集"),
              value: stats.datasets,
            },
          ]}
        />
      </Reveal>

      {/* 仿老 Dify tab: 录入入口 (2 张卡) */}
      <Reveal delay={DELAY.heroStep2}>
        <EntryCardGrid
          columns={ENTRY_COLS_TWO}
          items={[
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
              title: tr("批量导入"),
            },
          ]}
        />
      </Reveal>
    </div>
  );
};
