"use client";
// 知识图谱抽取启动弹框 (2026-07-03)
// 复刻原 page.tsx 表单内容 (FileDropzone + 3 AppSelect + 启动按钮),
// 包成 AppDialog 由列表页触发. 提交后调 startExtract 启新 task, 弹框关闭, 跳进度页.
/* oxlint-disable max-statements, id-length -- 弹框逻辑连贯, 拆分增加阅读成本; 短变量 d/e/s 是 map 回调惯例 */
import { useState, useTransition, type FormEvent } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { FileText, X } from "lucide-react";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import { FIVE } from "@/const";
import { fmtSize } from "@/lib/format";
import {
  fetchExtractDatasets,
  fetchExtractors,
  fetchSplitters,
  startExtract,
  uploadExtractFile,
} from "@/lib/api/knowledge";

/**
 * ExtractCreateDialogProps - 抽取创建弹框属性
 * @property open - 是否打开
 * @property onOpenChange - 打开状态变更回调
 */
export interface ExtractCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * ExtractCreateDialog - 知识图谱抽取启动弹框
 * @param props - 组件属性
 * @client-bff
 */
const ExtractCreateDialog = ({ open, onOpenChange }: ExtractCreateDialogProps) => {
  const tr = useTranslations();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [dataset, setDataset] = useState("motor");
  const [extractor, setExtractor] = useState("llm_pydantic");
  const [splitter, setSplitter] = useState("heading");
  const [error, setError] = useState<string | null>(null);

  const { data: datasets = [] } = useQuery({
    queryKey: ["kg", "extract-datasets"],
    queryFn: fetchExtractDatasets,
  });
  const { data: extractors = [] } = useQuery({
    queryKey: ["kg", "extractors"],
    queryFn: fetchExtractors,
  });
  const { data: splitters = [] } = useQuery({
    queryKey: ["kg", "splitters"],
    queryFn: fetchSplitters,
  });

  const handleClose = (next: boolean) => {
    if (!next) {
      // 关闭时重置 (避免下次打开残留)
      setFile(null);
      setError(null);
    }
    onOpenChange(next);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!file) {
      setError(tr("请先选择文件"));
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        const { uri } = await uploadExtractFile(file, dataset);
        const { task_id } = await startExtract({
          uri,
          dataset,
          extractor,
          splitter,
        });
        // 关闭弹框 + 跳进度页
        handleClose(false);
        void router.push(`/knowledge/extract/${task_id}?dataset=${encodeURIComponent(dataset)}`);
      } catch (submitError) {
        const message = submitError instanceof Error ? submitError.message : tr("启动失败");
        setError(message);
      }
    });
  };

  return (
    <AppDialog
      open={open}
      onOpenChange={handleClose}
      title={tr("新建提取")}
      description={tr("选择数据集与抽取器")}
      maxWidth="lg"
      error={error}
      errorTestid="extract-dialog-error"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("数据集")}</label>
          <AppSelect
            value={dataset}
            onChange={setDataset}
            options={datasets.map((d) => ({ value: d.label, label: d.label }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("抽取器")}</label>
          <AppSelect
            value={extractor}
            onChange={setExtractor}
            options={extractors.map((e) => ({ value: e.id, label: e.id }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("切片器")}</label>
          <AppSelect
            value={splitter}
            onChange={setSplitter}
            options={splitters.map((s) => ({ value: s.id, label: s.id }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">{tr("上传 Markdown 文件")}</label>
          {file === null ? (
            <FileDropzone onFile={setFile} accept=".md" maxSizeMB={FIVE} />
          ) : (
            <div
              className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/40 p-4"
              data-testid="extract-file-info"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-foreground">{file.name}</div>
                  <div className="text-xs text-muted-foreground">{fmtSize(file.size)}</div>
                </div>
              </div>
              <Button
                data-testid="extract-file-clear"
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setFile(null)}
                aria-label={tr("清空")}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-border/40 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleClose(false)}
            disabled={isPending}
          >
            {tr("取消")}
          </Button>
          <Button type="submit" disabled={!file || isPending}>
            {isPending ? tr("加载中…") : tr("启动抽取")}
          </Button>
        </div>
      </form>
    </AppDialog>
  );
};

/**
 * @client-bff
 */
export default ExtractCreateDialog;
