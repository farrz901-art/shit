"use client";
// pre-analysis 上传弹框 (2026-07-03) — 替列表页 FileDropzone
// 3 段式: 选文件 → 文件信息+清空 → 上传 (成功 toast + 500ms 关弹框刷新列表, 失败保留弹框)
// (2026-07-06) 高级选项折叠区: AppSelect 后端选择 + 动态参数 + AppTooltip 帮助图标

import { useEffect, useState } from "react";
import { FileText, HelpCircle, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "next-intl";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import {
  AppRadioGroup,
  type AppRadioOption,
  AppSelect,
  type AppSelectOption,
} from "@/components/common/input";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { Button } from "@/components/ui/button";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { fmtSize } from "@/lib/format";
import {
  preAnalysisUpload,
  type ChapterExtractionConfig,
  type TableExtractionConfig,
} from "@/lib/api/pre-analysis";

/** 弹框自动关闭延迟 (毫秒) */
const DIALOG_CLOSE_DELAY_MS = 500;
/** 上传 PDF 文件大小上限 (MB) */
const PDF_MAX_SIZE_MB = 100;

// (2026-07-06) 高级选项: 硬编码 zh+en 合一 label/tooltip, 不进 i18n
// (2026-07-07) 表格提取器改 RadioGroup 后, BACKEND_OPTIONS 加 tooltip 字段, 类型走 AppRadioOption
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

const BACKEND_OPTIONS: (AppRadioOption & { tooltip: string })[] = [
  {
    value: "camelot",
    label: "Camelot",
    tooltip: "lattice/stream/network/hybrid/ml 5 种解析器，按 flavor 切换不同参数组",
  },
  {
    value: "pymupdf",
    label: "PyMuPDF",
    tooltip: "PyMuPDF 内置 find_tables()，开箱即用，识别速度最快",
  },
  {
    value: "pdfplumber",
    label: "pdfplumber",
    tooltip: "基于 pdfplumber 的 lines/text 策略 + 容差参数",
  },
];

const BACKEND_DEFAULT_PARAMS: Record<TableBackend, Record<string, string | number>> = {
  pymupdf: {},
  // (2026-07-09) line_scale 40→15: 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"]=15 是 camelot 2.0 官方推荐,
  // 旧 40 容易把短线判为"短横线"丢. 前后端必须对齐. 后端兜底保留.
  camelot: { flavor: "lattice", line_scale: 15, line_tol: 2 },
  pdfplumber: {
    vertical_strategy: "lines",
    horizontal_strategy: "lines",
    snap_tolerance: 3,
    join_tolerance: 3,
  },
};

/**
 * (2026-07-07) 按 flavor 返回 camelot 的可配参数列表 — 跟 camelot.utils.flavor_to_kwargs 对齐:
 *   lattice → line_tol / joint_tol / line_scale
 *   stream  → row_tol / column_tol (edge_tol 是 camelot 内部别名, 后端默认 50 已够, 不暴露)
 *   network → 同 stream
 *   hybrid  → 流式 + 网格都接受, 默认按 stream 显示
 *   ml      → 模型相关, 暂时不暴露 (需 [ml] extra)
 */
const getCamelotParamKeys = (flavor: string): string[] => {
  const baseKeys = ["flavor"];
  if (flavor === "lattice") {
    return [...baseKeys, "line_scale", "line_tol"];
  }
  if (flavor === "stream" || flavor === "network") {
    return [...baseKeys, "row_tol", "column_tol"];
  }
  if (flavor === "hybrid") {
    return [...baseKeys, "row_tol", "column_tol", "line_scale", "line_tol"];
  }
  // ml flavor 暂不暴露参数 (调模型名 / 阈值太专业)
  return baseKeys;
};

// (2026-07-07) camelot 走动态 getCamelotParamKeys(flavor), 不进静态字典.
// Partial 是为了 tsc 类型严格 — Record<TableBackend, ...> 要求全覆盖,
// 但 camelot 是动态的 (跟 flavor 联动), 故意漏.
const BACKEND_PARAMS_KEYS: Partial<Record<TableBackend, string[]>> = {
  pymupdf: [],
  pdfplumber: ["vertical_strategy", "horizontal_strategy", "snap_tolerance", "join_tolerance"],
};

const FLAVOR_OPTIONS: AppSelectOption[] = [
  { value: "lattice", label: "lattice (表格线)" },
  { value: "stream", label: "stream (空白间距)" },
  { value: "network", label: "network" },
  { value: "hybrid", label: "hybrid" },
  { value: "ml", label: "ml (Table Transformer, 需 [ml] extra)" },
];

const STRATEGY_OPTIONS: AppSelectOption[] = [
  { value: "lines", label: "lines (显式线)" },
  { value: "lines_strict", label: "lines_strict (严格)" },
  { value: "text", label: "text (文本对齐)" },
  { value: "explicit", label: "explicit (显式坐标)" },
];

// (2026-07-09 PDF 章节树状化) 章节显示层级选项 — 跟后端 chapter_max_level_for_display 字段对齐 (1-6)
const LEVEL_OPTIONS: AppSelectOption[] = [
  { value: "2", label: "1-2 级 (只显示章/节)" },
  { value: "3", label: "1-3 级 (默认)" },
  { value: "4", label: "1-4 级" },
  { value: "5", label: "1-5 级" },
  { value: "6", label: "1-6 级 (全展开)" },
];

/** (2026-07-09) 后端章节配置默认值 — 跟 ChapterExtractionConfig 字段对齐 */
const DEFAULT_CHAPTER_MAX_LEVEL = 3;
const DEFAULT_LLM_PROVIDER = "openai" as const;

/** 预分析上传弹框属性 */
export interface PreAnalysisUploadDialogProps {
  /** 弹框打开状态 */
  open: boolean;
  /** 弹框打开状态变更回调 */
  onOpenChange: (open: boolean) => void;
  /** (2026-07-03) 上传完成回调 (默认只刷列表, 不跳详情) */
  onComplete?: () => void;
}

/**
 * (2026-07-06) 上传弹框状态子 hook — 5 个 state + paramKeys + backend reset.
 * 提取自 usePreAnalysisUpload 以满足 oxlint max-statements ≤10.
 * (2026-07-09) 删 showAdvanced: 高级选项不再折叠, 状态机只剩表单数据.
 */
const useUploadState = () => {
  const [pickedFile, setPickedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // (2026-07-09) 默认 backend = camelot, 把"高级选项"折叠区移除外, 这是用户主选.
  const [backend, setBackend] = useState<TableBackend>("camelot");
  const [params, setParams] = useState<Record<string, string | number>>({});
  // (2026-07-09 PDF 章节树状化) 章节配置 state — 章节显示层级 + LLM 增强开关
  const [chapterMaxLevel, setChapterMaxLevel] = useState<number>(DEFAULT_CHAPTER_MAX_LEVEL);
  const [enableLlmRefinement, setEnableLlmRefinement] = useState(false);

  // paramKeys 仍计算 (params 传给后端需要它), 但 UI 不再渲染参数区, 详见组件 JSX 注释.
  const paramKeys: string[] =
    backend === "camelot"
      ? getCamelotParamKeys(String(params.flavor ?? "lattice"))
      : (BACKEND_PARAMS_KEYS[backend] ?? []);

  useEffect(() => {
    setParams(BACKEND_DEFAULT_PARAMS[backend]);
  }, [backend]);

  return {
    pickedFile,
    setPickedFile,
    isUploading,
    setIsUploading,
    uploadError,
    setUploadError,
    backend,
    setBackend,
    params,
    setParams,
    paramKeys,
    chapterMaxLevel,
    setChapterMaxLevel,
    enableLlmRefinement,
    setEnableLlmRefinement,
  };
};

/**
 * (2026-07-06) 预分析上传弹框 handler hook — 4 个 handler.
 * 提取自 usePreAnalysisUpload 以满足 oxlint max-statements ≤10.
 */
const useUploadHandlers = (
  state: ReturnType<typeof useUploadState>,
  props: { onOpenChange: (open: boolean) => void; onComplete?: () => void },
) => {
  const translate = useTranslations();

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && state.isUploading) {
      return;
    }
    if (!nextOpen) {
      state.setPickedFile(null);
      state.setUploadError(null);
      // (2026-07-09) showAdvanced 已删, 不再重置; 重置 backend 到默认 camelot.
      state.setBackend("camelot");
      state.setParams({});
      // (2026-07-09) 关弹框重置章节配置到默认值
      state.setChapterMaxLevel(DEFAULT_CHAPTER_MAX_LEVEL);
      state.setEnableLlmRefinement(false);
    }
    props.onOpenChange(nextOpen);
  };

  const handleClear = (): void => {
    state.setPickedFile(null);
    state.setUploadError(null);
  };

  const executeUpload = async (
    config: TableExtractionConfig,
    chapterConfig: ChapterExtractionConfig,
  ): Promise<void> => {
    try {
      await preAnalysisUpload(state.pickedFile as File, config, chapterConfig);
      toast.success(translate("上传成功"));
      setTimeout(() => {
        // (2026-07-09) 走 handleOpenChange(false) 走单一入口, 触发 state 重置.
        // 原 props.onOpenChange(false) 直接调父组件, 绕过了 handleOpenChange 里的
        // reset 逻辑, 导致再次点开弹框还显示上次提交的表单.
        handleOpenChange(false);
        props.onComplete?.();
      }, DIALOG_CLOSE_DELAY_MS);
    } catch (error) {
      state.setUploadError(error instanceof Error ? error.message : String(error));
    } finally {
      state.setIsUploading(false);
    }
  };

  const handleUpload = async (): Promise<void> => {
    if (!state.pickedFile || state.isUploading) {
      return;
    }
    state.setIsUploading(true);
    state.setUploadError(null);
    // (2026-07-09) showAdvanced 已删, 始终用 user 选的实际 backend / params 传给后端.
    // 表格参数 UI 隐藏但 params 数据照传 (走 BACKEND_DEFAULT_PARAMS 默认值, 后端兜底).
    const config: TableExtractionConfig = { backend: state.backend, params: state.params };
    // (2026-07-09) 章节配置: 章节显示层级 + LLM 增强开关 + 默认 provider.
    const chapterConfig: ChapterExtractionConfig = {
      chapter_max_level_for_display: state.chapterMaxLevel,
      enable_llm_refinement: state.enableLlmRefinement,
      llm_provider: DEFAULT_LLM_PROVIDER,
    };
    await executeUpload(config, chapterConfig);
  };

  return { handleOpenChange, handleClear, handleUpload, translate };
};

