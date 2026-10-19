"use server";
// 知识库相关 server actions: createQA / createTriples / commitDocuments / optimizeAnswer.
// (2026-06-12 重构) 简单数据 Dify 操作直调 DifyDatasets (server 端 fetch Dify),
// 不再绕 BFF HTTP. BFF 只保留 multipart/流式/任务管理 (上传/chatflow/批量任务).
// Neo4j 三元组直连 FastAPI (/api/kg/triples).
// (2026-06-13) Task 10: createQA 改走审核 (submit kind=qa),
//   不再直写 Dify — 由审核 executor 异步执行.
// (2026-06-13) Task 11-13: createTriples (kind=triple) / commitDocuments (kind=batch) /
//   OptimizeAnswer (kind=optimize) 同样改走审核; 不再直调 DifyDatasets 或 FastAPI /api/kg/triples.
import { submit } from "@/lib/api/approvals";
import { actionError } from "@/lib/actions-utils";
import { revalidatePath } from "next/cache";

/** 统一返回包装 — 永不抛, 错误走 error 字段. */
export type ActionResult<TData> = { ok: true; data: TData } | { ok: false; error: string };

/** QA 对创建入参
 * @property dataset_id - 数据集 ID
 * @property question - 问题文本
 * @property answer - 答案文本
 * @property tags - 标签列表 (可选)
 * @property sync_to_neo4j - 是否同步到 Neo4j (可选)
 */
interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}

/** QA 创建结果 (审核流)
 * @property approval_id - 审批 ID
 * @property review_status - 审批状态
 * @property apply_status - 应用状态
 */
