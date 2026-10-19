// SystemResourcesSection: 主机资源面板 (2026-06-15)
// 从 health-client.tsx 拆出, 含 CpuColumn / MemoryColumn / GpuRow / GpuColumn
// 视觉: 全宽 3 列 (CPU/内存/GPU) 配进度条 + 大数字
// (2026-06-29 P2) CVA 化: resourceLevelVariants 1 个 cva() 替代 4 个 if 链 (cpu/mem/gpu/statusText)
//   - 改前: cpuProgressColor / memProgressColor / gpuProgressColor 3 个 if 链 + statusTextColor 1 个三元, 4 个函数同模式重复
//   - 改后: resourceLevelVariants(level: "ok" | "warn" | "crit" | "muted") 1 个 cva, 4 处复用
"use client";
import { Cpu, MemoryStick } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { CheckResult } from "@/lib/api/health";
import { Progress } from "@/components/ui/progress";
import { cva } from "class-variance-authority";
import { useTranslations } from "next-intl";

// === 常量 ===
/** 进度条默认值 */
const PROGRESS_DEFAULT = 0;
/** 百分比显示小数位数 */
const PCT_DECIMALS = 1;
/** 空值数量 */
const EMPTY_COUNT = 0;
/** CPU 警告阈值 (%) */
const CPU_WARN_PCT = 60;
/** CPU 严重阈值 (%) */
const CPU_CRIT_PCT = 85;
/** 内存警告阈值 (%) */
const MEM_WARN_PCT = 70;
/** 内存严重阈值 (%) */
const MEM_CRIT_PCT = 90;
/** GPU 警告阈值 (%) */
const GPU_WARN_PCT = 60;
/** GPU 严重阈值 (%) */
const GPU_CRIT_PCT = 85;

// === 资源等级 → 颜色 ===
// 4 个旧 if 链 (cpuProgressColor / memProgressColor / gpuProgressColor / statusTextColor) 合并为 1 个 cva
// level 推算: undefined → muted, > CRIT → crit, > WARN → warn, else → ok
/** resourceLevelVariants - 资源等级 → 颜色 CVA 变体
 * 4 个旧 if 链合并为 1 个 cva, 供 Progress indicator / 文字色复用
 * @shared
 */
const resourceLevelVariants = cva("", {
  defaultVariants: { level: "ok" },
  variants: {
    level: {
      crit: "bg-destructive text-destructive",
      muted: "bg-muted text-muted-foreground",
      ok: "bg-moss text-moss",
      warn: "bg-ochre text-ochre",
    },
  },
});

/** ResourceLevel - 资源等级联合类型 */
type ResourceLevel = "ok" | "warn" | "crit" | "muted";

// 阈值 → 资源等级: 通用函数, cpu/mem/gpu 3 处复用
// 改前 3 个 if 链 (cpu/mem/gpuLevel) 各 4-5 行, 改后 1 个函数 + 3 个阈值常量配置
// undefined 一律走 muted (项目内只此 1 种 fallback, 抽参无意义, 写死在函数体)

/** pickLevel - 根据百分比和阈值计算资源等级
 * @param pct 资源使用百分比 (undefined → muted)
 * @param critThreshold 严重阈值
 * @param warnThreshold 警告阈值
 * @returns 资源等级
 * @shared
 */
const pickLevel = (
  pct: number | undefined,
  critThreshold: number,
  warnThreshold: number,
): ResourceLevel => {
  if (pct === undefined) {
    return "muted";
  }
  if (pct > critThreshold) {
    return "crit";
  }
  if (pct > warnThreshold) {
    return "warn";
  }
  return "ok";
};

/** cpuLevel - 根据 CPU 百分比计算资源等级
 * @param cpuPct CPU 使用率 (undefined → muted)
 * @returns 资源等级
 * @shared
 */
const cpuLevel = (cpuPct: number | undefined): ResourceLevel =>
  pickLevel(cpuPct, CPU_CRIT_PCT, CPU_WARN_PCT);
/** memLevel - 根据内存百分比计算资源等级
 * @param memPct 内存使用率 (undefined → muted)
 * @returns 资源等级
 * @shared
 */
const memLevel = (memPct: number | undefined): ResourceLevel =>
  pickLevel(memPct, MEM_CRIT_PCT, MEM_WARN_PCT);
/** gpuLevel - 根据 GPU 利用率计算资源等级
 * @param utilPct GPU 利用率
 * @returns 资源等级
 * @shared
 */
const gpuLevel = (utilPct: number): ResourceLevel => pickLevel(utilPct, GPU_CRIT_PCT, GPU_WARN_PCT);

// === Sub-columns ===

/** CpuColumn - CPU 资源信息列
 * @shared
 */
const CpuColumn = ({ cpuPct }: { cpuPct: number | undefined }) => (
  <div className="space-y-2 bg-card/40 p-5">
    <div className="flex items-baseline justify-between">
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground">
        <Cpu className="h-3 w-3" strokeWidth={1.5} />
        CPU
      </div>
      <div className="num text-2xl font-light tabular-nums">
        {cpuPct !== undefined ? cpuPct.toFixed(PCT_DECIMALS) : "—"}
        <span className="ml-0.5 text-sm text-muted-foreground">%</span>
      </div>
    </div>
    <Progress
      value={cpuPct ?? PROGRESS_DEFAULT}
      className="h-1.5 bg-ink/5"
      indicatorClassName={resourceLevelVariants({ level: cpuLevel(cpuPct) })}
    />
  </div>
);

/** MemoryColumn - 内存资源信息列
 * @shared
 */
