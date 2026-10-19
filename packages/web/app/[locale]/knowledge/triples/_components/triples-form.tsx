"use client";
// 三元组录入 client 子组件 (2026-06-12) — 接 RSC 预取的 schema, 渲染录入表格.
// 提交走 createTriples server action (Task 12 建的), form action + useActionState 模式
// (跟 documents/import/ImportCommitCard 一致). 客户端编辑 (行 CRUD) 保留在 client.
// (2026-06-09 redesign) hero + 表格视觉提升
// (2026-06-11) 录入表格改为 DataTable; 行内编辑控件 (Input/Picker) 由 page 闭包注入 render
// (2026-06-11) 提交时一次性 schema.safeParse(rows) 校验 (按 spec 不嵌 Form)
// (2026-06-22) 提取 useTripleForm hook 管理行状态 + 提交逻辑
// (2026-06-25) 提交按钮包裹层从裸 <form action> 迁移到 AppForm (Task 7, 包装统一)
import { AppForm, AppSubmit } from "@/components/common/form";
import { AnimatePresence } from "motion/react";
import { AnimateUp, Reveal } from "@/components/motion/animated";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { LabelPicker, RelationPicker } from "@/components/knowledge/schema-field-renderer";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { KnowledgeSchema } from "@/lib/schema-types";
import { cn } from "@/lib/utils";
import { DELAY } from "@/lib/motion";
import { toast } from "sonner";
import { useTranslations } from "next-intl";
import { type Row, useTripleForm } from "../_hooks/use-triple-form";

/** 基础数字: 数组第一项 */
const FIRST_IDX = 0;
/** 基础数字: 偏移量 */
const OFFSET_1 = 1;

const inputClass =
  "border-border/80 transition-shadow duration-300 focus:shadow-[0_0_0_4px_hsl(0_0%_10%/0.04)]";

/**
 * useTriplesColumns - 表格列定义 (含行内编辑控件 + i18n 文案)
 * @param schema - 知识图谱 schema
 * @param trans - useTranslations 返回值
 * @param handlers - 行编辑 handlers
 * @returns 列定义数组
 */
const useTriplesColumns = (
  schema: KnowledgeSchema,
  trans: ReturnType<typeof useTranslations>,
  handlers: { update: (idx: number, patch: Partial<Row>) => void; remove: (idx: number) => void },
): ColumnDef<Row>[] => {
  const { update, remove } = handlers;
  return [
    {
      id: "index",
      accessorKey: "index",
      cell: (ctx) => <span className="num text-muted-foreground">{ctx.row.index + OFFSET_1}</span>,
      header: () => "#",
      size: 56,
    },
    {
      id: "from_label",
      accessorKey: "from_label",
      cell: (ctx) => (
        <LabelPicker
          schema={schema}
          value={ctx.row.original.from_label}
          onChange={(val) => update(ctx.row.index, { from_label: val })}
        />
      ),
      header: () => trans("起点 (类型)"),
    },
    {
      id: "from_value",
      accessorKey: "from_value",
      cell: (ctx) => (
        <Input
          value={ctx.row.original.from_value}
          onChange={(evt) => update(ctx.row.index, { from_value: evt.target.value })}
          className={inputClass}
        />
      ),
      header: () => trans("起点值"),
    },
    {
      id: "rel_type",
      accessorKey: "rel_type",
      cell: (ctx) => (
        <RelationPicker
          schema={schema}
          fromLabel={ctx.row.original.from_label}
          value={ctx.row.original.rel_type}
          onChange={(val) => {
            const newRel = schema.relations.find((item) => item.name === val);
            const toLabel = newRel?.to ?? "";
            update(ctx.row.index, { rel_type: val, to_label: toLabel });
          }}
        />
      ),
      header: () => trans("关系"),
    },
    {
      id: "to_label",
      accessorKey: "to_label",
      cell: (ctx) => {
        const rel = schema.relations.find((item) => item.name === ctx.row.original.rel_type);
        return <span className="num text-clay">{rel?.to ?? "—"}</span>;
      },
      header: () => trans("终点 (类型)"),
    },
    {
      id: "to_value",
      accessorKey: "to_value",
      cell: (ctx) => (
        <Input
          value={ctx.row.original.to_value}
          onChange={(evt) => update(ctx.row.index, { to_value: evt.target.value })}
          className={inputClass}
        />
      ),
      header: () => trans("终点值"),
    },
    {
      id: "properties",
      accessorKey: "properties",
      cell: (ctx) => (
        <Input
          value={ctx.row.original.properties}
          onChange={(evt) => update(ctx.row.index, { properties: evt.target.value })}
          className={`num ${inputClass}`}
        />
      ),
      header: () => trans("属性 (JSON)"),
    },
    {
      meta: { align: "right" },
      id: "actions",
      accessorKey: "actions",
      cell: (ctx) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => remove(ctx.row.index)}
          className="text-muted-foreground hover:text-destructive"
          aria-label={trans("删除行")}
        >
          ×
        </Button>
      ),
      header: () => "·",
      size: 48,
    },
  ];
};

/**
 * 三元组表单组件属性
 * @property schema - 知识图谱 schema
 */
