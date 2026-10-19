"use client";
// EvaluateNewForm client 子组件 (2026-06-12) — Task 20 抽自 evaluate/new/page.tsx
// 保留 Papa Parse 客户端解析 CSV (5MB, 1-200 行, 预览全部数据行, 表头提示总行数)
// 提交走 BFF multipart: createRun(file, concurrency) (lib/api/evaluate.ts)
//   不走 _actions/evaluate.ts createRun — 那个是 JSON variant, 跟 multipart 互斥
// Page.tsx 已变 RSC wrapper, 此组件只负责交互态 + 文件解析 + multipart 上传
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { Reveal } from "@/components/motion/animated";
import { PageHeader } from "@/components/common/navigation/app-page-header";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { LocalizedLink } from "@/components/i18n/localized-link";
import { Input } from "@/components/ui/input";
import { useRouter } from "@/i18n/navigation";
import { getErrorMessage } from "@/lib/api/errors";
import { createRun, templateUrl } from "@/lib/api/evaluate";
import { DELAY } from "@/lib/motion";
import { useTranslations } from "next-intl";
import Papa from "papaparse";
import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";

/** ParsedCsv - CSV 解析后的结果类型 */
interface ParsedCsv {
  /** 解析后的数据行 */
  rows: { question: string; ground_truth: string | null }[];
  /** 有效数据总行数 */
  total: number;
}

/** 最小并发数 */
const MIN_CONCURRENCY = 1;
/** 最大并发数 */
const MAX_CONCURRENCY = 10;
/** 单次评估最大行数上限 */
const MAX_ROWS = 200;
/** 空数据行数常量 */
const EMPTY_ROWS = 0;

// Form 只负责 concurrency 等元信息; 文件/解析在父组件状态里
/** NewEvalSchema - 新建评估表单验证 Schema (并发数校验) */
const NewEvalSchema = z.object({
  concurrency: z.coerce.number().int().min(MIN_CONCURRENCY).max(MAX_CONCURRENCY),
});
type NewEvalForm = z.infer<typeof NewEvalSchema>;

/** csvPreviewColumns - 数据预览表格列定义 (question + ground_truth) */
const csvPreviewColumns: ColumnDef<{ question: string; ground_truth: string | null }>[] = [
  {
    id: "question",
    accessorKey: "question",
    cell: (ctx) => <span className="max-w-md truncate">{ctx.row.original.question}</span>,
    header: () => "question",
  },
  {
    id: "ground_truth",
    accessorKey: "ground_truth",
    cell: (ctx) => (
      <span className="max-w-md truncate text-muted-foreground">
        {ctx.row.original.ground_truth ?? "—"}
      </span>
    ),
    header: () => "ground_truth",
  },
];

/** getSubmitLabel - 根据上传状态获取提交按钮文案
 * @param uploading 是否正在上传
 * @param trans i18n 翻译函数
 * @returns 按钮显示文本
 * @shared
 */
const getSubmitLabel = (uploading: boolean, trans: ReturnType<typeof useTranslations>): string => {
  if (uploading) {
    return trans("上传中…");
  }
  return trans("开始评估 →");
};

/** buildCsvRows - 从 Papa Parse 解析后的原始数据构建标准行格式
 * @param data Papa Parse 输出的原始行数组
 * @param trans i18n 翻译函数
 * @returns 包含有效行数和行数据的对象
 * @throws 无有效数据或超出上限时抛错
 * @shared
 */
const buildCsvRows = (
  data: Record<string, string>[],
  trans: ReturnType<typeof useTranslations>,
): { count: number; rows: { ground_truth: string | null; question: string }[] } => {
  const rows = data
    .map((row) => ({
      ground_truth: (row.ground_truth ?? "").trim() || null,
      question: (row.question ?? "").trim(),
    }))
    .filter((row) => row.question);
  const count = rows.length;
  if (count === EMPTY_ROWS) {
    throw new Error(trans("至少 1 行有效数据"));
  }
  if (count > MAX_ROWS) {
    throw new Error(trans("题数 {count} 超过上限 200", { count }));
  }
  return { count, rows };
};

/** parseClientSide - 客户端使用 Papa Parse 解析 CSV 文件
 * @param file 用户上传的 CSV 文件
 * @param trans i18n 翻译函数
 * @returns 解析后的 ParsedCsv 数据
 * @throws 缺 question 列或数据不合法时抛错
 * @client-bff
 */
const parseClientSide = (
  file: File,
  trans: ReturnType<typeof useTranslations>,
): Promise<ParsedCsv> =>
  new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      complete: (res) => {
        if (!res.meta.fields?.includes("question")) {
          reject(new Error(trans("缺 'question' 列, 表头必须是: question,ground_truth")));
          return;
        }
        try {
          const { count, rows } = buildCsvRows(res.data, trans);
          resolve({ rows, total: count });
        } catch (error) {
          reject(error);
        }
      },
      error: (parseError) => reject(new Error(`${trans("CSV 解析失败:")} ${parseError.message}`)),
      header: true,
      skipEmptyLines: true,
    });
  });