const MemoryColumn = ({
  memPct,
  memUsedMb,
  memTotalMb,
  translate,
}: {
  memPct: number | undefined;
  memUsedMb: number | undefined;
  memTotalMb: number | undefined;
  translate: ReturnType<typeof useTranslations>;
}) => (
  <div className="space-y-2 bg-card/40 p-5">
    <div className="flex items-baseline justify-between">
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground">
        <MemoryStick className="h-3 w-3" strokeWidth={1.5} />
        {translate("内存")}
      </div>
      <div className="num text-2xl font-light tabular-nums">
        {memPct !== undefined ? memPct.toFixed(PCT_DECIMALS) : "—"}
        <span className="ml-0.5 text-sm text-muted-foreground">%</span>
      </div>
    </div>
    <Progress
      value={memPct ?? PROGRESS_DEFAULT}
      className="h-1.5 bg-ink/5"
      indicatorClassName={resourceLevelVariants({ level: memLevel(memPct) })}
    />
    {memUsedMb !== undefined && memTotalMb !== undefined && (
      <div className="num text-[10px] tabular-nums text-muted-foreground/70">
        {memUsedMb.toLocaleString()} / {memTotalMb.toLocaleString()} MB
      </div>
    )}
  </div>
);

/** GpuRow - 单 GPU 行展示组件
 * @shared
 */
const GpuRow = ({ gpuData, index }: { gpuData: GpuItem; index: number }) => (
  <div className="space-y-1">
    <div className="flex items-baseline justify-between gap-2">
      <span className="num text-[11px] tabular-nums text-muted-foreground">#{index}</span>
      <span className="num text-[11px] tabular-nums text-foreground truncate">
        {gpuData.util_pct}%
      </span>
    </div>
    <Progress
      value={gpuData.util_pct}
      className="h-1 bg-ink/5"
      indicatorClassName={resourceLevelVariants({ level: gpuLevel(gpuData.util_pct) })}
    />
    <div className="num text-[10px] tabular-nums text-muted-foreground/60 truncate">
      {gpuData.name}
      <span className="mx-1 opacity-30">·</span>
      {gpuData.mem_used_mb}/{gpuData.mem_total_mb} MB
    </div>
  </div>
);

/** GpuColumn - GPU 资源列表列组件
 * @shared
 */
const GpuColumn = ({
  gpuList,
  translate,
}: {
  gpuList: GpuItem[];
  translate: ReturnType<typeof useTranslations>;
}) => (
  <div className="space-y-2 bg-card/40 p-5">
    <div className="flex items-baseline justify-between">
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-[0.15em] text-muted-foreground">
        GPU
        {gpuList.length > EMPTY_COUNT && <span className="num opacity-50">×{gpuList.length}</span>}
      </div>
    </div>
    {gpuList.length === EMPTY_COUNT ? (
      <p className="num text-xs text-muted-foreground/70">{translate("无 GPU / 驱动未安装")}</p>
    ) : (
      <div className="space-y-2">
        {gpuList.map((gpuData, index) => (
          <GpuRow key={index} gpuData={gpuData} index={index} />
        ))}
      </div>
    )}
  </div>
);

// === GPU 类型 ===

/** GpuItem - GPU 信息类型 */
interface GpuItem {
  /** GPU 名称 */
  name: string;
  /** GPU 利用率 (%) */
  util_pct: number;
  /** GPU 已用显存 (MB) */
  mem_used_mb: number;
  /** GPU 总显存 (MB) */
  mem_total_mb: number;
}

// === SystemResourcesSection ===

/** SystemResourcesSectionProps - 主机资源面板属性 */
export interface SystemResourcesSectionProps {
  /** 系统健康检查结果 (含 cpu/mem/gpu extra 字段) */
  system: CheckResult;
}

/** SystemResourcesSection - 主机资源面板组件 (CPU / 内存 / GPU 三列) */
export const SystemResourcesSection = ({ system }: SystemResourcesSectionProps) => {
  const translate = useTranslations();
  const cpuPct = system.extra.cpu_pct as number | undefined;
  const memPct = system.extra.mem_pct as number | undefined;
  const memUsedMb = system.extra.mem_used_mb as number | undefined;
  const memTotalMb = system.extra.mem_total_mb as number | undefined;
  const gpuList = (system.extra.gpu ?? []) as GpuItem[];
  const isOk = system.status === "ok";

  return (
    <section
      aria-label="system resources"
      data-testid="health-section"
      data-section-title="system"
      className="rounded-lg border border-border/60 bg-card/40"
    >
      <div className="border-b border-border/60 px-5 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu
              className={`h-4 w-4 ${resourceLevelVariants({ level: isOk ? "ok" : "crit" })}`}
              strokeWidth={1.5}
            />
            <h2 className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              {translate("主机资源")}
            </h2>
          </div>
          <Badge variant={isOk ? "secondary" : "destructive"}>{system.status}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-px bg-border/40 md:grid-cols-3">
        <CpuColumn cpuPct={cpuPct} />
        <MemoryColumn
          memPct={memPct}
          memUsedMb={memUsedMb}
          memTotalMb={memTotalMb}
          translate={translate}
        />
        <GpuColumn gpuList={gpuList} translate={translate} />
      </div>

      {system.error && (
        <details className="border-t border-border/60 bg-destructive/5 px-5 py-3">
          <summary className="cursor-pointer text-xs uppercase tracking-[0.15em] text-destructive">
            error
          </summary>
          <pre className="num mt-2 overflow-x-auto rounded bg-destructive/10 p-2 text-xs text-destructive">
            {system.error}
          </pre>
        </details>
      )}
    </section>
  );
};
