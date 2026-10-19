"use client";
// Triples 表单状态 hook (2026-06-22) — 管理行 CRUD + 提交逻辑.
// 从 triples-form.tsx 提取, 降低主组件体积.
import { type ActionResult, createTriples } from "@/app/[locale]/_actions/knowledge";
import { useActionState, useState } from "react";
import type { KnowledgeSchema } from "@/lib/schema-types";
import { z } from "zod";

// --- 类型定义 (与 knowledge.ts 服务端类型镜像, 避免 client import server-only 模块) ---

const MIN_LENGTH_1 = 1; // 基础数字: z.string().min(1)
/**
 * TripleRowSchema - 单行 Zod 校验 schema
 * @shared
 */
const TripleRowSchema = z.object({
  from_label: z.string().min(MIN_LENGTH_1, "起点类型缺失"),
  from_value: z.string().min(MIN_LENGTH_1, "起点值缺失"),
  properties: z.string().refine(
    (val) => {
      try {
        JSON.parse(val);
        return true;
      } catch {
        return false;
      }
    },
    { message: "properties 不是合法 JSON" },
  ),
  rel_type: z.string().min(MIN_LENGTH_1, "关系缺失"),
  to_key: z.string(),
  to_label: z.string().min(MIN_LENGTH_1, "终点类型缺失"),
  to_value: z.string().min(MIN_LENGTH_1, "终点值缺失"),
});

const MIN_ROWS_1 = 1; // 基础数字: z.array().min(1)
/**
 * TriplesPayloadSchema - 表单负载 Zod 校验 schema
 * @shared
 */
const TriplesPayloadSchema = z.object({
  rows: z.array(TripleRowSchema).min(MIN_ROWS_1, "至少 1 行"),
});

/**
 * Row - 三元组表单行类型
 * @property id - 行唯一 ID
 * @property from_label - 起点类型
 * @property from_key - 起点字段 key
 * @property from_value - 起点值
 * @property rel_type - 关系类型
 * @property to_label - 终点类型
 * @property to_key - 终点字段 key
 * @property to_value - 终点值
 * @property properties - 属性 (JSON 字符串)
 */
export interface Row {
  id: string;
  from_label: string;
  from_key: string;
  from_value: string;
  rel_type: string;
  to_label: string;
  to_key: string;
  to_value: string;
  properties: string;
}

/** 服务端三元组行输入 (properties 为对象, 非 JSON 字符串) */
interface TripleRowInput {
  from_key: string;
  from_label: string;
  from_value: string;
  rel_type: string;
  to_key: string;
  to_label: string;
  to_value: string;
  properties: Record<string, unknown>;
}

/**
 * TriplesResponse - createTriples 响应
 * @property approval_id - 审批 ID
 * @property review_status - 审核状态
 * @property apply_status - 应用状态
 */
