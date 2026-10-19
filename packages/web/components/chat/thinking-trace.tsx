/**
 * 思考链路追踪 (Thinking Trace) — 展示 Dify workflow / agent 各节点执行步骤
 * 数据: Step[] { node: 节点名, status: started/finished, detail?: 补充说明 }
 * 渲染: Badge 状态色 (started=warning/finished=moss) + 节点名 + 补充
 * 配色: STEP_STATUS_CLASS lookup map (2026-06-28 P4 refactor: 替 if/else 链, 满足业务 enum 走 lookup 规约)
 * 用途: 调试时快速定位卡在哪一步 / 跟 Dify workflow log 对照
 */
import { Badge } from "@/components/ui/badge";

/**
 * 思考追踪步骤数据结构
 * @shared
 */
interface Step {
  node: string;
  status: "started" | "finished";
  detail?: string;
}

// 状态 → 配色 className (2026-06-28 P4 refactor): 替 if/else 链, 满足 §业务 enum 走 lookup 规约
/**
 * 步骤状态 → Tailwind 配色 class 查找表
 * @shared
 */
const STEP_STATUS_CLASS: Record<Step["status"], string> = {
  finished: "border-moss/40 text-moss",
  started: "border-status-warning/40 text-status-warning",
};

/**
 * 渲染单个步骤行 (Badge 状态色 + 节点名 + 补充说明)
 * @param step 步骤数据
 * @param idx 步骤序号
 * @returns JSX 元素
 * @client-bff
 */
const renderStep = (step: Step, idx: number) => (
  <div key={idx} className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs">
    <Badge variant="outline" className={STEP_STATUS_CLASS[step.status]}>
      {step.status}
    </Badge>
    <span className="num text-muted-foreground">{step.node}</span>
    {step.detail && <span className="text-muted-foreground/70">· {step.detail}</span>}
  </div>
);

/**
 * 思考链路追踪组件 — 展示 Dify workflow 各节点执行步骤
 * @param props.steps 步骤数组 (node + status + detail)
 * @returns JSX 元素
 * @shared
 */
export const ThinkingTrace = ({ steps }: { steps: Step[] }) => (
  <div className="mt-2 space-y-1">{steps.map(renderStep)}</div>
);
