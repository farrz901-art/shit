// QA 录入 client 表单 (Task 17, 2026-06-12) — 改 RSC 后, 灌入 RSC 预取的 datasetId.
// (2026-06-25) 迁移到 AppForm (Task 7) — extract onFinish 命名函数 handleSubmit, 去 useActionState.
// formVals 保留 useState (syncNeo4j / tagsRaw), 其他字段交给 AppField 管理.
// (2026-06-11 i18n) useTranslations + t() 包裹中文文案.
"use client";
import { type ActionResult, createQA } from "@/app/[locale]/_actions/knowledge";
import { AppField, AppForm, AppSubmit } from "@/components/common/form";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Reveal, Stagger } from "@/components/motion/animated";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useRouter } from "@/i18n/navigation";
import { useAppStore } from "@/lib/store/app-store";
import { DELAY } from "@/lib/motion";
import { HelpCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { ZERO } from "@/const";

const MIN_LENGTH_2 = 2;
// AppForm schema: question/answer 走表单字段校验, tags 走字符串即可 (split 在 handleSubmit 处理)
const QASchema = z.object({
  answer: z.string().min(MIN_LENGTH_2, "答案至少 2 字"),
  question: z.string().min(MIN_LENGTH_2, "问题至少 2 字"),
});

interface QA {
  // (2026-06-13) Task 10: createQA 现在返审核记录, 不是直写后的 doc 快照.
  // 这里只保留客户端关心的提示用字段 (审核通过后会真正写入 Dify).
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

interface QAFormValues {
  answer: string;
  question: string;
}

interface Props {
  datasetId?: string; // 可选: 未传时从 zustand store 读 (跟 import page 一致)
}

// (2026-06-25) 提取 onFinish 命名函数到外层, 避免 JSX 内联 async 箭头 (项目规约)
// formVals (syncNeo4j / tagsRaw) 走 useState, AppField 只管 question/answer
const useQASubmit = ({
  datasetId,
  formVals,
}: {
  datasetId: string | undefined;
  formVals: { syncNeo4j: boolean; tagsRaw: string };
}) => {
  const tr = useTranslations();
  const router = useRouter();
  const params = useParams<{ locale: string }>();

  // 提交结果状态 — useActionState 改用 useState 手维护
  const [result, setResult] = useState<ActionResult<QA> | null>(null);
  const toastedIdRef = useRef<number | null>(null);

  // 提交时调 createQA server action, 处理 toast + 跳转
  const handleSubmit = async (values: QAFormValues): Promise<void> => {
    const res = await createQA({
      answer: values.answer,
      dataset_id: datasetId ?? "",
      question: values.question,
      sync_to_neo4j: formVals.syncNeo4j,
      tags: formVals.tagsRaw
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    });
    setResult(res);
  };

  // 反馈 + 跳转副作用
  useEffect(() => {
    if (!result) {
      return;
    }
    const approvalId = result.ok ? result.data.approval_id : ZERO;
    if (result.ok && approvalId > ZERO && approvalId !== toastedIdRef.current) {
      toastedIdRef.current = approvalId;
      toast.success(`${tr("已提交审核")} #${approvalId}`);
      router.push(`/${params.locale}/submissions`);
    } else if (!result.ok && result.error) {
      toast.error(result.error);
    }
  }, [result, tr, router, params.locale]);

  // 提取反馈计算到外层, 减少 QASubmitForm 语句
  const submitFeedback = computeSubmitFeedback(result, tr);
  return { handleSubmit, submitFeedback };
};

// (2026-06-20) 提取反馈计算到外层, 减少 QASubmitForm 语句
const computeSubmitFeedback = (
  state: ActionResult<QA> | null,
  tr: (key: string) => string,
): { msg: string; variant: "destructive" | "success" } | null => {
  if (state?.ok) {
    return { msg: tr("已写入 Dify"), variant: "success" };
  }
  if (state?.error) {
    return { msg: state.error, variant: "destructive" };
  }
  return null;
};

// syncNeo4j 复选框 — 走 form.Field 原生 (Checkbox 不在 AppField 内置控件里)
const SyncToNeo4jField = ({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) => {
  const tr = useTranslations();
  return (
    <Label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-border/40 bg-card px-3 py-2.5 transition-colors hover:border-ink/30">
      <Checkbox checked={checked} onCheckedChange={onChange} data-testid="sync-neo4j-checkbox" />
      <span className="text-base">{tr("同步到 Neo4j (QAPair + ABOUT 关系)")}</span>
      <span className="group relative">
        <HelpCircle className="h-4 w-4 text-muted-foreground hover:text-foreground" />
        <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg border border-border/60 bg-card p-3 text-sm text-muted-foreground opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
          {tr("勾选后同时写入 Neo4j 知识图谱：")}
          <br />
          <span className="num">QAPair(问题:xxx) -[ABOUT]-&gt; Product(型号:xxx)</span>
          <br />
          <span className="text-xs">
            {tr("tags 第一个值作为 Product/model, 建立 QAPair→Product 关系")}
          </span>
        </span>
      </span>
    </Label>
  );
};

// tagsRaw input 走 form.Field 原生 (Input + 受控 value, 跟 syncNeo4j 类似不走 AppField 内置)
const TagsField = ({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) => {
  const tr = useTranslations();
  return (
    <div className="space-y-2">
      <Label className="text-base font-medium">{tr("标签 (逗号分隔)")}</Label>
      <Input
        name="tags"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)]"
      />
    </div>
  );
};

/** QASubmitForm
 * @param props
 * @client-bff
 */
export const QASubmitForm = ({ datasetId: datasetIdProp }: Props = {}) => {
  const tr = useTranslations();
  // DatasetId 来源: prop 优先, 否则从 zustand store 读
  const datasetId = datasetIdProp ?? useAppStore((store) => store.datasetId);
  // formVals 保留 useState — syncNeo4j / tagsRaw 不在 AppField 内置, 走 useState 受控
  const [formVals, setFormVals] = useState({ syncNeo4j: false, tagsRaw: "" });
  const { handleSubmit, submitFeedback } = useQASubmit({ datasetId, formVals });

  // (2026-06-12) bug fix: 初始 result=null, 必须用户真提交过才渲染反馈
  const setSyncNeo4j = (val: boolean) => setFormVals((prev) => ({ ...prev, syncNeo4j: val }));
  const setTagsRaw = (val: string) => setFormVals((prev) => ({ ...prev, tagsRaw: val }));

  return (
    <div className="h-full overflow-y-auto space-y-8">
      {/* Hero */}
      <Reveal delay={DELAY.secondary}>
        <Stagger>
          <div className="flex items-center gap-3">
            <span className="eyebrow">{tr("向量库 · QA 录入")}</span>
            <span className="h-px flex-1 bg-border" />
            <span className="num text-sm text-muted-foreground/60">Datasets →</span>
          </div>
          <div className="mt-2 flex items-center justify-between gap-4">
            <h1 className="display text-4xl tracking-tight md:text-5xl">{tr("录 QA 对")}</h1>
            <BackLink
              href="/knowledge/documents"
              useHistory
              label={tr("返回向量库")}
              data-testid="back-link"
            />
          </div>
        </Stagger>
      </Reveal>

      <Reveal delay={DELAY.heroStep2}>
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-lg">{tr("新增")}</CardTitle>
          </CardHeader>
          <CardContent>
            <AppForm
              defaultValues={{ answer: "", question: "" }}
              schema={QASchema}
              onFinish={handleSubmit}
              className="space-y-5"
            >
              <AppField name="question" label={tr("问题")} required>
                <Textarea
                  rows={3}
                  data-testid="qa-question"
                  className="resize-y border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)]"
                />
              </AppField>
              <AppField name="answer" label={tr("答案")} required>
                <Textarea
                  rows={5}
                  data-testid="qa-answer"
                  className="resize-y border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)]"
                />
              </AppField>
              <TagsField
                value={formVals.tagsRaw}
                onChange={setTagsRaw}
                placeholder={tr("电机, 选型, 1LE 系列")}
              />

              <SyncToNeo4jField checked={formVals.syncNeo4j} onChange={setSyncNeo4j} />

              {submitFeedback && (
                <ErrorBanner
                  variant={submitFeedback.variant}
                  description={submitFeedback.msg}
                  dataTestid="qa-submit-result"
                />
              )}

              <div className="flex flex-wrap items-center gap-3">
                <AppSubmit data-testid="qa-submit">{tr("录入 Dify")}</AppSubmit>
              </div>
            </AppForm>
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
};