interface Props {
  schema: KnowledgeSchema;
}

/**
 * getSubmitLabel - 获取提交按钮文案
 * @param trans - useTranslations 返回值
 * @param pending - 是否 pending
 * @returns 按钮文本
 */
const getSubmitLabel = (trans: ReturnType<typeof useTranslations>, pending: boolean): string => {
  if (pending) {
    return trans("提交中…");
  }
  return trans("批量提交");
};

/**
 * TriplesForm - 三元组录入表单
 * @param props.schema - 知识图谱 schema
 * @client-bff
 */
export const TriplesForm = ({ schema }: Props) => {
  const trans = useTranslations();
  const router = useRouter();
  const params = useParams<{ locale: string }>();

  const {
    rows,
    addRow,
    removeRow,
    updateRow,
    clearRows,
    clientError,
    state,
    formAction,
    isPending,
  } = useTripleForm(schema);

  // (2026-06-13) Task 21: 跟踪上一次 toast 提示的 approval_id, 避免 useActionState 在错误回退时重复弹.
  const [toastedId, setToastedId] = useState<number | null>(null);

  const columns = useTriplesColumns(schema, trans, { remove: removeRow, update: updateRow });

  // (2026-06-13) Task 21: 提交成功后弹 toast + 跳 /submissions 让用户看审核进度.
  // 用 approval_id 去重, 避免 useActionState 在错误回退时重复弹.
  useEffect(() => {
    if (state.ok && state.data.approval_id > FIRST_IDX && state.data.approval_id !== toastedId) {
      setToastedId(state.data.approval_id);
      toast.success(trans("已提交审核 #{id}", { id: state.data.approval_id }));
      router.push(`/${params.locale}/submissions`);
    } else if (!state.ok && state.error && !clientError) {
      toast.error(state.error);
    }
  }, [state, clientError, trans, router, params.locale, toastedId]);

  // (2026-06-13) Task 11-13: 提交后展示审核 ID + 状态; 客户端校验错仍按行号显示.
  return (
    <div className="h-full overflow-y-auto space-y-8">
      <TriplesHero />

      <Reveal delay={DELAY.primary}>
        <Card className="border-border/60">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-lg">
                {trans("行")} <span className="num text-clay">{rows.length}</span>
              </CardTitle>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={addRow}>
                  {trans("+ 新增行")}
                </Button>
                <Button variant="outline" onClick={clearRows}>
                  {trans("清空")}
                </Button>
                <AppForm defaultValues={{}} action={formAction}>
                  <AppSubmit className="inline" disabled={isPending} data-testid="triples-submit">
                    {getSubmitLabel(trans, isPending)}
                  </AppSubmit>
                </AppForm>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <DataTable<Row> dataSource={rows} columns={columns} rowKey="id" maxHeight="auto" />
            <AnimatePresence>
              {state.ok && state.data.approval_id > FIRST_IDX && (
                <TriplesResult
                  approvalId={state.data.approval_id}
                  reviewStatus={state.data.review_status}
                />
              )}
              {(clientError || (!state.ok && (state as { ok: false; error: string }).error)) && (
                <TriplesError
                  message={clientError ?? (state as { ok: false; error: string }).error}
                />
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </Reveal>
    </div>
  );
};

/**
 * TriplesResultProps - 提交结果属性
 * @property approvalId - 审批 ID
 * @property reviewStatus - 审核状态
 */
interface TriplesResultProps {
  approvalId: number;
  reviewStatus: "pending" | "approved" | "rejected";
}

/**
 * TriplesHero - 三元组录入页面标题区域
 */
const TriplesHero = () => {
  const trans = useTranslations();
  return (
    <PageHero
      eyebrow={trans("知识图谱 · 三元组录入")}
      title={trans("录三元组")}
      meta="Neo4j →"
      description={trans("实体 - 关系 - 实体。关系定下后, 终点类型自动联动。")}
      backHref="/knowledge/graph"
      backLabel={trans("返回知识图谱")}
    />
  );
};

/**
 * TriplesResult - 提交成功结果展示
 * @param props.approvalId - 审批 ID
 * @param props.reviewStatus - 审核状态
 */
const TriplesResult = ({ approvalId, reviewStatus }: TriplesResultProps) => {
  const trans = useTranslations();
  return (
    <AnimateUp
      show
      enterFromTop
      data-testid="triples-result"
      className={cn("mt-4 rounded-lg border p-3 text-base", "border-moss/30 bg-moss/5 text-moss")}
    >
      {trans("已提交审核 #{id} (状态: {status})", {
        id: approvalId,
        status: reviewStatus,
      })}
    </AnimateUp>
  );
};

/**
 * TriplesError - 提交错误展示
 * @param props.message - 错误消息
 */
const TriplesError = ({ message }: { message: string }) => (
  <AnimateUp show enterFromTop className="mt-4">
    <ErrorBanner
      variant="destructive"
      descriptionNode={
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {message.split("; ").map((msg, msgIdx) => (
            <li key={msgIdx}>{msg}</li>
          ))}
        </ul>
      }
      description=""
      dataTestid="triples-error"
    />
  </AnimateUp>
);