// (2026-07-09) 表格参数 UI 隐藏, renderParamInput 暂时 unused — export 保留,
// 后续放开参数 UI 时直接 import 使用, 不需要重新引入.
export const renderParamInput = (
  paramKey: string,
  params: Record<string, string | number>,
  setParams: (params: Record<string, string | number>) => void,
): React.ReactNode => {
  const currentVal = params[paramKey];
  if (paramKey === "flavor") {
    return (
      <AppSelect
        options={FLAVOR_OPTIONS}
        value={String(currentVal ?? "lattice")}
        onChange={(newVal) => setParams({ ...params, [paramKey]: newVal })}
        dataTestid={`param-${paramKey}`}
      />
    );
  }
  if (paramKey === "vertical_strategy" || paramKey === "horizontal_strategy") {
    return (
      <AppSelect
        options={STRATEGY_OPTIONS}
        value={String(currentVal ?? "lines")}
        onChange={(newVal) => setParams({ ...params, [paramKey]: newVal })}
        dataTestid={`param-${paramKey}`}
      />
    );
  }
  return (
    <Input
      id={`param-${paramKey}`}
      type="number"
      value={String(currentVal ?? "")}
      onChange={(event) => setParams({ ...params, [paramKey]: Number(event.target.value) })}
      data-testid={`param-${paramKey}`}
    />
  );
};

