// 单指标柱状图 (纯 CSS, 不装 chart 库)

// ──────────── 局部常量 ────────────
/** 高分阈值 @shared */
const SCORE_HIGH = 0.7;
/** 中分阈值 @shared */
const SCORE_MEDIUM = 0.4;
/** 进度条最小值 @shared */
const BAR_MIN = 0;
/** 百分比最大值 @shared */
const PERCENTAGE_MAX = 100;
/** 数值小数位 @shared */
const DECIMAL_PLACES = 3;
/** 默认最大值 @shared */
const DEFAULT_MAX = 1;

/** MetricBar props
 * @property label - 指标标签
 * @property value - 指标值
 * @property max - 最大值 (默认 1)
 * @shared
 */
interface Props {
  label: string;
  value: number | null;
  max?: number;
}

/** 根据数值返回颜色类名
 * @param val - 数值
 * @returns Tailwind 颜色类名
 * @shared
 */
const getColor = (val: number): string => {
  if (val >= SCORE_HIGH) {
    return "bg-moss";
  }
  if (val >= SCORE_MEDIUM) {
    return "bg-status-warning";
  }
  return "bg-destructive";
};

/** MetricBar - 单指标柱状图 (纯 CSS)
 * @param label - 指标标签
 * @param value - 指标值
 * @param max - 最大值
 * @returns 柱状图 JSX
 * @shared
 */
export const MetricBar = ({ label, value, max = DEFAULT_MAX }: Props) => {
  let pct = BAR_MIN;
  if (value != null) {
    pct = Math.round((value / max) * PERCENTAGE_MAX);
  }

  let barColor = "bg-muted";
  if (value != null) {
    barColor = getColor(value);
  }

  let displayValue = "—";
  if (value != null) {
    displayValue = value.toFixed(DECIMAL_PLACES);
  }

  return (
    <div className="flex items-center gap-3">
      <span className="w-36 shrink-0 text-sm text-muted-foreground">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="num w-12 shrink-0 text-right text-sm font-medium">{displayValue}</span>
    </div>
  );
};
