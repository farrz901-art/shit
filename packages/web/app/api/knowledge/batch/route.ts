// 批量导入 (后台任务 + 进度可查)
// (2026-06-14) 改走 apiFetch() (server side 自动 cookie 透传)
// (2026-06-30) 业务 API 走 wrapper: createTriples (不再直接 apiFetch)
import { type NextRequest, NextResponse } from "next/server";
import { DifyDatasets } from "@/lib/api/dify-datasets";
import { createTriples } from "@/lib/api/knowledge";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { ZERO } from "@/const";
import { nowMs } from "@/lib/date";

// 简化为 in-memory task map; v2 走 FastAPI /api/kg/batch
/** TaskState - 批量导入任务状态 */
interface TaskState {
  state: string;
  total: number;
  processed: number;
  success: number;
  failed: number;
  errors: string[];
}
const tasks = new Map<string, TaskState>();

// 常量 (2026-06-25 const-cleanup: NO_FAILURES 改 import ZERO)
const RADIX = 36;
const TRIM_START = 2;
const ID_LENGTH = 14;
const PROGRESS_OFFSET = 1;
const SUCCESS_THRESHOLD = 0.8;
const MIN_TOTAL = 1;

/**
 * processItem - 处理单个导入项
 * @param datasetId - 数据集 ID
 * @param item - 导入项
 * @param idx - 项索引
 */
const processItem = async (
  datasetId: string,
  item: { target: "dify" | "neo4j"; type: string; payload: Record<string, unknown> },
  idx: number,
): Promise<void> => {
  if (item.target === "dify" && item.type === "qa") {
    const payload = item.payload as { question: string; answer: string; tags?: string[] };
    let content = `Q: ${payload.question}\nA: ${payload.answer}`;
    if (payload.tags?.length) {
      content += `\nTags: ${payload.tags.join(", ")}`;
    }
    await DifyDatasets.createDocumentByText(datasetId, `batch-qa-${nowMs()}-${idx}`, content);
  } else if (item.target === "neo4j" && item.type === "triple") {
    const payload = item.payload as {
      from: { label: string; key: string; value: string };
      rel: string;
      to: { label: string; key: string; value: string };
    };
    await createTriples(
      {
        rows: [
          {
            from_key: payload.from.key,
            from_label: payload.from.label,
            from_value: payload.from.value,
            properties: {},
            rel_type: payload.rel,
            to_key: payload.to.key,
            to_label: payload.to.label,
            to_value: payload.to.value,
          },
        ],
      },
      await serverAuthHeaders(),
    );
  } else {
    throw new Error(`未知 target/type: ${item.target}/${item.type}`);
  }
};

/**
 * computeFinalState - 计算任务最终状态
 * @param task - 任务状态
 * @returns 最终状态字符串
 */
const computeFinalState = (task: TaskState): string => {
  if (task.failed === ZERO) {
    return "done";
  }
  if (task.total >= MIN_TOTAL && task.success / task.total >= SUCCESS_THRESHOLD) {
    return "partial";
  }
  return "failed";
};

/**
 * runBatch - 异步执行批量导入
 * @param datasetId - 数据集 ID
 * @param items - 导入项列表
 * @param task - 任务状态
 */
const runBatch = async (
  datasetId: string,
  items: { target: "dify" | "neo4j"; type: string; payload: Record<string, unknown> }[],
  task: TaskState,
): Promise<void> => {
  task.state = "running";
  for (let idx = 0; idx < items.length; idx++) {
    const item = items[idx];
    try {
      await processItem(datasetId, item, idx);
      task.success++;
    } catch (error) {
      task.failed++;
      task.errors.push(`item ${idx}: ${String(error)}`);
    }
    task.processed = idx + PROGRESS_OFFSET;
  }
  task.state = computeFinalState(task);
};

/**
 * 批量导入 BFF: POST /api/knowledge/batch
 * @param req - 请求对象
 * @returns Response (含 task_id)
 * @client-bff
 */
export const POST = async (req: NextRequest) => {
  const { dataset_id, items } = (await req.json()) as {
    dataset_id: string;
    items: { target: "dify" | "neo4j"; type: string; payload: Record<string, unknown> }[];
  };
  if (!dataset_id || !Array.isArray(items)) {
    return NextResponse.json({ error: "dataset_id / items 必填" }, { status: 400 });
  }

  const taskId = Math.random().toString(RADIX).slice(TRIM_START, ID_LENGTH);
  const taskState: TaskState = {
    errors: [],
    failed: 0,
    processed: 0,
    state: "queued",
    success: 0,
    total: items.length,
  };
  tasks.set(taskId, taskState);

  // 异步跑
  runBatch(dataset_id, items, taskState);

  return NextResponse.json({ task_id: taskId });
};

/**
 * 批量导入进度查询 BFF: GET /api/knowledge/batch
 * @param req - 请求对象
 * @returns Response (含任务进度信息)
 * @client-bff
 */
export const GET = async (req: NextRequest) => {
  const id = req.nextUrl.searchParams.get("task_id") ?? "";
  const task = tasks.get(id);
  if (!task) {
    return NextResponse.json({ error: "task 不存在" }, { status: 404 });
  }
  return NextResponse.json({ task_id: id, ...task });
};
