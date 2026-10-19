"use client";
// 型号解码页 (2026-06-09 redesign) — 拆解视图 + 字符高亮 + 快捷键
// E2E 选择器兼容: "产品订货号解码" 标题, "解码" 按钮, input[placeholder*="1LE0001"]
// (2026-06-11) motion.button 替换为 shadcn Button
// (2026-06-17) v2 RBAC: 套 GuardClient 做 4 层防护第 2 层
import { ApiError, NetworkError } from "@/lib/api/errors";
import { FadeUp, Reveal, Stagger, StaggerItem } from "@/components/motion/animated";
import { useEvent, useLocalStorage, useToggle } from "react-use";
import { useRef, useState, useTransition } from "react";
import { AppToggle } from "@/components/common/input/app-toggle";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { DecodeField } from "./decode-field";
import { DecodeInputBar } from "./decode-input-bar";
import { DELAY, LIFT } from "@/lib/motion";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { GuardClient } from "@/components/auth/guard-client";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { SeriesDialog } from "./series-dialog";
import { decode } from "@/lib/api/system";
import { useTranslations } from "next-intl";

/** 示例型号 @shared */
const EXAMPLE = "1LE0001-1AA42-1AA4";
/** JSON 缩进空格数 @shared */
const JSON_INDENT = 2;

/** 解码结果类型
 * @property series - 产品系列
 * @property prefix - 前缀
 * @property manufacturer - 制造商
 * @property name - 产品名称
 * @property raw_input - 原始输入
 * @property normalized - 标准化结果
 * @property display - 显示文本
 * @shared
 */
type DecodeResult = Record<string, unknown> & {
  series?: string;
  prefix?: string;
  manufacturer?: string;
  name?: string;
  raw_input?: string;
  normalized?: string;
  display?: string;
  [k: string]: unknown;
};

/** 构建复制文本: llm 模式拼 llm_view 数组, 其他模式走 JSON.stringify
 * @param result - 解码结果
 * @param view - 视图类型
 * @returns 复制文本
 * @shared
 */
const buildCopyText = (result: DecodeResult, view: "cards" | "llm"): string => {
  if (view === "llm") {
    return ((result.llm_view as string[] | undefined) ?? []).join("\n");
  }
  return JSON.stringify(result, null, JSON_INDENT);
};

/** 过滤主字段: 隐藏 raw_input / normalized / display 三个底层字段
 * @param result - 解码结果
 * @returns 过滤后的键值对数组
 * @shared
 */
const filterMainFields = (result: DecodeResult | null): [string, unknown][] => {
  if (!result) {
    return [];
  }
  return Object.entries(result).filter(
    ([key]) => key !== "raw_input" && key !== "normalized" && key !== "display",
  );
};

/** 错误归一: ApiError/NetworkError 取 .message, 其他转字符串
 * @param error - 原始错误
 * @returns 格式化后错误信息
 * @shared
 */
const formatDecodeError = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  return String(error);
};

/** 解码动作回调 hook (submit / fillExample / copyJSON)
 * @param options - 回调参数
 * @param options.model - 当前型号文本
 * @param options.setModel - 设置型号文本
 * @param options.result - 解码结果
 * @param options.setResult - 设置解码结果
 * @param options.setErr - 设置错误信息
 * @param options.inputRef - 输入框 ref
 * @param options.isPending - 是否正在提交
 * @param options.startTransition - React 过渡函数
 * @returns 解码动作回调
 * @client-bff
 */
const useDecodeActions = ({
  model,
  setModel,
  result,
  setResult,
  setErr,
  inputRef,
  isPending,
  startTransition,
}: {
  model: string;
  setModel: React.Dispatch<React.SetStateAction<string>>;
  result: DecodeResult | null;
  setResult: React.Dispatch<React.SetStateAction<DecodeResult | null>>;
  setErr: React.Dispatch<React.SetStateAction<string | null>>;
  inputRef: React.RefObject<HTMLInputElement | null>;
  isPending: boolean;
  startTransition: React.TransitionStartFunction;
}) => {
  const submit = () => {
    startTransition(async () => {
      setErr(null);
      setResult(null);
      try {
        setResult(await decode(model));
      } catch (error) {
        setErr(formatDecodeError(error));
      }
    });
  };

  // (2026-06-14) react-use: useEvent 替手写 useKeyboardSubmit (addEventListener + cleanup 模板)
  useEvent("keydown", (event: KeyboardEvent) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && model && !isPending) {
      submit();
    }
  });

  const fillExample = () => {
    setModel(EXAMPLE);
    inputRef.current?.focus();
  };

  const copyJSON = async () => {
    if (!result) {
      return;
    }
    // CopyButton 内部处理 1.5s 反馈 + sonner toast.error, 无需手动 setCopied
  };

  return { copyJSON, fillExample, submit };
};