/**
 * 预分析上传弹框组件 — 3 段式: 选文件 -> 文件信息+清空 -> 上传 + 高级选项
 * @param props - 组件属性
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 弹框打开状态变更回调
 * @param props.onComplete - 上传完成回调
 * @returns 预分析上传弹框
 * @client-bff
 */
export const PreAnalysisUploadDialog = ({
  open,
  onOpenChange,
  onComplete,
}: PreAnalysisUploadDialogProps) => {
  const state = useUploadState();
  const { handleOpenChange, handleClear, handleUpload, translate } = useUploadHandlers(state, {
    onOpenChange,
    onComplete,
  });

  return (
    <AppDialog
      dataTestid="upload-dialog"
      error={state.uploadError}
      errorTestid="upload-dialog-error"
      icon={<UploadCloud className="h-5 w-5" />}
      maxWidth="md"
      open={open}
      title={translate("上传 PDF")}
      closeOnEscape={false}
      onOpenChange={handleOpenChange}
      footer={
        <>
          <Button
            disabled={state.isUploading}
            variant="outline"
            onClick={() => handleOpenChange(false)}
          >
            {translate("取消")}
          </Button>
          <Button
            data-testid="upload-dialog-start"
            disabled={!state.pickedFile || state.isUploading}
            onClick={() => void handleUpload()}
          >
            {state.isUploading ? translate("上传中…") : translate("开始上传")}
          </Button>
        </>
      }
    >
      {state.pickedFile === null ? (
        <FileDropzone
          accept=".pdf"
          maxSizeMB={PDF_MAX_SIZE_MB}
          onFile={state.setPickedFile}
          title={translate("点击上传按钮开始")}
        />
      ) : (
        <div
          className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/40 p-4"
          data-testid="upload-dialog-file-info"
        >
          <div className="flex min-w-0 items-center gap-3">
            <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">
                {state.pickedFile.name}
              </div>
              <div className="text-xs text-muted-foreground">{fmtSize(state.pickedFile.size)}</div>
            </div>
          </div>
          <Button
            data-testid="upload-dialog-clear"
            disabled={state.isUploading}
            size="sm"
            variant="ghost"
            onClick={handleClear}
          >
            <X className="mr-1 h-4 w-4" />
            {translate("清空")}
          </Button>
        </div>
      )}
      {/* (2026-07-09) 高级选项区不再折叠, 直接展示 (删 Collapsible + showAdvanced state) */}
      <div className="mt-4 space-y-4">
        <div>
          {/* (2026-07-07) Label 包根 (shadcn RadioGroupItem 不带 id, htmlFor 失效; 改用 Label 触发整组焦点) */}
          <Label className="text-sm font-medium">表格提取器</Label>
          <AppRadioGroup
            options={BACKEND_OPTIONS}
            value={state.backend}
            onChange={(val) => state.setBackend(val as TableBackend)}
            dataTestid="backend-radio"
            renderLabel={(opt) => (
              <span className="flex items-center gap-1">
                {opt.label}
                <AppTooltip content={opt.tooltip}>
                  <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
                </AppTooltip>
              </span>
            )}
          />
        </div>
        {state.backend === "pymupdf" ? (
          <p className="text-xs text-muted-foreground">
            使用 PyMuPDF 内置 find_tables(), 无需额外配置
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            {state.backend === "camelot"
              ? "使用 Camelot lattice 解析器, 按后端默认参数运行"
              : "使用 pdfplumber 策略, 按后端默认参数运行"}
          </p>
        )}
        {/*
              (2026-07-09) 临时隐藏表格参数配置 UI — 3 个 backend (pymupdf / camelot / pdfplumber)
              都不渲染参数输入控件. 参数数据 (state.params) 仍然传给后端 (走 BACKEND_DEFAULT_PARAMS 默认值).
              后续如需开放, 把下面注释块取消即可:

              {state.paramKeys.map((key: string) => (
                <div key={key}>
                  <div className="flex items-center gap-1">
                    <label className="text-sm font-medium" htmlFor={`param-${key}`}>
                      {PARAM_METADATA[key].label}
                    </label>
                    <AppTooltip content={PARAM_METADATA[key].tooltip}>
                      <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
                    </AppTooltip>
                  </div>
                  {renderParamInput(key, state.params, state.setParams)}
                </div>
              ))}
            */}
        {/* (2026-07-09 PDF 章节树状化) 章节显示层级 + LLM 增强开关 */}
        <div className="space-y-3 border-t border-border/60 pt-3">
          <Label className="text-sm font-medium">{translate("章节配置")}</Label>
          <div>
            <div className="flex items-center gap-1">
              <label className="text-sm font-medium" htmlFor="chapter-max-level">
                {translate("章节显示层级")}
              </label>
              <AppTooltip content={translate("控制在章节树中显示的最大层级深度, 数字越大展示越细")}>
                <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
              </AppTooltip>
            </div>
            <AppSelect
              options={LEVEL_OPTIONS}
              value={String(state.chapterMaxLevel)}
              onChange={(val) => state.setChapterMaxLevel(Number(val))}
              dataTestid="chapter-max-level"
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card/40 p-3">
            <div className="space-y-0.5">
              <div className="flex items-center gap-1">
                <label className="text-sm font-medium" htmlFor="enable-llm-refinement">
                  {translate("启用 LLM 增强")}
                </label>
                <AppTooltip
                  content={translate(
                    "开启后用 LLM 识别章节 + 生成每章摘要, 会显著增加耗时和 API 调用",
                  )}
                >
                  <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
                </AppTooltip>
              </div>
              <p className="text-xs text-muted-foreground">
                {translate("纯 OCR 识别 → LLM 增强识别 + 章节摘要")}
              </p>
            </div>
            <Switch
              checked={state.enableLlmRefinement}
              data-testid="enable-llm-refinement"
              id="enable-llm-refinement"
              onCheckedChange={state.setEnableLlmRefinement}
            />
          </div>
        </div>
      </div>
    </AppDialog>
  );
};