interface TriplesResponse {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

// --- 常量 ---

/** 基础数字: 数组第一项 */
const FIRST_IDX = 0;
/** 基础数字: 偏移量 */
const OFFSET_1 = 1;
/** 基础数字: toString(36) */
const RANDOM_STR_BASE = 36;
/** 基础数字: slice(2) */
const SLICE_FROM = 2;
/** 基础数字: issue.path[1] */
const PATH_IDX_1 = 1;
/** 基础数字: issue.path[2] */
const PATH_IDX_2 = 2;
/** 基础数字: issue.path[0] */
const PATH_IDX_0 = 0;

/**
 * 初始表单状态
 * @shared
 */
const initialState: ActionResult<TriplesResponse> = {
  data: { apply_status: "none", approval_id: 0, review_status: "pending" },
  ok: true,
};

// --- 工具函数 ---

// 智能默认: 取 schema 里第一个关系的 from/to 作为默认. 拆 helper 降 cyclomatic complexity.
/** 根据节点名查找 schema 中的节点定义 */
const findNodeByName = (schema: KnowledgeSchema, name: string) =>
  schema.nodes.find((node) => node.name === name);

/** 获取节点第一个字段的 key */
const firstFieldKey = (node: ReturnType<typeof findNodeByName>) =>
  node?.fields?.[FIRST_IDX]?.key ?? "";

/** 生成随机行 ID */
const newRowId = () => Math.random().toString(RANDOM_STR_BASE).slice(SLICE_FROM);

/** 创建空行 (基于 schema 第一关系设默认值) */
const empty = (schema?: KnowledgeSchema): Row => {
  const rel = schema?.relations?.[FIRST_IDX];
  let fromKey = "";
  let toKey = "";
  if (rel) {
    fromKey = firstFieldKey(findNodeByName(schema, rel.from));
    toKey = firstFieldKey(findNodeByName(schema, rel.to));
  }
  return {
    from_key: fromKey,
    from_label: rel?.from ?? "",
    from_value: "",
    id: newRowId(),
    properties: "{}",
    rel_type: rel?.name ?? "",
    to_key: toKey,
    to_label: rel?.to ?? "",
    to_value: "",
  };
};

/**
 * 解析 Zod 校验错误, 返回带行号的错误信息
 * @param issue - Zod 校验问题
 * @returns 格式化后的错误字符串
 */
const formatValidationIssue = (issue: z.ZodIssue): string => {
  // Path 形如 ['rows', 0, 'from_value']
  const rowIdx = issue.path[PATH_IDX_1];
  const path2 = issue.path[PATH_IDX_2];
  const path0 = issue.path[PATH_IDX_0];
  const field = String(path2 ?? path0 ?? "?");
  let rowNum = "?";
  if (typeof rowIdx === "number") {
    rowNum = String(rowIdx + OFFSET_1);
  }
  return `第 ${rowNum} 行 ${field}: ${issue.message}`;
};

/**
 * 解析 Zod 错误数组为字符串数组
 * @param issues - Zod 校验问题数组
 * @returns 格式化后的错误字符串数组
 */
const parseValidationErrors = (issues: z.ZodIssue[]): string[] => issues.map(formatValidationIssue);

/**
 * 将表单行转换为服务端 TripleRowInput 数组
 * @param rows - 表单行数组
 * @returns 服务端三元组输入数组
 */
const toTripleInputs = (rows: Row[]): TripleRowInput[] =>
  rows.map((row) => ({
    from_key: row.from_key,
    from_label: row.from_label,
    from_value: row.from_value,
    properties: JSON.parse(row.properties) as Record<string, unknown>,
    rel_type: row.rel_type,
    to_key: row.to_key,
    to_label: row.to_label,
    to_value: row.to_value,
  }));

// --- Hook ---

/**
 * UseTripleFormReturn - useTripleForm hook 返回值
 * @property rows - 行数据
 * @property addRow - 新增行
 * @property removeRow - 删除行
 * @property updateRow - 更新行
 * @property clearRows - 清空行
 * @property clientError - 客户端校验错误
 * @property state - useActionState 结果
 * @property formAction - form action
 * @property isPending - 是否 pending
 */
export interface UseTripleFormReturn {
  rows: Row[];
  addRow: () => void;
  removeRow: (idx: number) => void;
  updateRow: (idx: number, patch: Partial<Row>) => void;
  clearRows: () => void;
  clientError: string | null;
  state: ActionResult<TriplesResponse>;
  formAction: (payload: FormData) => void;
  isPending: boolean;
}

/**
 * UseTripleForm — 管理三元组录入表单的行状态 + 提交逻辑.
 *
 * @param schema - 知识图谱 schema (节点/关系定义), 用于默认行初始值.
 * @returns 行数据 CRUD 方法 + useActionState 结果.
 */
export const useTripleForm = (schema: KnowledgeSchema): UseTripleFormReturn => {
  const [rows, setRows] = useState<Row[]>([empty(schema)]);
  const [clientError, setClientError] = useState<string | null>(null);

  const [state, formAction, isPending] = useActionState(
    async (
      _prev: ActionResult<TriplesResponse>,
      _formData: FormData,
    ): Promise<ActionResult<TriplesResponse>> => {
      const parsed = TriplesPayloadSchema.safeParse({ rows });
      if (!parsed.success) {
        const errors = parseValidationErrors(parsed.error.issues);
        setClientError(errors.join("; "));
        return { error: errors.join("; "), ok: false };
      }
      setClientError(null);
      return createTriples({ rows: toTripleInputs(parsed.data.rows as Row[]) });
    },
    initialState,
  );

  const addRow = () => setRows((prev) => [...prev, empty(schema)]);
  const removeRow = (idx: number) =>
    setRows((prev) => prev.filter((_unused, rowIdx) => rowIdx !== idx));
  const updateRow = (idx: number, patch: Partial<Row>) =>
    setRows((prev) =>
      prev.map((row, rowIdx) => {
        if (rowIdx === idx) {
          return { ...row, ...patch };
        }
        return row;
      }),
    );
  const clearRows = () => setRows([empty()]);

  return {
    rows,
    addRow,
    removeRow,
    updateRow,
    clearRows,
    clientError,
    state,
    formAction,
    isPending,
  };
};