interface QAResult {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

/** 创建 QA 对 (走审核流)
 * @param input - QA 输入 (dataset_id / question / answer / tags / sync_to_neo4j)
 * @returns 包含 approval_id 的 ActionResult 包装
 * @server-only
 */
export const createQA = async (input: QAInput): Promise<ActionResult<QAResult>> => {
  // (2026-06-13) Task 10: createQA 改走审核流 — POST /api/approvals (kind=qa).
  // 不再直写 Dify, 也移除本地 Neo4j 同步: 这两个动作由审批通过后
  // Executor 统一执行, 避免 client 双写 + 保证可观测/可回滚.
  if (!input.dataset_id || !input.question || !input.answer) {
    return { error: "dataset_id / question / answer 必填", ok: false };
  }

  try {
    const approval = await submit("qa", {
      answer: input.answer,
      dataset_id: input.dataset_id,
      question: input.question,
      sync_to_neo4j: input.sync_to_neo4j,
      tags: input.tags,
    });
    revalidatePath("/[locale]/submissions");
    return {
      data: {
        apply_status: approval.apply_status,
        approval_id: approval.id,
        review_status: approval.review_status,
      },
      ok: true,
    };
  } catch (error) {
    return actionError(error);
  }
};

/** 三元组单行输入
 * @property from_label - 源节点标签
 * @property from_key - 源节点键
 * @property from_value - 源节点值
 * @property rel_type - 关系类型
 * @property to_label - 目标节点标签
 * @property to_key - 目标节点键
 * @property to_value - 目标节点值
 * @property properties - 关系属性 (键值对)
 */
interface TripleRowInput {
  from_label: string;
  from_key: string;
  from_value: string;
  rel_type: string;
  to_label: string;
  to_key: string;
  to_value: string;
  properties: Record<string, unknown>;
}

/** 三元组批量创建入参
 * @property rows - 三元组行列表
 */
interface TriplesInput {
  rows: TripleRowInput[];
}

/** 三元组创建结果 (审核流)
 * @property approval_id - 审批 ID
 * @property review_status - 审批状态
 * @property apply_status - 应用状态
 */
interface TriplesResponse {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

/** 创建三元组 (走审核流)
 * @param input - 三元组输入 (rows)
 * @returns 包含 approval_id 的 ActionResult 包装
 * @server-only
 */
export const createTriples = async (
  input: TriplesInput,
): Promise<ActionResult<TriplesResponse>> => {
  // (2026-06-13) Task 11-13: createTriples 改走审核 (kind=triple).
  // 不再直连 FastAPI /api/kg/triples — 由审批通过后 Executor 统一执行,
  // 避免 client 同步写 Neo4j 不可观测/不可回滚.
  try {
    const approval = await submit("triple", { rows: input.rows });
    revalidatePath("/[locale]/submissions");
    return {
      data: {
        apply_status: approval.apply_status,
        approval_id: approval.id,
        review_status: approval.review_status,
      },
      ok: true,
    };
  } catch (error) {
    return actionError(error);
  }
};

/** 批量提交文档的单行输入
 * @property question - 问题
 * @property answer - 答案
 * @property tags - 标签 (可选)
 */
interface CommitRowInput {
  question: string;
  answer: string;
  tags?: string;
}

/** 批量提交文档入参
 * @property dataset_id - 目标数据集 ID
 * @property rows - 文档行列表
 */
interface CommitInput {
  dataset_id: string;
  rows: CommitRowInput[];
}

/** 批量提交结果 (审核流)
 * @property approval_id - 审批 ID
 * @property review_status - 审批状态
 * @property apply_status - 应用状态
 */
interface CommitResponse {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

/** 批量提交文档 (走审核流)
 * @param input - 提交入参 (dataset_id / rows)
 * @returns 包含 approval_id 的 ActionResult 包装
 * @server-only
 */
export const commitDocuments = async (
  input: CommitInput,
): Promise<ActionResult<CommitResponse>> => {
  // (2026-06-13) Task 11-13: commitDocuments 改走审核 (kind=batch).
  // 不再循环调 DifyDatasets.createDocumentByText — 由审批通过后 Executor 统一执行,
  // 避免 client 同步循环写 Dify 不可观测/不可回滚/逐行失败暴露.
  if (!input.dataset_id || !Array.isArray(input.rows)) {
    return { error: "dataset_id / rows 必填", ok: false };
  }
  try {
    const approval = await submit("batch", {
      dataset_id: input.dataset_id,
      rows: input.rows,
    });
    revalidatePath("/[locale]/submissions");
    return {
      data: {
        apply_status: approval.apply_status,
        approval_id: approval.id,
        review_status: approval.review_status,
      },
      ok: true,
    };
  } catch (error) {
    return actionError(error);
  }
};

/** 优化回答入参
 * @property dataset_id - 数据集 ID
 * @property question - 原始问题
 * @property original_answer - 原始答案
 * @property improved_answer - 改进后的答案
 * @property reason - 改进理由
 */
interface OptimizeInput {
  dataset_id: string;
  question: string;
  original_answer: string;
  improved_answer: string;
  reason: string;
}

/** 优化回答结果 (审核流)
 * @property approval_id - 审批 ID
 * @property review_status - 审批状态
 * @property apply_status - 应用状态
 */
interface OptimizeResponse {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

/** 提交优化回答 (走审核流)
 * @param input 优化输入
 * @returns ActionResult<OptimizeResponse>
 * @server-only
 */
export const optimizeAnswer = async (
  input: OptimizeInput,
): Promise<ActionResult<OptimizeResponse>> => {
  // (2026-06-13) Task 11-13: 新增 optimizeAnswer (kind=optimize).
  // Chat 反馈 (用户点 "答错了/不满意" + 给出改进回答 + 改进理由) 走审核流,
  // 由审批通过后 Executor 异步更新 Dify QA 对 + 同步 Neo4j (可选).
  if (!input.dataset_id || !input.question || !input.improved_answer) {
    return { error: "dataset_id / question / improved_answer 必填", ok: false };
  }
  try {
    const approval = await submit("optimize", {
      dataset_id: input.dataset_id,
      improved_answer: input.improved_answer,
      original_answer: input.original_answer,
      question: input.question,
      reason: input.reason,
    });
    revalidatePath("/[locale]/submissions");
    return {
      data: {
        apply_status: approval.apply_status,
        approval_id: approval.id,
        review_status: approval.review_status,
      },
      ok: true,
    };
  } catch (error) {
    return actionError(error);
  }
};

/** 满意度反馈入参
 * @property question - 问题文本
 * @property answer - 答案文本
 * @property messageId - 消息 ID
 */
interface LikeInput {
  question: string;
  answer: string;
  messageId: string;
}

/** 满意度反馈结果
 * @property approval_id - 审批 ID
 */
interface LikeResponse {
  approval_id: number;
}

/** 提交满意反馈 (走审核流)
 * @param input - 反馈入参 (question / answer / messageId)
 * @returns 包含 approval_id 的 ActionResult 包装
 * @server-only
 */
export const likeAnswer = async (input: LikeInput): Promise<ActionResult<LikeResponse>> => {
  // (2026-06-16) Task 6: 满意按钮接通 → kind=like approval.
  // 跟 optimize 走同 server action 流, 但 payload 更轻 (只记 Q&A + 消息 id, 无 reason).
  // 一次性, 后续不支持 unlike.
  if (!input.question || !input.answer || !input.messageId) {
    return { error: "question / answer / messageId 必填", ok: false };
  }
  try {
    const approval = await submit("like", {
      answer: input.answer,
      message_id: input.messageId,
      question: input.question,
    });
    revalidatePath("/[locale]/submissions");
    return { data: { approval_id: approval.id }, ok: true };
  } catch (error) {
    return actionError(error);
  }
};