// (2026-06-14) react-use: useLocalStorage 替手写 readPersistedView + usePersistedView;
//   UseEvent 替手写 useKeyboardSubmit (addEventListener + cleanup 模板)

/** decode 页面
 * @param props
 * @client-bff
 */
export default function DecodePage() {
  return (
    <GuardClient pageKey="decode">
      <DecodePageInner />
    </GuardClient>
  );
}

/** 解码页面内部组件 (含输入/结果展示/系列弹框)
 * @returns 解码页面 JSX
 * @client-bff
 */
const DecodePageInner = () => {
  const translate = useTranslations();
  const [model, setModel] = useState("");
  const [result, setResult] = useState<DecodeResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // (2026-06-14) React 19 useTransition 替 useState(loading) — 内部状态由 React 管, 不需要手动 setLoading(true/false) + finally 块
  const [isPending, startTransition] = useTransition();
  const [seriesOpen, toggleseriesOpen] = useToggle(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // (2026-06-14) react-use: useLocalStorage 替手写 readPersistedView + usePersistedView
  // React-use 泛型 initialValue 可选 → 返回 [T|undefined, ...], 实际传了 default "cards"
  const [view = "cards", setView] = useLocalStorage<"cards" | "llm">("decode.view", "cards");

  const { copyJSON, fillExample, submit } = useDecodeActions({
    inputRef,
    isPending,
    model,
    result,
    setErr,
    setModel,
    setResult,
    startTransition,
  });

  return (
    <div className="h-full overflow-y-auto">
      <PageHero
        eyebrow="Decoder"
        title={
          <>
            {translate("产品订货号")}
            <span className="text-clay">·</span>
            {translate("解码")}
          </>
        }
        meta="⌘ ↵"
        description={translate(
          "把完整订货号丢进来, 按 YAML 配置拆成字段。配置驱动, 零代码加新系列。",
        )}
        className="mb-10"
      />

      {/* 输入区 — 巨型 input + 字符 chunks 高亮 (抽到 DecodeInputBar) */}
      <Reveal className="mb-6" delay={0.2}>
        <DecodeInputBar
          hasError={Boolean(err)}
          inputRef={inputRef}
          loading={isPending}
          model={model}
          onFillExample={fillExample}
          onModelChange={setModel}
          onPickSeries={() => toggleseriesOpen(true)}
          onSubmit={submit}
        />
      </Reveal>

      {/* 错误条 */}
      {err && (
        <div className="mt-6">
          <ErrorBanner variant="destructive" description={err} />
        </div>
      )}

      {/* 结果 — 拆解视图 + 复制按钮 */}
      {result && (
        <FadeUp
          show
          lift={LIFT.heroLg}
          delay={DELAY.secondary}
          as="section"
          className="mt-10 space-y-8"
        >
          {/* Header — 厂家 + 系列 */}
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/60 pb-6">
            <div>
              <div className="eyebrow mb-1">{translate("解码结果")}</div>
              <h2 className="display text-3xl tracking-tight">
                {(result.name as string) ?? (result.series as string) ?? "—"}
              </h2>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-base text-muted-foreground">
                {result.manufacturer && (
                  <span>
                    <span className="eyebrow mr-1">{translate("厂商")}</span>
                    {result.manufacturer as string}
                  </span>
                )}
                {result.prefix && (
                  <span className="num">
                    <span className="eyebrow mr-1">{translate("前缀")}</span>
                    {result.prefix as string}
                  </span>
                )}
              </div>
            </div>
            <AppToggle
              options={[
                { label: translate("解码卡"), value: "cards" },
                { label: translate("Dify 视图"), value: "llm" },
              ]}
              value={view}
              onChange={(value) => value && setView(value as "cards" | "llm")}
              dataTestid="view"
            />
            {result && (
              <CopyButton
                text={buildCopyText(result, view)}
                label={view === "llm" ? translate("复制 LLM 文本") : translate("复制 JSON")}
                successLabel={`✓ ${translate("已复制")}`}
                variant="outline"
                size="sm"
                onCopied={copyJSON}
              />
            )}
          </div>

          {/* 字段网格 — 2 列 stagger / 或 LLM 视图 */}
          {view === "cards" && (
            <Stagger className="grid grid-cols-1 gap-3 md:grid-cols-2" delay={0.04}>
              {filterMainFields(result).map(([key, value]) => (
                <StaggerItem key={key}>
                  <DecodeField keyName={key} val={value} />
                </StaggerItem>
              ))}
            </Stagger>
          )}
          {view !== "cards" && (
            <pre
              data-testid="llm-view"
              className="num whitespace-pre-wrap rounded-lg border border-border/50 bg-card p-4 text-sm leading-relaxed"
            >
              {((result.llm_view as string[] | undefined) ?? []).join("\n")}
            </pre>
          )}
        </FadeUp>
      )}

      <SeriesDialog open={seriesOpen} onOpenChange={toggleseriesOpen} />
    </div>
  );
};
