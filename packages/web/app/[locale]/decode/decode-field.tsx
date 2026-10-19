// 解码字段展示 (2026-06-10)
import { CSS_EASE_STR } from "@/components/motion/animated";
import { cn } from "@/lib/utils";

/** 解码字段展示组件 props
 * @property keyName - 字段键名
 * @property val - 字段值
 * @shared
 */
interface Props {
  keyName: string;
  val: unknown;
}

/** 格式化未知类型值为字符串
 * @param val - 待格式化值
 * @returns 格式化后字符串
 * @shared
 */
const formatVal = (val: unknown): string => {
  if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
    return String(val);
  }
  return JSON.stringify(val);
};

/** DecodeField - 解码字段展示组件 */
export const DecodeField = ({ keyName, val }: Props) => {
  const base = keyName.replace(/_(?:zh|en|raw)$/, "");
  const suffixMatch = keyName.match(/_(?<suffix>zh|en|raw)$/);
  const suffix = suffixMatch?.groups?.suffix;
  const isRich = suffix === "zh" || suffix === "en" || suffix === "raw";
  const vStr = formatVal(val);

  let fieldClass = "font-medium text-foreground";
  if (isRich) {
    fieldClass = "text-muted-foreground";
  }

  return (
    <div className="group relative overflow-hidden rounded-lg border border-border/50 bg-card px-4 py-3 transition-colors duration-300 hover:border-ink/30 hover:bg-card/80">
      <div className="flex items-baseline justify-between gap-3">
        <div className="eyebrow shrink-0">
          {base}
          {suffix && <span className="ml-1 text-clay">·{suffix}</span>}
        </div>
        <div
          className={cn(
            "num truncate text-right text-base",
            fieldClass,
            suffix === "zh" && "text-foreground",
          )}
          title={vStr}
        >
          {vStr}
        </div>
      </div>
      <div
        className="absolute bottom-0 left-0 h-px w-0 bg-clay transition-all duration-500 group-hover:w-full"
        style={{ transitionTimingFunction: CSS_EASE_STR.outExpo }}
      />
    </div>
  );
};