/** DoSubmitParams - doSubmitEval 函数参数类型 */
interface DoSubmitParams {
  /** 上传的 CSV 文件 */
  file: File;
  /** 表单值 (含并发数) */
  formValues: NewEvalForm;
  /** i18n 路由实例, 提交成功后跳转 */
  router: ReturnType<typeof useRouter>;
  /** 设置上传错误状态 */
  setUploadErr: (val: string | null) => void;
  /** 设置上传中状态 */
  setUploading: (val: boolean) => void;
}

/** doSubmitEval - 执行评估提交 (走 BFF multipart 上传)
 * @param params 上传参数
 * @returns Promise<void>
 * @client-bff
 */
const doSubmitEval = async (params: DoSubmitParams): Promise<void> => {
  const { file, formValues, router, setUploadErr, setUploading } = params;
  try {
    // 走 BFF multipart — 跟 _actions/evaluate.ts createRun (JSON) 并存
    const result = await createRun(file, formValues.concurrency);
    router.push(`/evaluate/${result.id}`);
  } catch (error) {
    setUploadErr(getErrorMessage(error));
    setUploading(false);
  }
};

/** useEvaluateForm - 评估表单状态管理 Hook
 * @returns 表单状态、文件选择回调、提交回调及错误状态
 * @client-bff
 */
const useEvaluateForm = () => {
  const trans = useTranslations();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<ParsedCsv | null>(null);
  const [parseErr, setParseErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const onPick = async (pickedFile: File) => {
    setParseErr(null);
    setParsed(null);
    // FileDropzone 已经拦截 >5MB 走 fileRejections → 内部红字. 这里只处理合法文件.
    setFile(pickedFile);
    try {
      const parsedData = await parseClientSide(pickedFile, trans);
      setParsed(parsedData);
    } catch (error) {
      const errorMsg = String((error as Error).message);
      setParseErr(errorMsg);
      toast.error(errorMsg);
    }
  };

  const onSubmit = async (values: Record<string, unknown>) => {
    if (!file || !parsed) {
      return;
    }
    await doSubmitEval({
      file,
      formValues: values as unknown as NewEvalForm,
      router,
      setUploadErr,
      setUploading,
    });
  };

  return { file, onPick, onSubmit, parseErr, parsed, setUploadErr, trans, uploadErr, uploading };
};

/** EvaluateNewForm - 新建评估表单客户端组件, 负责文件解析 + multipart 上传 + 预览展示
 * @client-bff
 */
export const EvaluateNewForm = () => {
  const { file, onPick, onSubmit, parseErr, parsed, setUploadErr, trans, uploadErr, uploading } =
    useEvaluateForm();

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <PageHeader backHref="/evaluate" title={trans("新建评估")} />

      {!parsed && (
        <Reveal delay={DELAY.primary}>
          <div className="space-y-3">
            <FileDropzone accept={{ "text/csv": [".csv"] }} maxSizeMB={5} onFile={onPick} />
            <div className="text-center">
              <a
                href={templateUrl()}
                download="eval_template.csv"
                className="text-xs text-muted-foreground underline hover:text-foreground"
              >
                {trans("↓ 没模板? 下载")}
              </a>
            </div>
          </div>
        </Reveal>
      )}

      {parseErr && <ErrorBanner variant="destructive" description={parseErr} />}

      {parsed && file && (
        <Reveal delay={DELAY.data}>
          <AppForm
            defaultValues={{ concurrency: MIN_CONCURRENCY }}
            schema={NewEvalSchema}
            onFinish={onSubmit}
            onFinishFailed={() => setUploadErr(trans("请检查表单字段"))}
          >
            <div className="space-y-4">
              <div className="text-sm">
                {trans("文件名:")} <span className="num">{file.name}</span> (
                {trans("({count} 行)", { count: parsed.total })})
              </div>
              <div className="rounded-lg border border-border/40 bg-card overflow-hidden">
                <DataTable
                  columns={csvPreviewColumns}
                  dataSource={parsed.rows}
                  rowKey="question"
                  maxHeight="400px"
                />
              </div>
              <AppField name="concurrency" label={trans("并发数")} help={trans("范围 1-10")}>
                <Input
                  type="number"
                  min={MIN_CONCURRENCY}
                  max={MAX_CONCURRENCY}
                  className="num w-24"
                />
              </AppField>
            </div>

            {uploadErr && (
              <ErrorBanner variant="destructive" description={uploadErr} className="mt-4" />
            )}

            <div className="mt-4 flex items-center justify-end gap-3">
              <LocalizedLink
                href="/evaluate"
                className="rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition-colors hover:bg-muted/30"
              >
                {trans("取消")}
              </LocalizedLink>
              <AppSubmit disabled={uploading} data-testid="eval-start">
                {getSubmitLabel(uploading, trans)}
              </AppSubmit>
            </div>
          </AppForm>
        </Reveal>
      )}
    </div>
  );
};
