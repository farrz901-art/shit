/**
 * 引用来源面板 — 展示 assistant 回答引用到的 Dify dataset 文档片段
 * 列表渲染: documentName (顶部) + datasetName (来源 dataset) + score (相似度 2 位小数) + summary + content
 *   - score 字段可能缺失 (cite.score == null) → 不显示
 *   - summary 字段可选 → 不显示
 *   - content 截断 3 行 (line-clamp-3), 用户点开看完整 (AppCollapsible 外层包裹)
 * 注: idx 作 React key (citation 无稳定 id), 仅作渲染用不参与逻辑
 */
import type { Citation } from "@/lib/chat/types";
import { TWO } from "@/const";

/**
 * 引用来源面板 — 展示 Dify dataset 文档片段列表
 * @param props.citations 引用来源数组
 * @returns JSX 元素
 * @shared
 */
export const CitationPanel = ({ citations }: { citations: Citation[] }) => (
  <div className="mt-2 space-y-2">
    {citations.map((cite, idx) => (
      <div key={idx} className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2">
        <div className="flex items-baseline justify-between text-xs text-muted-foreground">
          <span className="truncate font-medium">{cite.documentName}</span>
          {cite.score != null && (
            <span className="num text-clay">score {cite.score.toFixed(TWO)}</span>
          )}
        </div>
        {cite.datasetName && (
          <div className="mt-0.5 text-[11px] text-muted-foreground/70">
            来自: {cite.datasetName}
          </div>
        )}
        {cite.summary && <div className="mt-1 text-sm italic">{cite.summary}</div>}
        <p className="mt-1 line-clamp-3 text-sm">{cite.content}</p>
      </div>
    ))}
  </div>
);
